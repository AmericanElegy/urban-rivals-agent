param([switch]$Execute, [switch]$ReusePairingToken)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$agentPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $agentPython)) {
    throw 'Run Install-TrainingAgent.ps1 first to create the isolated OCR environment.'
}
$agentArguments = @('-m', 'urban_rivals', 'serve')
if ($Execute) { $agentArguments += '--execute' }
if ($ReusePairingToken) { $agentArguments += '--reuse-pairing-token' }
& $agentPython @agentArguments
exit $LASTEXITCODE
