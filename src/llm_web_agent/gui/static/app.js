/**
 * LLM Web Agent - GUI Application
 * 
 * Client-side JavaScript for:
 * - View navigation (Landing, Guided, Execution)
 * - Recordings management
 * - SSE connection for real-time updates
 * - Control panel handlers
 * - Settings persistence
 * - Dual engine mode (Instructions vs Goal)
 * - Step table and progress tracking
 * - Screenshot updates
 * - Toast notifications
 */

// ============================================
// State Management
// ============================================
const AppState = {
    status: 'idle',
    currentRun: null,
    eventSource: null,
    screenshotInterval: null,
    startTime: null,
    durationInterval: null,
    engineMode: 'instructions',  // 'instructions' or 'goal'
    settings: null,
    steps: [],
    currentView: 'landing',  // 'landing', 'guided', 'execution'
    recordings: [],
};

// ============================================
// View Navigation
// ============================================
function showView(viewName) {
    AppState.currentView = viewName;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const view = document.getElementById(`${viewName}View`);
    if (view) view.classList.add('active');

    // Load data when switching to guided view
    if (viewName === 'guided') {
        loadRecordings();
    }
}

// ============================================
// Recordings Manager
// ============================================
async function loadRecordings() {
    try {
        const response = await fetch('/api/recordings');
        if (!response.ok) {
            AppState.recordings = [];
        } else {
            const data = await response.json();
            AppState.recordings = data.recordings || [];
        }
        renderRecordings();
    } catch (e) {
        console.error('Failed to load recordings:', e);
        AppState.recordings = [];
        renderRecordings();
    }
}

function renderRecordings() {
    const emptyState = document.getElementById('emptyState');
    const table = document.getElementById('recordingsTable');
    const tbody = document.getElementById('recordingsTableBody');
    const count = document.getElementById('recordingsCount');

    if (!tbody) return;

    count.textContent = `${AppState.recordings.length} recording${AppState.recordings.length !== 1 ? 's' : ''}`;

    if (AppState.recordings.length === 0) {
        emptyState.style.display = 'flex';
        table.style.display = 'none';
        return;
    }

    emptyState.style.display = 'none';
    table.style.display = 'table';

    tbody.innerHTML = AppState.recordings.map(rec => `
        <tr data-id="${rec.id}">
            <td class="recording-name">${escapeHtml(rec.name)}</td>
            <td class="recording-url" title="${escapeHtml(rec.start_url)}">${escapeHtml(rec.start_url || '-')}</td>
            <td>${rec.actions?.length || 0}</td>
            <td class="recording-date">${formatDate(rec.created_at)}</td>
            <td>
                <div class="recording-actions">
                    <button class="btn btn-success btn-sm" onclick="runRecording('${rec.id}')" title="Run">▶</button>
                    <button class="btn btn-primary btn-sm" onclick="downloadScript('${rec.id}')" title="Download Script" style="margin-left: 4px;">⬇️</button>
                    <button class="btn btn-secondary btn-sm" onclick="editRecording('${rec.id}')" title="Edit">✎</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteRecording('${rec.id}')" title="Delete">✕</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function runRecording(id) {
    const rec = AppState.recordings.find(r => r.id === id);
    if (!rec) return;

    showToast(`Running "${rec.name}"...`, 'info');

    try {
        const response = await fetch(`/ api / recordings / ${id} / run`, { method: 'POST' });
        if (response.ok) {
            showToast('Recording started!', 'success');
        } else {
            const err = await response.json();
            showToast(`Failed: ${err.detail || 'Unknown error'}`, 'error');
        }
    } catch (e) {
        showToast('Failed to run recording', 'error');
    }
}

async function downloadScript(id) {
    const rec = AppState.recordings.find(r => r.id === id);
    if (!rec) return;

    try {
        const response = await fetch(`/ api / recordings / ${id} / script`);
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = response.headers.get('Content-Disposition') ?
                response.headers.get('Content-Disposition').split('filename=')[1].replace(/"/g, '') :
                `${rec.name.replace(/\s+/g, '_')}.py`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            showToast('Download started', 'success');
        } else {
            showToast('Failed to generate script', 'error');
        }
    } catch (e) {
        showToast('Failed to download script', 'error');
    }
}

async function deleteRecording(id) {
    const rec = AppState.recordings.find(r => r.id === id);
    if (!rec) return;

    if (!confirm(`Delete "${rec.name}" ? `)) return;

    try {
        const response = await fetch(`/ api / recordings / ${id}`, { method: 'DELETE' });
        if (response.ok) {
            showToast('Recording deleted', 'success');
            loadRecordings();
        } else {
            showToast('Failed to delete recording', 'error');
        }
    } catch (e) {
        showToast('Failed to delete recording', 'error');
    }
}

function editRecording(id) {
    const rec = AppState.recordings.find(r => r.id === id);
    if (!rec) return;

    const newName = prompt('Rename recording:', rec.name);
    if (!newName || newName === rec.name) return;

    fetch(`/ api / recordings / ${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName })
    }).then(resp => {
        if (resp.ok) {
            showToast('Recording renamed', 'success');
            loadRecordings();
        } else {
            showToast('Failed to rename', 'error');
        }
    }).catch(() => showToast('Failed to rename', 'error'));
}

