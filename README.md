# WhatsApp Media Organizer

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
WhatsApp's media management is deliberately terrible. You can't organize files by conversation, you can't bulk export organized archives, and you're stuck with a chronological dump of thousands of files with cryptic names. This is **by design** to keep you locked into their ecosystem.

Your data belongs to you. Organize it however you want.

## Quick Guide

### What You'll Need

- Android phone with WhatsApp
- USB cable to connect phone to computer
- About 30 minutes
- Your Google Contacts (optional but recommended)

### Step 1: Enable WhatsApp 64-Digit Backup Key

1. Open **WhatsApp** on your phone
2. Tap **⋮** (three dots) → **Settings**
3. Go to **Chats** → **Chat backup**
4. Tap **End-to-end encrypted backup** → **Turn on**
5. Select **Use a 64-digit encryption key** (NOT password!)
6. **SAVE THIS KEY!** Screenshot it, write it down, put it in a password manager
7. Tap **Create** → **Done**

> [!WARN]
> This key is really important! Without it, you can't recover your messages if you reinstall WhatsApp

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

### Step 4: Use the WhatsApp Media Organizer

1. Download the latest installer from the [Releases page](https://github.com/chances190/wa-sort-media/releases).
2. Install and open **WhatsApp Media Suite**.
3. Follow the steps displayed in the app.

> [!NOTE]  
> This tool works entirely offline. Your messages and media never leave your computer.

## CLI Version

If you prefer using the terminal, there is a CLI available. You can run it directly from GitHub using [`uv`](https://docs.astral.sh/uv/):

```bash
uvx --from git+https://github.com/chances190/wa-sort-media.git wasort --help
```
or
```bash
uv tool install --from git+https://github.com/chances190/wa-sort-media.git
wasort --help
```

## Background: why extracting WhatsApp data is hard

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

## 🙏 Credits

- **Huge thanks to [TripCode](https://github.com/TripCode)** for creating the original WhatsApp crypt12 decrypter, which laid the foundation for all subsequent encryption research and tools.
- **Thanks to [ElDavoo](https://github.com/ElDavoo)** for creating and maintaining [wa-crypt-tools](https://github.com/ElDavoo/wa-crypt-tools), which builds on that foundation to enable database decryption without root access.
- **Thanks to [YuvrajRaghuvanshiS](https://github.com/YuvrajRaghuvanshiS)** and all contributors to the [WhatsApp-Key-Database-Extractor](https://github.com/YuvrajRaghuvanshiS/WhatsApp-Key-Database-Extractor) and the broader community who've continued the work of reverse engineering WhatsApp's encryption.
- This tool wouldn't exist without the collective effort of these developers. 🙏
- Thanks to the WhatsApp developers who implemented the E2E 64-digit token backup feature. The one good thing in this mess.
