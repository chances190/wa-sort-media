param(
    [string]$deviceName,
    [string]$destinationPath
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$shell = New-Object -ComObject Shell.Application

# 1. Setup Destination
$absoluteDest = [System.IO.Path]::GetFullPath($destinationPath)
if (-not (Test-Path $absoluteDest)) { New-Item -ItemType Directory -Path $absoluteDest -Force | Out-Null }
$destFolder = $shell.NameSpace($absoluteDest)

# 2. Find Phone & WhatsApp Root
$thisPC = $shell.NameSpace(0x11)
$device = $thisPC.Items() | Where-Object { $_.Name -eq $deviceName }
$storage = $device.GetFolder.Items() | Where-Object { $_.Name -match "Internal|storage|Armazenamento|Memória" }

# Define target paths
$basePath = "Android\media\com.whatsapp\WhatsApp"
$dbSubPath = "$basePath\Databases"
$mediaSubPath = "$basePath\Media"

# Target Folders in Media
$targetMediaFolders = @("WhatsApp Audio", "WhatsApp Images", "WhatsApp Video", "WhatsApp Video Notes", "WhatsApp Voice Notes")

# Counter for progress tracking
$script:fileCount = 0
$script:totalFiles = 0

# Helper function to force-load MTP items (fixes lazy loading bug)
function Get-MTPItemsWithRetry($folderObj) {
    $items = $null
    $retryCount = 0
    $maxRetries = 10  # Try for up to 5 seconds
    
    while ($null -eq $items -or $items.Count -eq 0) {
        try {
            $items = $folderObj.GetFolder.Items()
            if ($items.Count -gt 0) { 
                return $items 
            }
        }
        catch {
            # Ignore errors and retry
        }
        
        if ($retryCount -ge $maxRetries) { 
            break 
        }
        
        Start-Sleep -Milliseconds 500
        $retryCount++
        # Accessing properties forces a refresh of the MTP cache
        $name = $folderObj.Name 
        $isFolder = $folderObj.IsFolder
    }
    
    return $items
}

function Get-MTPFolder($root, $path) {
    $current = $root
    foreach ($segment in $path.Split("\")) {
        if ($null -eq $current) { return $null }
        # Use retry logic to handle lazy loading
        $items = Get-MTPItemsWithRetry $current
        if ($null -eq $items -or $items.Count -eq 0) { return $null }
        $current = $items | Where-Object { $_.Name -eq $segment }
    }
    return $current
}

# --- COUNT TOTAL FILES FUNCTION (must be defined before use) ---
function Count-MTPFiles {
    param(
        [Parameter(Mandatory=$true)] $SourceFolderItem
    )
    
    $count = 0
    try {
        $items = Get-MTPItemsWithRetry $SourceFolderItem
        if ($null -ne $items) {
            foreach ($it in $items) {
                if ($it.IsFolder) {
                    $count += Count-MTPFiles -SourceFolderItem $it
                } else {
                    $count++
                }
            }
        }
    }
    catch {
        # Silently continue on errors
    }
    
    return $count
}

# --- PROCESS MEDIA (preserve folder structure) ---
function Copy-MTPFolderRecursive {
    param(
        [Parameter(Mandatory=$true)] $SourceFolderItem,
        [Parameter(Mandatory=$true)][string] $DestPath,
        [Parameter(Mandatory=$false)][string] $FolderName = ""
    )

    if (-not (Test-Path $DestPath)) { 
        New-Item -ItemType Directory -Path $DestPath -Force | Out-Null 
    }
    $destNs = $shell.NameSpace($DestPath)
    
    $items = Get-MTPItemsWithRetry $SourceFolderItem
    if ($null -eq $items) {
        Write-Host "[LOG] No items found in folder, skipping..."
        return
    }

    foreach ($it in $items) {
        if ($it.IsFolder) {
            $subDest = Join-Path $DestPath $it.Name
            if (-not (Test-Path $subDest)) { 
                New-Item -ItemType Directory -Path $subDest -Force | Out-Null 
            }
            Copy-MTPFolderRecursive -SourceFolderItem $it -DestPath $subDest
        } else {
            $script:fileCount++
            $percentage = if ($script:totalFiles -gt 0) { [math]::Round(($script:fileCount / $script:totalFiles) * 100) } else { 0 }
            Write-Host "[PROGRESS] $($script:fileCount)/$($script:totalFiles)"
            Write-Host "[FILE] Copying: $($it.Name)"
            $destNs.CopyHere($it, 16)  # 16 all yes + 4 no dialogue
        }
    }
}

# --- PROCESS DATABASE ---
Write-Host "[LOG] Searching for msgstore.db.crypt15..."
$dbFolder = Get-MTPFolder -root $storage -path $dbSubPath
if ($null -ne $dbFolder) {
    $dbItems = Get-MTPItemsWithRetry $dbFolder
    if ($null -ne $dbItems) {
        $dbFile = $dbItems | Where-Object { $_.Name -eq "msgstore.db.crypt15" }
        if ($null -ne $dbFile) {
            Write-Host "[LOG] Copying Database..."
            $destFolder.CopyHere($dbFile, 20)  # 16 all yes + 4 no dialogue
            $script:fileCount++
        }
    }
} else {
    Write-Host "[LOG] Database folder not found; skipping..."
}

# --- COUNT TOTAL FILES FOR PROGRESS ---
Write-Host "[LOG] Counting media files..."
$mediaFolderObj = Get-MTPFolder -root $storage -path $mediaSubPath
if ($null -ne $mediaFolderObj) {
    $mediaItems = Get-MTPItemsWithRetry $mediaFolderObj
    if ($null -ne $mediaItems) {
        foreach ($folderName in $targetMediaFolders) {
            $folderItem = $mediaItems | Where-Object { $_.Name -eq $folderName }
            if ($null -ne $folderItem) {
                $count = Count-MTPFiles -SourceFolderItem $folderItem
                $script:totalFiles += $count
                Write-Host "[LOG] '$folderName' has $count files"
            }
        }
    }
}

Write-Host "[LOG] Total files to copy: $($script:totalFiles)"

# --- START MEDIA COPY ---
$mediaFolderObj = Get-MTPFolder -root $storage -path $mediaSubPath
if ($null -ne $mediaFolderObj) {
    $mediaItems = Get-MTPItemsWithRetry $mediaFolderObj
    if ($null -ne $mediaItems) {
        foreach ($folderName in $targetMediaFolders) {
            $folderItem = $mediaItems | Where-Object { $_.Name -eq $folderName }
            if ($null -ne $folderItem) {
                $destSub = Join-Path $absoluteDest $folderName
                Write-Host "[LOG] Copying folder '$folderName' to '$destSub'..."
                Copy-MTPFolderRecursive -SourceFolderItem $folderItem -DestPath $destSub -FolderName $folderName
            } else {
                Write-Host "[LOG] Folder '$folderName' not found; skipping..."
            }
        }
    }
} else {
    Write-Host "[LOG] Media folder not found; skipping media copy."
}

Write-Host "[LOG] Finished all tasks."