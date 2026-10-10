@echo off
setlocal DisableDelayedExpansion
title Fix Claude workspace
set "CCW_SELF=%~f0"
set "CCW_DIR=%~dp0"
set "CCW_ARG=%~1"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "if ($ExecutionContext.SessionState.LanguageMode -ne 'FullLanguage') { Write-Host 'Windows security settings on this PC block this file. Send a photo of this window to Caiman support.'; exit 1 }; try { $ccwText = [IO.File]::ReadAllText($env:CCW_SELF) } catch { Write-Host 'Could not read this file. Copy it into your business folder and double-click it there.'; exit 1 }; $ccwMark = '#' + '#CHECK-START'; $ccwPos = $ccwText.IndexOf($ccwMark); if ($ccwPos -lt 0) { Write-Host 'This file is incomplete. Download it again.'; exit 1 }; & ([ScriptBlock]::Create($ccwText.Substring($ccwPos)))"
if errorlevel 3 exit /b
echo.
pause
exit /b
##CHECK-START
# Fix Claude's workspace (Caiman support, 2026-10-09)
# Gets Claude's workspace running on this PC, so Claude can run commands here and install the Caiman kit.
# With your OK at the Windows permission prompt it may:
#   - start the Claude VM Service and set it to start automatically,
#   - turn on the Virtual Machine Platform Windows feature,
#   - turn the Windows hypervisor back on if it was switched off,
#   - set this folder to "Always keep on this device" if it is in OneDrive.
# It changes nothing else. What it found and did is saved in claude-workspace-fix.txt next to this file.
# Written for Windows PowerShell 5.1. What it checks follows Anthropic's documented requirements for
# Claude's workspace on Windows (Windows 10 build 19041+, the .msix app, virtualization, Virtual Machine Platform).

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
$cimTimeout = 60

$here = $env:CCW_DIR
if ([string]::IsNullOrEmpty($here)) { $here = (Get-Location).Path }
$here = $here.TrimEnd('\')
$stamp = Get-Date

# ------------------------------------------------------------------ permission (one Windows prompt)
$isAdmin = $false
try { $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) } catch {}
if ($env:CCW_ASSUME_ADMIN -eq 'test-only') { $isAdmin = $true }
if (-not $isAdmin -and $env:CCW_ARG -ne 'elevated') {
    Write-Host ''
    Write-Host 'Windows will ask for permission to make changes. Click Yes.'
    try {
        $cmdExe = 'cmd.exe'
        if ($env:SystemRoot) { $cmdExe = $env:SystemRoot + '\System32\cmd.exe' }
        Start-Process -FilePath $cmdExe -ArgumentList ('/d /s /c ""' + $env:CCW_SELF + '" elevated"') -Verb RunAs -ErrorAction Stop
        exit 3
    } catch {
        Write-Host ''
        Write-Host 'Nothing was changed, because Windows did not get permission.'
        Write-Host 'Double-click the file again and click Yes. If Windows asks for a password you do not have, ask whoever manages this PC.'
        exit 1
    }
}

$facts = New-Object System.Collections.Generic.List[string]
$done = New-Object System.Collections.Generic.List[string]
$steps = New-Object System.Collections.Generic.List[string]
$notes = New-Object System.Collections.Generic.List[string]
$tails = New-Object System.Collections.Generic.List[string]

function Fact([string]$label, [string]$value) { $facts.Add(('{0,-36} {1}' -f ($label + ':'), $value)) }

function Get-Cim([string]$class, [string]$filter) {
    if ([string]::IsNullOrEmpty($filter)) { return Get-CimInstance -ClassName $class -OperationTimeoutSec $cimTimeout -ErrorAction Stop }
    return Get-CimInstance -ClassName $class -Filter $filter -OperationTimeoutSec $cimTimeout -ErrorAction Stop
}

function Get-Innermost($err) {
    $e = $err.Exception
    while ($e.InnerException) { $e = $e.InnerException }
    return $e
}

