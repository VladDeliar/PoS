function sitePages() {
    return {
        // ── navigation ──────────────────────────────────────────
        view: 'list',        // 'list' | 'edit'
        editingId: null,     // null = create, string = update

        // ── list data ───────────────────────────────────────────
        pages: [],
        loading: false,

        // ── edit form ───────────────────────────────────────────
        form: {
            title: '',
            description: '',
            image_display_type: 'standard',
            cover_image: '',
            categories: [],
            sections: [],
            is_published: true,
            sort_order: 0,
        },

        // ── edit UI state ───────────────────────────────────────
        dragging: false,
        tagInput: '',
        saving: false,
        _sortablePages: null,
        _sortableSections: null,
        _previewTimer: null,

        // ── delete modal ────────────────────────────────────────
        showDeleteModal: false,
        deletingId: null,

        // ── toast ───────────────────────────────────────────────
        showToast: false,
        toastMessage: '',
        toastError: false,

        // ════════════════════════════════════════════════════════
        // Init
        // ════════════════════════════════════════════════════════

        async init() {
            await this.loadPages();
        },

        // ════════════════════════════════════════════════════════
        // Load / navigation
        // ════════════════════════════════════════════════════════

        async loadPages() {
            this.loading = true;
            try {
                const res = await fetch('/api/site-pages/');
                if (res.ok) {
                    this.pages = await res.json();
                    this.$nextTick(() => this.initSortablePages());
                }
            } catch (e) {
                console.error('loadPages error:', e);
            } finally {
                this.loading = false;
            }
        },

        openCreate() {
            this.editingId = null;
            this.form = {
                title: '',
                description: '',
                image_display_type: 'standard',
                cover_image: '',
                categories: [],
                sections: [],
                is_published: true,
                sort_order: this.pages.length,
            };
            this.view = 'edit';
            this.$nextTick(() => this.initSortableSections());
        },

        openEdit(page) {
            this.editingId = page._id;
            this.form = {
                title: page.title || '',
                description: page.description || '',
                image_display_type: page.image_display_type || 'standard',
                cover_image: page.cover_image || '',
                categories: [...(page.categories || [])],
                sections: (page.sections || []).map(s => ({
                    id: s.id,
                    title: s.title || '',
                    text: s.text || '',
                    images: [...(s.images || [])],
                    sort_order: s.sort_order || 0,
                    _open: false,
                })),
                is_published: page.is_published !== false,
                sort_order: page.sort_order || 0,
            };
            this.view = 'edit';
            this.$nextTick(() => this.initSortableSections());
        },

        // ════════════════════════════════════════════════════════
        // Save
        // ════════════════════════════════════════════════════════

        async savePage() {
            if (!this.form.title.trim()) {
                this.showNotification('Заголовок є обов\'язковим полем', true);
                return;
            }

            this.saving = true;
            try {
                const payload = {
                    title: this.form.title.trim(),
                    description: this.form.description,
                    image_display_type: this.form.image_display_type,
                    cover_image: this.form.cover_image,
                    categories: this.form.categories,
                    sections: this.form.sections.map((s, i) => ({
                        id: s.id,
                        title: s.title,
                        text: s.text,
                        images: s.images,
                        sort_order: i,
                    })),
                    is_published: this.form.is_published,
                    sort_order: this.form.sort_order,
                };

                let res;
                if (this.editingId) {
                    res = await fetch(`/api/site-pages/${this.editingId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                } else {
                    res = await fetch('/api/site-pages/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload),
                    });
                    if (res.ok) {
                        const created = await res.json();
                        this.editingId = created._id;
                    }
                }

                if (res.ok) {
                    this.showNotification('Сторінку збережено');
                    await this.loadPages();
                    this.view = 'list';
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.showNotification(err.detail || 'Помилка збереження', true);
                }
            } catch (e) {
                this.showNotification('Помилка з\'єднання', true);
            } finally {
                this.saving = false;
            }
        },

        // ════════════════════════════════════════════════════════
        // Delete
        // ════════════════════════════════════════════════════════

        openDeleteModal(id) {
            this.deletingId = id;
            this.showDeleteModal = true;
        },

        async confirmDelete() {
            if (!this.deletingId) return;
            try {
                const res = await fetch(`/api/site-pages/${this.deletingId}`, { method: 'DELETE' });
                if (res.ok) {
                    this.showNotification('Сторінку видалено');
                    this.pages = this.pages.filter(p => p._id !== this.deletingId);
                } else {
                    this.showNotification('Помилка видалення', true);
                }
            } catch (e) {
                this.showNotification('Помилка з\'єднання', true);
            } finally {
                this.showDeleteModal = false;
                this.deletingId = null;
            }
        },

        // ════════════════════════════════════════════════════════
        // Image upload — cover
        // ════════════════════════════════════════════════════════

        handleCoverDrop(event) {
            this.dragging = false;
            const file = event.dataTransfer.files[0];
            if (file) this._uploadCover(file);
        },

        onCoverInputChange(event) {
            const file = event.target.files[0];
            if (file) this._uploadCover(file);
            event.target.value = '';
        },

        async _uploadCover(file) {
            if (!this._validateFile(file)) return;

            // If creating a new page, save it first to get an ID
            if (!this.editingId) {
                if (!this.form.title.trim()) {
                    this.showNotification('Спочатку введіть заголовок для збереження', true);
                    return;
                }
                await this._createPageDraft();
                if (!this.editingId) return;
            }

            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await fetch(`/api/site-pages/${this.editingId}/upload-image`, {
                    method: 'POST',
                    body: formData,
                });
                if (res.ok) {
                    const data = await res.json();
                    this.form.cover_image = data.url;
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.showNotification(err.detail || 'Помилка завантаження', true);
                }
            } catch (e) {
                this.showNotification('Помилка завантаження', true);
            }
        },

        async removeCoverImage() {
            if (!this.form.cover_image) return;
            try {
                await fetch(`/api/site-pages/image?path=${encodeURIComponent(this.form.cover_image)}`, { method: 'DELETE' });
            } catch (e) { /* ignore */ }
            this.form.cover_image = '';
        },

        // ════════════════════════════════════════════════════════
        // Image upload — sections
        // ════════════════════════════════════════════════════════

        openSectionImagePicker(section) {
            const input = document.getElementById(`section-upload-${section.id}`);
            if (input) input.click();
        },

        async onSectionImageChange(event, section) {
            const file = event.target.files[0];
            event.target.value = '';
            if (!file || !this._validateFile(file)) return;

            if (!this.editingId) {
                if (!this.form.title.trim()) {
                    this.showNotification('Спочатку введіть заголовок для збереження', true);
                    return;
                }
                await this._createPageDraft();
                if (!this.editingId) return;
            }

            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await fetch(
                    `/api/site-pages/${this.editingId}/sections/${section.id}/upload-image`,
                    { method: 'POST', body: formData }
                );
                if (res.ok) {
                    const data = await res.json();
                    section.images = [...section.images, data.url];
                } else {
                    const err = await res.json().catch(() => ({}));
                    this.showNotification(err.detail || 'Помилка завантаження', true);
                }
            } catch (e) {
                this.showNotification('Помилка завантаження', true);
            }
        },

        async removeSectionImage(section, url) {
            try {
                await fetch(`/api/site-pages/image?path=${encodeURIComponent(url)}`, { method: 'DELETE' });
            } catch (e) { /* ignore */ }
            section.images = section.images.filter(u => u !== url);
        },

        // ════════════════════════════════════════════════════════
        // Sections CRUD
        // ════════════════════════════════════════════════════════

        addSection() {
            this.form.sections.push({
                id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2),
                title: '',
                text: '',
                images: [],
                sort_order: this.form.sections.length,
                _open: true,
            });
            this.$nextTick(() => this.initSortableSections());
        },

        removeSection(idx) {
            this.form.sections.splice(idx, 1);
        },

        // ════════════════════════════════════════════════════════
        // Tags
        // ════════════════════════════════════════════════════════

        addTag() {
            const tag = this.tagInput.trim();
            if (tag && !this.form.categories.includes(tag)) {
                this.form.categories.push(tag);
            }
            this.tagInput = '';
        },

        addTagOnEnter(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                this.addTag();
            }
        },

        removeTag(tag) {
            this.form.categories = this.form.categories.filter(t => t !== tag);
        },

        // ════════════════════════════════════════════════════════
        // Published toggle (from list view)
        // ════════════════════════════════════════════════════════

        async togglePublished(page) {
            try {
                const res = await fetch(`/api/site-pages/${page._id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_published: !page.is_published }),
                });
                if (res.ok) {
                    page.is_published = !page.is_published;
                }
            } catch (e) { /* ignore */ }
        },

        // ════════════════════════════════════════════════════════
        // Sortable — pages list
        // ════════════════════════════════════════════════════════

        initSortablePages() {
            const el = document.getElementById('pages-sortable');
            if (!el || typeof Sortable === 'undefined') return;

            if (this._sortablePages) {
                this._sortablePages.destroy();
            }

            this._sortablePages = Sortable.create(el, {
                handle: '.drag-handle',
                animation: 150,
                ghostClass: 'sortable-ghost',
                chosenClass: 'sortable-chosen',
                onEnd: () => this.savePageOrder(),
            });
        },

        async savePageOrder() {
            const el = document.getElementById('pages-sortable');
            if (!el) return;

            const ids = Array.from(el.children).map(node => node.dataset.id);
            const items = ids.map((id, index) => ({ id, sort_order: index }));

            // Update local pages array to match new order
            const pageMap = Object.fromEntries(this.pages.map(p => [p._id, p]));
            this.pages = ids.map(id => pageMap[id]).filter(Boolean);

            try {
                await fetch('/api/site-pages/reorder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(items),
                });
            } catch (e) { /* ignore */ }
        },

        // ════════════════════════════════════════════════════════
        // Sortable — sections inside edit form
        // ════════════════════════════════════════════════════════

        initSortableSections() {
            const el = document.getElementById('sections-sortable');
            if (!el || typeof Sortable === 'undefined') return;

            if (this._sortableSections) {
                this._sortableSections.destroy();
            }

            this._sortableSections = Sortable.create(el, {
                handle: '.drag-handle',
                animation: 150,
                ghostClass: 'sortable-ghost',
                chosenClass: 'sortable-chosen',
                onEnd: () => this.syncSectionsOrder(),
            });
        },

        syncSectionsOrder() {
            const el = document.getElementById('sections-sortable');
            if (!el) return;
            const ids = Array.from(el.children).map(node => node.dataset.id);
            const sectionMap = Object.fromEntries(this.form.sections.map(s => [s.id, s]));
            this.form.sections = ids.map(id => sectionMap[id]).filter(Boolean);
        },

        // ════════════════════════════════════════════════════════
        // Helpers
        // ════════════════════════════════════════════════════════

        _validateFile(file) {
            const ext = file.name.split('.').pop().toLowerCase();
            if (!['jpg', 'jpeg', 'png'].includes(ext)) {
                this.showNotification('Тільки JPG або PNG файли', true);
                return false;
            }
            if (file.size > 3 * 1024 * 1024) {
                this.showNotification('Файл занадто великий (макс. 3 МБ)', true);
                return false;
            }
            return true;
        },

        async _createPageDraft() {
            try {
                const res = await fetch('/api/site-pages/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: this.form.title.trim() || 'Нова сторінка',
                        description: this.form.description,
                        image_display_type: this.form.image_display_type,
                        cover_image: '',
                        categories: this.form.categories,
                        sections: [],
                        is_published: false,
                        sort_order: this.pages.length,
                    }),
                });
                if (res.ok) {
                    const created = await res.json();
                    this.editingId = created._id;
                }
            } catch (e) { /* ignore */ }
        },

        showNotification(message, isError = false) {
            this.toastMessage = message;
            this.toastError = isError;
            this.showToast = true;
            setTimeout(() => { this.showToast = false; }, 3000);
        },
    };
}
