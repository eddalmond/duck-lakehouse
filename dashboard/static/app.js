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
    
    setInterval(loadRowCounts, 15000);
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
        
        if (data.busy) {
            // DB is busy with a write op — leave current counts, don't error
            return;
        }
        
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
    if (tab === 'sqleditor' && !sqlSchemaCache) {
        loadSqlSchema();
    }
}

// SQL Editor
let sqlSchemaCache = null;

async function loadSqlSchema() {
    const panel = document.getElementById('sql-schema-content');
    panel.innerHTML = '<p class="text-xs text-slate-400">Loading schema...</p>';
    
    try {
        const response = await fetch(`${API_BASE}/api/sql/schema`);
        const data = await response.json();
        
        if (data.need_init) {
            panel.innerHTML = '<p class="text-xs text-amber-600">Run Init first to create the DuckLake catalog.</p>';
            return;
        }
        if (data.busy) {
            panel.innerHTML = '<p class="text-xs text-amber-600">Database is busy...</p>';
            return;
        }
        
        sqlSchemaCache = data.schemas || {};
        buildSchemaPanel(sqlSchemaCache);
        buildExampleQueries(sqlSchemaCache);
    } catch (e) {
        panel.innerHTML = '<p class="text-xs text-red-500">Error loading schema</p>';
    }
}

function buildSchemaPanel(schemas) {
    const panel = document.getElementById('sql-schema-content');
    if (!schemas || Object.keys(schemas).length === 0) {
        panel.innerHTML = '<p class="text-xs text-slate-400">No tables found. Run the pipeline first.</p>';
        return;
    }
    
    let html = '';
    for (const [schema, tables] of Object.entries(schemas)) {
        html += `<div style="margin-bottom: 0.75rem;">`;
        html += `<div class="text-xs font-semibold text-slate-600" style="margin-bottom: 0.25rem; text-transform: uppercase; letter-spacing: 0.05em;">${escapeHtml(schema)}</div>`;
        for (const table of tables) {
            html += `<div class="sql-schema-table" style="margin-left: 0.5rem; margin-bottom: 0.25rem;">`;
            html += `<div class="text-xs font-medium text-blue-600 cursor-pointer hover:text-blue-800" onclick="insertTableRef('${escapeHtml(table.fq_name)}')" title="Click to insert table reference">${escapeHtml(table.name)}</div>`;
            if (table.columns && table.columns.length > 0) {
                html += `<div style="margin-left: 0.75rem;">`;
                for (const col of table.columns) {
                    html += `<div class="text-xs text-slate-400 cursor-pointer hover:text-slate-600" onclick="insertColRef('${escapeHtml(col.name)}')" title="${escapeHtml(col.type)}">${escapeHtml(col.name)} <span style="color:#94A3B8; font-size:0.65rem;">${escapeHtml(col.type)}</span></div>`;
                }
                html += `</div>`;
            }
            html += `</div>`;
        }
        html += `</div>`;
    }
    panel.innerHTML = html;
}

function buildExampleQueries(schemas) {
    const select = document.getElementById('sql-examples');
    if (!select) return;
    
    select.innerHTML = '<option value="">Example queries...</option>';
    
    const examples = [];
    const tableNames = [];
    for (const [schema, tables] of Object.entries(schemas)) {
        for (const t of tables) {
            tableNames.push(t.fq_name);
        }
    }
    
    if (tableNames.length > 0) {
        const firstTable = tableNames[0];
        const stgTable = tableNames.find(t => t.includes('stg_')) || firstTable;
        const fctTable = tableNames.find(t => t.includes('fct_')) || firstTable;
        
        examples.push({label: 'Preview staging data', query: `SELECT * FROM ${stgTable}\nLIMIT 10;`});
        examples.push({label: 'Count staging rows', query: `SELECT COUNT(*) AS total_rows\nFROM ${stgTable};`});
        examples.push({label: 'Distinct vaccine products', query: `SELECT DISTINCT VACCINE_PRODUCT_TERM, VACCINE_MANUFACTURER\nFROM ${stgTable}\nLIMIT 20;`});
        if (fctTable !== stgTable) {
            examples.push({label: 'Preview mart data', query: `SELECT * FROM ${fctTable}\nLIMIT 10;`});
            examples.push({label: 'Vaccinations by manufacturer', query: `SELECT vaccine_manufacturer, COUNT(*) AS count\nFROM ${fctTable}\nGROUP BY vaccine_manufacturer\nORDER BY count DESC;`});
        }
        examples.push({label: 'List all tables', query: `SELECT schema_name, table_name\nFROM duckdb_tables()\nWHERE database_name = 'vaccination_lake'\nORDER BY schema_name, table_name;`});
        examples.push({label: 'Column info for a table', query: `SELECT column_name, data_type\nFROM information_schema.columns\nWHERE table_schema = '${stgTable.split('.')[1]}'\n  AND table_name = '${stgTable.split('.')[2]}'\nORDER BY ordinal_position;`});
    } else {
        examples.push({label: 'List all tables', query: `SELECT schema_name, table_name\nFROM duckdb_tables()\nWHERE database_name = 'vaccination_lake'\nORDER BY schema_name, table_name;`});
    }
    
    for (const ex of examples) {
        const opt = document.createElement('option');
        opt.value = ex.query;
        opt.textContent = ex.label;
        select.appendChild(opt);
    }
}

