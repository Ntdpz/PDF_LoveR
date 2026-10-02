$ErrorActionPreference = 'Stop'
$taskProjectRoot = Split-Path -Parent $PSScriptRoot
$taskAppBase = & python -c 'import runpy,sys; print(runpy.run_path(sys.argv[1])["APP_FILE_NAME"])' (Join-Path $taskProjectRoot 'pdf_lover\version.py')
if ($LASTEXITCODE -ne 0) { throw 'Version lookup failed.' }
$taskRelease = Join-Path $taskProjectRoot ('dist\' + $taskAppBase)
$taskVerifyRoot = Join-Path $PSScriptRoot ('.verification\run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskVerifyRoot -Force | Out-Null

function Invoke-VerifiedProcess {
    param([string]$File, [string[]]$ProcessArgs, [string]$WorkingDir)
    $taskInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $taskInfo.FileName = $File
    $taskInfo.UseShellExecute = $false
    $taskInfo.CreateNoWindow = $true
    $taskInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $taskInfo.WorkingDirectory = $WorkingDir
    foreach ($taskArg in $ProcessArgs) { $taskInfo.ArgumentList.Add($taskArg) }
    $taskInfo.Environment.Remove('PYTHONHOME') | Out-Null
    $taskInfo.Environment.Remove('PYTHONPATH') | Out-Null
    $taskInfo.Environment['PATH'] = (Join-Path $env:WINDIR 'System32') + ';' + $env:WINDIR
    $taskProcess = [System.Diagnostics.Process]::Start($taskInfo)
    if (-not $taskProcess.WaitForExit(130000)) { throw ('Timed out: ' + $File) }
    if ($taskProcess.ExitCode -ne 0) { throw ('Process failed: ' + $File + ', exit ' + $taskProcess.ExitCode) }
}

function Test-Application {
    param([string]$File, [string]$Report, [string]$WorkingDir)
    Invoke-VerifiedProcess -File $File -ProcessArgs @('--self-test', $Report) -WorkingDir $WorkingDir
    $taskResult = Get-Content -LiteralPath $Report -Raw -Encoding utf8 | ConvertFrom-Json
    if (-not $taskResult.passed) { throw ('Application smoke check failed: ' + $Report) }
    return $taskResult
}

# One copied EXE, with no _internal/source/Python folder beside it.
$taskStandaloneDir = Join-Path $taskVerifyRoot 'portable เครื่องทดสอบ'
New-Item -ItemType Directory -Path $taskStandaloneDir | Out-Null
$taskStandaloneExe = Join-Path $taskStandaloneDir ($taskAppBase + '.exe')
Copy-Item -LiteralPath (Join-Path $taskRelease ($taskAppBase + '.exe')) -Destination $taskStandaloneExe
$taskStandalone = Test-Application -File $taskStandaloneExe -Report (Join-Path $taskVerifyRoot 'standalone.json') -WorkingDir $taskStandaloneDir

# Extract exactly the ZIP supplied to users, then execute the extracted app.
$taskZipDir = Join-Path $taskVerifyRoot 'zip extracted'
Expand-Archive -LiteralPath (Join-Path $taskRelease ($taskAppBase + '_Portable.zip')) -DestinationPath $taskZipDir
$taskZipApp = Join-Path $taskZipDir ($taskAppBase + '\' + $taskAppBase + '.exe')
$taskZip = Test-Application -File $taskZipApp -Report (Join-Path $taskVerifyRoot 'zip.json') -WorkingDir $taskZipDir

# Install into an isolated test directory. Suppress shortcuts during verification.
$taskInstallDir = Join-Path $taskVerifyRoot 'installed app'
$taskInstaller = Join-Path $taskRelease ($taskAppBase + '_Setup.exe')
Invoke-VerifiedProcess -File $taskInstaller -ProcessArgs @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/NOICONS',('/DIR=' + $taskInstallDir),('/LOG=' + (Join-Path $taskVerifyRoot 'install.log'))) -WorkingDir $taskVerifyRoot
$taskInstalledExe = Join-Path $taskInstallDir ($taskAppBase + '.exe')
$taskInstalled = Test-Application -File $taskInstalledExe -Report (Join-Path $taskVerifyRoot 'installed.json') -WorkingDir $taskInstallDir

# A file created after installation must survive uninstall.
$taskUserFile = Join-Path $taskInstallDir 'converted-output\user-result.txt'
New-Item -ItemType Directory -Path (Split-Path -Parent $taskUserFile) | Out-Null
Set-Content -LiteralPath $taskUserFile -Value 'User-created output must remain after uninstall.'
Invoke-VerifiedProcess -File (Join-Path $taskInstallDir 'unins000.exe') -ProcessArgs @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG=' + (Join-Path $taskVerifyRoot 'uninstall.log'))) -WorkingDir $taskVerifyRoot
if (Test-Path -LiteralPath $taskInstalledExe) { throw 'Uninstall left the installed executable behind.' }
if (-not (Test-Path -LiteralPath $taskUserFile)) { throw 'Uninstall removed user-created output.' }

$taskSummary = [ordered]@{
    passed = $true
    checked_at = (Get-Date).ToString('o')
    host = 'Windows 10 x64'
    standalone = $taskStandalone
    zip = $taskZip
    installed = $taskInstalled
    clean_process_path = $true
    uninstall = 'passed'
    user_output_preserved = $true
    logs = $taskVerifyRoot
}
$taskSummary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'distribution-check.json') -Encoding utf8
$taskSummary | ConvertTo-Json -Depth 5
