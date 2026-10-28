# Start the local SearXNG instance used as MYEXA's fallback search provider.
#
# Usage: powershell -ExecutionPolicy Bypass -File docker\start-searxng.ps1
#
# The instance is bound to 127.0.0.1:8080 and has no authentication, so it
# must stay on the loopback interface.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
if (-not (Test-Path $docker)) {
    $docker = 'docker'
}

Write-Host '[1/4] Checking Docker daemon...'
& $docker info --format '{{.ServerVersion}}' 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Docker daemon is not running. Start Docker Desktop and retry.'
    exit 1
}

Write-Host '[2/4] Preparing settings.yml...'
$template = Join-Path $root 'searxng\settings.template.yml'
$settings = Join-Path $root 'searxng\settings.yml'
if (-not (Test-Path $settings)) {
    # The instance API of RandomNumberGenerator works on both Windows PowerShell
    # 5.1 and PowerShell 7 — the static Fill() only exists on .NET Core.
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $secret = ([Convert]::ToBase64String($bytes) -replace '[^a-zA-Z0-9]', '')
    $content = (Get-Content $template -Raw -Encoding UTF8).Replace('CHANGE_ME_RANDOM_SECRET', $secret)
    # UTF-8 without BOM: a BOM breaks the YAML parser inside the container.
    [System.IO.File]::WriteAllText($settings, $content, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host '      settings.yml created with a random secret key.'
} else {
    Write-Host '      settings.yml already exists, keeping it.'
}

Write-Host '[3/4] Starting container...'
& $docker compose -f (Join-Path $root 'compose.yml') up -d
if ($LASTEXITCODE -ne 0) { Write-Error 'docker compose up failed'; exit 1 }

Write-Host '[4/4] Waiting for the JSON API...'
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/search?q=test&format=json' -TimeoutSec 20 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {
        # The container is still starting up.
    }
}

if (-not $ok) {
    Write-Error 'SearXNG did not become ready in time.'
    & $docker logs --tail 40 myexa-searxng
    exit 1
}

Write-Host ''
Write-Host 'SearXNG is ready: http://127.0.0.1:8080  (JSON: /search?q=...&format=json)'