function Hide-Secrets([string]$s) {
    $s = $s -replace '(?i)\b(bearer|basic)\s+[^\s"'',}]+', '$1 [removed]'
    $s = $s -replace '(?i)((api[_-]?key|token|secret|password|authorization)["'']?\s*[:=]\s*["'']?)(?!bearer\b|basic\b)[^\s"'',}]+', '$1[removed]'
    $s = $s -replace 'sk-ant-[\w-]+', '[removed]'
    $s = $s -replace '[\w.+-]+@[\w-]+(\.[\w-]+)+', '[email removed]'
    return $s
}

function Start-ClaudeService($svc) {
    # Returns '' when the service is running, otherwise the reason it is not.
    try {
        if ([string]$svc.Status -ne 'StartPending') { $svc.Start() }
        $svc.WaitForStatus('Running', (New-TimeSpan -Seconds 30))
    } catch {
        $ex = Get-Innermost $_
        if ($ex.GetType().Name -eq 'TimeoutException') { $why = 'it did not finish starting within 30 seconds' } else { $why = [string]$ex.Message }
        try { $svc.Refresh() } catch {}
        if ([string]$svc.Status -eq 'Running') { return '' }
        return $why
    }
    try { $svc.Refresh() } catch {}
    if ([string]$svc.Status -eq 'Running') { return '' }
    return 'it stopped again'
}

Write-Host ''
Write-Host 'Fixing Claude''s workspace on this PC. This takes a minute or two.'
Write-Host ''

