$ErrorActionPreference = "Stop"
py -m pip install --upgrade pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name Forge forge_desktop.pyw
Write-Host "Built dist\Forge.exe"
