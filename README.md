# WhatsApp Media Organizer

Organize your WhatsApp media files into conversation-based folders using the msgstore database and contacts.

## 📋 What This Does

This tool takes your WhatsApp media files (images, videos, audio, documents) and organizes them into folders by conversation/contact, instead of having everything mixed together in one big folder.

**Before:**
```
WhatsApp/Media/
  WhatsApp Images/
    IMG-20240101-WA0001.jpg
    IMG-20240102-WA0002.jpg
    ...
  WhatsApp Video/
    VID-20240101-WA0001.mp4
    ...
```

**After:**
```
Media_organized/
  John Doe/
    Images/
      IMG-20240101-WA0001.jpg
    Video/
      VID-20240101-WA0001.mp4
  Family Group/
    Images/
      IMG-20240102-WA0002.jpg
  ...
```

## 💢 Why This Exists

WhatsApp's media management is deliberately terrible. You can't organize files by conversation, you can't bulk export organized archives, and you're stuck with a chronological dump of thousands of files with cryptic names. This is **by design** to keep you locked into their ecosystem.

Your data belongs to you. Organize it however you want.


## � Choose Your Guide

This README has two paths depending on your technical comfort level:

- **[👤 For Regular Users](#-for-regular-users)** - Detailed step-by-step guide with clear explanations
- **[💻 For Developers](#-for-developers--power-users)** - Concise technical reference

---

## 👤 For Regular Users

### What You'll Need

- Android phone with WhatsApp
- USB cable to connect phone to computer
- About 30 minutes
- Your Google Contacts (optional but recommended)

### Step 1: Enable 64-Digit Backup Key

1. Open **WhatsApp** on your phone
2. Tap **⋮** (three dots) → **Settings**
3. Go to **Chats** → **Chat backup**
4. Tap **End-to-end encrypted backup** → **Turn on**
5. Select **Use a 64-digit encryption key** (NOT password!)
6. **SAVE THIS KEY!** Screenshot it, write it down, put it in a password manager
7. Tap **Create** → **Done**

> ⚠️ **Critical:** This key is really important! Without it, you can't recover your messages if you reinstall WhatsApp

### Step 2: Create Fresh Backup

1. In WhatsApp: **Settings** → **Chats** → **Chat backup**
2. Tap the big green **Back up** button
3. Wait for it to finish (may take 10-30 minutes if your chats are big)

### Step 3: Export Contacts

**Method A: Google Contacts**
1. Go to [contacts.google.com](https://contacts.google.com)
2. Sign in with the same Google account on your phone
3. Click **Export** (arrow on the top-right)
4. Choose **vCard** format → **Export**
5. Save as `contacts.vcf`

**Method B: Phone's Contacts App**
1. Open your Contacts app
2. Find **Import/Export** or **Settings**
3. Select **Export to vCard file**
4. Save somewhere you can find it

### Step 4: Copy Files from Phone

**What to copy:**
- `Databases` folder (contains encrypted backup)
- `Media` folder (all your images, videos, etc.)
- `contacts.vcf` file (from Step 3)

**How:**
1. Connect phone to computer via USB
2. On phone: Tap the USB notification → Select **File Transfer**
3. On computer: Open your phone in file explorer
4. Navigate to: `Internal storage/Android/media/com.whatsapp/WhatsApp/`
5. Copy the `Databases` and `Media` folders to your computer
6. Also copy your `contacts.vcf` if you saved it on phone

💡 **Tip:** Create a folder on your computer called `WhatsApp_Export` and put everything there.

### Step 5: Install Python

**Windows:**
1. Download from [python.org/downloads](https://www.python.org/downloads/)
2. Run the installer
3. ✅ **CHECK "Add Python to PATH"**
4. Click "Install Now"

**Mac:**
```bash
brew install python@3.10
```

**Linux:**
```bash
sudo apt install python3.10 python3-pip  # Debian/Ubuntu
sudo dnf install python3.10 python3-pip  # Fedora
```

### Step 6: Install Tools

Open Terminal/Command Prompt (Windows: `Win+R` → type `cmd` → Enter):

```bash
# Navigate to your WhatsApp export folder
cd path/to/WhatsApp_Export

# Install decryption tool
pip install wa-crypt-tools

# Install organizer
pip install git+https://github.com/yourusername/wa-sort-media.git
```

### Step 7: Create Encryption Key File

```bash
wadecrypt
```

When prompted, paste your 64-digit key from Step 1. This creates `encrypted_backup.key`.

### Step 8: Decrypt Database

```bash
wadecrypt decrypt encrypted_backup.key Databases/msgstore.db.crypt15 msgstore.db
```

You should see: **"Decryption successful!"**

> 📝 If your database has a date like `msgstore-2026-01-20.1.db.crypt15`, use that name instead.

### Step 9: Organize Your Media!

**Test with dry-run first (doesn't actually move files):**
```bash
wasort msgstore.db Media --contacts contacts.vcf --dry-run -v
```

**If it looks good, run for real:**
```bash
# Copy files (keeps originals)
wasort msgstore.db Media --contacts contacts.vcf --copy

# OR move files (deletes originals)
wasort msgstore.db Media --contacts contacts.vcf --move
```

Watch the progress bars! When done, check the `Media_organized` folder.

---

## 💻 For Developers / Power Users

### Technical Background:

If you aren't familiar with Android’s security model, here's why extracting WhatsApp data has historically been a significant hurdle:

On Android, every app runs in its own "sandbox." WhatsApp stores its encryption key and internal databases in a private directory:
`/data/data/com.whatsapp/files/key`

Directories on the `/data` folder are only accessible by the apps own UID or by the Root user. Without Root access, a user or a third-party desktop tool cannot "see" or copy this key.

While WhatsApp creates backups on your local storage (`msgstore.db.crypt15`, `wa.db.crypt15`), these files are useless without the key mentioned above.For a long time, all methods to get the key were fragile, hacky, inconvenient or all of the above.

- **Rooting:** Gaining root access to directly read /data/data/com.whatsapp/databases/.
    - Voids warranty (for those who care) and can brick the device if you're careless. Triggers Google's SafetyNet/Play Integrity check, breaking many banking apps and requiring workarounds (Magisk). Most critically, it forces a full re-login and reverification of WhatsApp, which is the primary point of failure for data preservation.
- **Downgrading:** Installing an older WhatsApp version with known vulnerabilities or legacy backup formats.
    - Highly unstable. Older versions often crash or fail to read current data structures. The re-login process on an old version frequently triggers server-side data wipes or account locks, leading to irreversible local data loss.
- **Legacy ADB Backups:** Using adb backup to request app data.
    - Effectively dead. WhatsApp disabled support, and Google deprecated the functionality. Does not work on Android 9+. Any tools claiming otherwise use patched ADB binaries or exploit CVE-2014-7956, which are unreliable.

Thankfully, WhatsApp has now introduced now supports **End-to-End Encrypted Backups** using a user-generated 64-digit encryption key, finally bypassing all of the problems above.

**As of Jan 2026, the 64-digit E2E encryption token is the ONLY reliable way to access your WhatsApp database for non-rooted users.**

### Quick Start

1. **Install Tools:**
    ```bash
    pip install wa-crypt-tools git+https://github.com/chances190/wa-sort-media.git
    ```

2. **Pull Files from Phone (ADB Method):**
    - Ensure ADB is installed and your phone is connected in file transfer mode.
    ```bash
    adb pull  /storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases .
    adb pull  /storage/emulated/0/media/com.whatsapp/WhatsApp/Media .
    ```

3. **Pull Real wa.db (Root Only):**
    - Requires root access on your device.
    - The `wa.db` in backups is **practically empty**, it's just a stub with minimal data.
    ```bash
    adb shell su -c "cp /data/data/com.whatsapp/databases/wa.db  /storage/emulated/0/"
    adb pull /storage/emulated/0/wa.db .
    ```

4. **Decrypt Database:**
    - Run interactively to create the key file:
    ```bash
    wadecrypt
    ```
    - Paste your 64-digit token when prompted.
    - Then decrypt the database:
    ```bash
    wadecrypt decrypt encrypted_backup.key Databases/msgstore.db.crypt15 msgstore.db
    ```

5. **Organize Media:**
    - Using Google Contacts VCF:
    ```bash
    wasort msgstore.db Media --contacts contacts.vcf
    ```
    - Or using wa.db:
    ```bash
    wasort msgstore.db Media --wa-db wa.db
    ```

## ⚙️ Command Reference

```bash
wasort <msgstore.db> <media_folder> [output_folder] [options]
```

**Arguments:**
- `msgstore.db` - Decrypted WhatsApp database
- `media_folder` - Your WhatsApp Media folder
- `output_folder` - (Optional) Where to put organized files (default: `<media_folder>_organized`)

**Options:**
- `--contacts <file.vcf>` - Use Google Contacts VCF export
- `--wa-db <wa.db>` - Use WhatsApp's wa.db
- `--copy` - Copy files (keeps originals) - **Default**
- `--move` - Move files (removes originals)
- `--dry-run` - Show what would happen without doing it
- `-v` / `--verbose` - Show detailed progress

## 🙏 Credits

- **Huge thanks to [TripCode](https://github.com/TripCode)** for creating the original WhatsApp crypt12 decrypter, which laid the foundation for all subsequent encryption research and tools.
- **Thanks to [ElDavoo](https://github.com/ElDavoo)** for creating and maintaining [wa-crypt-tools](https://github.com/ElDavoo/wa-crypt-tools), which builds on that foundation to enable database decryption without root access.
- **Thanks to [YuvrajRaghuvanshiS](https://github.com/YuvrajRaghuvanshiS)** and all contributors to the [WhatsApp-Key-Database-Extractor](https://github.com/YuvrajRaghuvanshiS/WhatsApp-Key-Database-Extractor) and the broader community who've continued the work of reverse engineering WhatsApp's encryption.
- This tool wouldn't exist without the collective effort of these developers. 🙏
- Thanks to the WhatsApp developers who implemented the E2E 64-digit token backup feature. The one good thing in this mess.


