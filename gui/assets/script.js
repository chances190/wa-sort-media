// ============================================================================
// WhatsApp Media Suite - frontend
//
// One-way flow: mutate `state`, then call render(). The DOM is always derived
// from state, so the view, stepper and footer can't drift out of sync.
// ============================================================================

const PAGES = ['backup', 'decrypt', 'organize', 'progress', 'done'];
const STEP_VIEW = ['backup', 'decrypt', 'organize'];

const state = {
    step: 1,
    view: 'backup',
    busy: false,
    canceled: false,
    opStart: 0,
    backupPath: '',
    mediaPath: '',
    dbPath: '',
    outputPath: '',
    contactsPath: '',
    key: '',
    device: '',
    backend: '',
    devices: [],
    backupDone: false,
    decryptDone: false,
};

// ============================================================================
// BOOT
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    if (window.pywebview && window.pywebview.api) init();
});
window.addEventListener('pywebviewready', init);

let initialized = false;
async function init() {
    if (initialized) return;
    initialized = true;

    await loadMediaFolders();
    restoreState();
    render();
    if (state.view === 'backup') refreshDevices();
}

// ============================================================================
// RENDERING
// ============================================================================

function render() {
    PAGES.forEach((name) => {
        const el = document.getElementById('page-' + name);
        if (!el) return;
        el.classList.toggle('hidden', name !== state.view);
        el.classList.toggle('flex', name === state.view);
    });
    renderStepper();
    renderFooter();
    const content = document.getElementById('content');
    if (content) content.scrollTop = 0;
}

function renderStepper() {
    document.querySelectorAll('.stepper-pill').forEach((btn) => {
        const n = Number(btn.dataset.step);
        const active = state.view === STEP_VIEW[n - 1];
        const done = (n === 1 && state.backupDone) || (n === 2 && state.decryptDone);
        btn.classList.toggle('is-active', active);
        btn.classList.toggle('is-done', done && !active);
        btn.classList.toggle('is-locked', !canEnter(n));
        const dot = btn.querySelector('.dot');
        if (dot) dot.textContent = done && !active ? '✓' : String(n);
    });
}

function renderFooter() {
    const back = document.getElementById('btn-back');
    const primary = document.getElementById('btn-primary');
    if (!back || !primary) return;

    if (state.view === 'progress') {
        back.classList.add('hidden');
        primary.textContent = 'Cancel';
        primary.disabled = false;
        primary.className = 'btn btn-danger flex-1';
        return;
    }
    if (state.view === 'done') {
        back.classList.add('hidden');
        primary.textContent = 'Start over';
        primary.disabled = false;
        primary.className = 'btn btn-primary flex-1';
        return;
    }

    primary.className = 'btn btn-primary flex-1';
    back.classList.toggle('hidden', state.step === 1);

    if (state.step === 1) {
        primary.textContent = 'Start backup';
        primary.disabled = !state.device || !state.backupPath;
    } else if (state.step === 2) {
        primary.textContent = 'Decrypt database';
        primary.disabled = !state.dbPath || state.key.length !== 64;
    } else {
        primary.textContent = 'Start organizing';
        primary.disabled = !state.decryptDone || !state.mediaPath || !state.outputPath;
    }
}

async function loadMediaFolders() {
    const box = document.getElementById('media-folders');
    if (!box) return;
    let folders = [];
    try {
        const result = await pywebview.api.get_media_folders();
        folders = result.folders || [];
    } catch (error) {
        console.error('Could not load media folders:', error);
        return;
    }
    box.innerHTML = '';
    folders.forEach((folder) => {
        const label = document.createElement('label');
        label.className = 'flex items-center gap-2 cursor-pointer';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = folder;
        checkbox.checked = true;
        checkbox.className = 'h-4 w-4';
        const span = document.createElement('span');
        span.textContent = folder.replace('WhatsApp ', '');
        label.append(checkbox, span);
        box.appendChild(label);
    });
}

function selectedFolders() {
    return Array.from(document.querySelectorAll('#media-folders input[type=checkbox]'))
        .filter((cb) => cb.checked)
        .map((cb) => cb.value);
}

// ============================================================================
// STATUS
// ============================================================================

function setStatus(message, kind = 'info') {
    const el = document.getElementById('status-strip');
    if (!el) return;
    el.textContent = message;
    el.className = 'status mx-5 mt-3 shrink-0 sm:mx-6 ' + kind;
}

function clearStatus() {
    const el = document.getElementById('status-strip');
    if (el) el.className = 'status mx-5 mt-3 hidden shrink-0 sm:mx-6';
}

// ============================================================================
// NAVIGATION
// ============================================================================

