param([string]$InnoCompiler)
$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $InnoCompiler) {
    $taskCompilerCandidates = @(
        (Join-Path $taskProjectRoot '.build-tools\InnoSetup\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 7\ISCC.exe'
    )
    $InnoCompiler = $taskCompilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $InnoCompiler -or -not (Test-Path -LiteralPath $InnoCompiler)) {
    throw 'Install Inno Setup or pass -InnoCompiler with the absolute ISCC.exe path.'
}
Push-Location -LiteralPath $taskProjectRoot
try {
    & python packaging\prepare_version.py
    if ($LASTEXITCODE -ne 0) { throw 'Version metadata generation failed.' }
    $taskAppBase = & python -c 'from pdf_lover.version import APP_FILE_NAME; print(APP_FILE_NAME)'
    if ($LASTEXITCODE -ne 0) { throw 'Version lookup failed.' }
    $taskVersion = & python -c 'from pdf_lover.version import VERSION; print(VERSION)'
    & python -m PyInstaller --noconfirm --workpath build-release --distpath build-release-dist packaging\folder.spec
    if ($LASTEXITCODE -ne 0) { throw 'Folder build failed.' }
    & python -m PyInstaller --noconfirm --workpath build-portable --distpath build-portable-dist packaging\portable.spec
    if ($LASTEXITCODE -ne 0) { throw 'Single-file build failed.' }
    $taskRelease = Join-Path $taskProjectRoot ('dist\' + $taskAppBase)
    New-Item -ItemType Directory -Path $taskRelease -Force | Out-Null
    Copy-Item -LiteralPath ('build-portable-dist\' + $taskAppBase + '.exe') -Destination (Join-Path $taskRelease ($taskAppBase + '.exe'))
    $taskGuide = (Get-Content -LiteralPath 'packaging\README_Distribution.txt' -Raw -Encoding utf8).Replace('{{VERSION}}', $taskVersion)
    $taskGuide | Set-Content -LiteralPath (Join-Path $taskRelease 'README_เริ่มใช้งาน.txt') -Encoding utf8
    $taskGuide | Set-Content -LiteralPath ('build-release-dist\' + $taskAppBase + '\README_เริ่มใช้งาน.txt') -Encoding utf8
    Compress-Archive -LiteralPath ('build-release-dist\' + $taskAppBase) -DestinationPath (Join-Path $taskRelease ($taskAppBase + '_Portable.zip')) -CompressionLevel Optimal -Force
    & $InnoCompiler '/Qp' (Join-Path $PSScriptRoot 'PDF_to_PNG.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
    $taskHashes = Get-ChildItem -LiteralPath $taskRelease -File | Where-Object { $_.Extension -in '.exe', '.zip' } | Get-FileHash -Algorithm SHA256
    $taskHashes | ForEach-Object { $_.Hash + '  ' + (Split-Path -Leaf $_.Path) } | Set-Content -LiteralPath (Join-Path $taskRelease 'SHA256SUMS.txt') -Encoding utf8
    Get-ChildItem -LiteralPath $taskRelease -File | Select-Object Name,Length
} finally {
    Pop-Location
}
