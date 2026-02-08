// Shared utilities for all Freerando pages

async function fetchJSON(url, options) {
    try {
        const resp = await fetch(url, options);
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

function formatDate(isoString) {
    if (!isoString) return '--';
    const d = new Date(isoString);
    if (isNaN(d.getTime())) {
        // Handle "YYYY-MM-DD HH:MM:SS" format
        return isoString.split(' ')[0] || isoString;
    }
    return d.toLocaleDateString('fr-FR');
}

function debounce(fn, ms) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms);
    };
}