function canEnter(step) {
    if (step === 1) return true;
    if (step === 2) return state.backupDone;
    if (step === 3) return state.backupDone && state.decryptDone;
    return false;
}

function goTo(step) {
    if (state.busy) return;
    if (!canEnter(step)) {
        setStatus(
            step === 2
                ? 'Back up first, or pick an existing backup folder.'
                : 'Decrypt the database before organizing.',
            'warn'
        );
        return;
    }
    state.step = step;
    state.view = STEP_VIEW[step - 1];
    clearStatus();
    if (step === 3) checkSpace();
    render();
}

function goBack() {
    if (state.busy) return;
    if (state.view === 'done') return startOver();
    if (state.step > 1) goTo(state.step - 1);
}

function primaryAction() {
    if (state.view === 'progress') return cancelOp();
    if (state.view === 'done') return startOver();
    if (state.step === 1) return startBackup();
    if (state.step === 2) return startDecrypt();
    return startOrganize();
}

// ============================================================================
// STEP 1: BACKUP
// ============================================================================

async function refreshDevices() {
    const select = document.getElementById('device-select');
    const status = document.getElementById('device-status');
    if (!select || !status) return;

    status.className = 'status warn mt-2';
    status.textContent = 'Looking for your phone…';

    try {
        const result = await pywebview.api.get_devices();
        state.devices = (result && result.devices) || [];
    } catch (error) {
        state.devices = [];
        status.className = 'status err mt-2';
        status.textContent = `Couldn't look for phones: ${error && error.message ? error.message : error}`;
        return;
    }

    select.innerHTML = '<option value="">Choose a device…</option>';
    state.devices.forEach((device) => {
        const option = document.createElement('option');
        option.value = device.id;
        option.textContent = device.label;
        select.appendChild(option);
    });

    if (state.devices.length > 0) {
        status.className = 'status ok mt-2';
        status.textContent = `Found ${state.devices.length} device(s).`;
    } else {
        status.className = 'status err mt-2';
        status.textContent = 'No phone found. Connect it with a USB cable, unlock it, and choose "File transfer", then press ↻.';
    }
    renderFooter();
}

function onDeviceChange() {
    const select = document.getElementById('device-select');
    const device = state.devices.find((d) => d.id === select.value);
    state.device = device ? device.id : '';
    state.backend = device ? device.backend : '';
    renderFooter();
}

async function browseBackupPath() {
    const result = await pywebview.api.pick_folder();
    if (!result.success || !result.path) return;
    state.backupPath = result.path;
    state.mediaPath = `${result.path}/Media`;
    document.getElementById('backup-path').value = result.path;
    const cryptInput = document.getElementById('crypt-db-path');
    if (cryptInput && !cryptInput.value) {
        cryptInput.value = `${result.path}/Databases/msgstore.db.crypt15`;
        state.dbPath = cryptInput.value;
    }
    // A browsed folder counts as a usable backup, so the user may skip ahead.
    state.backupDone = true;
    clearStatus();
    autoFill();
    saveState();
    renderFooter();
}

async function startBackup() {
    beginProgress('Backing up…');
    try {
        const result = await pywebview.api.start_backup(
            state.device,
            state.backend,
            state.backupPath,
            selectedFolders(),
            document.getElementById('skip-existing')?.checked || false
        );
        if (!result.success) throw new Error(result.error || 'Backup failed to start');
        state.backupPath = result.backup_path;
        state.mediaPath = `${result.backup_path}/Media`;
        renderFooter();
    } catch (error) {
        onError('Backup', error.message || String(error));
    }
}

function onBackupComplete() {
    state.busy = false;
    state.backupDone = true;
    state.mediaPath = `${state.backupPath}/Media`;
    const cryptInput = document.getElementById('crypt-db-path');
    if (cryptInput && !cryptInput.value) {
        cryptInput.value = `${state.backupPath}/Databases/msgstore.db.crypt15`;
        state.dbPath = cryptInput.value;
    }
    autoFill();
    saveState();
    state.step = 2;
    state.view = 'decrypt';
    setStatus('Backup complete. Now decrypt the database.', 'ok');
    render();
}

// ============================================================================
// STEP 2: DECRYPT
// ============================================================================

async function browseCryptFile() {
    const result = await pywebview.api.pick_file('database');
    if (!result.success || !result.path) return;
    state.dbPath = result.path;
    document.getElementById('crypt-db-path').value = result.path;
    clearStatus();
    saveState();
    renderFooter();
}

function onKeyInput() {
    state.key = document.getElementById('encryption-key').value.replace(/\s/g, '');
    document.getElementById('key-count').textContent = state.key.length;
    document.getElementById('key-valid').classList.toggle('hidden', state.key.length !== 64);
    renderFooter();
}

