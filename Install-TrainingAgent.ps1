$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$agentPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $agentPython)) {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        & py -3.12 -m venv .venv
    } else {
        python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python 3.12 virtual environment.' }
}
& $agentPython -m pip install -e '.[vision]'
if ($LASTEXITCODE -ne 0) { throw 'OCR dependency installation failed.' }
Write-Host 'Installed. Start with .\Start-TrainingAgent.ps1 (inspect only).'
