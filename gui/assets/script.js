// ============================================================================
// DEEPSEEK'S UX LOGIC (MERGED WITH PYWEBVIEW API)
// ============================================================================

// Global state
let currentStep = 1;
let backupPath = '';
let decryptedDBPath = '';
let contactsFilePath = '';
let mediaPath = '';
let selectedDevice = '';
let encryptionKey = '';
let backupCompleted = false;
let decryptionCompleted = false;

// Initialize page
document.addEventListener('DOMContentLoaded', function () {
    updateStepIndicators();
    initializePage();
});

function initializePage() {
    // Setup key length counter
    const encKeyInput = document.getElementById('encryption-key');
    if (encKeyInput) {
        encKeyInput.addEventListener('input', function (e) {
            const key = e.target.value.replace(/\s/g, '');
            encryptionKey = key;
            const lengthEl = document.getElementById('key-length');
            if (lengthEl) lengthEl.textContent = key.length;
            updateDecryptButton();
        });
    }

    // Setup device select handler
    const deviceSelect = document.getElementById('device-select');
    if (deviceSelect) {
        deviceSelect.addEventListener('change', function (e) {
            selectedDevice = e.target.value;
            updateBackupButton();
        });
    }

    // Load any saved state
    loadSavedState();

    // Animate slide-in elements
    animateSlideIn();

    // Auto-refresh devices when on backup page
    if (currentStep === 2) {
        refreshDevices();
    }
}

function animateSlideIn() {
    setTimeout(() => {
        document.querySelectorAll('.slide-in').forEach((el, index) => {
            setTimeout(() => {
                el.style.opacity = '1';
            }, index * 50);
        });
    }, 100);
}

// ============================================================================
// STEP NAVIGATION
// ============================================================================

function showStep(step) {
    // Validate step transitions
    if (step === 2 && !validateStep1()) return;
    if (step === 3 && !validateStep2()) return;
    if (step === 4 && !validateStep3()) return;
    if (step === 5 && !validateStep4()) return;

    // Hide all pages
    document.querySelectorAll('[id^="page-"]').forEach(page => {
        page.classList.add('hidden');
        page.classList.remove('active');
    });

    // Show selected page
    const pageId = `page-${getPageName(step)}`;
    const pageEl = document.getElementById(pageId);
    if (pageEl) {
        pageEl.classList.remove('hidden');
        pageEl.classList.add('active');
    }

    // Update stepper
    currentStep = step;
    updateStepIndicators();

    // Auto-fill paths when showing a step
    setTimeout(autoFillPaths, 100);

    // Animate slide-in elements
    animateSlideIn();

    // Auto-refresh devices when entering backup page
    if (step === 2) {
        setTimeout(refreshDevices, 200);
    }
}

function getPageName(step) {
    switch (step) {
        case 1: return 'welcome';
        case 2: return 'backup';
        case 3: return 'decrypt';
        case 4: return 'contacts';
        case 5: return 'organize';
        default: return 'welcome';
    }
}

function updateStepIndicators() {
    document.querySelectorAll('[data-step]').forEach(stepEl => {
        const stepNum = parseInt(stepEl.getAttribute('data-step'));
        const stepDot = stepEl.querySelector('.w-8');

        stepEl.classList.remove('opacity-100');
        stepEl.classList.add('opacity-50');

        if (stepNum === currentStep) {
            stepEl.classList.remove('opacity-50');
            stepEl.classList.add('opacity-100');
            if (stepDot) {
                stepDot.classList.remove('bg-primary-dark', 'bg-success');
                stepDot.classList.add('bg-primary');
            }
        } else if (stepNum < currentStep) {
            stepEl.classList.remove('opacity-50');
            stepEl.classList.add('opacity-100');
            if (stepDot) {
                stepDot.classList.remove('bg-primary');
                stepDot.classList.add('bg-success');
            }
        }
    });
}

function validateStep1() {
    return true; // Always allow going to backup step
}

function validateStep2() {
    if (!backupCompleted) {
        alert('Please complete the backup step first.');
        return false;
    }
    return true;
}

function validateStep3() {
    if (!decryptionCompleted) {
        alert('Please complete the decryption step first.');
        return false;
    }
    return true;
}

function validateStep4() {
    return true; // Always allow going to organize step
}

// ============================================================================
// FILE BROWSING (PYWEBVIEW API INTEGRATION)
// ============================================================================

