# Daily collection run, meant for Windows Task Scheduler (see docs/03_data_source.md).
# It resumes where the previous run stopped and stops by itself when the daily quota is used up.
# Exit codes: 0 = everything collected, 2 = paused (quota/throttle, resumes next run),
#             3 = another run is still going, anything else = error (see the log).
param(
    [string]$Config = "config/collect.toml"
)
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }

$log = Join-Path $repo ("data\logs\collect_{0:yyyyMMdd_HHmm}.log" -f (Get-Date))
& $uv run python -m so_recommender.collect --config $Config --log-file $log run
exit $LASTEXITCODE
