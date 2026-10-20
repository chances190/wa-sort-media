# Build the Windows bundle, and the installer if Inno Setup is available.
# Requires: uv (https://docs.astral.sh/uv/). Optional: Inno Setup 6 (ISCC.exe).
$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\.."
try {
    Write-Host "Syncing dependencies..."
    uv sync --all-groups

    Write-Host "Freezing the app with PyInstaller..."
    uv run --group build pyinstaller --noconfirm --clean wa-sort-media.spec

    Write-Host ""
    Write-Host "Bundle ready at: dist\WhatsApp Media Suite\"

    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($iscc) {
        Write-Host "Compiling installer with Inno Setup..."
        & $iscc.Source installer\wa-sort-media.iss
        Write-Host "Installer ready at: installer\Output\"
    } else {
        Write-Host "Inno Setup (ISCC.exe) not found; skipping installer step."
        Write-Host "Install it from https://jrsoftware.org/isinfo.php to produce a setup .exe."
    }
} finally {
    Pop-Location
}
