/**
 * DuckLake Dashboard - Frontend Application
 */

const API_BASE = '';
let activeStreams = new Map();

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    loadStatus();
    loadRowCounts();
    loadExplorerTables();
    setupEventListeners();
    
    setInterval(loadRowCounts, 5000);
});

function setupEventListeners() {
    document.getElementById('runAllBtn').addEventListener('click', runFullPipeline);
    document.getElementById('cleanBtn').addEventListener('click', cleanAll);
}

// Stage execution
function runStage(stage) {
    if (activeStreams.has(stage)) {
        logToConsole(`Stage ${stage} is already running...`, 'info');
        return;
    }
    
    setStageStatus(stage, 'running');
    logToConsole(`Starting ${stage}...`, 'info');
    
    const eventSource = new EventSource(`${API_BASE}/api/run/${stage}`);
    activeStreams.set(stage, eventSource);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.error) {
            logToConsole(`Error: ${data.error}`, 'error');
            setStageStatus(stage, 'error');
            eventSource.close();
            activeStreams.delete(stage);
        } else if (data.done) {
            if (data.exit_code === 0) {
                logToConsole(`${stage} completed successfully`, 'success');
                setStageStatus(stage, 'success');
            } else {
                logToConsole(`${stage} failed with exit code ${data.exit_code}`, 'error');
                setStageStatus(stage, 'error');
            }
            eventSource.close();
            activeStreams.delete(stage);
            
            // Refresh data
            loadRowCounts();
            loadExplorerTables();
            if (stage === 'ingest' || stage === 'dbt') {
                loadExplorerData(false);
            }
        } else {
            logToConsole(data.line);
        }
    };
    
    eventSource.onerror = () => {
        logToConsole(`Connection lost for ${stage}`, 'error');
        setStageStatus(stage, 'error');
        eventSource.close();
        activeStreams.delete(stage);
    };
}

// Full pipeline execution
async function runFullPipeline() {
    const btn = document.getElementById('runAllBtn');
    btn.disabled = true;
    btn.innerHTML = `<svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Running Pipeline...`;
    
    clearConsole();
    logToConsole('=== Starting Full Pipeline ===', 'info');
    
    const stages = ['generate', 'mesh', 'init', 'ingest', 'dbt'];
    
    for (const stage of stages) {
        await runStageAndWait(stage);
    }
    
    logToConsole('=== Pipeline Complete ===', 'success');
    btn.disabled = false;
    btn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Run Full Pipeline`;
}

function runStageAndWait(stage) {
    return new Promise((resolve) => {
        setStageStatus(stage, 'running');
        logToConsole(`\n>>> ${stage.toUpperCase()} <<<`, 'info');
        
        const eventSource = new EventSource(`${API_BASE}/api/run/${stage}`);
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.error) {
                logToConsole(`Error: ${data.error}`, 'error');
                setStageStatus(stage, 'error');
                eventSource.close();
                resolve();
            } else if (data.done) {
                if (data.exit_code === 0) {
                    logToConsole(`${stage} ✓`, 'success');
                    setStageStatus(stage, 'success');
                } else {
                    logToConsole(`${stage} ✗ (exit ${data.exit_code})`, 'error');
                    setStageStatus(stage, 'error');
                }
                eventSource.close();
                loadRowCounts();
                setTimeout(resolve, 500);
            } else {
                logToConsole(data.line);
            }
        };
        
        eventSource.onerror = () => {
            eventSource.close();
            resolve();
        };
    });
}

// Status management
function setStageStatus(stage, state) {
    const statusEl = document.getElementById(`status-${stage}`);
    const stageEl = document.getElementById(`stage-${stage}`);
    
    statusEl.className = `stage-status ${state}`;
    stageEl.className = `pipeline-stage ${state}`;
    
    const labels = {
        idle: 'Idle',
        running: 'Running...',
        success: 'Complete',
        error: 'Failed'
    };
    statusEl.textContent = labels[state];
}

async function loadStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();
        
        Object.entries(data).forEach(([stage, info]) => {
            if (!activeStreams.has(stage)) {
                setStageStatus(stage, info.state);
            }
        });
    } catch (e) {
        console.error('Failed to load status:', e);
    }
}

// Row counts (updated to populate explorer footer)
async function loadRowCounts() {
    try {
        const response = await fetch(`${API_BASE}/api/preview/row_counts`);
        const data = await response.json();
        
        const stagingEl = document.getElementById('staging-count');
        const martsEl = document.getElementById('marts-count');
        if (stagingEl) stagingEl.textContent = (data.staging || 0).toLocaleString();
        if (martsEl) martsEl.textContent = (data.marts || 0).toLocaleString();
    } catch (e) {
        console.error('Failed to load row counts:', e);
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Data Explorer
let explorerOffset = 0;
const EXPLORER_PAGE_SIZE = 50;

async function loadExplorerTables() {
    const select = document.getElementById('explorer-table-select');
    if (!select) return;
    const prevValue = select.value;
    try {
        const response = await fetch(`${API_BASE}/api/tables`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        const tables = data.tables || [];
        
        select.innerHTML = '<option value="">Choose a table...</option>';
        for (const t of tables) {
            const opt = document.createElement('option');
            opt.value = t.name;
            opt.textContent = `${t.name}${t.rows != null ? ` (${Number(t.rows).toLocaleString()} rows)` : ''}`;
            select.appendChild(opt);
        }
        
        if (prevValue && tables.some(t => t.name === prevValue)) {
            select.value = prevValue;
        }
    } catch (e) {
        console.error('Failed to load tables:', e);
    }
}

async function loadExplorerData(resetOffset = true) {
    const select = document.getElementById('explorer-table-select');
    const tableName = select.value;
    
    if (resetOffset) {
        explorerOffset = 0;
    }
    
    if (!tableName) {
        document.getElementById('explorer-table').innerHTML = '<thead><tr><td class="empty-state">Select a table to explore DuckDB data</td></tr></thead>';
        document.getElementById('explorer-info').textContent = '';
        document.getElementById('explorer-footer-detail').textContent = '';
        return;
    }
    
    try {
        const response = await fetch(
            `${API_BASE}/api/query/${encodeURIComponent(tableName)}?limit=${EXPLORER_PAGE_SIZE}&offset=${explorerOffset}`
        );
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('explorer-table').innerHTML = `<thead><tr><td class="empty-state">${data.error}</td></tr></thead>`;
            return;
        }
        
        const columns = data.columns || [];
        const rows = data.rows || [];
        
        if (rows.length === 0) {
            document.getElementById('explorer-info').textContent = `${data.total.toLocaleString()} rows · ${columns.length} columns`;
            document.getElementById('explorer-table').innerHTML = '<thead><tr><td class="empty-state">No data — run ingest and dbt transform first</td></tr></thead>';
            document.getElementById('explorer-footer-detail').textContent = '';
            return;
        }
        
        document.getElementById('explorer-info').textContent = `${data.total.toLocaleString()} rows · ${columns.length} columns`;
        
        const pageStart = explorerOffset + 1;
        const pageEnd = Math.min(explorerOffset + rows.length, data.total);
        document.getElementById('explorer-footer-detail').textContent = `Showing ${pageStart}-${pageEnd} of ${data.total.toLocaleString()}`;
        
        let tableHtml = `<thead><tr>${columns.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>`;
        for (const row of rows) {
            tableHtml += '<tr>';
            for (const col of columns) {
                const val = row[col];
                tableHtml += `<td title="${val !== null && val !== undefined ? String(val) : ''}">${val !== null && val !== undefined ? val : ''}</td>`;
            }
            tableHtml += '</tr>';
        }
        tableHtml += '</tbody>';
        
        document.getElementById('explorer-table').innerHTML = tableHtml;
    } catch (e) {
        console.error('Failed to load explorer data:', e);
        document.getElementById('explorer-table').innerHTML = '<thead><tr><td class="empty-state">Error loading data</td></tr></thead>';
    }
}

function explorerPrev() {
    explorerOffset = Math.max(0, explorerOffset - EXPLORER_PAGE_SIZE);
    loadExplorerData(false);
}

function explorerNext() {
    explorerOffset += EXPLORER_PAGE_SIZE;
    loadExplorerData(false);
}

// Console output
function logToConsole(message, type = 'normal') {
    const console = document.getElementById('console');
    const line = document.createElement('div');
    line.className = `log-line ${type}`;
    line.textContent = message;
    console.appendChild(line);
    console.scrollTop = console.scrollHeight;
}

function clearConsole() {
    document.getElementById('console').innerHTML = '';
}

// Clean all data
async function cleanAll() {
    if (!confirm('This will delete all generated data, catalog, and files. Continue?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/clean`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            logToConsole('All data cleaned successfully', 'success');
            ['generate', 'mesh', 'init', 'ingest', 'dbt'].forEach(s => setStageStatus(s, 'idle'));
            loadRowCounts();
        } else {
            logToConsole(`Clean failed: ${data.error}`, 'error');
        }
    } catch (e) {
        logToConsole(`Clean failed: ${e.message}`, 'error');
    }
}

