param([switch]$Execute)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$agentPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $agentPython)) {
    throw 'Run Install-TrainingAgent.ps1 first to create the isolated OCR environment.'
}
if ($Execute) {
    & $agentPython -m urban_rivals serve --execute
} else {
    & $agentPython -m urban_rivals serve
}
exit $LASTEXITCODE
