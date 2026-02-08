// Explorer: Map + Photo Grid + Lightbox
let map, markerCluster;
let currentPhotos = [];
let currentPage = 1;
let totalPages = 0;
let currentLightboxIndex = -1;

let isClipSearch = false;
let zonesVisible = true;

// --- BBOX OVERLAY ---
const ANALYSIS_MAX_DIM = 2048;

function getAnalysisDims(photo) {
    const w = photo.width || 1;
    const h = photo.height || 1;
    const maxDim = Math.max(w, h);
    if (maxDim <= ANALYSIS_MAX_DIM) return { w, h };
    const scale = ANALYSIS_MAX_DIM / maxDim;
    return { w: w * scale, h: h * scale };
}

function bboxStoredToDisplay(bbox, photo) {
    const img = document.getElementById('lb-img');
    if (!img || !img.clientWidth || !img.clientHeight) return null;
    const analysis = getAnalysisDims(photo);
    const scaleX = img.clientWidth / analysis.w;
    const scaleY = img.clientHeight / analysis.h;
    return {
        x: bbox[0] * scaleX,
        y: bbox[1] * scaleY,
        w: (bbox[2] - bbox[0]) * scaleX,
        h: (bbox[3] - bbox[1]) * scaleY,
    };
}

function addBboxGroup(svg, NS, d, label, dataAttr, dataVal, cssClass, hoverIn, hoverOut) {
    const g = document.createElementNS(NS, 'g');
    g.setAttribute(dataAttr, dataVal);
    g.classList.add('bbox-group');

    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', d.x);
    rect.setAttribute('y', d.y);
    rect.setAttribute('width', d.w);
    rect.setAttribute('height', d.h);
    rect.classList.add(cssClass);
    g.appendChild(rect);

    const labelText = document.createElementNS(NS, 'text');
    labelText.setAttribute('x', d.x + 3);
    labelText.setAttribute('y', d.y - 4);
    labelText.textContent = label;
    labelText.classList.add('bbox-label');
    if (cssClass === 'bbox-tag') labelText.classList.add('bbox-label-tag');
    g.appendChild(labelText);

    const bgRect = document.createElementNS(NS, 'rect');
    bgRect.classList.add('bbox-label-bg');
    if (cssClass === 'bbox-tag') bgRect.classList.add('bbox-label-bg-tag');
    g.insertBefore(bgRect, labelText);

    rect.addEventListener('mouseenter', () => { rect.classList.add('highlighted'); hoverIn(); });
    rect.addEventListener('mouseleave', () => { rect.classList.remove('highlighted'); hoverOut(); });

    svg.appendChild(g);

    try {
        const tBox = labelText.getBBox();
        bgRect.setAttribute('x', tBox.x - 3);
        bgRect.setAttribute('y', tBox.y - 1);
        bgRect.setAttribute('width', tBox.width + 6);
        bgRect.setAttribute('height', tBox.height + 2);
    } catch (e) {
        bgRect.setAttribute('x', d.x);
        bgRect.setAttribute('y', d.y - 16);
        bgRect.setAttribute('width', label.length * 7 + 6);
        bgRect.setAttribute('height', 14);
    }
    return rect;
}

function renderOverlayBoxes(photo) {
    const svg = document.getElementById('lb-overlay');
    if (!svg) return;
    svg.innerHTML = '';

    if (!zonesVisible) return;

    const NS = 'http://www.w3.org/2000/svg';

    // Face bboxes (green)
    if (photo.faces) {
        photo.faces.forEach(f => {
            const bbox = f.bbox;
            if (!bbox || (bbox[0] === 0 && bbox[1] === 0 && bbox[2] === 0 && bbox[3] === 0)) return;
            const d = bboxStoredToDisplay(bbox, photo);
            if (!d || d.w < 2 || d.h < 2) return;

            const rect = addBboxGroup(svg, NS, d, f.label || `face_${f.face_id}`,
                'data-face-id', f.face_id, 'bbox-face',
                () => highlightFaceItem(f.face_id, true),
                () => highlightFaceItem(f.face_id, false));

            if (f.confidence !== undefined && f.confidence < 0.1) {
                rect.classList.add('manual');
            }
        });
    }

    // Tag bboxes (yellow)
    if (photo.tags) {
        photo.tags.forEach(t => {
            if (!t.bbox) return;
            const bbox = t.bbox;
            if (bbox[0] === 0 && bbox[1] === 0 && bbox[2] === 0 && bbox[3] === 0) return;
            const d = bboxStoredToDisplay(bbox, photo);
            if (!d || d.w < 2 || d.h < 2) return;

            addBboxGroup(svg, NS, d, t.label || t.tag,
                'data-tag-id', t.id, 'bbox-tag',
                () => highlightTagChip(t.id, true),
                () => highlightTagChip(t.id, false));
        });
    }
}

function highlightTagChip(tagId, on) {
    const chip = document.querySelector(`#lb-tags-list .tag-chip[data-tag-id="${tagId}"]`);
    if (chip) chip.classList.toggle('tag-zone-highlighted', on);
}