async function browseBackupPath() {
    try {
        const result = await pywebview.api.pick_folder();
        if (result.success && result.path) {
            backupPath = result.path;
            const inputEl = document.getElementById('backup-path');
            if (inputEl) inputEl.value = result.path;

            // Check if this is an existing backup (has media folder or database)
            // If so, mark as completed and allow skipping to decrypt
            const skipBtn = document.getElementById('skip-backup-btn');
            if (skipBtn) {
                skipBtn.classList.remove('hidden');
            }

            // Auto-fill decrypt page - database is now at root of backup folder
            const cryptFile = result.path + '/msgstore.db.crypt15';
            const cryptDbInput = document.getElementById('crypt-db-path');
            if (cryptDbInput) cryptDbInput.value = cryptFile;

            // Set media path - media is in Media subfolder
            mediaPath = result.path + '/Media';

            // Mark as completed so user can skip
            backupCompleted = true;

            updateBackupButton();
            saveState();
            autoFillPaths();
        }
    } catch (error) {
        console.error('Folder picker error:', error);
    }
}

async function browseCryptFile() {
    try {
        const result = await pywebview.api.pick_file();
        if (result.success && result.path) {
            const inputEl = document.getElementById('crypt-db-path');
            if (inputEl) inputEl.value = result.path;
            updateDecryptButton();
            saveState();
        }
    } catch (error) {
        console.error('File picker error:', error);
    }
}

async function browseContactsFile() {
    try {
        const result = await pywebview.api.pick_file();
        if (result.success && result.path) {
            contactsFilePath = result.path;
            const inputEl = document.getElementById('contacts-path');
            if (inputEl) inputEl.value = result.path;
            saveState();
        }
    } catch (error) {
        console.error('File picker error:', error);
    }
}

async function browseOutputPath() {
    try {
        const result = await pywebview.api.pick_folder();
        if (result.success && result.path) {
            const inputEl = document.getElementById('output-path');
            if (inputEl) inputEl.value = result.path;
            updateOrganizeButton();
            saveState();
        }
    } catch (error) {
        console.error('Folder picker error:', error);
    }
}

// ============================================================================
// STEP 2: BACKUP (PYWEBVIEW API INTEGRATION)
// ============================================================================

async function refreshDevices() {
    const deviceStatus = document.getElementById('device-status');
    if (!deviceStatus) return;

    deviceStatus.classList.remove('hidden', 'success', 'error', 'warning');
    deviceStatus.textContent = "Scanning for devices...";
    deviceStatus.classList.add('status', 'warning');

    try {
        const result = await pywebview.api.get_devices();
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
            deviceStatus.textContent = `✓ Found ${result.devices.length} device(s)`;
            deviceStatus.classList.remove('warning');
            deviceStatus.classList.add('success');
        } else {
            deviceStatus.textContent = 'No devices found. Check USB connection and MTP mode.';
            deviceStatus.classList.remove('warning');
            deviceStatus.classList.add('warning');
        }
    } catch (error) {
        console.error('get_devices error', error);
        deviceStatus.textContent = `Error: ${error && error.message ? error.message : String(error)}`;
        deviceStatus.classList.remove('warning');
        deviceStatus.classList.add('error');
    }
}

function updateBackupButton() {
    const btn = document.getElementById('backup-btn');
    if (btn) {
        btn.disabled = !selectedDevice || !backupPath;
    }
}

async function startBackup() {
    const btn = document.getElementById('backup-btn');
    const progressContainer = document.getElementById('backup-progress-container');
    const backupText = document.getElementById('backup-text');
    const backupPercentage = document.getElementById('backup-percentage');
    const backupBarFill = document.getElementById('backup-bar-fill');

    if (!btn || !progressContainer) return;

    btn.disabled = true;
    btn.textContent = 'Backing up...';
    progressContainer.classList.remove('hidden');
    if (backupText) backupText.textContent = 'Starting backup...\n';
    if (backupPercentage) backupPercentage.textContent = 'Preparing...';
    if (backupBarFill) {
        // Reset to skeleton state
        backupBarFill.className = 'h-full skeleton transition-all duration-300';
        backupBarFill.style.width = '100%';
    }

    try {
        const result = await pywebview.api.start_backup(selectedDevice, backupPath);

        if (result.success) {
            // Store the backup path for later use
            backupPath = result.backup_path;

            // Auto-fill paths for next steps
            mediaPath = result.backup_path + '/Media';
            const cryptFile = result.backup_path + '/Databases/msgstore.db.crypt15';
            const cryptDbInput = document.getElementById('crypt-db-path');
            if (cryptDbInput) cryptDbInput.value = cryptFile;

            // The Python monitor will call window.backupComplete() when done
        } else {
            if (backupText) backupText.textContent += `\n✗ Error: ${result.error}`;
            btn.disabled = false;
            btn.textContent = 'Start Backup';
        }
    } catch (error) {
        if (backupText) backupText.textContent += `\n✗ Error: ${error.message || String(error)}`;
        btn.disabled = false;
        btn.textContent = 'Start Backup';
    }
}