async function openRecordingsFolder() {
    try {
        const response = await fetch('/api/recordings/open-folder', { method: 'POST' });
        if (response.ok) {
            showToast('Folder opened', 'success');
        } else {
            showToast('Failed to open folder', 'error');
        }
    } catch (e) {
        showToast('Failed to open folder', 'error');
    }
}

// ============================================
// New Recording Modal
// ============================================
function showNewRecordingModal() {
    const modal = document.getElementById('newRecordingModal');
    if (modal) modal.classList.add('show');
}

function hideNewRecordingModal() {
    const modal = document.getElementById('newRecordingModal');
    if (modal) modal.classList.remove('show');
    document.getElementById('recordingName').value = '';
    document.getElementById('recordingUrl').value = '';
}

async function startNewRecording() {
    const name = document.getElementById('recordingName').value.trim() || 'Untitled Recording';
    const url = document.getElementById('recordingUrl').value.trim();

    if (!url) {
        showToast('Please enter a starting URL', 'warning');
        return;
    }

    hideNewRecordingModal();

    try {
        const response = await fetch('/api/recordings/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, url })
        });

        if (response.ok) {
            showToast('Recording started in browser...', 'info');
        } else {
            const err = await response.json();
            showToast(`Failed: ${err.detail || 'Unknown error'}`, 'error');
        }
    } catch (e) {
        showToast('Failed to start recording', 'error');
    }
}