async function pasteKey() {
    const textarea = document.getElementById('encryption-key');
    try {
        const text = await navigator.clipboard.readText();
        if (!text) return;
        textarea.value = text.replace(/\s/g, '');
        onKeyInput();
    } catch (error) {
        textarea.focus();
        setStatus('Could not read the clipboard — paste with Ctrl+V.', 'warn');
    }
}

async function startDecrypt() {
    beginProgress('Decrypting database…');
    document.getElementById('prog-file').textContent = 'This can take a minute for large backups.';
    try {
        const result = await pywebview.api.decrypt_database(state.dbPath, state.key);
        if (result.success) {
            state.decryptDone = true;
            state.dbPath = result.decrypted_path;
            state.busy = false;
            autoFill();
            saveState();
            state.step = 3;
            state.view = 'organize';
            setStatus('Database decrypted. Choose a folder and organize.', 'ok');
            render();
            checkSpace();
        } else {
            onError('Decryption', result.error);
        }
    } catch (error) {
        onError('Decryption', error.message || String(error));
    }
}

// ============================================================================
// STEP 3: ORGANIZE
// ============================================================================

async function browseOutputPath() {
    const result = await pywebview.api.pick_folder();
    if (!result.success || !result.path) return;
    state.outputPath = result.path;
    document.getElementById('output-path').value = result.path;
    clearStatus();
    saveState();
    renderFooter();
    checkSpace();
}

async function browseContactsFile() {
    const result = await pywebview.api.pick_file('contacts');
    if (!result.success || !result.path) return;
    state.contactsPath = result.path;
    document.getElementById('contacts-path').value = result.path;
    autoFill();
    saveState();
}

async function checkSpace() {
    const info = document.getElementById('space-info');
    if (!info || !state.mediaPath || !state.outputPath) return;
    const result = await pywebview.api.check_space(state.mediaPath, state.outputPath);
    if (!result.success) {
        info.classList.add('hidden');
        return;
    }
    const needed = formatBytes(result.needed);
    const free = formatBytes(result.free);
    info.classList.remove('hidden');
    info.textContent = result.ok
        ? `Needs about ${needed} · ${free} free`
        : `⚠ Needs about ${needed}, but only ${free} free. Free up space or pick another folder.`;
}

async function startOrganize() {
    beginProgress('Organizing media…');
    try {
        const result = await pywebview.api.start_organization(
            state.dbPath,
            state.mediaPath,
            state.outputPath,
            state.contactsPath || null
        );
        if (!result.success) throw new Error(result.error || 'Organization failed to start');
    } catch (error) {
        onError('Organization', error.message || String(error));
    }
}

async function openOutputFolder() {
    if (!state.outputPath) return;
    const result = await pywebview.api.open_path(state.outputPath);
    if (!result.success) setStatus(result.error || 'Could not open the folder.', 'err');
}

// ============================================================================
// PROGRESS (driven by events pushed from Python)
// ============================================================================

window.__pyEvent = (event) => {
    if (!event || !event.name) return;
    const data = event.data || {};
    switch (event.name) {
        case 'backup:start':
            setProgress(0, data.total);
            break;
        case 'backup:file':
            document.getElementById('prog-file').textContent = data.name || '';
            break;
        case 'backup:progress':
            setProgress(data.current, data.total);
            break;
        case 'backup:log':
            appendLog(data.message);
            break;
        case 'backup:complete':
            onBackupComplete();
            break;
        case 'backup:canceled':
            onCanceled('Backup');
            break;
        case 'backup:error':
            onError('Backup', data.message);
            break;

        case 'organize:progress':
            setProgress(data.current, data.total);
            break;
        case 'organize:log':
            appendLog(data.message);
            break;
        case 'organize:complete':
            onOrganizeComplete();
            break;
        case 'organize:canceled':
            onCanceled('Organization');
            break;
        case 'organize:error':
            onError('Organization', data.message);
            break;
    }
};

function beginProgress(title) {
    state.busy = true;
    state.canceled = false;
    state.opStart = Date.now();
    state.view = 'progress';
    render();
    document.getElementById('prog-title').textContent = title;
    document.getElementById('prog-percent').textContent = '…';
    document.getElementById('prog-file').textContent = '';
    document.getElementById('prog-eta').textContent = '';
    document.getElementById('prog-log').textContent = '';
    document.getElementById('prog-bar').style.width = '0%';
}

