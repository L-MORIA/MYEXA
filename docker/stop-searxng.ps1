# Stop the local SearXNG fallback instance.
#
# Usage: powershell -ExecutionPolicy Bypass -File docker\stop-searxng.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
if (-not (Test-Path $docker)) {
    $docker = 'docker'
}

& $docker compose -f (Join-Path $root 'compose.yml') down
if ($LASTEXITCODE -ne 0) { Write-Error 'docker compose down failed'; exit 1 }
Write-Host 'SearXNG stopped.'
