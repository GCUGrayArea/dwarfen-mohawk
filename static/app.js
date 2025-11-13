// API Configuration
// Detect base URL: if we're in /v1/static/, use /v1 as base, otherwise use origin
const API_BASE_URL = window.location.pathname.startsWith('/v1/')
    ? window.location.origin + '/v1'
    : window.location.origin;
const API_KEY_STORAGE_KEY = 'zapier_api_key';
const AUTO_REFRESH_INTERVAL = 5000; // 5 seconds

// State Management
let apiKey = null;
let currentCursor = null;
let nextCursor = null;
let autoRefreshTimer = null;
let currentEventId = null;
let currentEventTimestamp = null;

// DOM Elements
const elements = {
    apiKeyInput: document.getElementById('api-key'),
    saveKeyBtn: document.getElementById('save-key-btn'),
    clearKeyBtn: document.getElementById('clear-key-btn'),
    generateKeyBtn: document.getElementById('generate-key-btn'),
    keyStatus: document.getElementById('key-status'),

    createEventForm: document.getElementById('create-event-form'),
    eventType: document.getElementById('event-type'),
    eventPayload: document.getElementById('event-payload'),
    eventSource: document.getElementById('event-source'),
    createResult: document.getElementById('create-result'),

    autoRefreshCheckbox: document.getElementById('auto-refresh'),
    refreshInboxBtn: document.getElementById('refresh-inbox-btn'),
    inboxList: document.getElementById('inbox-list'),
    inboxStats: document.getElementById('inbox-stats'),
    inboxLoading: document.getElementById('inbox-loading'),
    inboxError: document.getElementById('inbox-error'),

    prevPageBtn: document.getElementById('prev-page-btn'),
    nextPageBtn: document.getElementById('next-page-btn'),
    pageInfo: document.getElementById('page-info'),

    eventModal: document.getElementById('event-modal'),
    eventDetails: document.getElementById('event-details'),
    acknowledgeBtn: document.getElementById('acknowledge-btn'),
    cancelBtn: document.getElementById('cancel-btn'),
    closeModalBtn: document.getElementById('close-modal-btn')
};

// Initialize App
function init() {
    loadApiKey();
    setupEventListeners();

    if (apiKey) {
        loadInbox();
        startAutoRefresh();
    }
}

// API Key Management
function loadApiKey() {
    apiKey = localStorage.getItem(API_KEY_STORAGE_KEY);
    if (apiKey) {
        elements.apiKeyInput.value = '••••••••';
        showStatus('API key loaded from storage', 'success');
    }
}

function saveApiKey() {
    const key = elements.apiKeyInput.value.trim();
    if (!key) {
        showStatus('Please enter an API key', 'error');
        return;
    }

    apiKey = key;
    localStorage.setItem(API_KEY_STORAGE_KEY, key);
    elements.apiKeyInput.value = '••••••••';
    showStatus('API key saved successfully', 'success');

    loadInbox();
    startAutoRefresh();
}

function clearApiKey() {
    apiKey = null;
    localStorage.removeItem(API_KEY_STORAGE_KEY);
    elements.apiKeyInput.value = '';
    showStatus('API key cleared', 'success');
    stopAutoRefresh();
    elements.inboxList.innerHTML = '';
}

async function generateApiKey() {
    try {
        elements.generateKeyBtn.disabled = true;
        elements.generateKeyBtn.textContent = '🔄 Generating...';
        showStatus('Generating new API key...', 'info');

        const response = await fetch(`${API_BASE_URL}/admin/generate-key`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_email: 'demo@example.com',
                role: 'creator'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to generate API key');
        }

        const data = await response.json();

        // Show the generated key in a modal/alert
        const message = `✅ API Key Generated!\n\n` +
            `Key ID: ${data.key_id}\n` +
            `API Key: ${data.api_key}\n\n` +
            `⚠️ Save this key now! You won't see it again.\n\n` +
            `This key has been automatically configured and is ready to use.`;

        alert(message);

        // Auto-save the generated key
        apiKey = data.api_key;
        localStorage.setItem(API_KEY_STORAGE_KEY, data.api_key);
        elements.apiKeyInput.value = '••••••••';
        showStatus('✅ API key generated and saved!', 'success');

        // Load inbox with new key
        loadInbox();
        startAutoRefresh();

    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
        console.error('Failed to generate API key:', error);
    } finally {
        elements.generateKeyBtn.disabled = false;
        elements.generateKeyBtn.textContent = '🔑 Generate Demo API Key';
    }
}

