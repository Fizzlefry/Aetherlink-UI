Set-ExecutionPolicy Bypass -Scope Process -Force
$ErrorActionPreference = 'Stop'

docker exec -it aether-postgres psql -U aether -d aetherlink
