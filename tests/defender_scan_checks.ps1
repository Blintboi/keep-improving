$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\packaging\defender_scan.ps1')
$path='C:\ReleaseFixture\app.exe'
$before=@{$path='abc'}
$start=[pscustomobject]@{Id=1000;ScanId='fixture';Resources=$path}
$end=[pscustomobject]@{Id=1001;ScanId='fixture';Resources=''}
$clean=@($start,$end)
$checks=[ordered]@{}
Set-StrictMode -Version Latest
$scanFixture=Join-Path $PSScriptRoot 'FixtureRestriction.cs'
$scanFiles=Get-DefenderScanFiles $scanFixture
$checks.single_file_is_enumerated_under_strict_mode = $scanFiles.Count -eq 1 -and $scanFiles.ContainsKey([IO.Path]::GetFullPath($scanFixture))
$checks.clean_completed_scan_passes = @(Get-DefenderScanRejections $before $before $clean $path $true).Count -eq 0
$detected=$clean+@([pscustomobject]@{Id=1116;ScanId='';Resources=$path})
$checks.detection_blocks_even_when_scan_command_succeeded = @(Get-DefenderScanRejections $before $before $detected $path $true).Count -gt 0
$remediated=$clean+@([pscustomobject]@{Id=1117;ScanId='';Resources=$path})
$checks.successful_remediation_still_blocks_delivery = @(Get-DefenderScanRejections $before $before $remediated $path $true).Count -gt 0
$checks.removed_file_blocks = @(Get-DefenderScanRejections $before @{} $clean $path $true).Count -gt 0
$checks.modified_file_blocks = @(Get-DefenderScanRejections $before @{$path='changed'} $clean $path $true).Count -gt 0
$checks.no_scan_receipt_blocks = @(Get-DefenderScanRejections $before $before @() $path $true).Count -gt 0
$wrongEnd=[pscustomobject]@{Id=1001;ScanId='unrelated';Resources=''}
$checks.unrelated_completion_blocks = @(Get-DefenderScanRejections $before $before @($start,$wrongEnd) $path $true).Count -gt 0
$interrupted=$clean+@([pscustomobject]@{Id=1002;ScanId='fixture';Resources=''})
$checks.interrupted_scan_blocks = @(Get-DefenderScanRejections $before $before $interrupted $path $true).Count -gt 0
$checks.disabled_defender_blocks = @(Get-DefenderScanRejections $before $before $clean $path $false).Count -gt 0
$other=$clean+@([pscustomobject]@{Id=1116;ScanId='';Resources='C:\Unrelated\app.exe'})
$checks.unrelated_detection_does_not_accuse_release = @(Get-DefenderScanRejections $before $before $other $path $true).Count -eq 0
$checks | ConvertTo-Json
if (@($checks.Values | Where-Object { $_ -ne $true }).Count) { throw 'Defender scan gate regression.' }