function highlightTagBbox(tagId, on) {
    const svg = document.getElementById('lb-overlay');
    if (!svg) return;
    const g = svg.querySelector(`g[data-tag-id="${tagId}"]`);
    if (g) {
        const rect = g.querySelector('.bbox-tag');
        if (rect) rect.classList.toggle('highlighted', on);
    }
}

let overlayResizeTimer = null;
window.addEventListener('resize', () => {
    clearTimeout(overlayResizeTimer);
    overlayResizeTimer = setTimeout(() => {
        if (currentLightboxPhoto && document.getElementById('lightbox').style.display !== 'none') {
            renderOverlayBoxes(currentLightboxPhoto);
        }
    }, 150);
});

// --- INIT ---
async function init() {
    initMap();
    await loadFilters();
    await search();
    await loadGeoPhotos();

    document.getElementById('btn-search').addEventListener('click', () => { isClipSearch = false; currentPage = 1; search(); loadGeoPhotos(); });
    document.getElementById('filter-search').addEventListener('keydown', e => {
        if (e.key === 'Enter') { isClipSearch = false; currentPage = 1; search(); loadGeoPhotos(); }
    });

    // CLIP search
    document.getElementById('btn-clip').addEventListener('click', clipSearch);
    document.getElementById('clip-search').addEventListener('keydown', e => {
        if (e.key === 'Enter') clipSearch();
    });

    // Lightbox controls
    document.getElementById('lb-close').addEventListener('click', closeLightbox);
    document.getElementById('lb-prev').addEventListener('click', () => navigateLightbox(-1));
    document.getElementById('lb-next').addEventListener('click', () => navigateLightbox(1));
    document.addEventListener('keydown', e => {
        if (document.getElementById('lightbox').style.display === 'none') return;
        // Don't capture keys when typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            if (e.key === 'Escape' && drawMode) { disableDrawMode(); return; }
            return;
        }
        if (e.key === 'Escape') {
            if (drawMode) { disableDrawMode(); return; }
            if (isImageZoomed) { resetImageZoom(); return; }
            closeLightbox();
        }
        if (e.key === 'd' || e.key === 'D') {
            if (drawMode) { disableDrawMode(); } else { enableDrawMode(); }
        }
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

async function clipSearch() {
    const q = document.getElementById('clip-search').value.trim();
    if (!q) return;

    isClipSearch = true;
    document.getElementById('result-count').textContent = 'Recherche CLIP...';
    document.getElementById('photo-grid').innerHTML = '<div class="empty-state">Recherche en cours (encodage CLIP)...</div>';

    const data = await fetchJSON(`/api/explorer/search/clip?q=${encodeURIComponent(q)}&limit=60`);
    if (!data) {
        document.getElementById('result-count').textContent = 'Erreur';
        return;
    }

    currentPhotos = data.photos;
    totalPages = 1;

    document.getElementById('result-count').textContent =
        `CLIP: ${data.total} résultats pour "${data.query}"`;

    renderGrid();
    document.getElementById('pagination').innerHTML = '';
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
                ${p.clip_score ? `<div class="clip-score-badge">${(p.clip_score * 100).toFixed(0)}%</div>` : ''}
                ${p.tags && p.tags.length > 0 ? `<div class="photo-card-tags">${p.tags.slice(0, 3).map(t => `<span class="mini-tag">${t.tag}</span>`).join('')}</div>` : ''}
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
async function openLightbox(index) {
    currentLightboxIndex = index;
    const photo = currentPhotos[index];
    if (!photo) return;
    // Fetch full detail (tag bboxes, face data, face_type)
    const detail = await fetchJSON(`/api/explorer/photo/${photo.id}`);
    showLightboxPhoto(detail || photo);
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
    currentLightboxPhoto = photo;
    const lb = document.getElementById('lightbox');
    const img = document.getElementById('lb-img');
    const meta = document.getElementById('lb-meta');

    // Clear previous overlay
    const svg = document.getElementById('lb-overlay');
    if (svg) svg.innerHTML = '';

    // Bind onload BEFORE setting src (avoid race with cached images)
    img.onload = () => renderOverlayBoxes(photo);
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

    // Zones toggle
    metaHtml += '<div class="lb-section-header lb-zones-toggle">';
    metaHtml += '<label class="zones-toggle-label">';
    metaHtml += `<input type="checkbox" id="cb-zones-visible" ${zonesVisible ? 'checked' : ''}>`;
    metaHtml += '<span>Zones de detection</span></label></div>';

    // Tags (interactive)
    metaHtml += '<div class="lb-tags">';
    metaHtml += '<div class="lb-section-header"><strong>Tags</strong>';
    metaHtml += `<button class="btn-add-small" id="btn-add-tag" title="Ajouter un tag">+</button></div>`;
    metaHtml += '<div id="lb-tags-list">';
    if (photo.tags && photo.tags.length > 0) {
        photo.tags.forEach(t => {
            const cls = t.confirmed ? 'tag-confirmed' : 'tag-unconfirmed';
            const display = t.label || t.tag;
            metaHtml += `<span class="tag-chip ${cls}" data-tag-id="${t.id}">`;
            metaHtml += `<span class="tag-name" data-tag-id="${t.id}" title="Clic: confirmer / Double-clic: renommer">${display}</span>`;
            metaHtml += `<span class="tag-score">${t.score.toFixed(2)}</span>`;
            metaHtml += `<span class="tag-src">${t.source}</span>`;
            metaHtml += `<button class="tag-delete" data-tag-id="${t.id}" title="Supprimer">&times;</button>`;
            metaHtml += '</span>';
        });
    } else {
        metaHtml += '<span class="tag-empty">Aucun tag</span>';
    }
    metaHtml += '</div>';
    metaHtml += '<div id="add-tag-form" style="display:none" class="add-tag-form">';
    metaHtml += '<input type="text" id="new-tag-input" placeholder="Nouveau tag..." class="tag-input">';
    metaHtml += '<input type="text" id="new-tag-label" placeholder="Label (optionnel)" class="tag-input">';
    metaHtml += '<button id="new-tag-submit" class="btn-add-small">OK</button>';
    metaHtml += '</div>';
    metaHtml += '</div>';

    // Faces (interactive)
    metaHtml += '<div class="lb-faces-section">';
    metaHtml += '<div class="lb-section-header"><strong>Visages</strong>';
    metaHtml += `<button class="btn-add-small btn-draw" id="btn-draw-face" title="Dessiner une zone (D)">&#9998;</button>`;
    metaHtml += `<button class="btn-add-small" id="btn-add-face" title="Assigner un visage">+</button></div>`;
    metaHtml += '<div id="lb-faces-list">';
    const typeIcons = {'personne': '&#128100;', 'animal': '&#128062;', 'objet': '&#128230;'};
    if (photo.faces && photo.faces.length > 0) {
        photo.faces.forEach(f => {
            const hasBbox = f.bbox && !(f.bbox[0] === 0 && f.bbox[1] === 0 && f.bbox[2] === 0 && f.bbox[3] === 0);
            const bboxIcon = hasBbox ? '' : '<span class="no-bbox-icon" title="Pas de zone definie">&#8980;</span>';
            const typeIcon = f.face_type && typeIcons[f.face_type]
                ? `<span class="face-type-icon" title="${f.face_type}">${typeIcons[f.face_type]}</span>` : '';
            metaHtml += `<div class="lb-face-item" data-face-id="${f.face_id}">`;
            if (f.face_id) {
                metaHtml += `<img src="/api/faces/${f.face_id}/crop" class="lb-face-thumb" onerror="this.style.display='none'">`;
            }
            metaHtml += `<span class="lb-face-label">${f.label}</span>`;
            metaHtml += typeIcon;
            metaHtml += bboxIcon;
            metaHtml += `<select class="face-type-dropdown" data-face-id="${f.face_id}" title="Type">
                <option value="" ${!f.face_type ? 'selected' : ''}>--</option>
                <option value="personne" ${f.face_type === 'personne' ? 'selected' : ''}>Personne</option>
                <option value="animal" ${f.face_type === 'animal' ? 'selected' : ''}>Animal</option>
                <option value="objet" ${f.face_type === 'objet' ? 'selected' : ''}>Objet</option>
            </select>`;
            metaHtml += `<button class="face-remove-btn" data-face-id="${f.face_id}" title="Retirer">&times;</button>`;
            metaHtml += '</div>';
        });
    } else {
        metaHtml += '<span class="tag-empty">Aucun visage</span>';
    }
    metaHtml += '</div>';
    metaHtml += '<div id="add-face-form" style="display:none" class="add-face-form">';
    metaHtml += '<input type="text" id="face-search-input" placeholder="Rechercher un visage..." class="tag-input" autocomplete="off">';
    metaHtml += '<div id="face-search-results" class="face-search-results"></div>';
    metaHtml += '</div>';
    metaHtml += '</div>';

    // Albums
    metaHtml += '<div class="lb-albums-section">';
    metaHtml += '<div class="lb-section-header"><strong>Albums</strong>';
    metaHtml += `<button class="btn-add-small" id="btn-add-album" title="Ajouter à un album">+</button></div>`;
    metaHtml += '<div id="lb-albums-list"><span class="tag-empty">Chargement...</span></div>';
    metaHtml += '<div id="add-album-form" style="display:none" class="add-album-form">';
    metaHtml += '<select id="album-select" class="album-select"><option value="">Choisir un album...</option></select>';
    metaHtml += '</div>';
    metaHtml += '</div>';

    meta.innerHTML = metaHtml;
    lb.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Bind tag + face + album events
    bindTagEvents(photo);
    bindFaceEvents(photo);
    loadPhotoAlbums(photo);

    // Zones toggle
    const cbZones = document.getElementById('cb-zones-visible');
    if (cbZones) {
        cbZones.addEventListener('change', () => {
            zonesVisible = cbZones.checked;
            renderOverlayBoxes(photo);
        });
    }

    // Fallback: render immediately if image already cached
    if (img.complete && img.naturalWidth > 0) {
        renderOverlayBoxes(photo);
    }

    // Show/hide nav buttons
    document.getElementById('lb-prev').style.display = currentLightboxIndex > 0 ? '' : 'none';
    document.getElementById('lb-next').style.display =
        (currentLightboxIndex >= 0 && currentLightboxIndex < currentPhotos.length - 1) ? '' : 'none';
}

function resetImageZoom() {
    const img = document.getElementById('lb-img');
    if (img) {
        img.style.transform = '';
        img.style.transformOrigin = '';
    }
    isImageZoomed = false;
}

function closeLightbox() {
    resetImageZoom();
    document.getElementById('lightbox').style.display = 'none';
    document.body.style.overflow = '';
}

function navigateLightbox(dir) {
    resetImageZoom();
    const newIndex = currentLightboxIndex + dir;
    if (newIndex >= 0 && newIndex < currentPhotos.length) {
        openLightbox(newIndex);
    }
}

// --- Tag interaction helpers ---
let currentLightboxPhoto = null;

function bindTagEvents(photo) {
    currentLightboxPhoto = photo;

    // Click tag name → toggle confirm
    document.querySelectorAll('#lb-tags-list .tag-name').forEach(el => {
        el.addEventListener('click', async () => {
            const tagId = el.dataset.tagId;
            const result = await fetchJSON(`/api/tags/${tagId}/confirm`, {
                method: 'PUT',
            });
            if (result && result.ok) {
                const chip = el.closest('.tag-chip');
                chip.classList.toggle('tag-confirmed', result.confirmed);
                chip.classList.toggle('tag-unconfirmed', !result.confirmed);
            }
        });

        // Double-click → inline label edit
        el.addEventListener('dblclick', (e) => {
            e.preventDefault();
            const tagId = el.dataset.tagId;
            const tag = photo.tags.find(t => t.id == tagId);
            if (!tag) return;
            const currentLabel = el.textContent;
            const input = document.createElement('input');
            input.type = 'text';
            input.value = currentLabel;
            input.className = 'tag-label-input';
            el.textContent = '';
            el.appendChild(input);
            input.focus();
            input.select();

            const finish = async () => {
                const newLabel = input.value.trim();
                if (newLabel && newLabel !== currentLabel) {
                    const result = await fetchJSON(`/api/tags/${tagId}/label`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ label: newLabel }),
                    });
                    el.textContent = result && result.ok ? newLabel : currentLabel;
                } else {
                    el.textContent = currentLabel;
                }
            };

            input.addEventListener('blur', finish);
            input.addEventListener('keydown', ev => {
                if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); }
                if (ev.key === 'Escape') { input.value = currentLabel; input.blur(); }
            });
        });
    });

    // Hover tag chip → highlight bbox on image
    document.querySelectorAll('#lb-tags-list .tag-chip').forEach(chip => {
        const tagId = chip.dataset.tagId;
        chip.addEventListener('mouseenter', () => highlightTagBbox(tagId, true));
        chip.addEventListener('mouseleave', () => highlightTagBbox(tagId, false));
    });

    // Delete tag
    document.querySelectorAll('#lb-tags-list .tag-delete').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const tagId = btn.dataset.tagId;
            const result = await fetchJSON(`/api/tags/${tagId}`, { method: 'DELETE' });
            if (result && result.ok) {
                btn.closest('.tag-chip').remove();
            }
        });
    });

    // Add tag button
    const btnAdd = document.getElementById('btn-add-tag');
    const addForm = document.getElementById('add-tag-form');
    if (btnAdd && addForm) {
        btnAdd.addEventListener('click', () => {
            addForm.style.display = addForm.style.display === 'none' ? 'flex' : 'none';
            if (addForm.style.display === 'flex') {
                document.getElementById('new-tag-input').focus();
            }
        });

        const submitTag = async () => {
            const tagInput = document.getElementById('new-tag-input');
            const labelInput = document.getElementById('new-tag-label');
            const tag = tagInput.value.trim();
            if (!tag) return;

            const result = await fetchJSON(`/api/photos/${photo.id}/tags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tag: tag,
                    label: labelInput.value.trim() || null
                }),
            });

            if (result && result.ok) {
                // Refresh lightbox to show new tag
                const detail = await fetchJSON(`/api/explorer/photo/${photo.id}`);
                if (detail) showLightboxPhoto(detail);
            }
            addForm.style.display = 'none';
            tagInput.value = '';
            labelInput.value = '';
        };

        document.getElementById('new-tag-submit').addEventListener('click', submitTag);
        document.getElementById('new-tag-input').addEventListener('keydown', e => {
            if (e.key === 'Enter') submitTag();
            if (e.key === 'Escape') addForm.style.display = 'none';
        });
    }
}

// --- Album interaction helpers ---
async function loadPhotoAlbums(photo) {
    const albums = await fetchJSON(`/api/photos/${photo.id}/albums`);
    const listEl = document.getElementById('lb-albums-list');
    if (!listEl) return;

    if (!albums || albums.length === 0) {
        listEl.innerHTML = '<span class="tag-empty">Aucun album</span>';
    } else {
        listEl.innerHTML = albums.map(a => `
            <div class="lb-album-item" data-album-id="${a.id}">
                <span class="lb-album-name">${a.name}</span>
                <button class="album-remove-btn" data-album-id="${a.id}" title="Retirer">&times;</button>
            </div>
        `).join('');

        listEl.querySelectorAll('.album-remove-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const albumId = btn.dataset.albumId;
                const result = await fetchJSON(`/api/albums/${albumId}/photos/${photo.id}`, {
                    method: 'DELETE',
                });
                if (result && result.ok) loadPhotoAlbums(photo);
            });
        });
    }

    // Add to album button + dropdown
    const btnAdd = document.getElementById('btn-add-album');
    const addForm = document.getElementById('add-album-form');
    const selectEl = document.getElementById('album-select');

    if (btnAdd && addForm) {
        btnAdd.addEventListener('click', async () => {
            if (addForm.style.display === 'none') {
                // Load albums for dropdown
                const allAlbums = await fetchJSON('/api/albums?per_page=100');
                if (allAlbums && allAlbums.albums) {
                    selectEl.innerHTML = '<option value="">Choisir un album...</option>';
                    allAlbums.albums.forEach(a => {
                        const opt = document.createElement('option');
                        opt.value = a.id;
                        opt.textContent = `${a.name} (${a.photo_count})`;
                        selectEl.appendChild(opt);
                    });
                }
                addForm.style.display = 'block';
            } else {
                addForm.style.display = 'none';
            }
        });

        selectEl.addEventListener('change', async () => {
            const albumId = selectEl.value;
            if (!albumId) return;
            const result = await fetchJSON(`/api/albums/${albumId}/photos`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ photo_ids: [photo.id] }),
            });
            if (result && result.ok) {
                addForm.style.display = 'none';
                loadPhotoAlbums(photo);
            }
        });
    }
}

// --- Face interaction helpers ---
let isImageZoomed = false;

function highlightBbox(faceId, on) {
    const svg = document.getElementById('lb-overlay');
    if (!svg) return;
    const g = svg.querySelector(`g[data-face-id="${faceId}"]`);
    if (g) {
        const rect = g.querySelector('.bbox-face');
        if (rect) rect.classList.toggle('highlighted', on);
    }
}

function highlightFaceItem(faceId, on) {
    const item = document.querySelector(`#lb-faces-list .lb-face-item[data-face-id="${faceId}"]`);
    if (item) item.classList.toggle('face-highlighted', on);
}

function zoomToBbox(faceId, photo) {
    const img = document.getElementById('lb-img');
    const wrapper = document.getElementById('lb-image-wrapper');
    if (!img || !wrapper) return;

    if (isImageZoomed) {
        // Reset zoom
        img.style.transform = '';
        img.style.transformOrigin = '';
        isImageZoomed = false;
        return;
    }

    const face = (photo.faces || []).find(f => f.face_id == faceId);
    if (!face || !face.bbox) return;
    const bbox = face.bbox;
    if (bbox[0] === 0 && bbox[1] === 0 && bbox[2] === 0 && bbox[3] === 0) return;

    const d = bboxStoredToDisplay(bbox, photo);
    if (!d) return;

    const centerX = d.x + d.w / 2;
    const centerY = d.y + d.h / 2;
    const originX = (centerX / img.clientWidth) * 100;
    const originY = (centerY / img.clientHeight) * 100;

    img.style.transformOrigin = `${originX}% ${originY}%`;
    img.style.transform = 'scale(2.5)';
    isImageZoomed = true;
}

function bindFaceEvents(photo) {
    // Hover panel → highlight bbox
    document.querySelectorAll('#lb-faces-list .lb-face-item').forEach(item => {
        const faceId = item.dataset.faceId;
        item.addEventListener('mouseenter', () => highlightBbox(faceId, true));
        item.addEventListener('mouseleave', () => highlightBbox(faceId, false));
        // Click → zoom to bbox
        item.addEventListener('click', (e) => {
            if (e.target.closest('.face-remove-btn')) return;
            zoomToBbox(faceId, photo);
        });
    });

    // Draw button
    const btnDraw = document.getElementById('btn-draw-face');
    if (btnDraw) {
        btnDraw.addEventListener('click', () => {
            if (drawMode) { disableDrawMode(); } else { enableDrawMode(); }
        });
    }

    // Init draw listeners on the SVG
    initDrawListeners();

    // Face type dropdowns
    document.querySelectorAll('.face-type-dropdown').forEach(select => {
        select.addEventListener('change', async (e) => {
            e.stopPropagation();
            const faceId = select.dataset.faceId;
            const faceType = select.value || null;
            await fetchJSON(`/api/faces/${faceId}/type`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ face_type: faceType }),
            });
            // Refresh to show icon
            const detail = await fetchJSON(`/api/explorer/photo/${photo.id}`);
            if (detail) showLightboxPhoto(detail);
        });
        select.addEventListener('click', e => e.stopPropagation());
    });

    // Remove face buttons
    document.querySelectorAll('#lb-faces-list .face-remove-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const faceId = btn.dataset.faceId;
            const result = await fetchJSON(`/api/photos/${photo.id}/faces/${faceId}`, {
                method: 'DELETE',
            });
            if (result && result.ok) {
                const detail = await fetchJSON(`/api/explorer/photo/${photo.id}`);
                if (detail) showLightboxPhoto(detail);
            }
        });
    });

    // Add face button → show search form
    const btnAdd = document.getElementById('btn-add-face');
    const addForm = document.getElementById('add-face-form');
    const searchInput = document.getElementById('face-search-input');
    const resultsDiv = document.getElementById('face-search-results');

    if (btnAdd && addForm) {
        btnAdd.addEventListener('click', () => {
            addForm.style.display = addForm.style.display === 'none' ? 'block' : 'none';
            if (addForm.style.display === 'block') {
                searchInput.value = '';
                resultsDiv.innerHTML = '';
                searchInput.focus();
            }
        });
    }

    // Face search autocomplete
    let searchTimeout = null;
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            const q = searchInput.value.trim();
            if (q.length < 2) {
                resultsDiv.innerHTML = '';
                return;
            }
            searchTimeout = setTimeout(async () => {
                const faces = await fetchJSON(`/api/faces/search?q=${encodeURIComponent(q)}`);
                if (!faces || faces.length === 0) {
                    resultsDiv.innerHTML = '<div class="face-search-empty">Aucun résultat</div>';
                    return;
                }
                resultsDiv.innerHTML = faces.map(f => `
                    <div class="face-search-item" data-face-id="${f.id}">
                        <img src="/api/faces/${f.id}/crop" class="face-search-thumb" onerror="this.style.display='none'">
                        <span class="face-search-name">${f.label}</span>
                        <span class="face-search-count">${f.photo_count} photos</span>
                    </div>
                `).join('');

                // Click to assign
                resultsDiv.querySelectorAll('.face-search-item').forEach(item => {
                    item.addEventListener('click', async () => {
                        const faceId = item.dataset.faceId;
                        const result = await fetchJSON(`/api/photos/${photo.id}/faces`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ face_id: parseInt(faceId) }),
                        });
                        if (result && result.ok) {
                            const detail = await fetchJSON(`/api/explorer/photo/${photo.id}`);
                            if (detail) showLightboxPhoto(detail);
                        }
                        addForm.style.display = 'none';
                    });
                });
            }, 300);
        });

        searchInput.addEventListener('keydown', e => {
            if (e.key === 'Escape') addForm.style.display = 'none';
        });
    }
}

