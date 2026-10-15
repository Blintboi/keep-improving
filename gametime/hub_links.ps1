param([Parameter(Mandatory=$true)][string]$RequestPath)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$request = [IO.File]::ReadAllText($RequestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
$shell = New-Object -ComObject WScript.Shell
$result = [Collections.Generic.List[object]]::new()
if ($request.action -eq 'inventory') {
    foreach ($scan in $request.roots) {
        $pending = [Collections.Generic.Stack[object]]::new()
        $pending.Push(@([string]$scan.path, 0))
        while ($pending.Count) {
            $current = $pending.Pop()
            foreach ($file in @(Get-ChildItem -LiteralPath $current[0] -Force -ErrorAction SilentlyContinue)) {
                if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
                if ($file.PSIsContainer) {
                    if ($current[1] -lt $scan.depth) { $pending.Push(@($file.FullName, ($current[1] + 1))) }
                    continue
                }
                try {
                    if ($file.Extension -ieq '.lnk') {
                        $link = $shell.CreateShortcut($file.FullName)
                        $result.Add(@{path=$file.FullName; target=$link.TargetPath; arguments=$link.Arguments;
                            working=$link.WorkingDirectory; icon=$link.IconLocation; description=$link.Description})
                    } elseif ($file.Extension -ieq '.url' -and $file.Length -lt 65536) {
                        $result.Add(@{path=$file.FullName; contents=[IO.File]::ReadAllText($file.FullName)})
                    }
                } catch { } # An installer may be replacing an individual shortcut.
            }
        }
    }
} elseif ($request.action -eq 'create') {
    foreach ($item in $request.links) {
        # Python supplies a fresh staging path. This script never overwrites a user file.
        if ([IO.Path]::GetExtension($item.path) -ine '.lnk' -or (Test-Path -LiteralPath $item.path)) {
            throw 'Invalid shortcut staging path.'
        }
        $link = $shell.CreateShortcut($item.path)
        $link.TargetPath = $item.target
        $link.Arguments = $item.arguments
        $link.WorkingDirectory = $item.working
        $link.Description = $item.description
        if ($item.icon) { $link.IconLocation = $item.icon }
        $link.Save()
        $saved = $shell.CreateShortcut($item.path)
        if ($saved.TargetPath -ine $item.target -or $saved.Arguments -cne $item.arguments -or
            $saved.WorkingDirectory -ine $item.working) { throw 'Shortcut readback failed.' }
        $result.Add(@{path=$item.path; verified=$true})
    }
} else { throw 'Unknown shortcut request.' }
ConvertTo-Json -InputObject @($result.ToArray()) -Depth 8 -Compress
