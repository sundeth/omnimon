# PowerShell script to build Android APK with Buildozer (cleaned)
param(
    [switch]$Clean = $false,
    [switch]$Release = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=== Omnipet Android Build ===" -ForegroundColor Cyan

# Configuration
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WSLBuildDir = "~/omnipet_build"
$BuildType = if ($Release) { "release" } else { "debug" }

Write-Host "[1/4] Preparing build directory..." -ForegroundColor Yellow
wsl bash -c "mkdir -p $WSLBuildDir/{src/core,src/models,src/ui,src/ui/components,src/ui/windows,src/ui/minigames,src/input,src/battle,src/battle/dcom,src/battle/sim,src/training,src/services,src/data,src/data/protocols,src/data/attack_patterns,src/utils,src/scenes,assets,modules,config,save}"

Write-Host "[2/4] Syncing files to WSL..." -ForegroundColor Yellow
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/core/ $WSLBuildDir/src/core/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/models/ $WSLBuildDir/src/models/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/ui/ $WSLBuildDir/src/ui/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/input/ $WSLBuildDir/src/input/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/battle/ $WSLBuildDir/src/battle/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/training/ $WSLBuildDir/src/training/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/services/ $WSLBuildDir/src/services/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/data/ $WSLBuildDir/src/data/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/utils/ $WSLBuildDir/src/utils/"
wsl bash -c "rsync -avu --delete --exclude='__pycache__' --exclude='*.pyc' /mnt/e/Omnipet/src/scenes/ $WSLBuildDir/src/scenes/"
wsl bash -c "cp /mnt/e/Omnipet/src/vpet.py $WSLBuildDir/src/vpet.py"
wsl bash -c "cp /mnt/e/Omnipet/src/__init__.py $WSLBuildDir/src/__init__.py"
wsl bash -c "rsync -avu --delete /mnt/e/Omnipet/assets/ $WSLBuildDir/assets/"
wsl bash -c "rsync -avu --delete /mnt/e/Omnipet/modules/ $WSLBuildDir/modules/"
wsl bash -c "rsync -avu --delete /mnt/e/Omnipet/config/ $WSLBuildDir/config/"
wsl bash -c "rsync -avu --delete /mnt/e/Omnipet/save/ $WSLBuildDir/save/"
wsl bash -c "cp /mnt/e/Omnipet/main_android.py $WSLBuildDir/main.py"
wsl bash -c "cp /mnt/e/Omnipet/buildozer.spec $WSLBuildDir/"

# Clean caches
Write-Host "[3/4] Cleaning Python bytecode cache..." -ForegroundColor Yellow
wsl bash -c "cd $WSLBuildDir && find . -type f -name '*.pyc' -delete && find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
if ($Clean) { wsl bash -c "cd $WSLBuildDir && rm -rf .buildozer bin" }

Write-Host "[4/4] Building APK ($BuildType)..." -ForegroundColor Yellow
$buildCommand = if ($Release) { "cd $WSLBuildDir && buildozer android clean && buildozer android release" } else { "cd $WSLBuildDir && buildozer android clean && buildozer android debug" }
wsl bash -c $buildCommand

if ($LASTEXITCODE -eq 0) {
    Write-Host "=== Build Successful ===" -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path "$ProjectRoot\bin" | Out-Null
    wsl bash -c "cp $WSLBuildDir/bin/*.apk /mnt/e/Omnipet/bin/"
    Get-ChildItem "$ProjectRoot\bin\*.apk" | ForEach-Object { Write-Host "  $($_.Name)" -ForegroundColor Cyan }
} else {
    Write-Host "=== Build Failed ===" -ForegroundColor Red
}