param(
    [string]$Project = "ps_project",
    [string]$OutputRoot = (Join-Path $PSScriptRoot "../.local-backups"),
    [int]$MaxMediaMB = 500,
    [string]$CopyTo = ""
)
$ErrorActionPreference = "Stop"
if ($Project -notmatch '^[a-zA-Z0-9_-]+$' -or $MaxMediaMB -lt 1 -or $MaxMediaMB -gt 5000) { throw "Invalid backup configuration" }
$destinationRoot = [IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Force -Path $destinationRoot | Out-Null
$driveRoot = [IO.Path]::GetPathRoot($destinationRoot)
if (([IO.DriveInfo]::new($driveRoot)).AvailableFreeSpace -lt 10GB) { throw "Need at least 10 GB free disk before backup" }
$backupName = "pethome-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$destination = Join-Path $destinationRoot $backupName
New-Item -ItemType Directory -Path $destination | Out-Null
$postgres = "$Project-postgres-1"
$api = "$Project-fastapi-api-1"
$mounts = docker inspect $api --format '{{json .Mounts}}' | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Cannot locate application container" }
$mediaVolume = ($mounts | Where-Object Destination -eq '/app/data/community-uploads').Name
if (!$mediaVolume -or $mediaVolume -notmatch '^[a-zA-Z0-9_.-]+$') { throw "Cannot verify media volume" }
$mediaSize = docker run --rm --memory=64m --memory-swap=64m --mount "type=volume,source=$mediaVolume,target=/media,readonly" --entrypoint sh pgvector/pgvector:pg16 -c 'du -sk /media'
if ($LASTEXITCODE -ne 0) { throw "Cannot measure media volume" }
if ([long](($mediaSize -split '\s+')[0]) -gt ($MaxMediaMB*1024)) { throw "Media exceeds this bounded backup limit; use a dedicated backup host or explicitly increase MaxMediaMB" }
$remoteDump = "/tmp/$backupName.dump"
docker exec $postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file="$1"' sh $remoteDump
if ($LASTEXITCODE -ne 0) { throw "Database dump failed" }
docker cp "${postgres}:$remoteDump" (Join-Path $destination 'database.dump')
if ($LASTEXITCODE -ne 0) { throw "Database copy failed" }
docker exec $postgres sh -c 'rm -f -- "$1"' sh $remoteDump
docker run --rm --memory=64m --memory-swap=64m --mount "type=volume,source=$mediaVolume,target=/media,readonly" --mount "type=bind,source=$destination,target=/backup" --entrypoint sh pgvector/pgvector:pg16 -c 'tar -czf /backup/rescue-images.tar.gz -C /media .'
if ($LASTEXITCODE -ne 0) { throw "Media backup failed" }
$artifacts = 'database.dump','rescue-images.tar.gz' | ForEach-Object { $item=Get-Item -LiteralPath (Join-Path $destination $_); [pscustomobject]@{name=$item.Name;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash} }
[pscustomobject]@{created_at=[DateTime]::UtcNow.ToString('o');project=$Project;files=$artifacts;status='complete'} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destination 'manifest.json') -Encoding utf8
if ($CopyTo) {
    $offsiteRoot=[IO.Path]::GetFullPath($CopyTo)
    if ($offsiteRoot -eq $destinationRoot -or $offsiteRoot.StartsWith($destinationRoot+[IO.Path]::DirectorySeparatorChar)) { throw "CopyTo must be a different backup destination" }
    New-Item -ItemType Directory -Force -Path $offsiteRoot | Out-Null
    $offsiteDestination=Join-Path $offsiteRoot $backupName
    New-Item -ItemType Directory -Path $offsiteDestination | Out-Null
    foreach ($name in @('database.dump','rescue-images.tar.gz','manifest.json')) { Copy-Item -LiteralPath (Join-Path $destination $name) -Destination (Join-Path $offsiteDestination $name) }
    foreach ($item in $artifacts) { if ((Get-FileHash -LiteralPath (Join-Path $offsiteDestination $item.name)).Hash -ne $item.sha256) { throw "Offsite checksum mismatch" } }
}
Write-Output "Backup complete: $destination"