function loadSqlExample() {
    const select = document.getElementById('sql-examples');
    const editor = document.getElementById('sql-editor');
    if (select.value) {
        editor.value = select.value;
        select.value = '';
    }
}

function insertTableRef(fqName) {
    const editor = document.getElementById('sql-editor');
    const pos = editor.selectionStart;
    const before = editor.value.substring(0, pos);
    const after = editor.value.substring(pos);
    editor.value = before + fqName + after;
    editor.focus();
}

function insertColRef(colName) {
    const editor = document.getElementById('sql-editor');
    const pos = editor.selectionStart;
    const before = editor.value.substring(0, pos);
    const after = editor.value.substring(pos);
    editor.value = before + colName + after;
    editor.focus();
}

async function executeSql() {
    const editor = document.getElementById('sql-editor');
    const resultsDiv = document.getElementById('sql-results');
    const query = editor.value.trim();
    
    if (!query) {
        resultsDiv.innerHTML = '<p class="text-amber-600 text-sm">Please enter a SQL query.</p>';
        return;
    }
    
    resultsDiv.innerHTML = '<p class="text-slate-400 text-sm">Running query...</p>';
    
    try {
        const response = await fetch(`${API_BASE}/api/sql`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        
        const data = await response.json();
        
        if (data.error) {
            resultsDiv.innerHTML = `<p class="text-red-600 text-sm">Error: ${escapeHtml(data.error)}</p>`;
            return;
        }
        
        if (data.busy) {
            resultsDiv.innerHTML = '<p class="text-amber-600 text-sm">Database is busy with a write operation. Please try again.</p>';
            return;
        }
        
        // Build results table
        const columns = data.columns || [];
        const rows = data.rows || [];
        
        if (columns.length === 0) {
            resultsDiv.innerHTML = '<p class="text-slate-400 text-sm">Query executed successfully. No columns returned.</p>';
            return;
        }
        
        if (rows.length === 0) {
            resultsDiv.innerHTML = '<p class="text-slate-400 text-sm">Query returned 0 rows.</p>';
            return;
        }
        
        // Build table
        let html = '<div style="margin-bottom: 0.5rem;" class="text-sm text-slate-600">';
        html += `Returned <strong>${data.row_count}</strong> row${data.row_count !== 1 ? 's' : ''}</div>`;
        html += '<div style="overflow-x: auto;"><table class="data-table" style="font-size: 12px;"><thead><tr>';
        
        columns.forEach(col => {
            html += `<th>${escapeHtml(col)}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        rows.forEach(row => {
            html += '<tr>';
            columns.forEach(col => {
                const val = row[col];
                let display = val === null ? '<span class="text-slate-400">NULL</span>' : escapeHtml(String(val));
                html += `<td>${display}</td>`;
            });
            html += '</tr>';
        });
        
        html += '</tbody></table></div>';
        resultsDiv.innerHTML = html;
        
    } catch (e) {
        resultsDiv.innerHTML = `<p class="text-red-600 text-sm">Error: ${escapeHtml(e.message)}</p>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
