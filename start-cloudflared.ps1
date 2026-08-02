$ErrorActionPreference = "Stop"

$configPath = Join-Path $PSScriptRoot "cloudflared.sandystudio.yml"
$candidates = @(
    "C:\Program Files (x86)\cloudflared\cloudflared.exe",
    "C:\Program Files\cloudflared\cloudflared.exe",
    (Get-Command cloudflared -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
)

$exe = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $exe) {
    throw "No encontré cloudflared. Instálalo con: winget install --id Cloudflare.cloudflared -e"
}

Write-Host "Usando cloudflared en: $exe"
Write-Host "Configuracion: $configPath"

& $exe tunnel --config $configPath run
