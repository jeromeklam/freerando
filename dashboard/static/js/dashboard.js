const REFRESH_SYSTEM = 10000;
const REFRESH_DOCKER = 15000;
const REFRESH_PHOTOS = 300000;
const REFRESH_PG = 60000;

async function fetchJSON(url) {
    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error(`Fetch ${url} failed:`, e);
        return null;
    }
}

function humanBytes(bytes) {
    if (bytes === null || bytes === undefined) return '--';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
    return `${bytes.toFixed(1)} ${units[i]}`;
}

function humanUptime(seconds) {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}j ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

function diskColor(percent) {
    if (percent > 90) return 'var(--accent-red)';
    if (percent > 70) return 'var(--accent-orange)';
    return 'var(--accent-green)';
}

function statusClass(status) {
    if (status === 'running') return 'status-running';
    if (status === 'exited') return 'status-stopped';
    return 'status-error';
}

// --- SYSTEM ---
async function refreshSystem() {
    const data = await fetchJSON('/api/system');
    if (!data) return;

    // Temperature
    const tempEl = document.getElementById('cpu-temp');
    if (data.cpu_temp !== null) {
        tempEl.textContent = `${data.cpu_temp.toFixed(1)}°C`;
        tempEl.style.color = data.cpu_temp > 70 ? 'var(--accent-red)' :
                             data.cpu_temp > 55 ? 'var(--accent-orange)' : 'var(--accent-green)';
    } else {
        tempEl.textContent = '--';
    }

    // CPU
    document.getElementById('cpu-percent').textContent = `${data.cpu_percent}%`;
    document.getElementById('cpu-freq').textContent =
        data.cpu_freq.current ? `${Math.round(data.cpu_freq.current)} MHz` : '--';

    const coresEl = document.getElementById('cpu-cores');
    coresEl.innerHTML = data.cpu_per_core.map((p, i) =>
        `<span class="core-badge" style="border-left:3px solid ${p > 80 ? 'var(--accent-red)' : p > 50 ? 'var(--accent-orange)' : 'var(--accent-green)'}">C${i}: ${p}%</span>`
    ).join('');

    // RAM
    document.getElementById('ram-percent').textContent = `${data.ram.percent}%`;
    document.getElementById('ram-detail').textContent =
        `${humanBytes(data.ram.used)} / ${humanBytes(data.ram.total)}`;

    // Disks
    const diskList = document.getElementById('disk-list');
    diskList.innerHTML = data.disks.map(d => `
        <div class="disk-entry">
            <div class="disk-label">${d.mountpoint} <span style="color:var(--text-secondary)">(${d.device})</span></div>
            <div class="disk-bar">
                <div class="disk-bar-fill" style="width:${d.percent}%;background:${diskColor(d.percent)}"></div>
                <div class="disk-bar-text">${d.percent}%</div>
            </div>
            <div class="disk-detail">${humanBytes(d.used)} / ${humanBytes(d.total)} (${humanBytes(d.free)} libre)</div>
        </div>
    `).join('');

    // Network
    document.getElementById('net-ips').innerHTML =
        Object.entries(data.network.ips).map(([nic, ip]) =>
            `<div class="net-entry"><span>${nic}</span><strong>${ip}</strong></div>`
        ).join('');
    document.getElementById('net-speed').innerHTML = `
        <div class="net-entry"><span>Upload</span><strong>${humanBytes(data.network.upload_speed)}/s</strong></div>
        <div class="net-entry"><span>Download</span><strong>${humanBytes(data.network.download_speed)}/s</strong></div>
    `;

    // Uptime
    document.getElementById('uptime').textContent = `Uptime: ${humanUptime(data.uptime_seconds)}`;

    // Charts
    updateCharts(data);

    document.getElementById('last-refresh').textContent =
        `MAJ: ${new Date().toLocaleTimeString('fr-FR')}`;
}