$restartNeeded = $false
$permOnly = $false
$biosStep = $false
try {
    # -------------------------------------------------------------- look
    Write-Host '- Checking Windows'
    $os = $null; $cs = $null; $cpu = $null
    try { $os = @(Get-Cim 'Win32_OperatingSystem' '')[0] } catch {}
    try { $cs = @(Get-Cim 'Win32_ComputerSystem' '')[0] } catch {}
    try { $cpu = @(Get-Cim 'Win32_Processor' '')[0] } catch {}
    $build = 0
    if ($os) {
        try { $build = [int]$os.BuildNumber } catch {}
        Fact 'Windows' ('{0} (build {1}, {2})' -f $os.Caption, $os.BuildNumber, $os.OSArchitecture)
    } else { Fact 'Windows' 'could not read' }
    Fact 'Computer name' ([string]$env:COMPUTERNAME)
    Fact 'Running with permission' ($(if ($isAdmin) { 'yes' } else { 'no (it could only try to start the Claude VM Service)' }))

    $onDomain = $false; $isGuest = $false
    if ($cs) {
        Fact 'PC make and model' ((([string]$cs.Manufacturer).Trim() + ' ' + ([string]$cs.Model).Trim()).Trim())
        if ($cs.PartOfDomain -eq $true) { $onDomain = $true }
        if ((([string]$cs.Manufacturer) + ' ' + ([string]$cs.Model)) -match 'Virtual Machine|VMware|VirtualBox|KVM|QEMU|Parallels|Xen') { $isGuest = $true }
    }

    $hv = $null; if ($cs) { $hv = $cs.HypervisorPresent }
    $fw = $null; if ($cpu) { $fw = $cpu.VirtualizationFirmwareEnabled }
    $virtState = 'unknown'
    if ($hv -eq $true) { $virtState = 'on (a hypervisor is running)' }
    elseif ($hv -eq $false -and $fw -eq $true) { $virtState = 'on in BIOS, but no hypervisor is running' }
    elseif ($hv -eq $false -and $fw -eq $false) { $virtState = 'OFF in BIOS' }
    Fact 'Virtualization' $virtState

    # Virtual Machine Platform: Enabled, Disabled, EnablePending, DisablePending (or unknown)
    $vmpState = 'unknown'
    try {
        $vf = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -ErrorAction Stop
        if ($vf) { $vmpState = [string]$vf.State }
    } catch {
        try {
            $f = @(Get-Cim 'Win32_OptionalFeature' "Name='VirtualMachinePlatform'")[0]
            if ($f) { switch ([int]$f.InstallState) { 1 { $vmpState = 'Enabled' } 2 { $vmpState = 'Disabled' } } }
        } catch {}
    }
    Fact 'Virtual Machine Platform' $vmpState

    $rebootPending = $false
    foreach ($k in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
                     'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired')) {
        try { if (Test-Path -LiteralPath $k -ErrorAction Stop) { $rebootPending = $true } } catch {}
    }
    if ($vmpState -eq 'EnablePending') { $rebootPending = $true }
    Fact 'Windows restart pending' ($(if ($rebootPending) { 'yes' } else { 'no' }))

    $svc = $null
    foreach ($n in @('CoworkVMService', 'CoworkVMServiceStore')) {
        $s = Get-Service -Name $n -ErrorAction SilentlyContinue
        if ($s) { $svc = $s; break }
    }
    $stype = ''
    if ($svc) {
        try { $stype = [string]$svc.StartType } catch {}
        Fact 'Claude VM Service' ('{0}: {1} (start type: {2})' -f $svc.Name, [string]$svc.Status, $stype)
    } else { Fact 'Claude VM Service' 'NOT FOUND' }

    $pkgs = @()
    try { $pkgs = @(Get-AppxPackage -Name '*Claude*' -ErrorAction Stop) } catch {}
    if ($pkgs.Count -gt 0) { foreach ($p in $pkgs) { Fact 'Claude app package' ('{0} {1}' -f $p.Name, $p.Version) } } else { Fact 'Claude app package' 'none found' }
    $oldExe = $false
    if ($env:LOCALAPPDATA) { $oldExe = Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'AnthropicClaude') }
    if ($oldExe) { Fact 'Old .exe install folder' 'found' }

    $roots = New-Object System.Collections.Generic.List[string]
    if ($env:APPDATA) { $roots.Add((Join-Path $env:APPDATA 'Claude')) }
    if ($env:LOCALAPPDATA) {
        $roots.Add((Join-Path $env:LOCALAPPDATA 'Claude'))
        $pk = Join-Path $env:LOCALAPPDATA 'Packages'
        if (Test-Path -LiteralPath $pk) {
            foreach ($d in @(Get-ChildItem -LiteralPath $pk -Directory -Filter '*Claude*' -ErrorAction SilentlyContinue)) {
                $roots.Add((Join-Path $d.FullName 'LocalCache\Roaming\Claude'))
                $roots.Add((Join-Path $d.FullName 'LocalCache\Local\Claude'))
            }
        }
    }
    $rootfs = $null
    foreach ($r in $roots) {
        $vb = Join-Path $r 'vm_bundles'
        if (Test-Path -LiteralPath $vb) {
            $hit = Get-ChildItem -LiteralPath $vb -Recurse -Filter 'rootfs.vhdx' -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hit) { $rootfs = $hit; break }
        }
    }
    if ($rootfs) { Fact 'Workspace disk (rootfs.vhdx)' ('{0:N1} GB, saved {1:yyyy-MM-dd HH:mm}' -f ($rootfs.Length / 1GB), $rootfs.LastWriteTime) } else { Fact 'Workspace disk (rootfs.vhdx)' 'not found' }

    $logFiles = @()
    foreach ($r in $roots) {
        $logDir = Join-Path $r 'logs'
        if (Test-Path -LiteralPath $logDir) { $logFiles += @(Get-ChildItem -LiteralPath $logDir -File -Filter 'cowork*.log' -ErrorAction SilentlyContinue) }
    }
    $latest = @($logFiles | Sort-Object LastWriteTime -Descending | Group-Object Name | ForEach-Object { $_.Group[0] } | Sort-Object LastWriteTime -Descending | Select-Object -First 3)
    foreach ($lf in $latest) {
        $tail = @()
        try { $tail = @(Get-Content -LiteralPath $lf.FullName -Tail 40 -Encoding UTF8 -ErrorAction Stop) } catch {}
        $tails.Add(('--- {0} (last changed {1:yyyy-MM-dd HH:mm}) ---' -f $lf.FullName, $lf.LastWriteTime))
        foreach ($l in $tail) { $tails.Add((Hide-Secrets ([string]$l))) }
        $tails.Add('')
    }

    $dataDrive = $env:SystemDrive
    if ($env:LOCALAPPDATA) { try { $dataDrive = Split-Path -Path $env:LOCALAPPDATA -Qualifier -ErrorAction Stop } catch {} }
    if ([string]::IsNullOrEmpty($dataDrive)) { $dataDrive = 'C:' }
    $freeGB = $null
    try {
        $disk = @(Get-Cim 'Win32_LogicalDisk' ("DeviceID='" + $dataDrive + "'"))[0]
        if ($disk) { $freeGB = [math]::Round(([double]$disk.FreeSpace) / 1GB, 1) }
    } catch {}
    if ($null -ne $freeGB) { Fact ('Free space (' + $dataDrive + ')') ('{0} GB' -f $freeGB) }

    $inOneDrive = ($here -match 'OneDrive')
    Fact 'This folder' $here

    # -------------------------------------------------------------- what only a person can do
    if ($build -gt 0 -and $build -lt 19041) {
        $steps.Add('Update Windows (Start > Settings > Windows Update). Claude needs Windows 10 version 2004 or later.')
    }
    if (-not $svc) {
        if ($pkgs.Count -eq 0 -and $oldExe) {
            $steps.Add('Your Claude app came from the old installer, which has no workspace. Uninstall Claude (Start > Settings > Apps > Claude > Uninstall), then install it again from claude.com/download.')
        } else {
            $steps.Add('Reinstall Claude: uninstall it (Start > Settings > Apps > Claude > Uninstall), then install it again from claude.com/download.')
        }
        if (-not $env:CCW_NO_BROWSER) { try { Start-Process -FilePath 'explorer.exe' -ArgumentList 'https://claude.com/download' -ErrorAction Stop } catch {} }
    }
    $biosStep = $false
    if ($hv -eq $false -and $fw -eq $false) {
        $biosStep = $true
        $steps.Add('Turn on virtualization in this PC''s BIOS. The setting is called Intel Virtualization Technology (VT-x), or SVM / AMD-V. It needs a restart into the BIOS, and the key for that depends on the PC maker. If you want help, send a photo of this window to Caiman support.')
    }

    # -------------------------------------------------------------- fixes (with permission)
    if ($isAdmin) {
        if ($vmpState -ne 'Enabled' -and $vmpState -ne 'EnablePending' -and $vmpState -ne 'unknown') {
            Write-Host '- Turning on Virtual Machine Platform. This can take a few minutes; do not close this window.'
            try {
                $null = Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart -ErrorAction Stop
                $done.Add('Turned on Virtual Machine Platform.')
                $restartNeeded = $true
            } catch {
                $notes.Add('Could not turn on Virtual Machine Platform: ' + [string](Get-Innermost $_).Message)
                $steps.Add('Turn on Virtual Machine Platform: press Start, type "Turn Windows features on or off", tick "Virtual Machine Platform", click OK and restart.')
            }
        }

        if ($hv -eq $false -and $fw -ne $false -and $vmpState -eq 'Enabled' -and -not $rebootPending) {
            $hlt = ''
            try {
                $bcd = (bcdedit.exe /enum '{current}' 2>&1 | Out-String)
                if ($bcd -match '(?im)^hypervisorlaunchtype\s+(\S+)') { $hlt = $Matches[1] }
            } catch {}
            Fact 'Hypervisor launch setting' ($(if ($hlt) { $hlt } else { 'not set' }))
            if ($hlt -ne 'Auto') {
                Write-Host '- Turning the Windows hypervisor back on'
                try {
                    $null = (bcdedit.exe /set '{current}' hypervisorlaunchtype auto 2>&1 | Out-String)
                    if ($LASTEXITCODE -eq 0) {
                        $done.Add('Turned the Windows hypervisor back on (it was switched off).')
                        $notes.Add('The hypervisor launch setting was changed from "' + $(if ($hlt) { $hlt } else { 'not set' }) + '" to Auto. Old versions of VirtualBox and some Android emulators can behave differently with it on. To undo: bcdedit /set {current} hypervisorlaunchtype off (as administrator).')
                        $restartNeeded = $true
                    }
                    else { $notes.Add('Could not change the hypervisor launch setting (bcdedit exit code ' + $LASTEXITCODE + ').') }
                } catch { $notes.Add('Could not change the hypervisor launch setting: ' + [string](Get-Innermost $_).Message) }
            } else {
                $restartNeeded = $true
                $notes.Add('Virtual Machine Platform is on and the hypervisor is set to start, but none is running. A restart usually fixes this. If this file says the same after a restart, send this file to Caiman support.')
            }
        }
        if ($rebootPending) { $restartNeeded = $true }

        if ($svc) {
            if ($stype -and $stype -ne 'Automatic' -and ([string]$svc.Status -ne 'Running' -or $stype -eq 'Disabled')) {
                try {
                    Set-Service -Name $svc.Name -StartupType Automatic -ErrorAction Stop
                    $done.Add('Set the Claude VM Service to start automatically (it was set to ' + $stype + ').')
                    $stype = 'Automatic'
                } catch { $notes.Add('Could not change how the Claude VM Service starts: ' + [string](Get-Innermost $_).Message) }
            }
            if ([string]$svc.Status -ne 'Running') {
                Write-Host '- Starting the Claude VM Service'
                $why = Start-ClaudeService $svc
                if ($why -eq '') { $done.Add('Started the Claude VM Service.') }
                elseif ($restartNeeded) { $notes.Add('The Claude VM Service did not start yet (' + $why + '). It should start after the restart.') }
                else { $notes.Add('The Claude VM Service would not start: ' + $why) }
            }
        }

        if ($inOneDrive) {
            # Only for a business folder (not the OneDrive, Documents or Desktop root), only when some files are
            # online-only, and only when they are small enough to download without filling the disk.
            $leaf = Split-Path -Path $here -Leaf
            $isRoot = ($leaf -match '^(OneDrive.*|Documents|Desktop|Pictures|Documentos|Escritorio)$')
            $cloudFiles = @()
            if (-not $isRoot) {
                try {
                    $cloudFiles = @(Get-ChildItem -LiteralPath $here -Recurse -File -Force -ErrorAction SilentlyContinue |
                        Select-Object -First 20000 | Where-Object { (([int64]$_.Attributes) -band 0x441000) -ne 0 })
                } catch {}
            }
            if ($cloudFiles.Count -gt 0) {
                $cloudGB = [math]::Round((($cloudFiles | Measure-Object -Property Length -Sum).Sum) / 1GB, 2)
                if ($cloudGB -le 2 -and $null -ne $freeGB -and ($freeGB - $cloudGB) -gt 25) {
                    $null = (attrib.exe +P -U ($here + '\*') /S /D 2>&1 | Out-String)
                    $pinCode = $LASTEXITCODE
                    $null = (attrib.exe +P -U $here 2>&1 | Out-String)
                    if ($pinCode -eq 0) { $done.Add('Set this folder to stay on this PC in OneDrive, so Claude can read every file (' + $cloudFiles.Count + ' files were only in the cloud).') }
                    else { $notes.Add('Could not set the folder to "Always keep on this device" (attrib exit code ' + $pinCode + ').') }
                } else {
                    $notes.Add(('{0} files in this folder are only in OneDrive ({1} GB). If Claude cannot read a file, right-click the folder and choose "Always keep on this device".' -f $cloudFiles.Count, $cloudGB))
                }
            }
        }
    } else {
        if ($svc -and [string]$svc.Status -ne 'Running') {
            $why = Start-ClaudeService $svc
            if ($why -eq '') { $done.Add('Started the Claude VM Service.') } else { $notes.Add('The Claude VM Service would not start: ' + $why) }
        }
        $notes.Add('Windows did not give this file permission to make changes, so it only checked (and tried to start the Claude VM Service).')
        if ($vmpState -ne 'Enabled' -and $vmpState -ne 'EnablePending' -and $vmpState -ne 'unknown') {
            $steps.Add('Turn on Virtual Machine Platform: press Start, type "Turn Windows features on or off", tick "Virtual Machine Platform", click OK and restart. This needs an administrator account.')
        }
        if ($rebootPending) { $restartNeeded = $true }
        if ($steps.Count -eq 0 -and ($hv -ne $true -or ($svc -and [string]$svc.Status -ne 'Running'))) {
            $steps.Add('Windows did not let this file make changes. Double-click it again and click Yes, or ask whoever manages this PC to run it.')
            $permOnly = $true
        }
    }

    if (-not $rootfs -and $null -ne $freeGB -and $freeGB -lt 20) {
        $steps.Add(('Free up space on {0}. Claude''s workspace needs about 20 GB free and there is {1} GB.' -f $dataDrive, $freeGB))
    }
    if ($onDomain) { $notes.Add('This PC is managed by a company. If a step is blocked, the company''s IT team has to do it.') }
    if ($isGuest) { $notes.Add('This Windows runs inside a virtual machine, which needs nested virtualization for Claude''s workspace.') }
} catch {
    $notes.Add('The fix stopped early because of an error: ' + [string](Get-Innermost $_).Message)
    $steps.Add('Send the file claude-workspace-fix.txt from this folder to Caiman support.')
}

