Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
python -m parking_gs.server --port 8080