function showStatus(message, type) {
    elements.keyStatus.textContent = message;
    elements.keyStatus.className = `status-message ${type}`;
    setTimeout(() => {
        elements.keyStatus.textContent = '';
        elements.keyStatus.className = 'status-message';
    }, 5000);
}

// Event Creation
async function createEvent(eventData) {
    if (!apiKey) {
        showResult('Please configure your API key first', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/events`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`
            },
            body: JSON.stringify(eventData)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || 'Failed to create event');
        }

        showResult(`Event created successfully!\nEvent ID: ${data.event_id}`, 'success', data);

        // Refresh inbox to show new event
        setTimeout(() => loadInbox(), 500);

    } catch (error) {
        showResult(`Error: ${error.message}`, 'error');
    }
}

function showResult(message, type, data = null) {
    elements.createResult.innerHTML = `
        <p style="color: ${type === 'success' ? '#22543d' : '#742a2a'}; margin-bottom: 10px;">
            ${message}
        </p>
        ${data ? `<pre>${JSON.stringify(data, null, 2)}</pre>` : ''}
    `;
}

// Inbox Management
async function loadInbox(cursor = null) {
    if (!apiKey) {
        elements.inboxError.textContent = 'Please configure your API key first';
        elements.inboxLoading.style.display = 'none';
        return;
    }

    elements.inboxLoading.style.display = 'block';
    elements.inboxError.textContent = '';

    try {
        let url = `${API_BASE_URL}/inbox?limit=10`;
        if (cursor) {
            url += `&cursor=${encodeURIComponent(cursor)}`;
        }

        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${apiKey}`
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || 'Failed to load inbox');
        }

        displayInbox(data);
        updatePaginationControls(data.pagination);

    } catch (error) {
        elements.inboxError.textContent = `Error: ${error.message}`;
    } finally {
        elements.inboxLoading.style.display = 'none';
    }
}

function displayInbox(data) {
    const events = data.events || [];

    // Update stats
    elements.inboxStats.textContent =
        `Total undelivered events: ${data.pagination?.total_undelivered || 0}`;

    // Clear and populate inbox list
    elements.inboxList.innerHTML = '';

    if (events.length === 0) {
        return; // CSS will show "No undelivered events"
    }

    events.forEach(event => {
        const item = createInboxItem(event);
        elements.inboxList.appendChild(item);
    });
}

function createInboxItem(event) {
    const div = document.createElement('div');
    div.className = 'inbox-item';
    div.onclick = () => showEventDetails(event);

    const payloadPreview = JSON.stringify(event.payload, null, 2)
        .split('\n')
        .slice(0, 3)
        .join('\n');

    div.innerHTML = `
        <div class="inbox-item-header">
            <span class="event-type">${escapeHtml(event.event_type)}</span>
            <span class="event-timestamp">${formatTimestamp(event.timestamp)}</span>
        </div>
        <div class="event-id">ID: ${escapeHtml(event.event_id)}</div>
        <div class="payload-preview">${escapeHtml(payloadPreview)}...</div>
    `;

    return div;
}

function updatePaginationControls(pagination) {
    if (!pagination) return;

    nextCursor = pagination.next_cursor;

    elements.nextPageBtn.disabled = !pagination.has_more;
    elements.prevPageBtn.disabled = !currentCursor;

    elements.pageInfo.textContent =
        `Showing up to 10 events (${pagination.total_undelivered} total)`;
}

async function goToNextPage() {
    if (nextCursor) {
        currentCursor = nextCursor;
        await loadInbox(nextCursor);
    }
}

async function goToPreviousPage() {
    currentCursor = null;
    nextCursor = null;
    await loadInbox();
}

// Event Details Modal
async function showEventDetails(event) {
    currentEventId = event.event_id;
    currentEventTimestamp = event.timestamp;

    elements.eventDetails.innerHTML = `
        <div class="detail-row">
            <div class="detail-label">Event ID:</div>
            <div class="detail-value">${escapeHtml(event.event_id)}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Event Type:</div>
            <div class="detail-value">${escapeHtml(event.event_type)}</div>
        </div>
        <div class="detail-row">
            <div class="detail-label">Timestamp:</div>
            <div class="detail-value">${escapeHtml(event.timestamp)}</div>
        </div>
        ${event.source ? `
        <div class="detail-row">
            <div class="detail-label">Source:</div>
            <div class="detail-value">${escapeHtml(event.source)}</div>
        </div>
        ` : ''}
        <div class="detail-row">
            <div class="detail-label">Payload:</div>
            <div class="detail-value">
                <pre>${escapeHtml(JSON.stringify(event.payload, null, 2))}</pre>
            </div>
        </div>
    `;

    elements.eventModal.classList.add('active');
}

function closeModal() {
    elements.eventModal.classList.remove('active');
    currentEventId = null;
    currentEventTimestamp = null;
}

async function acknowledgeEvent() {
    if (!currentEventId || !apiKey) return;

    try {
        const response = await fetch(
            `${API_BASE_URL}/inbox/${currentEventId}`,
            {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${apiKey}`
                }
            }
        );

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || 'Failed to acknowledge event');
        }

        closeModal();
        loadInbox(currentCursor);

    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

