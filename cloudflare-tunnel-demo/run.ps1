#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

docker compose up -d
Write-Host "Cloudflare Tunnel dang khoi dong..." -ForegroundColor Green
Write-Host "URL cong khai se hien trong logs sau vai giay." -ForegroundColor Cyan
Write-Host "Chay: docker compose logs -f" -ForegroundColor Cyan