function cancelBackup() {
    try {
        pywebview.api.cancel_backup();
    } catch (error) {
        console.error('Cancel backup error:', error);
    }
    const container = document.getElementById('backup-progress-container');
    if (container) container.classList.add('hidden');
    const btn = document.getElementById('backup-btn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Start Backup';
    }
}

// Callback from Python for progress updates
window.updateProgress = (message, percentage) => {
    const textEl = document.getElementById('backup-text');
    const barEl = document.getElementById('backup-bar-fill');
    const percentEl = document.getElementById('backup-percentage');

    // Always show log messages
    if (textEl) {
        textEl.textContent += message + '\n';
        textEl.scrollTop = textEl.scrollHeight;
    }

    // If we have a percentage (actual file copying), show it
    if (percentage !== undefined && percentage !== null && percentage > 0) {
        if (percentEl) percentEl.textContent = `${Math.round(percentage)}%`;
        if (barEl) {
            // Switch from skeleton to actual progress gradient
            barEl.classList.remove('skeleton');
            barEl.classList.add('bg-gradient-to-r', 'from-primary', 'to-success', 'flex', 'items-center', 'pl-2', 'text-xs', 'font-semibold', 'text-white');
            barEl.style.width = Math.round(percentage) + '%';
        }
    } else if (percentage === 0 && message.includes('[LOG]')) {
        // During counting phase, show a pulsing animation to indicate activity
        if (barEl && !barEl.classList.contains('bg-gradient-to-r')) {
            barEl.classList.add('skeleton');  // Show skeleton animation during counting
        }
    }
};

// Callback from Python when backup completes
window.backupComplete = () => {
    const progressContainer = document.getElementById('backup-progress-container');
    if (!progressContainer) return;

    backupCompleted = true;

    progressContainer.innerHTML = `
        <div class="text-center p-4">
            <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-600" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                </svg>
            </div>
            <h4 class="font-semibold text-green-700 mb-2">Backup Complete!</h4>
            <p class="text-sm text-text-light mb-4">WhatsApp files have been backed up successfully</p>
            <button class="bg-primary text-white py-2 px-6 rounded text-sm hover:bg-primary-dark" onclick="showStep(3)">
                Continue to Decryption →
            </button>
        </div>
    `;

    saveState();
    autoFillPaths();
};

// Callback from Python when backup is canceled
window.backupCanceled = () => {
    const textEl = document.getElementById('backup-text');
    if (textEl) {
        textEl.textContent += '\n⚠ Backup canceled';
    }
    const btn = document.getElementById('backup-btn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Start Backup';
    }
};

// ============================================================================
// STEP 3: DECRYPT (PYWEBVIEW API INTEGRATION)
// ============================================================================

function updateDecryptButton() {
    const btn = document.getElementById('decrypt-btn');
    const cryptPath = document.getElementById('crypt-db-path')?.value;
    const keyValid = encryptionKey.replace(/\s/g, '').length === 64;
    if (btn) {
        btn.disabled = !cryptPath || !keyValid;
    }
}