// Auto-refresh
function startAutoRefresh() {
    if (autoRefreshTimer) return;

    if (elements.autoRefreshCheckbox.checked) {
        autoRefreshTimer = setInterval(() => {
            loadInbox(currentCursor);
        }, AUTO_REFRESH_INTERVAL);
    }
}

function stopAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
}

function toggleAutoRefresh() {
    if (elements.autoRefreshCheckbox.checked) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
}

// Event Listeners
function setupEventListeners() {
    // API Key
    elements.saveKeyBtn.addEventListener('click', saveApiKey);
    elements.clearKeyBtn.addEventListener('click', clearApiKey);
    elements.generateKeyBtn.addEventListener('click', generateApiKey);

    // Create Event
    elements.createEventForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        let payload;
        try {
            payload = JSON.parse(elements.eventPayload.value);
        } catch (error) {
            showResult('Invalid JSON payload', 'error');
            return;
        }

        const eventData = {
            event_type: elements.eventType.value.trim(),
            payload: payload
        };

        if (elements.eventSource.value.trim()) {
            eventData.source = elements.eventSource.value.trim();
        }

        await createEvent(eventData);
    });

    // Inbox Controls
    elements.refreshInboxBtn.addEventListener('click', () => loadInbox(currentCursor));
    elements.autoRefreshCheckbox.addEventListener('change', toggleAutoRefresh);
    elements.nextPageBtn.addEventListener('click', goToNextPage);
    elements.prevPageBtn.addEventListener('click', goToPreviousPage);

    // Modal
    elements.acknowledgeBtn.addEventListener('click', acknowledgeEvent);
    elements.cancelBtn.addEventListener('click', closeModal);
    elements.closeModalBtn.addEventListener('click', closeModal);

    // Close modal on outside click
    elements.eventModal.addEventListener('click', (e) => {
        if (e.target === elements.eventModal) {
            closeModal();
        }
    });
}

// Utility Functions
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Start the app when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