// --- DOCKER ---
async function refreshDocker() {
    const data = await fetchJSON('/api/docker');
    if (!data) return;

    document.getElementById('docker-status').innerHTML =
        `<span class="status-badge ${statusClass(data.status)}">${data.status}</span>`;

    if (data.image) {
        document.getElementById('docker-image').textContent = data.image;
    }

    if (data.started_at) {
        const started = new Date(data.started_at);
        document.getElementById('docker-uptime').textContent =
            `Depuis: ${started.toLocaleString('fr-FR')}`;
    }

    if (data.error) {
        document.getElementById('docker-logs').textContent = data.error;
    } else {
        document.getElementById('docker-logs').textContent =
            data.logs.map(l => {
                // Trim the docker timestamp prefix for readability
                const parts = l.split(' ');
                if (parts.length > 1 && parts[0].includes('T')) {
                    return parts.slice(1).join(' ');
                }
                return l;
            }).join('\n');
    }
}

// --- PHOTOS ---
async function refreshPhotos() {
    const data = await fetchJSON('/api/photos');
    if (!data) return;

    document.getElementById('photo-count').textContent =
        data.total_count.toLocaleString('fr-FR');
    document.getElementById('photo-size').textContent = data.total_size_human;

    // Extensions
    if (data.by_extension && Object.keys(data.by_extension).length > 0) {
        document.getElementById('photo-extensions').textContent =
            Object.entries(data.by_extension)
                .sort((a, b) => b[1] - a[1])
                .map(([ext, count]) => `${ext}: ${count}`)
                .join('  ');
    }

    // By year bars
    const maxCount = Math.max(...data.by_year.map(y => y.count), 1);
    document.getElementById('photo-by-year').innerHTML = data.by_year.map(y => `
        <div class="year-row">
            <span class="year-label">${y.year}</span>
            <div class="year-bar-bg">
                <div class="year-bar-fill" style="width:${Math.round(y.count / maxCount * 100)}%"></div>
            </div>
            <span class="year-count">${y.count.toLocaleString('fr-FR')}</span>
        </div>
    `).join('');

    // Recent files table
    if (data.recent_files.length > 0) {
        const rows = data.recent_files.map(f =>
            `<tr><td>${f.filename}</td><td>${f.modified}</td><td>${f.size_human}</td></tr>`
        ).join('');
        document.getElementById('photo-recent-table').innerHTML =
            `<tr><th>Fichier</th><th>Date</th><th>Taille</th></tr>${rows}`;
    }
}

// --- POSTGRESQL ---
async function refreshPostgres() {
    const data = await fetchJSON('/api/postgres');
    if (!data) return;

    const statusEl = document.getElementById('pg-status');
    if (data.connected) {
        statusEl.innerHTML = '<span class="status-badge status-running">Connecte</span>';
        document.getElementById('pg-info').innerHTML = `
            <div class="metric-row"><span>Host</span><strong>${data.host}</strong></div>
            <div class="metric-row"><span>Base</span><strong>${data.database}</strong></div>
            <div class="metric-row"><span>Taille</span><strong>${data.db_size}</strong></div>
            ${data.postgis_version ? `<div class="metric-row"><span>PostGIS</span><strong>${data.postgis_version}</strong></div>` : ''}
        `;

        if (data.tables.length > 0) {
            const rows = data.tables.map(t =>
                `<tr><td>${t.schema}.${t.table}</td><td>${t.row_count.toLocaleString('fr-FR')}</td></tr>`
            ).join('');
            document.getElementById('pg-tables').innerHTML =
                `<tr><th>Table</th><th>Lignes</th></tr>${rows}`;
        } else {
            document.getElementById('pg-tables').innerHTML =
                '<tr><td colspan="2" style="color:var(--text-secondary)">Aucune table utilisateur</td></tr>';
        }
    } else {
        statusEl.innerHTML = '<span class="status-badge status-error">Erreur</span>';
        document.getElementById('pg-info').innerHTML =
            `<div style="color:var(--accent-red);margin-top:0.5rem">${data.error || 'Connexion impossible'}</div>`;
        document.getElementById('pg-tables').innerHTML = '';
    }
}

// --- ANALYSIS ---
const REFRESH_ANALYSIS = 30000;

function progressBar(done, total, color) {
    const pct = total > 0 ? Math.round(done / total * 100) : 0;
    return `
        <div class="progress-item">
            <div class="progress-bar-mini">
                <div class="progress-bar-mini-fill" style="width:${pct}%;background:${color}"></div>
            </div>
            <span>${done.toLocaleString('fr-FR')} / ${total.toLocaleString('fr-FR')}</span>
        </div>
    `;
}