// ============================================
// DOM Elements
// ============================================
const elements = {
    // Status
    statusBadge: document.getElementById('statusBadge'),
    runId: document.getElementById('runId'),
    progress: document.getElementById('progress'),
    duration: document.getElementById('duration'),
    progressBarContainer: document.getElementById('progressBarContainer'),
    progressBar: document.getElementById('progressBar'),

    // Controls
    startBtn: document.getElementById('startBtn'),
    pauseBtn: document.getElementById('pauseBtn'),
    stopBtn: document.getElementById('stopBtn'),

    // Mode Toggle
    instructionsModeBtn: document.getElementById('instructionsModeBtn'),
    goalModeBtn: document.getElementById('goalModeBtn'),
    instructionsModeInfo: document.getElementById('instructionsModeInfo'),
    goalModeInfo: document.getElementById('goalModeInfo'),
    instructionsInputGroup: document.getElementById('instructionsInputGroup'),
    goalInputGroup: document.getElementById('goalInputGroup'),
    instructionCount: document.getElementById('instructionCount'),

    // Task Input
    taskInput: document.getElementById('taskInput'),
    goalInput: document.getElementById('goalInput'),
    startUrl: document.getElementById('startUrl'),
    visibleBrowser: document.getElementById('visibleBrowser'),
    useWebsocket: document.getElementById('useWebsocket'),
    generateReport: document.getElementById('generateReport'),
    instructionFile: document.getElementById('instructionFile'),
    localFileInput: document.getElementById('localFileInput'),

    // Preview
    browserFrame: document.getElementById('browserFrame'),
    screenshotImg: document.getElementById('screenshotImg'),
    refreshScreenshot: document.getElementById('refreshScreenshot'),

    // Logs
    logsContainer: document.getElementById('logsContainer'),
    stepsTableBody: document.getElementById('stepsTableBody'),
    logFilter: document.getElementById('logFilter'),
    clearLogs: document.getElementById('clearLogs'),

    // History
    historyList: document.getElementById('historyList'),
    refreshHistory: document.getElementById('refreshHistory'),

    // Settings Modal
    settingsBtn: document.getElementById('settingsBtn'),
    settingsModal: document.getElementById('settingsModal'),
    closeSettings: document.getElementById('closeSettings'),
    cancelSettings: document.getElementById('cancelSettings'),
    saveSettings: document.getElementById('saveSettings'),
    settingsStatus: document.getElementById('settingsStatus'),
    settingsSavedBadge: document.getElementById('settingsSavedBadge'),

    // Settings Fields
    llmModel: document.getElementById('llmModel'),
    apiUrl: document.getElementById('apiUrl'),
    browserChannel: document.getElementById('browserChannel'),
    timeout: document.getElementById('timeout'),
    maxSteps: document.getElementById('maxSteps'),
    retryAttempts: document.getElementById('retryAttempts'),
    settingsWebsocket: document.getElementById('settingsWebsocket'),
    settingsVisible: document.getElementById('settingsVisible'),
    settingsReport: document.getElementById('settingsReport'),
    reportDir: document.getElementById('reportDir'),
    reportJson: document.getElementById('reportJson'),
    reportMd: document.getElementById('reportMd'),
    reportHtml: document.getElementById('reportHtml'),

    // Help Modal
    helpBtn: document.getElementById('helpBtn'),
    helpModal: document.getElementById('helpModal'),
    closeHelp: document.getElementById('closeHelp'),

    // Toast
    toastContainer: document.getElementById('toastContainer'),
};

// ============================================
// Utility Functions
// ============================================
function formatTime(date) {
    return date.toLocaleTimeString('en-US', { hour12: false });
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return `${mins}m ${secs}s`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }
}