async function startDecrypt() {
    const btn = document.getElementById('decrypt-btn');
    const progressContainer = document.getElementById('decrypt-progress-container');
    const decryptText = document.getElementById('decrypt-text');
    const cryptPath = document.getElementById('crypt-db-path')?.value;

    if (!btn || !progressContainer || !cryptPath) return;

    btn.disabled = true;
    progressContainer.classList.remove('hidden');
    if (decryptText) decryptText.textContent = 'Starting decryption...';

    try {
        const result = await pywebview.api.decrypt_database(cryptPath, encryptionKey);

        if (result.success) {
            decryptedDBPath = result.decrypted_path;
            decryptionCompleted = true;

            // Show success UI
            setTimeout(() => {
                progressContainer.innerHTML = `
                    <div class="text-center p-4">
                        <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-600" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <h4 class="font-semibold text-green-700 mb-2">Database Decrypted Successfully!</h4>
                        <p class="text-sm text-text-light mb-4">Your WhatsApp messages are now accessible.</p>
                        <button class="bg-primary text-white py-2 px-6 rounded text-sm hover:bg-primary-dark" onclick="showStep(4)">
                            Continue to Contacts →
                        </button>
                    </div>
                `;
                saveState();
                autoFillPaths();
            }, 500);
        } else {
            if (decryptText) decryptText.textContent = `✗ Decryption failed: ${result.error}`;
            btn.disabled = false;
        }
    } catch (error) {
        if (decryptText) decryptText.textContent = `✗ Error: ${error.message || String(error)}`;
        btn.disabled = false;
    }
}

// ============================================================================
// STEP 5: ORGANIZE (PYWEBVIEW API INTEGRATION)
// ============================================================================

function updateOrganizeButton() {
    const btn = document.getElementById('organize-btn');
    const outputPath = document.getElementById('output-path')?.value;
    if (btn) {
        btn.disabled = !decryptedDBPath || !mediaPath || !outputPath;
    }
}

async function startOrganization() {
    const btn = document.getElementById('organize-btn');
    const progressContainer = document.getElementById('org-progress-container');
    const orgText = document.getElementById('org-text');
    const orgPercentage = document.getElementById('org-percentage');
    const orgBarFill = document.getElementById('org-bar-fill');
    const outputPathValue = document.getElementById('output-path')?.value;

    if (!btn || !progressContainer || !outputPathValue) return;

    btn.disabled = true;
    btn.textContent = 'Organizing...';
    progressContainer.classList.remove('hidden');
    if (orgText) orgText.textContent = 'Starting organization...\n';
    if (orgPercentage) orgPercentage.textContent = 'Preparing...';
    if (orgBarFill) {
        // Reset to skeleton state
        orgBarFill.className = 'h-full skeleton transition-all duration-300';
        orgBarFill.style.width = '100%';
    }

    try {
        const result = await pywebview.api.start_organization(
            decryptedDBPath,
            mediaPath,
            outputPathValue,
            contactsFilePath || null
        );

        if (!result.success) {
            if (orgText) orgText.textContent += `\n✗ Error: ${result.error}`;
            btn.disabled = false;
            btn.textContent = 'Start Organization';
        }
        // If successful, the Python monitor will call window.organizerComplete() when done
    } catch (error) {
        if (orgText) orgText.textContent += `\n✗ Error: ${error.message || String(error)}`;
        btn.disabled = false;
        btn.textContent = 'Start Organization';
    }
}

function cancelOrganization() {
    try {
        pywebview.api.cancel_organization();
    } catch (error) {
        console.error('Cancel organization error:', error);
    }
    const container = document.getElementById('org-progress-container');
    if (container) container.classList.add('hidden');
    const btn = document.getElementById('organize-btn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Start Organization';
    }
}

function openOutputFolder() {
    const outputPath = document.getElementById('output-path')?.value;
    if (outputPath) {
        // In pywebview this would open the folder
        alert(`Opening folder: ${outputPath}`);
    }
}

// Callback from Python for organization progress
window.updateOrganizerProgress = (message, percentage) => {
    const textEl = document.getElementById('org-text');
    if (textEl) {
        textEl.textContent += message + '\n';
        textEl.scrollTop = textEl.scrollHeight;
    }
    if (percentage !== undefined && percentage !== null && percentage > 0) {
        const percentEl = document.getElementById('org-percentage');
        const barEl = document.getElementById('org-bar-fill');
        if (percentEl) percentEl.textContent = `${Math.round(percentage)}%`;
        if (barEl) {
            // Switch from skeleton to actual progress
            barEl.classList.remove('skeleton');
            barEl.classList.add('bg-gradient-to-r', 'from-primary', 'to-success', 'flex', 'items-center', 'pl-2', 'text-xs', 'font-semibold', 'text-white');
            barEl.style.width = Math.round(percentage) + '%';
        }
    }
};

