$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install -e ".[dev]"
python -m pytest -q

$Output = Join-Path $Root "demo-output"
if (Test-Path $Output) {
    Remove-Item -Recurse -Force $Output
}

tkp-normalize `
    (Join-Path $Root "fixtures\sanitized_conversations.json") `
    $Output `
    --schema (Join-Path $Root "schema\normalized_conversation.schema.json")