// ============================================
// Toast Notifications
// ============================================
function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast toast - ${type}`;

    const icons = {
        info: 'ℹ️',
        success: '✓',
        warning: '⚠️',
        error: '✗'
    };

    toast.innerHTML = `
    < span class= "toast-icon" > ${icons[type]}</span >
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;

    elements.toastContainer.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Auto remove
    if (duration > 0) {
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

// ============================================
// SSE Connection
// ============================================
function connectSSE() {
    if (AppState.eventSource) {
        AppState.eventSource.close();
    }

    AppState.eventSource = new EventSource('/api/agent/stream');

    AppState.eventSource.onopen = () => {
        console.log('SSE connected');
        addLog('Connected to agent', 'info');
    };

    AppState.eventSource.onerror = (e) => {
        console.error('SSE error', e);
        setTimeout(connectSSE, 3000);
    };

    // Handle state changes
    AppState.eventSource.addEventListener('state', (e) => {
        const data = JSON.parse(e.data);
        updateStatus(data.status);
    });

    // Handle step updates
    AppState.eventSource.addEventListener('step', (e) => {
        const data = JSON.parse(e.data);
        const step = data.step;

        addLog(`Step ${step.step_number}: ${step.action} - ${step.message}`,
            step.status === 'success' ? 'success' :
                step.status === 'failed' ? 'error' : 'info');

        updateStepTable(step);
        updateProgress(step.step_number);
    });

    // Handle run started
    AppState.eventSource.addEventListener('run_started', (e) => {
        const data = JSON.parse(e.data);
        AppState.currentRun = data;
        elements.runId.textContent = data.run_id;
        AppState.steps = [];
        clearStepTable();
        addLog(`Run started: ${data.task.substring(0, 50)}...`, 'info');
        showToast('Task started', 'success');
    });

    // Handle run completed
    AppState.eventSource.addEventListener('run_completed', (e) => {
        const data = JSON.parse(e.data);

        if (data.success) {
            addLog('Run completed successfully', 'success');
            showToast('Task completed!', 'success');
        } else {
            addLog(`Run failed: ${data.error || 'Unknown error'}`, 'error');
            showToast(`Task failed: ${data.error}`, 'error');
        }

        stopDurationTimer();
        stopScreenshotPolling();
        loadHistory();
    });
}

// ============================================
// Status Updates
// ============================================
function updateStatus(status) {
    AppState.status = status;
    const statusText = elements.statusBadge.querySelector('.status-text');
    statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);

    // Update badge class
    elements.statusBadge.className = 'status-badge';
    elements.statusBadge.classList.add(`status - ${status}`);

    // Update button states
    const isRunning = ['running', 'starting', 'paused', 'stopping'].includes(status);
    const isPaused = status === 'paused';
    const canStart = status === 'idle' || status === 'stopped' || status === 'error';

    elements.startBtn.disabled = !canStart;
    elements.pauseBtn.disabled = !isRunning || isPaused;
    elements.stopBtn.disabled = !isRunning;

    if (isPaused) {
        elements.pauseBtn.innerHTML = `
    < svg viewBox = "0 0 24 24" fill = "currentColor" >
    <polygon points="5 3 19 12 5 21 5 3" />
            </svg >
        Resume
            `;
    } else {
        elements.pauseBtn.innerHTML = `
        < svg viewBox = "0 0 24 24" fill = "currentColor" >
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
            </svg >
        Pause
            `;
    }

    // Show/hide progress bar
    elements.progressBarContainer.style.display = isRunning ? 'block' : 'none';
}

// ============================================
// Step Table
// ============================================
function updateStepTable(step) {
    // Find or create row
    let row = document.querySelector(`#stepsTableBody tr[data - step= "${step.step_number}"]`);

    if (!row) {
        row = document.createElement('tr');
        row.dataset.step = step.step_number;
        elements.stepsTableBody.appendChild(row);
    }

    const statusIcon = {
        success: '✓',
        failed: '✗',
        running: '⏳',
        pending: '○'
    }[step.status] || '○';

    const statusClass = `step - ${step.status}`;
    const duration = step.duration_ms ? `${(step.duration_ms / 1000).toFixed(1)} s` : '-';

    row.innerHTML = `
    < td > ${step.step_number}</td >
        <td>${step.action}</td>
        <td title="${step.message}">${step.message.substring(0, 30)}${step.message.length > 30 ? '...' : ''}</td>
        <td class="${statusClass}">${statusIcon}</td>
        <td>${duration}</td>
`;

    // Scroll to bottom
    elements.stepsTableBody.parentElement.scrollTop = elements.stepsTableBody.parentElement.scrollHeight;
}

function clearStepTable() {
    elements.stepsTableBody.innerHTML = '';
}

function updateProgress(current, total = null) {
    if (total) {
        elements.progress.textContent = `${current} / ${total}`;
        const percent = (current / total) * 100;
        elements.progressBar.style.width = `${percent}%`;
    } else {
        elements.progress.textContent = `${current} / ?`;
    }
}

