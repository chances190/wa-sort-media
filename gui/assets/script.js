// Global state
let selectedDevice = '';
let selectedPath = '';
let dbPath = '';
let mediaPath = '';
let outputPath = '';
let currentStep = 1;

//=== WORKFLOW STEPPER ===
function showStep(step) {
    currentStep = step;

    // Hide all pages
    document.querySelectorAll('#page-backup, #page-contacts, #page-organizer').forEach(page => {
        page.classList.add('hidden');
        page.classList.remove('flex');
    });

    // Update stepper opacity
    document.querySelectorAll('[data-step]').forEach(stepEl => {
        const stepNum = parseInt(stepEl.dataset.step);
        if (stepNum === step) {
            stepEl.classList.remove('opacity-50');
            stepEl.classList.add('opacity-100');
        } else {
            stepEl.classList.remove('opacity-100');
            stepEl.classList.add('opacity-50');
        }
    });

    // Show correct page
    const pageId = step === 1 ? 'page-backup' : step === 2 ? 'page-contacts' : 'page-organizer';
    const page = document.getElementById(pageId);
    page.classList.remove('hidden');
    page.classList.add('flex', 'flex-col', 'flex-1');

    // Animate step elements
    setTimeout(() => {
        page.querySelectorAll('.slide-in').forEach((el, index) => {
            el.style.animationDelay = `${0.05 + (index * 0.05)}s`;
            el.classList.remove('opacity-0');
            el.classList.add('opacity-100');
        });
    }, 50);
}
async function refreshDevices() {
    const status = document.getElementById('device-status');
    if (!status) return;
    status.textContent = 'Searching for devices...';
    status.className = 'p-3 rounded text-sm mt-2 leading-normal bg-status-info text-[#0c5460]';
    status.classList.remove('hidden');

    try {
        const result = await window.pywebview.api.get_devices();
        if (result && result.success && Array.isArray(result.devices) && result.devices.length > 0) {
            const select = document.getElementById('device-select');
            if (select) {
                select.innerHTML = '<option value="">Choose a device...</option>';
                result.devices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device;
                    option.textContent = device;
                    select.appendChild(option);
                });
            }
            status.textContent = `✓ Found ${result.devices.length} device(s)`;
            status.className = 'p-3 rounded text-sm mt-2 leading-normal bg-status-success text-[#155724]';
        } else {
            status.textContent = 'No devices found. Check USB connection and MTP mode.';
            status.className = 'p-3 rounded text-sm mt-2 leading-normal bg-status-warning text-[#664d03]';
        }
    } catch (error) {
        console.error('get_devices error', error);
        status.textContent = `Error: ${error && error.message ? error.message : String(error)}`;
        status.className = 'p-3 rounded text-sm mt-2 leading-normal bg-status-error text-[#721c24]';
    }
}

document.getElementById('device-select').addEventListener('change', (e) => {
    selectedDevice = e.target.value;
    updateStartButton();
});

async function browsePath() {
    try {
        const result = await pywebview.api.pick_folder();
        if (result.success && result.path) {
            selectedPath = result.path;
            document.getElementById('backup-path').value = result.path;
            updateStartButton();
        }
    } catch (error) {
        console.error('Folder picker error:', error);
    }
}

function updateStartButton() {
    const btn = document.getElementById('start-btn');
    btn.disabled = !selectedDevice || !selectedPath;
}

async function startBackup() {
    const result = await pywebview.api.start_backup(selectedDevice, selectedPath);
    if (result.success) {
        document.getElementById('progress-container').classList.add('active');
        document.getElementById('progress-text').textContent = 'Starting backup...\n';
        document.getElementById('start-btn').disabled = true;
    } else {
        alert(`Error: ${result.error}`);
    }
}

function updateProgress(message, percentage) {
    const textEl = document.getElementById('progress-text');
    textEl.textContent += message + '\n';
    textEl.scrollTop = textEl.scrollHeight;

    // Update progress bar
    const fillEl = document.getElementById('progress-bar-fill');
    const percentEl = document.getElementById('progress-percentage');

    const pct = Math.min(Math.max(percentage, 0), 100);
    fillEl.style.width = pct + '%';
    percentEl.textContent = Math.round(pct) + '%';
}

function backupComplete() {
    document.getElementById('progress-container').classList.remove('active');
    document.getElementById('start-btn').disabled = false;
    alert('✓ Backup completed successfully!\n\nClick Continue to proceed with contact backup.');
    // Auto-advance to next step
    setTimeout(() => showStep(2), 500);
}

function backupCanceled() {
    document.getElementById('progress-container').classList.add('hidden');
    alert('Backup canceled');
}

async function cancelBackup() {
    await pywebview.api.cancel_backup();
}

//=== ORGANIZER PAGE (Step 3) ===
async function browseDbFile() {
    try {
        const result = await pywebview.api.pick_file();
        if (result.success && result.path) {
            dbPath = result.path;
            document.getElementById('db-path').value = result.path;
            updateOrganizeButton();
        }
    } catch (error) {
        console.error('File picker error:', error);
    }
}

async function browseMediaPath() {
    try {
        const result = await pywebview.api.pick_folder();
        if (result.success && result.path) {
            mediaPath = result.path;
            document.getElementById('media-path').value = result.path;
            updateOrganizeButton();
        }
    } catch (error) {
        console.error('Folder picker error:', error);
    }
}

async function browseOutputPath() {
    try {
        const result = await pywebview.api.pick_folder();
        if (result.success && result.path) {
            outputPath = result.path;
            document.getElementById('output-path').value = result.path;
            updateOrganizeButton();
        }
    } catch (error) {
        console.error('Folder picker error:', error);
    }
}

function updateOrganizeButton() {
    const btn = document.getElementById('organize-btn');
    btn.disabled = !dbPath || !mediaPath || !outputPath;
}

async function startOrganization() {
    const progress = document.getElementById('org-progress-container');
    progress.classList.add('active');
    document.getElementById('org-text').textContent = 'Starting organization...\n';
    document.getElementById('organize-btn').disabled = true;

    try {
        const result = await pywebview.api.start_organization(dbPath, mediaPath, outputPath);
        if (!result.success) {
            alert('Error: ' + result.error);
            progress.classList.add('hidden');
            document.getElementById('organize-btn').disabled = false;
        }
    } catch (error) {
        alert('Error: ' + error.message);
        progress.classList.add('hidden');
    }
}

function updateOrganizerProgress(message, percentage) {
    const textEl = document.getElementById('org-text');
    textEl.textContent += message + '\n';
    textEl.scrollTop = textEl.scrollHeight;

    // Update progress bar
    const fillEl = document.getElementById('org-bar-fill');
    const percentEl = document.getElementById('org-percentage');

    const pct = Math.min(Math.max(percentage, 0), 100);
    fillEl.style.width = pct + '%';
    fillEl.textContent = Math.round(pct) + '%';
    percentEl.textContent = Math.round(pct) + '% Complete';
}

function organizerComplete() {
    document.getElementById('org-progress-container').classList.remove('active');
    document.getElementById('organize-btn').disabled = false;
    alert('✓ Organization completed successfully!\n\nYour media is now organized by contact.');
}

function organizerCanceled() {
    document.getElementById('org-progress-container').classList.add('hidden');
    alert('Organization canceled');
}

async function cancelOrganization() {
    await pywebview.api.cancel_organization();
}

// Initialize on load
window.addEventListener('pywebviewready', () => {
    refreshDevices();
});
