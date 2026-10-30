# Release preflight only: never launches an application or changes Defender policy.
function Get-DefenderScanFiles([string]$Target) {
    $item = Get-Item -LiteralPath $Target -ErrorAction Stop
    $files = @(if ($item.PSIsContainer) { Get-ChildItem -LiteralPath $Target -File -Recurse -ErrorAction Stop } else { $item })
    if (-not $files.Count) { throw 'No release files to scan.' }
    $hashes = @{}
    foreach ($file in $files) {
        if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Release scan contains a file link.' }
        $hashes[$file.FullName] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256 -ErrorAction Stop).Hash
    }
    return $hashes
}

function Get-DefenderScanRejections($Before, $After, $Events, [string]$Target, [bool]$ProtectionEnabled) {
    if (-not $ProtectionEnabled) { 'Microsoft Defender must be active with real-time protection enabled.' }
    if (-not $Before.Count -or $Before.Count -ne $After.Count) { 'Release files disappeared or changed during scanning.' }
    foreach ($path in $Before.Keys) {
        if ($Before[$path] -ne $After[$path]) { 'A release file was removed or changed during scanning.'; break }
    }
    $starts = @($Events | Where-Object { $_.Id -eq 1000 -and $_.Resources -and $_.Resources.IndexOf($Target,[StringComparison]::OrdinalIgnoreCase) -ge 0 })
    $completed = $false
    foreach ($start in $starts) {
        if ($start.ScanId -and @($Events | Where-Object { $_.Id -eq 1001 -and $_.ScanId -eq $start.ScanId }).Count) { $completed = $true }
    }
    if (-not $completed) { 'No completed Defender scan for these release files was recorded.' }
    foreach ($event in $Events) {
        if ($event.Id -in @(1116,1117,1118,1119) -and $event.Resources -and $event.Resources.IndexOf($Target,[StringComparison]::OrdinalIgnoreCase) -ge 0) {
            'Defender detected a threat in the release files, even if remediation succeeded.'; break
        }
        if ($event.Id -eq 1002 -and $event.ScanId -in @($starts | ForEach-Object { $_.ScanId })) {
            'The Defender scan was interrupted.'; break
        }
    }
}

function Assert-DefenderReleaseScan([string]$Target, [string]$ReportPath) {
    $Target = [IO.Path]::GetFullPath($Target)
    $ReportPath = [IO.Path]::GetFullPath($ReportPath)
    $report = [ordered]@{ target=$Target; passed=$false; started_utc=[DateTime]::UtcNow.ToString('o') }
    try {
        $before = Get-DefenderScanFiles $Target
        $status = Get-MpComputerStatus -ErrorAction Stop
        $report.signature_version = $status.AntivirusSignatureVersion
        if (-not ($status.AntivirusEnabled -and $status.RealTimeProtectionEnabled -and $status.AMServiceEnabled)) {
            throw 'Defender is not active. Release verification cannot proceed.'
        }
        $preferences = Get-MpPreference -ErrorAction Stop
        if ($preferences.DisableArchiveScanning) { throw 'Defender archive scanning is disabled. Release verification cannot proceed.' }
        foreach ($file in $before.Keys) {
            foreach ($excluded in $preferences.ExclusionPath) {
                if (-not $excluded) { continue }
                $expanded = [Environment]::ExpandEnvironmentVariables($excluded).TrimEnd('\')
                if ($file -like $expanded -or $file -like ($expanded+'\*')) { throw 'A release file is excluded from Defender scanning.' }
            }
            foreach ($excluded in $preferences.ExclusionExtension) {
                if ($excluded -and [IO.Path]::GetExtension($file).TrimStart('.') -like $excluded.TrimStart('.')) { throw 'A release file extension is excluded from Defender scanning.' }
            }
        }
        $started = (Get-Date).AddSeconds(-1)
        Start-MpScan -ScanType CustomScan -ScanPath $Target -ErrorAction Stop
        # A successful scan command can still have found and quarantined malware.
        # Require its completion event, no matching detections, and unchanged bytes.
        # Event Log delivery can lag the synchronous scan command slightly.
        $deadline = [DateTime]::UtcNow.AddSeconds(10)
        do {
            $eventErrors=@()
            $events = @(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Windows Defender/Operational';StartTime=$started;Id=1000,1001,1002,1116,1117,1118,1119} -ErrorAction SilentlyContinue -ErrorVariable eventErrors | ForEach-Object {
                [xml]$xml=$_.ToXml(); $data=@{}
                foreach ($field in $xml.Event.EventData.Data) { $data[$field.Name]=$field.'#text' }
                [pscustomobject]@{Id=$_.Id;ScanId=$data['Scan ID'];Resources=($data['Scan Resources']+' '+$data['Path']);Threat=$data['Threat Name']}
            })
            foreach ($errorRecord in $eventErrors) {
                if ($errorRecord.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound*') { throw $errorRecord }
            }
            $ids=@($events | Where-Object { $_.Id -eq 1000 -and $_.Resources.IndexOf($Target,[StringComparison]::OrdinalIgnoreCase) -ge 0 } | ForEach-Object { $_.ScanId })
            if (@($events | Where-Object { $_.Id -in @(1001,1002) -and $_.ScanId -in $ids }).Count) { break }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $deadline)
        $after = Get-DefenderScanFiles $Target
        $status = Get-MpComputerStatus -ErrorAction Stop
        $active = $status.AntivirusEnabled -and $status.RealTimeProtectionEnabled -and $status.AMServiceEnabled
        $rejections = @(Get-DefenderScanRejections $before $after $events $Target $active)
        $report.file_count = $before.Count
        $report.detections = @($events | Where-Object { $_.Id -in @(1116,1117,1118,1119) -and $_.Resources.IndexOf($Target,[StringComparison]::OrdinalIgnoreCase) -ge 0 } | Select-Object Id,Threat)
        if ($rejections.Count) { throw ($rejections -join ' ') }
        $report.sha256 = $before
        $report.passed = $true
    } catch {
        $report.error = $_.Exception.Message
        throw
    } finally {
        New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($ReportPath)) -Force | Out-Null
        $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    }
}