// ============================================
// Control Panel
// ============================================
async function startTask() {
    const mode = AppState.engineMode;
    let task;

    if (mode === 'instructions') {
        task = elements.taskInput.value.trim();
    } else {
        task = elements.goalInput.value.trim();
    }

    if (!task) {
        showToast('Please enter a task', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/agent/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                task: task,
                url: elements.startUrl.value.trim() || null,
                visible: elements.visibleBrowser.checked,
                use_websocket: elements.useWebsocket.checked,
                model: elements.llmModel.value,
                generate_report: elements.generateReport.checked,
                report_dir: elements.reportDir?.value || './reports',
                engine_mode: mode,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start task');
        }

        AppState.startTime = Date.now();
        startDurationTimer();
        startScreenshotPolling();

    } catch (e) {
        console.error('Failed to start task:', e);
        showToast(e.message, 'error');
    }
}

async function stopTask() {
    try {
        const response = await fetch('/api/agent/stop', { method: 'POST' });
        const data = await response.json();
        addLog(`Stop requested: ${data.message}`, 'warning');
    } catch (e) {
        console.error('Failed to stop task:', e);
        showToast('Failed to stop task', 'error');
    }
}

async function togglePause() {
    const isPaused = AppState.status === 'paused';
    const endpoint = isPaused ? '/api/agent/resume' : '/api/agent/pause';

    try {
        await fetch(endpoint, { method: 'POST' });
    } catch (e) {
        console.error('Failed to toggle pause:', e);
    }
}

// ============================================
// Mode Toggle
// ============================================
function setMode(mode) {
    AppState.engineMode = mode;

    // Update buttons
    elements.instructionsModeBtn.classList.toggle('active', mode === 'instructions');
    elements.goalModeBtn.classList.toggle('active', mode === 'goal');

    // Update info text
    elements.instructionsModeInfo.style.display = mode === 'instructions' ? 'block' : 'none';
    elements.goalModeInfo.style.display = mode === 'goal' ? 'block' : 'none';

    // Update input visibility
    elements.instructionsInputGroup.style.display = mode === 'instructions' ? 'block' : 'none';
    elements.goalInputGroup.style.display = mode === 'goal' ? 'block' : 'none';

    // Save preference
    saveSettingsPartial({ engine_mode: mode });
}

function updateInstructionCount() {
    const text = elements.taskInput.value;
    const lines = text.split('\n').filter(line => line.trim() && !line.trim().startsWith('#'));
    elements.instructionCount.textContent = lines.length;
}

// ============================================
// Screenshot Handling
// ============================================
function startScreenshotPolling() {
    stopScreenshotPolling();
    AppState.screenshotInterval = setInterval(fetchScreenshot, 1000);
    fetchScreenshot();
}

function stopScreenshotPolling() {
    if (AppState.screenshotInterval) {
        clearInterval(AppState.screenshotInterval);
        AppState.screenshotInterval = null;
    }
}

async function fetchScreenshot() {
    try {
        const response = await fetch('/api/agent/screenshot');
        if (response.ok) {
            const data = await response.json();
            if (data.screenshot) {
                elements.screenshotImg.src = `data:image/png;base64,${data.screenshot}`;
                elements.screenshotImg.style.display = 'block';
                elements.browserFrame.querySelector('.browser-placeholder').style.display = 'none';
            }
        }
    } catch (e) {
        // Ignore errors during polling
    }
}

// ============================================
// Duration Timer
// ============================================
function startDurationTimer() {
    stopDurationTimer();
    AppState.durationInterval = setInterval(() => {
        if (AppState.startTime) {
            const elapsed = (Date.now() - AppState.startTime) / 1000;
            elements.duration.textContent = formatDuration(elapsed);
        }
    }, 1000);
}

function stopDurationTimer() {
    if (AppState.durationInterval) {
        clearInterval(AppState.durationInterval);
        AppState.durationInterval = null;
    }
}

// ============================================
// Logs
// ============================================
function addLog(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;

    const icons = { info: 'ℹ️', success: '✓', warning: '⚠️', error: '✗', step: '📍' };

    entry.innerHTML = `
        <span class="log-time">${formatTime(new Date())}</span>
        <span class="log-icon">${icons[type] || 'ℹ️'}</span>
        <span class="log-message">${message}</span>
    `;

    elements.logsContainer.appendChild(entry);
    elements.logsContainer.scrollTop = elements.logsContainer.scrollHeight;
}

