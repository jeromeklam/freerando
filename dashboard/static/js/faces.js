/**
 * Faces management: grid, rename, merge, browse photos.
 */
(function () {
    'use strict';

    let faces = [];
    let currentPage = 1;
    let totalPages = 0;
    let selected = new Set();  // face IDs selected for merge
    let viewingFaceId = null;  // when browsing a face's photos
    let facePhotosPage = 1;

    const grid = document.getElementById('faces-grid');
    const totalEl = document.getElementById('faces-total');
    const paginationEl = document.getElementById('faces-pagination');
    const btnMerge = document.getElementById('btn-merge');
    const photosPanel = document.getElementById('face-photos-panel');
    const btnBack = document.getElementById('btn-back-faces');
    const photosTitle = document.getElementById('face-photos-title');
    const photosCount = document.getElementById('face-photos-count');
    const photosGrid = document.getElementById('face-photos-grid');
    const photosPagination = document.getElementById('face-photos-pagination');
    const mergeModal = document.getElementById('merge-modal');
    const mergeModalText = document.getElementById('merge-modal-text');
    const mergeCancel = document.getElementById('merge-cancel');
    const mergeConfirm = document.getElementById('merge-confirm');

    // --- Load faces ---
    async function loadFaces(page) {
        currentPage = page || 1;
        try {
            const data = await fetchJSON(`/api/faces?page=${currentPage}&per_page=24`);
            faces = data.faces;
            totalPages = Math.ceil(data.total / data.per_page);
            totalEl.textContent = `${data.total} visage${data.total !== 1 ? 's' : ''}`;
            renderGrid();
            renderPagination(paginationEl, currentPage, totalPages, loadFaces);
        } catch (e) {
            grid.innerHTML = '<div class="empty-state">Erreur de chargement des visages</div>';
        }
    }

    // --- Render face cards ---
    function renderGrid() {
        if (!faces.length) {
            grid.innerHTML = '<div class="empty-state">Aucun visage détecté</div>';
            return;
        }

        grid.innerHTML = faces.map(f => {
            const isSelected = selected.has(f.id);
            const meta = [];
            if (f.age_estimate) meta.push(f.age_estimate);
            if (f.gender_estimate) meta.push(f.gender_estimate === 'M' ? 'Homme' : 'Femme');

            return `
                <div class="face-card ${isSelected ? 'face-card-selected' : ''}"
                     data-face-id="${f.id}">
                    <div class="face-card-select" title="Sélectionner pour fusion">
                        <input type="checkbox" ${isSelected ? 'checked' : ''}
                               data-select-face="${f.id}">
                    </div>
                    <div class="face-crop-wrapper" data-browse="${f.id}">
                        <img src="/api/faces/${f.id}/crop" alt="${f.label}"
                             loading="lazy" class="face-crop-img">
                    </div>
                    <div class="face-card-info">
                        <div class="face-card-label" data-edit-face="${f.id}"
                             title="Cliquer pour renommer">${f.label}</div>
                        ${meta.length ? `<div class="face-card-meta">${meta.join(' · ')}</div>` : ''}
                        <div class="face-card-count">${f.photo_count} photo${f.photo_count !== 1 ? 's' : ''}</div>
                    </div>
                </div>
            `;
        }).join('');

        // Bind events
        grid.querySelectorAll('[data-select-face]').forEach(cb => {
            cb.addEventListener('change', e => {
                const fid = parseInt(e.target.dataset.selectFace);
                if (e.target.checked) selected.add(fid);
                else selected.delete(fid);
                updateMergeButton();
                e.target.closest('.face-card').classList.toggle('face-card-selected', e.target.checked);
            });
        });

        grid.querySelectorAll('[data-browse]').forEach(el => {
            el.addEventListener('click', () => {
                const fid = parseInt(el.dataset.browse);
                showFacePhotos(fid);
            });
        });

        grid.querySelectorAll('[data-edit-face]').forEach(el => {
            el.addEventListener('click', () => {
                const fid = parseInt(el.dataset.editFace);
                startRename(el, fid);
            });
        });
    }

    // --- Rename inline ---
    function startRename(el, faceId) {
        const currentLabel = el.textContent;
        const input = document.createElement('input');
        input.type = 'text';
        input.value = currentLabel;
        input.className = 'face-rename-input';
        el.textContent = '';
        el.appendChild(input);
        input.focus();
        input.select();

        const finish = async () => {
            const newLabel = input.value.trim();
            if (newLabel && newLabel !== currentLabel) {
                try {
                    await fetchJSON(`/api/faces/${faceId}/label`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ label: newLabel }),
                    });
                    el.textContent = newLabel;
                    // Update in local array
                    const f = faces.find(f => f.id === faceId);
                    if (f) f.label = newLabel;
                } catch {
                    el.textContent = currentLabel;
                }
            } else {
                el.textContent = currentLabel;
            }
        };

        input.addEventListener('blur', finish);
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
            if (e.key === 'Escape') { input.value = currentLabel; input.blur(); }
        });
    }

    // --- Merge ---
    function updateMergeButton() {
        btnMerge.disabled = selected.size < 2;
        btnMerge.textContent = selected.size >= 2
            ? `Fusionner ${selected.size} visages`
            : 'Fusionner la sélection';
    }

    btnMerge.addEventListener('click', () => {
        if (selected.size < 2) return;
        const ids = [...selected];
        const targetId = ids[0];
        const targetFace = faces.find(f => f.id === targetId);
        mergeModalText.innerHTML = `
            Fusionner <strong>${selected.size} visages</strong> en un seul.<br>
            Le visage cible sera : <strong>${targetFace ? targetFace.label : 'ID ' + targetId}</strong><br>
            <small>Les ${selected.size - 1} autre(s) seront supprimé(s).</small>
        `;
        mergeModal.style.display = 'flex';
    });

    mergeCancel.addEventListener('click', () => {
        mergeModal.style.display = 'none';
    });

    mergeConfirm.addEventListener('click', async () => {
        mergeModal.style.display = 'none';
        const ids = [...selected];
        const targetId = ids[0];
        const sourceIds = ids.slice(1);
        try {
            await fetchJSON('/api/faces/merge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_ids: sourceIds, target_id: targetId }),
            });
            selected.clear();
            updateMergeButton();
            loadFaces(currentPage);
        } catch (e) {
            console.error('Merge error:', e);
        }
    });

    // --- Browse face photos ---
    async function showFacePhotos(faceId) {
        viewingFaceId = faceId;
        facePhotosPage = 1;

        grid.style.display = 'none';
        paginationEl.style.display = 'none';
        document.querySelector('.faces-toolbar').style.display = 'none';
        photosPanel.style.display = 'block';

        const face = faces.find(f => f.id === faceId);
        photosTitle.textContent = face ? face.label : `Visage #${faceId}`;

        await loadFacePhotos();
    }

    async function loadFacePhotos() {
        try {
            const data = await fetchJSON(
                `/api/faces/${viewingFaceId}/photos?page=${facePhotosPage}&per_page=50`
            );
            photosCount.textContent = `${data.total} photo${data.total !== 1 ? 's' : ''}`;
            const totalPg = Math.ceil(data.total / data.per_page);

            if (!data.photos.length) {
                photosGrid.innerHTML = '<div class="empty-state">Aucune photo</div>';
            } else {
                photosGrid.innerHTML = data.photos.map(p => `
                    <div class="photo-card">
                        <img src="${p.thumb_url}" alt="${p.filename}" loading="lazy">
                        <div class="photo-card-info">
                            <div class="photo-card-name">${p.filename}</div>
                            <div class="photo-card-date">${p.date_taken ? formatDate(p.date_taken) : ''}</div>
                        </div>
                    </div>
                `).join('');
            }

            renderPagination(photosPagination, facePhotosPage, totalPg, pg => {
                facePhotosPage = pg;
                loadFacePhotos();
            });
        } catch {
            photosGrid.innerHTML = '<div class="empty-state">Erreur de chargement</div>';
        }
    }

    btnBack.addEventListener('click', () => {
        photosPanel.style.display = 'none';
        grid.style.display = '';
        paginationEl.style.display = '';
        document.querySelector('.faces-toolbar').style.display = '';
        viewingFaceId = null;
    });

    // --- Pagination helper ---
    function renderPagination(container, page, pages, callback) {
        if (pages <= 1) { container.innerHTML = ''; return; }

        let html = '<div class="pagination">';
        const range = 2;
        for (let i = 1; i <= pages; i++) {
            if (i === 1 || i === pages || (i >= page - range && i <= page + range)) {
                html += `<button class="page-btn ${i === page ? 'active' : ''}" data-page="${i}">${i}</button>`;
            } else if (i === page - range - 1 || i === page + range + 1) {
                html += '<span class="page-dots">…</span>';
            }
        }
        html += '</div>';
        container.innerHTML = html;

        container.querySelectorAll('.page-btn').forEach(btn => {
            btn.addEventListener('click', () => callback(parseInt(btn.dataset.page)));
        });
    }

    // --- Init ---
    loadFaces(1);
})();
