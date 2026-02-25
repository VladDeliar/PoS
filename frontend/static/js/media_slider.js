function mediaSlider() {
    return {
        // ── state ──────────────────────────────────────────
        enabled: false,
        items: [],      // [{id, type, url?, name?, image?, product_id?, sort_order}]
        saving: false,

        // ── upload ─────────────────────────────────────────
        uploading: false,
        uploadDragging: false,

        // ── dish search ────────────────────────────────────
        dishSearch: '',
        allMenuItems: [],
        filteredDishes: [],
        menuItemsLoading: false,
        menuItemsLoaded: false,

        // ── drag-to-reorder ────────────────────────────────
        dragSrcIdx: null,
        dragOverIdx: null,

        // ── toast ──────────────────────────────────────────
        showToast: false,
        toastMsg: '',
        toastError: false,

        // ════════════════════════════════════════════════════
        // Init
        // ════════════════════════════════════════════════════
        async init() {
            await this.loadConfig();
            await this.loadMenuItems();
        },

        // ════════════════════════════════════════════════════
        // Load config from server
        // ════════════════════════════════════════════════════
        async loadConfig() {
            try {
                const res = await fetch('/api/settings/media-slider');
                if (res.ok) {
                    const data = await res.json();
                    this.enabled = data.enabled || false;
                    this.items = (data.items || [])
                        .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
                }
            } catch (e) {
                console.error('loadConfig error:', e);
            }
        },

        // ════════════════════════════════════════════════════
        // Load menu items for dish search
        // ════════════════════════════════════════════════════
        async loadMenuItems() {
            if (this.menuItemsLoaded) return;
            this.menuItemsLoading = true;
            try {
                const res = await fetch('/api/menu-items?active_only=true');
                if (res.ok) {
                    const data = await res.json();
                    // Normalize: menu-items endpoint returns joined objects with _id from product
                    this.allMenuItems = data.filter(d => d.item_type !== 'combo' && d.image);
                    this.menuItemsLoaded = true;
                }
            } catch (e) {
                console.error('loadMenuItems error:', e);
            } finally {
                this.menuItemsLoading = false;
            }
        },

        // ════════════════════════════════════════════════════
        // Dish search (client-side filter)
        // ════════════════════════════════════════════════════
        filterDishes() {
            const q = this.dishSearch.trim().toLowerCase();
            if (!q) {
                this.filteredDishes = [];
                return;
            }
            const addedIds = new Set(
                this.items.filter(i => i.type === 'dish').map(i => i.product_id)
            );
            this.filteredDishes = this.allMenuItems
                .filter(d => {
                    const name = (d.name || '').toLowerCase();
                    return name.includes(q) && !addedIds.has(d._id || d.product_id);
                })
                .slice(0, 10);
        },

        addDishItem(dish) {
            this.items.push({
                id: this._genId(),
                type: 'dish',
                product_id: dish._id || dish.product_id,
                name: dish.name,
                image: dish.image || '',
                sort_order: this.items.length
            });
            this.dishSearch = '';
            this.filteredDishes = [];
        },

        // ════════════════════════════════════════════════════
        // File upload
        // ════════════════════════════════════════════════════
        onFileInputChange(event) {
            const file = event.target.files[0];
            if (file) this._uploadFile(file);
            event.target.value = '';
        },

        handleFileDrop(event) {
            this.uploadDragging = false;
            const file = event.dataTransfer.files[0];
            if (file) this._uploadFile(file);
        },

        async _uploadFile(file) {
            this.uploading = true;
            try {
                const formData = new FormData();
                formData.append('file', file);
                const res = await fetch('/api/settings/media-slider/upload', {
                    method: 'POST',
                    body: formData
                });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    this._toast(err.detail || 'Помилка завантаження', true);
                    return;
                }
                const data = await res.json();
                this.items.push({
                    id: this._genId(),
                    type: 'image',
                    url: data.url,
                    sort_order: this.items.length
                });
            } catch (e) {
                this._toast('Помилка завантаження файлу', true);
            } finally {
                this.uploading = false;
            }
        },

        // ════════════════════════════════════════════════════
        // Remove item
        // ════════════════════════════════════════════════════
        async removeItem(idx) {
            const item = this.items[idx];
            if (item.type === 'image' && item.url) {
                fetch('/api/settings/media-slider/image?path=' + encodeURIComponent(item.url), {
                    method: 'DELETE'
                }).catch(e => console.warn('File delete error:', e));
            }
            this.items.splice(idx, 1);
            this.items.forEach((it, i) => { it.sort_order = i; });
        },

        // ════════════════════════════════════════════════════
        // Drag-to-reorder (native HTML5)
        // ════════════════════════════════════════════════════
        onDragStart(event, idx) {
            this.dragSrcIdx = idx;
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', String(idx));
        },

        onDragOver(event, idx) {
            event.dataTransfer.dropEffect = 'move';
            this.dragOverIdx = idx;
        },

        onDrop(event, idx) {
            if (this.dragSrcIdx === null || this.dragSrcIdx === idx) {
                this.dragSrcIdx = null;
                this.dragOverIdx = null;
                return;
            }
            const moved = this.items.splice(this.dragSrcIdx, 1)[0];
            this.items.splice(idx, 0, moved);
            this.items.forEach((it, i) => { it.sort_order = i; });
            this.dragSrcIdx = null;
            this.dragOverIdx = null;
        },

        onDragEnd() {
            this.dragSrcIdx = null;
            this.dragOverIdx = null;
        },

        // ════════════════════════════════════════════════════
        // Save
        // ════════════════════════════════════════════════════
        async save() {
            this.saving = true;
            try {
                const payload = {
                    enabled: this.enabled,
                    items: this.items.map((it, i) => ({ ...it, sort_order: i }))
                };
                const res = await fetch('/api/settings/media-slider', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    this._toast('Збережено!');
                } else {
                    this._toast('Помилка збереження', true);
                }
            } catch (e) {
                this._toast('Помилка збереження', true);
            } finally {
                this.saving = false;
            }
        },

        // ════════════════════════════════════════════════════
        // Helpers
        // ════════════════════════════════════════════════════
        _genId() {
            return Math.random().toString(36).slice(2, 10);
        },

        _toast(msg, isError = false) {
            this.toastMsg = msg;
            this.toastError = isError;
            this.showToast = true;
            setTimeout(() => { this.showToast = false; }, 3000);
        }
    };
}
