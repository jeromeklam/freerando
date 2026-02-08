// Albums: create, browse, manage photos
(function () {
    let currentPage = 1;
    let currentAlbum = null;
    let albumPhotosPage = 1;

    async function init() {
        await loadAlbums();

        document.getElementById('btn-new-album').addEventListener('click', showCreateModal);
        document.getElementById('btn-cancel-album').addEventListener('click', hideCreateModal);
        document.getElementById('btn-confirm-album').addEventListener('click', createAlbum);
        document.getElementById('btn-back-albums').addEventListener('click', backToList);
        document.getElementById('btn-delete-album').addEventListener('click', deleteCurrentAlbum);

        document.getElementById('new-album-name').addEventListener('keydown', e => {
            if (e.key === 'Enter') createAlbum();
            if (e.key === 'Escape') hideCreateModal();
        });
    }

    // --- Album List ---
    async function loadAlbums() {
        const data = await fetchJSON(`/api/albums?page=${currentPage}&per_page=24`);
        if (!data) return;

        document.getElementById('album-count').textContent =
            `${data.total} album${data.total !== 1 ? 's' : ''}`;

        const grid = document.getElementById('albums-grid');
        if (data.albums.length === 0) {
            grid.innerHTML = '<div class="empty-state">Aucun album. Cliquez sur "+ Nouvel album" pour commencer.</div>';
            return;
        }

        grid.innerHTML = data.albums.map(a => {
            const coverUrl = a.cover_photo_id
                ? `/api/explorer/photo/${a.cover_photo_id}/thumb?size=300`
                : '';
            return `
                <div class="album-card" data-album-id="${a.id}">
                    <div class="album-cover ${!coverUrl ? 'album-no-cover' : ''}"
                         ${coverUrl ? `style="background-image:url(${coverUrl})"` : ''}>
                        <div class="album-cover-overlay">
                            <span class="album-photo-count">${a.photo_count} photos</span>
                        </div>
                    </div>
                    <div class="album-card-info">
                        <div class="album-card-name">${a.name}</div>
                        ${a.description ? `<div class="album-card-desc">${a.description}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        grid.querySelectorAll('.album-card').forEach(card => {
            card.addEventListener('click', () => {
                const albumId = parseInt(card.dataset.albumId);
                const album = data.albums.find(a => a.id === albumId);
                if (album) openAlbum(album);
            });
        });

        renderAlbumPagination(data.page, Math.ceil(data.total / 24), data.total);
    }

    function renderAlbumPagination(page, pages, total) {
        const el = document.getElementById('albums-pagination');
        if (pages <= 1) { el.innerHTML = ''; return; }
        let html = '<div class="pagination">';
        if (page > 1) html += `<button class="page-btn" onclick="albumGoToPage(${page - 1})">&laquo;</button>`;
        const start = Math.max(1, page - 2);
        const end = Math.min(pages, page + 2);
        for (let i = start; i <= end; i++) {
            html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="albumGoToPage(${i})">${i}</button>`;
        }
        if (page < pages) html += `<button class="page-btn" onclick="albumGoToPage(${page + 1})">&raquo;</button>`;
        html += '</div>';
        el.innerHTML = html;
    }

    window.albumGoToPage = function (page) {
        currentPage = page;
        loadAlbums();
    };

    // --- Create Album ---
    function showCreateModal() {
        document.getElementById('new-album-name').value = '';
        document.getElementById('new-album-desc').value = '';
        document.getElementById('modal-new-album').style.display = 'flex';
        document.getElementById('new-album-name').focus();
    }

    function hideCreateModal() {
        document.getElementById('modal-new-album').style.display = 'none';
    }

    async function createAlbum() {
        const name = document.getElementById('new-album-name').value.trim();
        if (!name) return;
        const desc = document.getElementById('new-album-desc').value.trim();

        const result = await fetchJSON('/api/albums', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: desc || null }),
        });

        if (result && result.ok) {
            hideCreateModal();
            await loadAlbums();
        }
    }

    // --- Album Detail ---
    async function openAlbum(album) {
        currentAlbum = album;
        albumPhotosPage = 1;

        document.getElementById('albums-view').style.display = 'none';
        document.getElementById('album-detail-view').style.display = 'block';
        document.getElementById('album-detail-name').textContent = album.name;

        await loadAlbumPhotos();
    }

    function backToList() {
        currentAlbum = null;
        document.getElementById('album-detail-view').style.display = 'none';
        document.getElementById('albums-view').style.display = 'block';
        loadAlbums();
    }

    async function loadAlbumPhotos() {
        if (!currentAlbum) return;

        const data = await fetchJSON(
            `/api/albums/${currentAlbum.id}/photos?page=${albumPhotosPage}&per_page=60`
        );
        if (!data) return;

        document.getElementById('album-detail-count').textContent =
            `${data.total} photo${data.total !== 1 ? 's' : ''}`;

        const grid = document.getElementById('album-photos-grid');
        if (data.photos.length === 0) {
            grid.innerHTML = '<div class="empty-state">Aucune photo dans cet album.</div>';
            return;
        }

        grid.innerHTML = data.photos.map(p => `
            <div class="photo-card album-photo-card" data-photo-id="${p.id}">
                <img src="${p.thumb_url}" alt="${p.filename}">
                <div class="photo-card-info">
                    <div class="photo-card-name">${p.filename}</div>
                    <div class="photo-card-date">${formatDate(p.date_taken)}</div>
                </div>
                <button class="album-photo-remove" data-photo-id="${p.id}" title="Retirer de l'album">&times;</button>
            </div>
        `).join('');

        // Remove from album
        grid.querySelectorAll('.album-photo-remove').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const photoId = btn.dataset.photoId;
                const result = await fetchJSON(
                    `/api/albums/${currentAlbum.id}/photos/${photoId}`,
                    { method: 'DELETE' }
                );
                if (result && result.ok) await loadAlbumPhotos();
            });
        });

        const pages = Math.ceil(data.total / 60);
        renderAlbumPhotosPagination(data.page, pages);
    }

    function renderAlbumPhotosPagination(page, pages) {
        const el = document.getElementById('album-photos-pagination');
        if (pages <= 1) { el.innerHTML = ''; return; }
        let html = '<div class="pagination">';
        if (page > 1) html += `<button class="page-btn" onclick="albumPhotosGoToPage(${page - 1})">&laquo;</button>`;
        for (let i = Math.max(1, page - 2); i <= Math.min(pages, page + 2); i++) {
            html += `<button class="page-btn${i === page ? ' active' : ''}" onclick="albumPhotosGoToPage(${i})">${i}</button>`;
        }
        if (page < pages) html += `<button class="page-btn" onclick="albumPhotosGoToPage(${page + 1})">&raquo;</button>`;
        html += '</div>';
        el.innerHTML = html;
    }

    window.albumPhotosGoToPage = function (page) {
        albumPhotosPage = page;
        loadAlbumPhotos();
    };

    async function deleteCurrentAlbum() {
        if (!currentAlbum) return;
        if (!confirm(`Supprimer l'album "${currentAlbum.name}" ?`)) return;

        const result = await fetchJSON(`/api/albums/${currentAlbum.id}`, {
            method: 'DELETE',
        });
        if (result && result.ok) backToList();
    }

    document.addEventListener('DOMContentLoaded', init);
})();