function clearLogs() {
    elements.logsContainer.innerHTML = '';
    addLog('Logs cleared', 'info');
}

// ============================================
// History
// ============================================
async function loadHistory() {
    // historyList may not exist if right sidebar is removed
    if (!elements.historyList) return;

    try {
        const response = await fetch('/api/runs/');
        if (!response.ok) return;

        const data = await response.json();
        const runs = data.runs || [];

        if (runs.length === 0) {
            elements.historyList.innerHTML = '<div class="history-empty"><p>No runs yet</p></div>';
            return;
        }

        elements.historyList.innerHTML = runs.slice(0, 10).map(run => `
            <div class="history-item ${run.status}">
                <div class="history-header">
                    <span class="history-id">${run.run_id}</span>
                    <span class="history-status ${run.status}">${run.status === 'stopped' ? '✓' : '✗'}</span>
                </div>
                <div class="history-task">${run.task.substring(0, 50)}${run.task.length > 50 ? '...' : ''}</div>
                <div class="history-meta">
                    <span>${new Date(run.started_at).toLocaleTimeString()}</span>
                </div>
            </div>
        `).join('');

    } catch (e) {
        console.error('Failed to load history:', e);
    }
}

// ============================================
// Settings Persistence
// ============================================
async function loadGUISettings() {
    try {
        const response = await fetch('/api/config/gui');
        if (!response.ok) return;

        const settings = await response.json();
        AppState.settings = settings;

        // Apply settings to form
        if (settings.engine_mode) setMode(settings.engine_mode);
        if (settings.model) elements.llmModel.value = settings.model;
        if (settings.api_url) elements.apiUrl.value = settings.api_url;
        if (settings.use_websocket !== undefined) {
            elements.useWebsocket.checked = settings.use_websocket;
            if (elements.settingsWebsocket) elements.settingsWebsocket.checked = settings.use_websocket;
        }
        if (settings.visible_browser !== undefined) {
            elements.visibleBrowser.checked = settings.visible_browser;
            if (elements.settingsVisible) elements.settingsVisible.checked = settings.visible_browser;
        }
        if (settings.browser_channel !== undefined && elements.browserChannel) {
            elements.browserChannel.value = settings.browser_channel || '';
        }
        if (settings.max_steps && elements.maxSteps) elements.maxSteps.value = settings.max_steps;
        if (settings.step_timeout_ms && elements.timeout) elements.timeout.value = settings.step_timeout_ms;
        if (settings.retry_attempts && elements.retryAttempts) elements.retryAttempts.value = settings.retry_attempts;
        if (settings.generate_report !== undefined && elements.generateReport) {
            elements.generateReport.checked = settings.generate_report;
            if (elements.settingsReport) elements.settingsReport.checked = settings.generate_report;
        }
        if (settings.report_dir && elements.reportDir) elements.reportDir.value = settings.report_dir;

        console.log('GUI settings loaded');

    } catch (e) {
        console.error('Failed to load GUI settings:', e);
    }
}

