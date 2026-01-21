# Force output to UTF-8 for Python to handle diacritics
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$shell = New-Object -ComObject Shell.Application
$thisPC = $shell.NameSpace(0x11)

# Filter: 
# 1. Must be a folder (IsFolder)
# 2. Must NOT be a local disk or common library folder
# 3. Must have a 'Path' that starts with '::' (Standard for MTP/Virtual devices)
$devices = $thisPC.Items() | Where-Object { 
    $_.IsFolder -and 
    $_.Type -notmatch "Local Disk|System Folder|Library|Network" -and
    $_.Path -like "::*"
}

foreach ($dev in $devices) { 
    Write-Output $dev.Name 
}