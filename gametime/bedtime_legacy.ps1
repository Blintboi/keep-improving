param([ValidateSet('Inspect','Disable')][string]$Mode='Inspect')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$service=New-Object -ComObject Schedule.Service
$service.Connect()
$folder=$service.GetFolder('\')
$task=@($folder.GetTasks(0) | Where-Object Name -eq ('BedtimeReminder-'+$sid))
if ($task.Count -ne 1) { exit 0 }
$task=$task[0]
$definition=$task.Definition
$principal=$definition.Principal.UserId
if ($principal -notmatch '^S-1-') { $principal=([Security.Principal.NTAccount]::new($principal)).Translate([Security.Principal.SecurityIdentifier]).Value }
$script=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'BedtimeReminder\bedtime_reminder.py'
if ($definition.RegistrationInfo.Description -notlike 'BedtimeReminder.v1*' -or $principal -ne $sid -or $definition.Actions.Count -ne 1) { exit 0 }
$action=$definition.Actions.Item(1)
if ($action.Type -ne 0 -or $action.Arguments -ne ('"'+$script+'" --scheduled') -or [IO.Path]::GetFileName($action.Path) -ne 'pythonw.exe') { exit 0 }
if ($Mode -eq 'Inspect') {
    if ($task.Enabled) { [Console]::Out.Write($task.Xml) }
} else {
    $task.Enabled=$false
    if ($task.Enabled) { throw 'Legacy bedtime task could not be disabled.' }
    [Console]::Out.Write('disabled')
}