// --- Draw mode ---
let drawMode = false;
let drawStart = null;
let drawRect = null;
let drawnBbox = null;

function bboxDisplayToStored(displayBbox, photo) {
    const img = document.getElementById('lb-img');
    if (!img || !img.clientWidth || !img.clientHeight) return null;
    const analysis = getAnalysisDims(photo);
    const scaleX = analysis.w / img.clientWidth;
    const scaleY = analysis.h / img.clientHeight;
    return [
        Math.round(displayBbox.x * scaleX),
        Math.round(displayBbox.y * scaleY),
        Math.round((displayBbox.x + displayBbox.w) * scaleX),
        Math.round((displayBbox.y + displayBbox.h) * scaleY),
    ];
}

function enableDrawMode() {
    drawMode = true;
    const svg = document.getElementById('lb-overlay');
    const wrapper = document.getElementById('lb-image-wrapper');
    if (svg) svg.style.pointerEvents = 'all';
    if (wrapper) wrapper.style.cursor = 'crosshair';
    // Show indicator
    let indicator = document.getElementById('draw-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'draw-indicator';
        indicator.className = 'draw-indicator';
        indicator.textContent = 'Tracez un rectangle sur la photo — Echap pour annuler';
        const wrapper = document.getElementById('lb-image-wrapper');
        if (wrapper) wrapper.appendChild(indicator);
    }
    indicator.style.display = 'block';
    document.getElementById('btn-draw-face')?.classList.add('active');
}

