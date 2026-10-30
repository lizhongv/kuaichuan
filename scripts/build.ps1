<#
.SYNOPSIS
    一键构建 KuaiChuan.exe：安装依赖 → 生成图标 → 运行测试 → PyInstaller 打包。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build.ps1
    powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipTests
#>
param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> 安装依赖" -ForegroundColor Cyan
python -m pip install -r requirements-dev.txt -q
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }

Write-Host "==> 生成图标" -ForegroundColor Cyan
python scripts\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "图标生成失败" }

if (-not $SkipTests) {
    Write-Host "==> 运行测试" -ForegroundColor Cyan
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "测试未通过，已停止打包" }
}

Write-Host "==> PyInstaller 打包" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\kuaichuan.spec
if ($LASTEXITCODE -ne 0) { throw "打包失败" }

$exe = Join-Path $Root "dist\KuaiChuan.exe"
Write-Host ("==> 完成：{0}（{1:N1} MB）" -f $exe, ((Get-Item $exe).Length / 1MB)) -ForegroundColor Green
