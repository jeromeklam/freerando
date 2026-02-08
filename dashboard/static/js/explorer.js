// Explorer: Map + Photo Grid + Lightbox
let map, markerCluster;
let currentPhotos = [];
let currentPage = 1;
let totalPages = 0;
let currentLightboxIndex = -1;

// --- INIT ---
async function init() {
    initMap();
    await loadFilters();
    await search();
    await loadGeoPhotos();

    document.getElementById('btn-search').addEventListener('click', () => { currentPage = 1; search(); loadGeoPhotos(); });
    document.getElementById('filter-search').addEventListener('keydown', e => {
        if (e.key === 'Enter') { currentPage = 1; search(); loadGeoPhotos(); }
    });

    // Lightbox controls
    document.getElementById('lb-close').addEventListener('click', closeLightbox);
    document.getElementById('lb-prev').addEventListener('click', () => navigateLightbox(-1));
    document.getElementById('lb-next').addEventListener('click', () => navigateLightbox(1));
    document.addEventListener('keydown', e => {
        if (document.getElementById('lightbox').style.display === 'none') return;
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') navigateLightbox(-1);
        if (e.key === 'ArrowRight') navigateLightbox(1);
    });
}

// --- MAP ---
function initMap() {
    map = L.map('map').setView([46.5, 2.5], 6); // France center
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap',
        maxZoom: 19
    }).addTo(map);

    markerCluster = L.markerClusterGroup({
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        disableClusteringAtZoom: 16
    });
    map.addLayer(markerCluster);
}

async function loadGeoPhotos() {
    const params = buildFilterParams();
    const qs = new URLSearchParams(params).toString();
    const data = await fetchJSON(`/api/explorer/photos/geo?${qs}`);
    if (!data) return;

    markerCluster.clearLayers();

    const markers = data.features.map(f => {
        const p = f.properties;
        const [lon, lat] = f.geometry.coordinates;
        const marker = L.marker([lat, lon]);
        marker.bindPopup(() => {
            const div = document.createElement('div');
            div.className = 'map-popup';
            div.innerHTML = `
                <img src="/api/explorer/photo/${p.id}/thumb?size=300" class="popup-thumb"
                     onclick="openLightboxById(${p.id})" style="cursor:pointer">
                <div class="popup-info">
                    <strong>${p.filename}</strong>
                    <span>${p.date_taken || ''}</span>
                </div>
            `;
            return div;
        }, { maxWidth: 220, minWidth: 180 });
        return marker;
    });

    markerCluster.addLayers(markers);

    // Fit bounds if markers exist
    if (markers.length > 0) {
        map.fitBounds(markerCluster.getBounds(), { padding: [30, 30], maxZoom: 12 });
    }
}

// --- FILTERS ---
function buildFilterParams() {
    const params = {};
    const tag = document.getElementById('filter-tag').value;
    const camera = document.getElementById('filter-camera').value;
    const dateFrom = document.getElementById('filter-date-from').value;
    const dateTo = document.getElementById('filter-date-to').value;
    const q = document.getElementById('filter-search').value.trim();
    const gps = document.getElementById('filter-gps').checked;

    if (tag) params.tag = tag;
    if (camera) params.camera = camera;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    if (q) params.q = q;
    if (gps) params.has_gps = '1';
    return params;
}

async function loadFilters() {
    const data = await fetchJSON('/api/explorer/filters');
    if (!data) return;

    const tagSelect = document.getElementById('filter-tag');
    // Combine CLIP and YOLO tags, deduplicate
    const allTags = new Map();
    (data.tags.clip || []).forEach(t => allTags.set(t.tag, (allTags.get(t.tag) || 0) + t.count));
    (data.tags.yolo || []).forEach(t => allTags.set(t.tag, (allTags.get(t.tag) || 0) + t.count));
    [...allTags.entries()]
        .sort((a, b) => b[1] - a[1])
        .forEach(([tag, count]) => {
            const opt = document.createElement('option');
            opt.value = tag;
            opt.textContent = `${tag} (${count})`;
            tagSelect.appendChild(opt);
        });

    const camSelect = document.getElementById('filter-camera');
    data.cameras.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.model;
        opt.textContent = `${c.model} (${c.count})`;
        camSelect.appendChild(opt);
    });
}

// --- PHOTO SEARCH + GRID ---
async function search() {
    const params = buildFilterParams();
    params.page = currentPage;
    params.per_page = 60;

    const qs = new URLSearchParams(params).toString();
    const data = await fetchJSON(`/api/explorer/photos?${qs}`);
    if (!data) return;

    currentPhotos = data.photos;
    totalPages = data.pages;

    document.getElementById('result-count').textContent =
        `${data.total.toLocaleString('fr-FR')} photos`;

    renderGrid();
    renderPagination(data.page, data.pages, data.total);
}