async function refreshAnalysis() {
    const data = await fetchJSON('/api/analysis');
    if (!data) return;

    const errEl = document.getElementById('analysis-error');
    if (data.error) {
        errEl.textContent = data.error;
        errEl.style.display = 'block';
        return;
    }
    errEl.style.display = 'none';

    const t = data.totals;

    // Pipeline progress
    document.getElementById('analysis-progress').innerHTML = `
        <div class="progress-item">
            <span class="progress-label">EXIF</span>
            ${progressBar(t.exif_done, t.total_photos, 'var(--accent-green)')}
        </div>
        <div class="progress-item">
            <span class="progress-label">CLIP</span>
            ${progressBar(t.clip_done, t.total_photos, 'var(--accent-blue)')}
        </div>
        <div class="progress-item">
            <span class="progress-label">YOLO</span>
            ${progressBar(t.yolo_done, t.total_photos, 'var(--accent-orange)')}
        </div>
        <div class="progress-item">
            <span class="progress-label">Visages</span>
            ${progressBar(t.face_done, t.total_photos, '#9b59b6')}
        </div>
        <div style="margin-top:0.6rem;font-size:0.8rem;color:var(--text-secondary)">
            <div class="metric-row"><span>Photos avec GPS</span><strong style="color:var(--accent-green)">${t.with_gps.toLocaleString('fr-FR')}</strong></div>
            <div class="metric-row"><span>Photos avec date</span><strong>${t.with_date.toLocaleString('fr-FR')}</strong></div>
            <div class="metric-row"><span>Tags CLIP</span><strong>${(data.tag_counts.clip || 0).toLocaleString('fr-FR')}</strong></div>
            <div class="metric-row"><span>Detections YOLO</span><strong>${(data.tag_counts.yolo || 0).toLocaleString('fr-FR')}</strong></div>
        </div>
    `;

    // Top CLIP tags
    if (data.top_clip_tags.length > 0) {
        document.getElementById('analysis-clip-tags').innerHTML =
            data.top_clip_tags.map(t =>
                `<span class="tag-chip">${t.tag}<span class="tag-count">${t.count}</span></span>`
            ).join('');
    } else {
        document.getElementById('analysis-clip-tags').innerHTML =
            '<span style="color:var(--text-secondary);font-size:0.8rem">En attente...</span>';
    }

    // Top YOLO detections
    if (data.top_yolo_tags.length > 0) {
        document.getElementById('analysis-yolo-tags').innerHTML =
            data.top_yolo_tags.map(t =>
                `<span class="tag-chip">${t.tag}<span class="tag-count">${t.count}</span></span>`
            ).join('');
    } else {
        document.getElementById('analysis-yolo-tags').innerHTML =
            '<span style="color:var(--text-secondary);font-size:0.8rem">En attente...</span>';
    }

    // Faces
    const facesEl = document.getElementById('analysis-faces');
    if (data.unique_faces > 0) {
        let html = `<div style="margin-bottom:0.5rem;font-size:0.85rem"><strong style="color:var(--accent-green)">${data.unique_faces}</strong> visages uniques</div>`;
        html += data.face_clusters.map(f => `
            <div class="face-item">
                <div>
                    <span class="face-label">${f.label}</span>
                    <span class="face-meta">${f.gender}, ~${f.age} ans</span>
                </div>
                <span class="face-count">${f.photo_count} photos</span>
            </div>
        `).join('');
        facesEl.innerHTML = html;
    } else {
        facesEl.innerHTML = '<span style="color:var(--text-secondary);font-size:0.8rem">En attente...</span>';
    }
}

// --- INIT ---
async function init() {
    refreshSystem();
    refreshDocker();
    refreshPhotos();
    refreshPostgres();
    refreshAnalysis();

    setInterval(refreshSystem, REFRESH_SYSTEM);
    setInterval(refreshDocker, REFRESH_DOCKER);
    setInterval(refreshPhotos, REFRESH_PHOTOS);
    setInterval(refreshPostgres, REFRESH_PG);
    setInterval(refreshAnalysis, REFRESH_ANALYSIS);
}

document.addEventListener('DOMContentLoaded', init);