# ------------------------------------------------------------------ what the member sees
$lines = New-Object System.Collections.Generic.List[string]
if ($done.Count -gt 0) {
    $lines.Add('What this fixed:')
    foreach ($d in $done) { $lines.Add(' - ' + $d) }
    $lines.Add('')
}
$lines.Add('What to do now:')
$n = 1
foreach ($s in $steps) { $lines.Add((' {0}. {1}' -f $n, $s)); $n++ }
if ($steps.Count -gt 0) {
    if ($restartNeeded -and -not $biosStep -and -not $permOnly) { $lines.Add((' {0}. Restart your computer.' -f $n)); $n++ }
    if (-not $permOnly) { $lines.Add((' {0}. Then double-click this file again.' -f $n)) }
} elseif ($restartNeeded) {
    $lines.Add((' {0}. Restart your computer.' -f $n)); $n++
    $lines.Add((' {0}. Open Claude, start a new task in your business project and say: update my Caiman kit' -f $n))
} else {
    if ($done.Count -eq 0 -and $isAdmin) { $lines.Insert(0, 'Everything on this PC already looks right.'); $lines.Insert(1, '') }
    $lines.Add((' {0}. Quit Claude completely (File > Exit), then open it again.' -f $n)); $n++
    $lines.Add((' {0}. Start a new task in your business project and say: update my Caiman kit' -f $n))
}
if ($steps.Count -eq 0 -and -not $rootfs) {
    $lines.Add('    The first time, Claude downloads its workspace (more than 1 GB), so that task can take up to an hour.')
}
$lines.Add('')
$lines.Add('If Claude still cannot run commands on your computer after that, send the file')
$lines.Add('claude-workspace-fix.txt (in this folder) to Caiman support.')