// Explorer tab switching
function switchExplorerTab(tab) {
    document.querySelectorAll('.explorer-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.explorer-tab-content').forEach(t => t.style.display = 'none');
    event.target.classList.add('active');
    document.getElementById(`explorer-tab-${tab}`).style.display = '';
}

// DuckDB UI
async function startDuckDBUI() {
    const btn = document.getElementById('duckui-start-btn');
    const statusText = document.getElementById('duckui-status-text');
    btn.disabled = true;
    btn.textContent = 'Starting...';
    statusText.textContent = 'Starting DuckDB UI server...';

    try {
        const resp = await fetch(`${API_BASE}/api/duckdb-ui/start`);
        const data = await resp.json();

        if (data.status === 'started') {
            statusText.textContent = 'Waiting for UI to be ready...';
            let ready = false;
            for (let i = 0; i < 20; i++) {
                await new Promise(r => setTimeout(r, 1000));
                try {
                    const check = await fetch(`${API_BASE}/duckdb-ui/`, { method: 'HEAD' });
                    if (check.ok || check.status === 200) {
                        ready = true;
                        break;
                    }
                } catch {}
            }
            if (ready) {
                document.getElementById('duckui-launch').style.display = 'none';
                const frame = document.getElementById('duckui-frame-wrap');
                frame.style.display = '';
                document.getElementById('duckui-iframe').src = `${API_BASE}/duckdb-ui/`;
                statusText.textContent = 'Running';
            } else {
                statusText.textContent = 'UI started but not reachable yet. Try again in a moment.';
            }
        } else {
            statusText.textContent = `Error: ${data.message || 'unknown'}`;
        }
    } catch (e) {
        statusText.textContent = `Error: ${e.message}`;
    }
    btn.disabled = false;
    btn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Launch DuckDB UI`;
}

function openDuckDBUI() {
    window.open(`${API_BASE}/duckdb-ui/`, '_blank');
}
