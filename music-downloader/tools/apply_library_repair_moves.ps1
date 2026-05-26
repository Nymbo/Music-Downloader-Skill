param(
    [string]$MovePlanPath = (Join-Path (Get-Location).Path 'library-audit-work\library-repair-move-plan.json'),
    [string]$LibraryRoot = 'P:\FileBrowser\Music Library'
)

$ErrorActionPreference = 'Stop'

function Get-Mp3Count {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }
    return (Get-ChildItem -LiteralPath $Path -Recurse -File -Filter '*.mp3' -Force | Measure-Object).Count
}

function Assert-UnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label is outside library root: $fullPath"
    }
}

$resolvedPlan = (Resolve-Path -LiteralPath $MovePlanPath).Path
$plan = Get-Content -LiteralPath $resolvedPlan -Raw | ConvertFrom-Json
$resolvedLibraryRoot = (Resolve-Path -LiteralPath $LibraryRoot).Path

$results = @()
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logPath = Join-Path (Split-Path -Parent $resolvedPlan) "apply-library-repair-$timestamp.log"

Start-Transcript -Path $logPath | Out-Null
try {
    foreach ($item in $plan.plan) {
        $source = [string]$item.source
        $target = [string]$item.target
        $expected = [int]$item.expectedTrackCount
        $artist = [string]$item.artist
        $album = [string]$item.album

        Assert-UnderRoot -Path $target -Root $resolvedLibraryRoot -Label 'Target'

        if (-not (Test-Path -LiteralPath $source)) {
            throw "Replacement source is missing for $artist - $album`: $source"
        }

        $sourceCount = Get-Mp3Count -Path $source
        if ($sourceCount -ne $expected) {
            throw "Replacement source count mismatch for $artist - $album`: $sourceCount/$expected"
        }

        $targetParent = Split-Path -Parent $target
        Assert-UnderRoot -Path $targetParent -Root $resolvedLibraryRoot -Label 'Target parent'
        if (-not (Test-Path -LiteralPath $targetParent)) {
            New-Item -ItemType Directory -Path $targetParent | Out-Null
        }

        if (Test-Path -LiteralPath $target) {
            if (-not [bool]$item.deleteExisting) {
                throw "Target already exists for add operation: $target"
            }
            Assert-UnderRoot -Path $target -Root $resolvedLibraryRoot -Label 'Delete target'
            Remove-Item -LiteralPath $target -Recurse -Force
        }

        Move-Item -LiteralPath $source -Destination $target

        $targetCount = Get-Mp3Count -Path $target
        if ($targetCount -ne $expected) {
            throw "Moved album count mismatch for $artist - $album`: $targetCount/$expected"
        }

        $results += [pscustomobject]@{
            artist = $artist
            album = $album
            action = if ([bool]$item.deleteExisting) { 'replace' } else { 'add' }
            target = $target
            expectedTrackCount = $expected
            actualTrackCount = $targetCount
        }
    }
}
finally {
    Stop-Transcript | Out-Null
}

$resultPath = Join-Path (Split-Path -Parent $resolvedPlan) "apply-library-repair-$timestamp.json"
[pscustomobject]@{
    generatedAt = (Get-Date).ToString('o')
    movePlan = $resolvedPlan
    libraryRoot = $resolvedLibraryRoot
    logPath = $logPath
    applied = $results.Count
    results = $results
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $resultPath -Encoding utf8

Write-Host "Applied $($results.Count) library repair moves."
Write-Host "Log: $logPath"
Write-Host "Result: $resultPath"