async function saveGUISettings() {
    try {
        const formats = [];
        if (elements.reportJson?.checked) formats.push('json');
        if (elements.reportMd?.checked) formats.push('md');
        if (elements.reportHtml?.checked) formats.push('html');

        const settings = {
            engine_mode: AppState.engineMode,
            model: elements.llmModel.value,
            api_url: elements.apiUrl.value,
            use_websocket: elements.settingsWebsocket?.checked ?? elements.useWebsocket.checked,
            visible_browser: elements.settingsVisible?.checked ?? elements.visibleBrowser.checked,
            browser_channel: elements.browserChannel?.value || null,
            max_steps: parseInt(elements.maxSteps?.value) || 50,
            step_timeout_ms: parseInt(elements.timeout?.value) || 30000,
            retry_attempts: parseInt(elements.retryAttempts?.value) || 3,
            generate_report: elements.settingsReport?.checked ?? elements.generateReport.checked,
            report_dir: elements.reportDir?.value || './reports',
            report_formats: formats.length > 0 ? formats : ['json', 'md', 'html'],
        };

        const response = await fetch('/api/config/gui', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });

        if (response.ok) {
            AppState.settings = settings;
            showSavedBadge();
            if (elements.settingsStatus) elements.settingsStatus.textContent = 'Settings saved!';
            showToast('Settings saved', 'success');
        }

    } catch (e) {
        console.error('Failed to save settings:', e);
        showToast('Failed to save settings', 'error');
    }
}

async function saveSettingsPartial(updates) {
    try {
        await fetch('/api/config/gui', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        });
    } catch (e) {
        console.error('Failed to save partial settings:', e);
    }
}

function showSavedBadge() {
    const badge = elements.settingsSavedBadge;
    if (badge) {
        badge.style.display = 'inline';
        setTimeout(() => { badge.style.display = 'none'; }, 2000);
    }
}

// ============================================
// Instruction Files
// ============================================
async function loadInstructionFiles() {
    try {
        const response = await fetch('/api/config/instructions');
        if (!response.ok) return;

        const files = await response.json();

        elements.instructionFile.innerHTML = '<option value="">Select instruction file...</option>';
        files.forEach(file => {
            const option = document.createElement('option');
            option.value = file.name;
            option.textContent = `${file.name} (${file.lines} lines)`;
            elements.instructionFile.appendChild(option);
        });

    } catch (e) {
        console.error('Failed to load instruction files:', e);
    }
}

async function loadInstructionFile(filename) {
    if (!filename) return;

    try {
        const response = await fetch(`/api/config/instructions/${encodeURIComponent(filename)}`);
        if (!response.ok) return;

        const data = await response.json();
        elements.taskInput.value = data.content;
        updateInstructionCount();
        setMode('instructions');
        showToast(`Loaded ${filename}`, 'success');

    } catch (e) {
        console.error('Failed to load instruction file:', e);
        showToast('Failed to load file', 'error');
    }
}

// ============================================
// Models from API
// ============================================
async function loadModels() {
    try {
        const response = await fetch('/api/agent/models');
        if (!response.ok) return;

        const data = await response.json();
        const models = data.models || [];

        if (models.length > 0 && elements.llmModel) {
            elements.llmModel.innerHTML = models.map(m =>
                `<option value="${m.id}">${m.name}</option>`
            ).join('');

            // Apply saved model
            if (AppState.settings?.model) {
                elements.llmModel.value = AppState.settings.model;
            }
        }

    } catch (e) {
        console.error('Failed to load models:', e);
    }
}