function setProgress(current, total) {
    const safeTotal = total || 0;
    const pct = safeTotal > 0 ? Math.max(0, Math.min(100, Math.round((current / safeTotal) * 100))) : 0;
    document.getElementById('prog-percent').textContent = safeTotal > 0 ? `${pct}%` : '…';
    document.getElementById('prog-bar').style.width = `${pct}%`;

    const elapsed = (Date.now() - state.opStart) / 1000;
    const rate = current > 0 ? current / elapsed : 0;
    const remaining = rate > 0 ? (safeTotal - current) / rate : Infinity;
    document.getElementById('prog-eta').textContent =
        remaining >= 5 && remaining < 600 ? `About ${formatDuration(remaining)} remaining` : '';
}

function appendLog(line) {
    const el = document.getElementById('prog-log');
    if (!el || !line) return;
    el.textContent += line + '\n';
    el.scrollTop = el.scrollHeight;
}

function cancelOp() {
    if (state.view !== 'progress') return;
    state.canceled = true;
    appendLog('Canceling…');
    if (state.step === 1) pywebview.api.cancel_backup();
    else if (state.step === 3) pywebview.api.cancel_organization();
}

function onOrganizeComplete() {
    state.busy = false;
    document.getElementById('done-path').textContent = state.outputPath;
    state.view = 'done';
    clearStatus();
    saveState();
    render();
}

function onCanceled(what) {
    state.busy = false;
    state.step = 1;
    state.view = 'backup';
    setStatus(`${what} canceled.`, 'warn');
    render();
}

function onError(what, message) {
    state.busy = false;
    state.step = 1;
    state.view = 'backup';
    setStatus(`${what} failed: ${message}`, 'err');
    render();
}

// ============================================================================
// SHARED
// ============================================================================

function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatDuration(seconds) {
    if (!isFinite(seconds) || seconds < 0) return '';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    const m = Math.floor(seconds / 60);
    return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`;
}

function autoFill() {
    const dbEl = document.getElementById('auto-db-path');
    const mediaEl = document.getElementById('auto-media-path');
    const contactsEl = document.getElementById('auto-contacts-path');
    if (dbEl) {
        dbEl.textContent = state.decryptDone
            ? `Database: ${state.dbPath}`
            : 'Database: waiting for decryption';
    }
    if (mediaEl) {
        mediaEl.textContent = state.backupDone
            ? `Media: ${state.mediaPath}`
            : 'Media: waiting for backup';
    }
    if (contactsEl) {
        contactsEl.textContent = state.contactsPath
            ? `Contacts: ${state.contactsPath}`
            : 'Contacts: none — folders use phone numbers';
    }
    renderFooter();
}

function saveState() {
    localStorage.setItem('whatsappMediaSuiteState', JSON.stringify({
        backupPath: state.backupPath,
        mediaPath: state.mediaPath,
        dbPath: state.dbPath,
        outputPath: state.outputPath,
        contactsPath: state.contactsPath,
        backupDone: state.backupDone,
        decryptDone: state.decryptDone,
    }));
}

function restoreState() {
    const raw = localStorage.getItem('whatsappMediaSuiteState');
    if (!raw) return;
    try {
        const s = JSON.parse(raw);
        Object.assign(state, {
            backupPath: s.backupPath || '',
            mediaPath: s.mediaPath || '',
            dbPath: s.dbPath || '',
            outputPath: s.outputPath || '',
            contactsPath: s.contactsPath || '',
            backupDone: s.backupDone || false,
            decryptDone: s.decryptDone || false,
        });
        const set = (id, value) => {
            const el = document.getElementById(id);
            if (el && value) el.value = value;
        };
        set('backup-path', state.backupPath);
        set('crypt-db-path', state.dbPath);
        set('output-path', state.outputPath);
        set('contacts-path', state.contactsPath);

        state.step = state.decryptDone ? 3 : state.backupDone ? 2 : 1;
        state.view = STEP_VIEW[state.step - 1];
        autoFill();
    } catch (error) {
        console.error('Error restoring state:', error);
    }
}

function startOver() {
    Object.assign(state, {
        step: 1, view: 'backup', busy: false, canceled: false,
        backupPath: '', mediaPath: '', dbPath: '', outputPath: '', contactsPath: '',
        key: '', device: '', backend: '', backupDone: false, decryptDone: false,
    });
    ['backup-path', 'crypt-db-path', 'output-path', 'contacts-path', 'encryption-key']
        .forEach((id) => { const el = document.getElementById(id); if (el) el.value = ''; });
    document.getElementById('key-count').textContent = '0';
    document.getElementById('key-valid').classList.add('hidden');
    document.getElementById('space-info').classList.add('hidden');
    localStorage.removeItem('whatsappMediaSuiteState');
    clearStatus();
    autoFill();
    render();
}

async function exportDiagnostics() {
    const result = await pywebview.api.export_diagnostics();
    setStatus(
        result.success ? `Diagnostics saved to ${result.path}` : `Couldn't export diagnostics: ${result.error}`,
        result.success ? 'info' : 'err'
    );
}