function renderGrid() {
    const grid = document.getElementById('photo-grid');

    if (currentPhotos.length === 0) {
        grid.innerHTML = '<div class="empty-state">Aucune photo ne correspond aux filtres</div>';
        return;
    }

    grid.innerHTML = currentPhotos.map((p, i) => `
        <div class="photo-card" data-index="${i}" onclick="openLightbox(${i})">
            <img data-src="${p.thumb_url}" alt="${p.filename}" class="lazy-img">
            <div class="photo-card-info">
                <div class="photo-card-name">${p.filename}</div>
                <div class="photo-card-date">${formatDate(p.date_taken)}</div>
                ${p.tags.length > 0 ? `<div class="photo-card-tags">${p.tags.slice(0, 3).map(t => `<span class="mini-tag">${t.tag}</span>`).join('')}</div>` : ''}
            </div>
        </div>
    `).join('');

    // Lazy loading with IntersectionObserver
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy-img');
                observer.unobserve(img);
            }
        });
    }, { rootMargin: '200px' });

    grid.querySelectorAll('.lazy-img').forEach(img => observer.observe(img));
}

function renderPagination(page, pages, total) {
    const el = document.getElementById('pagination');
    if (pages <= 1) { el.innerHTML = ''; return; }

    let html = '<div class="pagination">';

    if (page > 1) {
        html += `<button class="page-btn" onclick="goToPage(${page - 1})">&laquo;</button>`;
    }

    // Show pages around current
    const start = Math.max(1, page - 2);
    const end = Math.min(pages, page + 2);

    if (start > 1) html += `<button class="page-btn" onclick="goToPage(1)">1</button>`;
    if (start > 2) html += '<span class="page-dots">...</span>';

    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }

    if (end < pages - 1) html += '<span class="page-dots">...</span>';
    if (end < pages) html += `<button class="page-btn" onclick="goToPage(${pages})">${pages}</button>`;

    if (page < pages) {
        html += `<button class="page-btn" onclick="goToPage(${page + 1})">&raquo;</button>`;
    }

    html += '</div>';
    el.innerHTML = html;
}

function goToPage(page) {
    currentPage = page;
    search();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- LIGHTBOX ---
function openLightbox(index) {
    currentLightboxIndex = index;
    const photo = currentPhotos[index];
    if (!photo) return;
    showLightboxPhoto(photo);
}

async function openLightboxById(photoId) {
    // Try to find in current results first
    const idx = currentPhotos.findIndex(p => p.id === photoId);
    if (idx >= 0) {
        openLightbox(idx);
        return;
    }
    // Fetch from API
    const photo = await fetchJSON(`/api/explorer/photo/${photoId}`);
    if (photo) {
        currentLightboxIndex = -1;
        showLightboxPhoto(photo);
    }
}

function showLightboxPhoto(photo) {
    const lb = document.getElementById('lightbox');
    const img = document.getElementById('lb-img');
    const meta = document.getElementById('lb-meta');

    img.src = `/api/explorer/photo/${photo.id}/thumb?size=1200`;
    img.alt = photo.filename;

    let metaHtml = `<h3>${photo.filename}</h3>`;
    metaHtml += `<div class="lb-meta-row"><span>Date</span><strong>${formatDate(photo.date_taken)}</strong></div>`;
    if (photo.camera_model) {
        metaHtml += `<div class="lb-meta-row"><span>Camera</span><strong>${photo.camera_model}</strong></div>`;
    }
    if (photo.width && photo.height) {
        metaHtml += `<div class="lb-meta-row"><span>Taille</span><strong>${photo.width}x${photo.height}</strong></div>`;
    }
    if (photo.latitude && photo.longitude) {
        metaHtml += `<div class="lb-meta-row"><span>GPS</span><strong>${photo.latitude.toFixed(4)}, ${photo.longitude.toFixed(4)}</strong></div>`;
    }
    if (photo.altitude) {
        metaHtml += `<div class="lb-meta-row"><span>Altitude</span><strong>${Math.round(photo.altitude)} m</strong></div>`;
    }

    // Tags
    if (photo.tags && photo.tags.length > 0) {
        metaHtml += '<div class="lb-tags">';
        photo.tags.forEach(t => {
            metaHtml += `<span class="tag-chip">${t.tag}<span class="tag-count">${t.score.toFixed(2)}</span></span>`;
        });
        metaHtml += '</div>';
    }

    // Faces
    if (photo.faces && photo.faces.length > 0) {
        metaHtml += '<div class="lb-faces-section"><strong>Visages</strong>';
        photo.faces.forEach(f => {
            metaHtml += `<div class="lb-face-item">${f.label} <span style="color:var(--text-secondary)">${f.gender}, ~${f.age} ans</span></div>`;
        });
        metaHtml += '</div>';
    }

    meta.innerHTML = metaHtml;
    lb.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Show/hide nav buttons
    document.getElementById('lb-prev').style.display = currentLightboxIndex > 0 ? '' : 'none';
    document.getElementById('lb-next').style.display =
        (currentLightboxIndex >= 0 && currentLightboxIndex < currentPhotos.length - 1) ? '' : 'none';
}

function closeLightbox() {
    document.getElementById('lightbox').style.display = 'none';
    document.body.style.overflow = '';
}

function navigateLightbox(dir) {
    const newIndex = currentLightboxIndex + dir;
    if (newIndex >= 0 && newIndex < currentPhotos.length) {
        openLightbox(newIndex);
    }
}

document.addEventListener('DOMContentLoaded', init);
