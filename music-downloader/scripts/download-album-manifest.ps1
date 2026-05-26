param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [string]$OutputRoot = (Join-Path (Get-Location).Path 'Downloaded'),

    [string]$YtDlpPath = 'yt-dlp',

    [string]$Artist = '',

    [switch]$Worker,

    [switch]$AllowUnverified,

    [switch]$ContinueOnAlbumError,

    [int]$MaxParallel = 8,

    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Path))
}

function ConvertTo-SafePathSegment {
    param([Parameter(Mandatory = $true)][string]$Value)

    $invalid = [System.IO.Path]::GetInvalidFileNameChars()
    $chars = foreach ($char in $Value.ToCharArray()) {
        if ($invalid -contains $char) { '_' } else { $char }
    }

    return (-join $chars).Trim()
}

function ConvertTo-ProcessArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    return '"' + ($Value -replace '"', '\"') + '"'
}

function Import-AlbumManifest {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Manifest not found: $Path"
    }

    $manifest = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json

    if (-not $manifest.artists) {
        throw "Manifest must contain an artists array."
    }

    return $manifest
}

function Get-Album {
    param(
        [Parameter(Mandatory = $true)][string]$ArtistName,
        [Parameter(Mandatory = $true)]$Album,
        [Parameter(Mandatory = $true)][string]$DestinationRoot,
        [Parameter(Mandatory = $true)][string]$Downloader
    )

    $albumName = [string]$Album.title
    $url = [string]$Album.url

    if ([string]::IsNullOrWhiteSpace($albumName)) {
        throw "Album is missing a title for artist: $ArtistName"
    }

    if ([string]::IsNullOrWhiteSpace($url)) {
        throw "Album is missing a URL: $ArtistName - $albumName"
    }

    if (-not $AllowUnverified -and $Album.verified -ne $true) {
        throw "Album is not marked verified: $ArtistName - $albumName"
    }

    Write-Host ''
    Write-Host '==============================' -ForegroundColor Cyan
    Write-Host ("Downloading: {0} - {1}" -f $ArtistName, $albumName) -ForegroundColor Yellow
    Write-Host '==============================' -ForegroundColor Cyan

    $artistFolder = ConvertTo-SafePathSegment -Value $ArtistName
    $normalizedRoot = $DestinationRoot -replace '\\', '/'
    $outTemplate = '{0}/{1}/%(playlist_title)s/%(playlist_index)02d - %(title)s.%(ext)s' -f $normalizedRoot, $artistFolder

    if ($PlanOnly) {
        Write-Host ("Would download to: {0}" -f $outTemplate)
        Write-Host ("URL: {0}" -f $url)
        return
    }

    $extraArgs = @()
    if (-not [string]::IsNullOrWhiteSpace($env:YT_DLP_EXTRA_ARGS)) {
        $extraArgs = $env:YT_DLP_EXTRA_ARGS -split ' '
    }

    & $Downloader -f 'bestaudio/best' --extract-audio --audio-format mp3 --audio-quality 0 --embed-metadata @extraArgs -o $outTemplate $url

    if ($LASTEXITCODE -ne 0) {
        throw "yt-dlp failed for: $ArtistName - $albumName (exit code $LASTEXITCODE)"
    }
}

$resolvedManifest = Resolve-FullPath -Path $ManifestPath
$resolvedOutputRoot = Resolve-FullPath -Path $OutputRoot
$manifest = Import-AlbumManifest -Path $resolvedManifest

New-Item -ItemType Directory -Force -Path $resolvedOutputRoot | Out-Null

if ($Worker) {
    if ([string]::IsNullOrWhiteSpace($Artist)) {
        throw "Worker mode requires -Artist."
    }

    $artistEntry = @($manifest.artists | Where-Object { $_.name -eq $Artist }) | Select-Object -First 1

    if (-not $artistEntry) {
        throw "Artist not found in manifest: $Artist"
    }

    $logRoot = Join-Path $resolvedOutputRoot '_logs'
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

    $safeArtist = ConvertTo-SafePathSegment -Value $Artist
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $logPath = Join-Path $logRoot ("{0}-{1}.log" -f $safeArtist, $timestamp)

    try {
        Start-Transcript -LiteralPath $logPath | Out-Null
    } catch {
        Write-Warning ("Could not start transcript: {0}" -f $_.Exception.Message)
    }

    try {
        $failedAlbums = @()

        foreach ($album in @($artistEntry.albums)) {
            try {
                Get-Album -ArtistName $artistEntry.name -Album $album -DestinationRoot $resolvedOutputRoot -Downloader $YtDlpPath
            } catch {
                $failedAlbums += [pscustomobject]@{
                    Artist = [string]$artistEntry.name
                    Album = [string]$album.title
                    Error = [string]$_.Exception.Message
                }

                Write-Warning ("Album failed: {0} - {1}: {2}" -f $artistEntry.name, $album.title, $_.Exception.Message)

                if (-not $ContinueOnAlbumError) {
                    throw
                }
            }
        }

        if ($failedAlbums.Count -gt 0) {
            Write-Host ''
            Write-Host ("Failed albums for artist: {0}" -f $artistEntry.name) -ForegroundColor Red
            $failedAlbums | Format-Table -AutoSize | Out-String | Write-Host
            exit 1
        }

        Write-Host ''
        Write-Host ("Completed artist: {0}" -f $artistEntry.name) -ForegroundColor Green
    } finally {
        try {
            Stop-Transcript | Out-Null
        } catch {
        }
    }

    exit 0
}

if ($PlanOnly) {
    foreach ($artistEntry in @($manifest.artists)) {
        $albumCount = @($artistEntry.albums).Count
        Write-Host ("{0}: {1} album(s)" -f $artistEntry.name, $albumCount)
    }

    exit 0
}

$command = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $command) {
    $command = Get-Command powershell -ErrorAction Stop
}

$shellPath = $command.Source
$scriptPath = $PSCommandPath
$runningWorkers = @()

foreach ($artistEntry in @($manifest.artists)) {
    if ([string]::IsNullOrWhiteSpace([string]$artistEntry.name)) {
        throw "Every artist entry must have a name."
    }

    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        (ConvertTo-ProcessArgument -Value $scriptPath),
        '-ManifestPath',
        (ConvertTo-ProcessArgument -Value $resolvedManifest),
        '-OutputRoot',
        (ConvertTo-ProcessArgument -Value $resolvedOutputRoot),
        '-YtDlpPath',
        (ConvertTo-ProcessArgument -Value $YtDlpPath),
        '-Worker',
        '-Artist',
        (ConvertTo-ProcessArgument -Value ([string]$artistEntry.name))
    )

    if ($AllowUnverified) {
        $arguments += '-AllowUnverified'
    }

    if ($ContinueOnAlbumError) {
        $arguments += '-ContinueOnAlbumError'
    }

    while (@($runningWorkers | Where-Object { -not $_.HasExited }).Count -ge $MaxParallel) {
        Start-Sleep -Seconds 5
        $runningWorkers = @($runningWorkers | Where-Object { -not $_.HasExited })
    }

    Write-Host ("Starting artist terminal: {0}" -f $artistEntry.name) -ForegroundColor Cyan
    $runningWorkers += Start-Process -FilePath $shellPath -ArgumentList $arguments -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -PassThru
}

while (@($runningWorkers | Where-Object { -not $_.HasExited }).Count -gt 0) {
    Start-Sleep -Seconds 10
    $runningWorkers = @($runningWorkers | Where-Object { -not $_.HasExited })
}