# ------------------------------------------------------------------ the support file
$out = New-Object System.Collections.Generic.List[string]
$out.Add('CLAUDE WORKSPACE FIX')
$out.Add(('Run {0:yyyy-MM-dd HH:mm} on {1}' -f $stamp, [string]$env:COMPUTERNAME))
$out.Add('')
foreach ($l in $lines) { $out.Add($l) }
$out.Add('')
if ($notes.Count -gt 0) { $out.Add('NOTES'); foreach ($x in $notes) { $out.Add('- ' + $x) }; $out.Add('') }
$out.Add('DETAILS')
foreach ($f in $facts) { $out.Add($f) }
$out.Add('')
if ($tails.Count -gt 0) {
    $out.Add('WORKSPACE LOG (last lines; keys, tokens and email addresses removed)')
    foreach ($l in $tails) { $out.Add($l) }
}
$reportPath = Join-Path $here 'claude-workspace-fix.txt'
try { [IO.File]::WriteAllText($reportPath, (($out -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false))) }
catch {
    try {
        $reportPath = Join-Path ([IO.Path]::GetTempPath()) 'claude-workspace-fix.txt'
        [IO.File]::WriteAllText($reportPath, (($out -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
    } catch {}
}

Write-Host ''
Write-Host '=================================================================='
foreach ($l in $lines) { Write-Host $l }
Write-Host '=================================================================='