// Callback from Python when organization completes
window.organizerComplete = () => {
    const progressContainer = document.getElementById('org-progress-container');
    const outputPath = document.getElementById('output-path')?.value;
    if (!progressContainer) return;

    progressContainer.innerHTML = `
        <div class="text-center p-4">
            <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-green-600" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                </svg>
            </div>
            <h4 class="font-semibold text-green-700 mb-2">Media Organized Successfully!</h4>
            <p class="text-sm text-text-light mb-4">Files saved to: ${outputPath}</p>
            <div class="flex gap-2">
                <button class="flex-1 bg-primary text-white py-2 px-4 rounded text-sm hover:bg-primary-dark" onclick="showStep(1)">
                    Start Over
                </button>
                <button class="flex-1 bg-card text-primary border border-primary py-2 px-4 rounded text-sm hover:bg-[#f0f5f4]" onclick="openOutputFolder()">
                    Open Folder
                </button>
            </div>
        </div>
    `;

    saveState();
};

// Callback from Python when organization is canceled
window.organizerCanceled = () => {
    const textEl = document.getElementById('org-text');
    if (textEl) {
        textEl.textContent += '\n⚠ Organization canceled';
    }
    const btn = document.getElementById('organize-btn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Start Organization';
    }
};

// ============================================================================
// AUTO-FILL PATHS
// ============================================================================

function autoFillPaths() {
    // Page 3 (Decrypt) - auto-fill if backup completed
    if (backupCompleted && backupPath) {
        const cryptPath = `${backupPath}/Databases/msgstore.db.crypt15`;
        const cryptInput = document.getElementById('crypt-db-path');
        if (cryptInput && !cryptInput.value) {
            cryptInput.value = cryptPath;
        }
        const noteEl = document.getElementById('db-auto-note');
        if (noteEl) noteEl.textContent = "Auto-filled from backup";
    }

    // Page 5 (Organize) - auto-fill all paths
    if (backupPath) {
        // Output path
        const outputInput = document.getElementById('output-path');
        if (outputInput && !outputInput.value) {
            outputInput.value = `${backupPath}/Organized_Media`;
        }

        // Auto-fill source paths display
        const mediaPathEl = document.getElementById('auto-media-path');
        const dbPathEl = document.getElementById('auto-db-path');
        const contactsPathEl = document.getElementById('auto-contacts-path');

        if (backupCompleted && mediaPathEl) {
            mediaPathEl.textContent = `Media: ${mediaPath || backupPath + '/Media'}`;
        }

        if (decryptedDBPath && dbPathEl) {
            dbPathEl.textContent = `Database: ${decryptedDBPath}`;
        } else if (decryptionCompleted && dbPathEl) {
            dbPathEl.textContent = `Database: ${backupPath}/msgstore.db`;
        }

        if (contactsFilePath && contactsPathEl) {
            contactsPathEl.textContent = `Contacts: ${contactsFilePath}`;
        } else if (contactsPathEl) {
            contactsPathEl.textContent = "Contacts: None (folders will use phone numbers)";
        }

        // Update organize button state
        updateOrganizeButton();
    }
}

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

function saveState() {
    const state = {
        backupPath: backupPath,
        backupCompleted: backupCompleted,
        decryptedDBPath: decryptedDBPath,
        decryptionCompleted: decryptionCompleted,
        contactsFilePath: contactsFilePath,
        mediaPath: mediaPath,
        currentStep: currentStep
    };
    localStorage.setItem('whatsappMediaSuiteState', JSON.stringify(state));
}

function loadSavedState() {
    const savedState = localStorage.getItem('whatsappMediaSuiteState');
    if (savedState) {
        try {
            const state = JSON.parse(savedState);
            backupPath = state.backupPath || '';
            backupCompleted = state.backupCompleted || false;
            decryptedDBPath = state.decryptedDBPath || '';
            decryptionCompleted = state.decryptionCompleted || false;
            contactsFilePath = state.contactsFilePath || '';
            mediaPath = state.mediaPath || '';
            currentStep = state.currentStep || 1;

            // Update UI with saved state
            const backupInput = document.getElementById('backup-path');
            if (backupPath && backupInput) {
                backupInput.value = backupPath;
            }
            const contactsInput = document.getElementById('contacts-path');
            if (contactsFilePath && contactsInput) {
                contactsInput.value = contactsFilePath;
            }

            // Show appropriate step
            showStep(currentStep);
        } catch (error) {
            console.error('Error loading saved state:', error);
        }
    }
}