// ============================================
// Event Listeners
// ============================================
function setupEventListeners() {
    // Landing page mode cards
    document.querySelectorAll('.mode-card').forEach(card => {
        card.addEventListener('click', () => {
            const mode = card.dataset.mode;
            if (mode === 'guided') {
                showView('guided');
            } else if (mode === 'instructions' || mode === 'goal') {
                setMode(mode);
                showView('execution');
            }
        });
    });

    // Back buttons
    document.getElementById('backToLanding')?.addEventListener('click', () => showView('landing'));
    document.getElementById('backFromExecution')?.addEventListener('click', () => showView('landing'));

    // Guided view
    document.getElementById('newRecordingBtn')?.addEventListener('click', showNewRecordingModal);
    document.getElementById('closeNewRecording')?.addEventListener('click', hideNewRecordingModal);
    document.getElementById('cancelNewRecording')?.addEventListener('click', hideNewRecordingModal);
    document.getElementById('startRecording')?.addEventListener('click', startNewRecording);

    // New recording modal - click outside to close
    document.getElementById('newRecordingModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'newRecordingModal') hideNewRecordingModal();
    });

    // Control buttons (execution view)
    elements.startBtn?.addEventListener('click', startTask);
    elements.stopBtn?.addEventListener('click', stopTask);
    elements.pauseBtn?.addEventListener('click', togglePause);

    // Mode toggle
    elements.instructionsModeBtn?.addEventListener('click', () => setMode('instructions'));
    elements.goalModeBtn?.addEventListener('click', () => setMode('goal'));

    // Instruction count
    elements.taskInput?.addEventListener('input', updateInstructionCount);

    // Screenshot refresh
    elements.refreshScreenshot?.addEventListener('click', fetchScreenshot);

    // Clear logs
    elements.clearLogs?.addEventListener('click', clearLogs);

    // History refresh
    elements.refreshHistory?.addEventListener('click', loadHistory);

    // Instruction file select
    elements.instructionFile?.addEventListener('change', (e) => {
        loadInstructionFile(e.target.value);
    });

    // Settings modal
    elements.settingsBtn?.addEventListener('click', () => {
        elements.settingsModal.classList.add('show');
    });

    elements.closeSettings?.addEventListener('click', () => {
        elements.settingsModal.classList.remove('show');
    });

    elements.cancelSettings?.addEventListener('click', () => {
        elements.settingsModal.classList.remove('show');
    });

    elements.saveSettings?.addEventListener('click', () => {
        saveGUISettings();
        elements.settingsModal.classList.remove('show');
    });

    // Help modal
    elements.helpBtn?.addEventListener('click', () => {
        elements.helpModal?.classList.add('show');
    });

    elements.closeHelp?.addEventListener('click', () => {
        elements.helpModal?.classList.remove('show');
    });

    // Click outside to close modals
    elements.settingsModal?.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            elements.settingsModal.classList.remove('show');
        }
    });

    elements.helpModal?.addEventListener('click', (e) => {
        if (e.target === elements.helpModal) {
            elements.helpModal.classList.remove('show');
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter to start
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            if (!elements.startBtn.disabled) startTask();
        }
        // Escape to stop or close modal
        if (e.key === 'Escape') {
            if (elements.settingsModal.classList.contains('show')) {
                elements.settingsModal.classList.remove('show');
            } else if (elements.helpModal?.classList.contains('show')) {
                elements.helpModal.classList.remove('show');
            } else if (!elements.stopBtn.disabled) {
                stopTask();
            }
        }
        // Ctrl+, for settings
        if (e.ctrlKey && e.key === ',') {
            e.preventDefault();
            elements.settingsModal.classList.add('show');
        }
    });

    // Local file input handler
    elements.localFileInput?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (evt) => {
            elements.taskInput.value = evt.target.result;
            updateInstructionCount();
            showToast(`Loaded ${file.name}`, 'success');
            // Switch to instructions mode
            setMode('instructions');
        };
        reader.onerror = () => {
            showToast('Failed to read file', 'error');
        };
        reader.readAsText(file);
    });
}

// ============================================
// Initialization
// ============================================
async function init() {
    console.log('LLM Web Agent GUI initialized');

    // Setup event listeners
    setupEventListeners();

    // Connect to SSE
    connectSSE();

    // Load data
    await loadGUISettings();
    await loadModels();
    loadHistory();
    loadInstructionFiles();
    updateInstructionCount();

    // Fetch initial status
    try {
        const response = await fetch('/api/agent/status');
        if (response.ok) {
            const data = await response.json();
            updateStatus(data.status);
            if (data.current_run) {
                elements.runId.textContent = data.current_run.run_id;
                if (data.is_running) {
                    startDurationTimer();
                    startScreenshotPolling();
                }
            }
        }
    } catch (e) {
        console.error('Failed to fetch initial status:', e);
    }

    addLog('GUI ready. Enter a task and click Start to begin.', 'info');
}

// Start the app
document.addEventListener('DOMContentLoaded', init);
