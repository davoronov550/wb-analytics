# Поднимает dev-окружение и ждёт, пока все сервисы станут healthy.
#
#   pwsh tools/dev-up.ps1
#   pwsh tools/dev-up.ps1 -Reset     # пересоздать тома (после правки init/*.sql)
#
# Init-скрипты PostgreSQL и ClickHouse отрабатывают только на чистом томе,
# поэтому правка init/*.sql без -Reset не даст эффекта.

[CmdletBinding()]
param(
    [switch]$Reset,
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot 'deploy/compose/docker-compose.yml'

if (-not (Test-Path $composeFile)) {
    throw "Не найден $composeFile"
}

if ($Reset) {
    Write-Host '==> Удаляю тома' -ForegroundColor Yellow
    docker compose -f $composeFile down -v
}

Write-Host '==> Поднимаю инфраструктуру' -ForegroundColor Cyan
docker compose -f $composeFile up -d
if ($LASTEXITCODE -ne 0) { throw 'docker compose up завершился с ошибкой' }

# minio-init — одноразовый контейнер, он обязан завершиться, а не стать healthy.
$longRunning = @('postgres', 'kafka', 'schema-registry', 'clickhouse', 'redis', 'minio')

Write-Host "==> Жду готовности (до $TimeoutSeconds с)" -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ($true) {
    $pending = @()
    foreach ($svc in $longRunning) {
        $id = (docker compose -f $composeFile ps -q $svc)
        if (-not $id) { $pending += "$svc (не запущен)"; continue }
        $state = docker inspect --format '{{.State.Health.Status}}' $id 2>$null
        if ($state -ne 'healthy') { $pending += "$svc ($state)" }
    }

    if ($pending.Count -eq 0) { break }

    if ((Get-Date) -gt $deadline) {
        Write-Host "Не дождался: $($pending -join ', ')" -ForegroundColor Red
        docker compose -f $composeFile ps
        throw 'Таймаут ожидания готовности инфраструктуры'
    }

    Write-Host "    ждут: $($pending -join ', ')"
    Start-Sleep -Seconds 3
}

Write-Host '==> Инфраструктура готова' -ForegroundColor Green
docker compose -f $composeFile ps

Write-Host ''
Write-Host 'Строки подключения — deploy/compose/README.md' -ForegroundColor DarkGray