function disableDrawMode() {
    drawMode = false;
    drawStart = null;
    const svg = document.getElementById('lb-overlay');
    const wrapper = document.getElementById('lb-image-wrapper');
    if (svg) svg.style.pointerEvents = 'none';
    if (wrapper) wrapper.style.cursor = '';
    // Remove draw rect if exists
    if (drawRect) { drawRect.remove(); drawRect = null; }
    const indicator = document.getElementById('draw-indicator');
    if (indicator) indicator.style.display = 'none';
    document.getElementById('btn-draw-face')?.classList.remove('active');
    // Remove popup
    const popup = document.getElementById('draw-assign-popup');
    if (popup) popup.remove();
}

function initDrawListeners() {
    const svg = document.getElementById('lb-overlay');
    if (!svg) return;

    function getPos(e) {
        const rect = svg.getBoundingClientRect();
        if (e.touches) {
            return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
        }
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    function onStart(e) {
        if (!drawMode) return;
        e.preventDefault();
        drawStart = getPos(e);
        const NS = 'http://www.w3.org/2000/svg';
        drawRect = document.createElementNS(NS, 'rect');
        drawRect.setAttribute('x', drawStart.x);
        drawRect.setAttribute('y', drawStart.y);
        drawRect.setAttribute('width', 0);
        drawRect.setAttribute('height', 0);
        drawRect.classList.add('bbox-drawing');
        svg.appendChild(drawRect);
    }

    function onMove(e) {
        if (!drawMode || !drawStart || !drawRect) return;
        e.preventDefault();
        const pos = getPos(e);
        const x = Math.min(drawStart.x, pos.x);
        const y = Math.min(drawStart.y, pos.y);
        const w = Math.abs(pos.x - drawStart.x);
        const h = Math.abs(pos.y - drawStart.y);
        drawRect.setAttribute('x', x);
        drawRect.setAttribute('y', y);
        drawRect.setAttribute('width', w);
        drawRect.setAttribute('height', h);
    }

    function onEnd(e) {
        if (!drawMode || !drawStart || !drawRect) return;
        e.preventDefault();
        const pos = e.changedTouches ? {
            x: e.changedTouches[0].clientX - svg.getBoundingClientRect().left,
            y: e.changedTouches[0].clientY - svg.getBoundingClientRect().top,
        } : getPos(e);
        const x = Math.min(drawStart.x, pos.x);
        const y = Math.min(drawStart.y, pos.y);
        const w = Math.abs(pos.x - drawStart.x);
        const h = Math.abs(pos.y - drawStart.y);

        drawStart = null;

        if (w < 10 || h < 10) {
            if (drawRect) { drawRect.remove(); drawRect = null; }
            return;
        }

        drawnBbox = { x, y, w, h };
        showAssignPopup(drawnBbox);
    }

    // Mouse events
    svg.addEventListener('mousedown', onStart);
    svg.addEventListener('mousemove', onMove);
    svg.addEventListener('mouseup', onEnd);

    // Touch events
    svg.addEventListener('touchstart', onStart, { passive: false });
    svg.addEventListener('touchmove', onMove, { passive: false });
    svg.addEventListener('touchend', onEnd, { passive: false });
}

function showAssignPopup(displayBbox) {
    let popup = document.getElementById('draw-assign-popup');
    if (popup) popup.remove();

    const photo = currentLightboxPhoto;
    if (!photo) return;

    const storedBbox = bboxDisplayToStored(displayBbox, photo);
    if (!storedBbox) return;

    popup = document.createElement('div');
    popup.id = 'draw-assign-popup';
    popup.className = 'draw-assign-popup';

    popup.innerHTML = `
        <div class="draw-popup-header">Assigner cette zone</div>
        <div class="draw-popup-tabs">
            <button class="draw-tab active" data-tab="face">Visage</button>
            <button class="draw-tab" data-tab="tag">Tag / Objet</button>
        </div>
        <div id="draw-tab-face" class="draw-tab-content">
            <input type="text" id="draw-face-search" class="tag-input" placeholder="Nom du visage..." autocomplete="off">
            <div id="draw-face-results" class="face-search-results"></div>
            <div class="draw-face-type-row">
                <label class="draw-type-label">Type:</label>
                <select id="draw-face-type" class="tag-input draw-type-select">
                    <option value="">--</option>
                    <option value="personne">Personne</option>
                    <option value="animal">Animal</option>
                    <option value="objet">Objet</option>
                </select>
            </div>
            <div class="draw-popup-actions">
                <button id="draw-create-face" class="btn-primary btn-small">Creer</button>
                <button id="draw-cancel-face" class="btn-secondary btn-small">Annuler</button>
            </div>
        </div>
        <div id="draw-tab-tag" class="draw-tab-content" style="display:none">
            <input type="text" id="draw-tag-search" class="tag-input" placeholder="Nom du tag..." autocomplete="off">
            <div id="draw-tag-results" class="face-search-results"></div>
            <div class="draw-popup-actions">
                <button id="draw-create-tag" class="btn-primary btn-small">Ajouter</button>
                <button id="draw-cancel-tag" class="btn-secondary btn-small">Annuler</button>
            </div>
        </div>
    `;

    const wrapper = document.getElementById('lb-image-wrapper');
    if (wrapper) wrapper.appendChild(popup);

    const popupX = Math.min(displayBbox.x + displayBbox.w + 10, wrapper.clientWidth - 240);
    const popupY = Math.max(displayBbox.y, 10);
    popup.style.left = popupX + 'px';
    popup.style.top = popupY + 'px';

    // Tab switching
    popup.querySelectorAll('.draw-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            popup.querySelectorAll('.draw-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('draw-tab-face').style.display = tab.dataset.tab === 'face' ? 'block' : 'none';
            document.getElementById('draw-tab-tag').style.display = tab.dataset.tab === 'tag' ? 'block' : 'none';
            if (tab.dataset.tab === 'tag') document.getElementById('draw-tag-search').focus();
            else document.getElementById('draw-face-search').focus();
        });
    });

    // --- Face tab ---
    const faceInput = document.getElementById('draw-face-search');
    const faceResults = document.getElementById('draw-face-results');
    faceInput.focus();

    document.getElementById('draw-cancel-face').addEventListener('click', () => disableDrawMode());
    document.getElementById('draw-cancel-tag').addEventListener('click', () => disableDrawMode());

    document.getElementById('draw-create-face').addEventListener('click', async () => {
        const name = faceInput.value.trim();
        if (!name) { faceInput.focus(); return; }
        const faceType = document.getElementById('draw-face-type').value || null;

        const createResult = await fetchJSON('/api/faces', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label: name }),
        });
        if (createResult && createResult.ok) {
            if (faceType) {
                await fetchJSON(`/api/faces/${createResult.face_id}/type`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ face_type: faceType }),
                });
            }
            await assignFaceWithBbox(photo.id, createResult.face_id, storedBbox);
        }
    });

    let faceTimer = null;
    faceInput.addEventListener('input', () => {
        clearTimeout(faceTimer);
        const q = faceInput.value.trim();
        if (q.length < 2) { faceResults.innerHTML = ''; return; }
        faceTimer = setTimeout(async () => {
            const faces = await fetchJSON(`/api/faces/search?q=${encodeURIComponent(q)}`);
            if (!faces || faces.length === 0) {
                faceResults.innerHTML = '<div class="face-search-empty">Aucun visage existant</div>';
                return;
            }
            faceResults.innerHTML = faces.map(f => `
                <div class="face-search-item" data-face-id="${f.id}">
                    <img src="/api/faces/${f.id}/crop" class="face-search-thumb" onerror="this.style.display='none'">
                    <span class="face-search-name">${f.label}</span>
                    <span class="face-search-count">${f.photo_count} photos</span>
                </div>
            `).join('');
            faceResults.querySelectorAll('.face-search-item').forEach(item => {
                item.addEventListener('click', async () => {
                    await assignFaceWithBbox(photo.id, parseInt(item.dataset.faceId), storedBbox);
                });
            });
        }, 300);
    });

    // --- Tag tab ---
    const tagInput = document.getElementById('draw-tag-search');
    const tagResults = document.getElementById('draw-tag-results');

    document.getElementById('draw-create-tag').addEventListener('click', async () => {
        const tagName = tagInput.value.trim();
        if (!tagName) { tagInput.focus(); return; }
        const result = await fetchJSON(`/api/photos/${photo.id}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag: tagName, bbox: storedBbox }),
        });
        disableDrawMode();
        if (result && result.ok) {
            const detail = await fetchJSON(`/api/explorer/photo/${photo.id}`);
            if (detail) showLightboxPhoto(detail);
        }
    });

    let tagTimer = null;
    tagInput.addEventListener('input', () => {
        clearTimeout(tagTimer);
        const q = tagInput.value.trim();
        if (q.length < 2) { tagResults.innerHTML = ''; return; }
        tagTimer = setTimeout(async () => {
            const tags = await fetchJSON(`/api/tags/search?q=${encodeURIComponent(q)}`);
            if (!tags || tags.length === 0) {
                tagResults.innerHTML = '<div class="face-search-empty">Aucun tag existant</div>';
                return;
            }
            tagResults.innerHTML = tags.map(t => `
                <div class="tag-search-item" data-tag="${t.tag}">
                    <span class="tag-search-name">${t.tag}</span>
                    <span class="face-search-count">${t.count} photos</span>
                </div>
            `).join('');
            tagResults.querySelectorAll('.tag-search-item').forEach(item => {
                item.addEventListener('click', async () => {
                    const result = await fetchJSON(`/api/photos/${photo.id}/tags`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ tag: item.dataset.tag, bbox: storedBbox }),
                    });
                    disableDrawMode();
                    if (result && result.ok) {
                        const detail = await fetchJSON(`/api/explorer/photo/${photo.id}`);
                        if (detail) showLightboxPhoto(detail);
                    }
                });
            });
        }, 300);
    });

    // Keyboard
    [faceInput, tagInput].forEach(input => {
        input.addEventListener('keydown', e => {
            if (e.key === 'Escape') disableDrawMode();
        });
    });
    faceInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('draw-create-face').click();
    });
    tagInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('draw-create-tag').click();
    });
}

async function assignFaceWithBbox(photoId, faceId, bbox) {
    const result = await fetchJSON(`/api/photos/${photoId}/faces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ face_id: faceId, bbox: bbox }),
    });
    disableDrawMode();
    if (result && result.ok) {
        const detail = await fetchJSON(`/api/explorer/photo/${photoId}`);
        if (detail) showLightboxPhoto(detail);
    }
}

document.addEventListener('DOMContentLoaded', init);
