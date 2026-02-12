function pageBuilderApp() {
    return {
        config: {
            version: 2,
            sections: [],
            branding: { accentColor: '#4CAF50', fontFamily: 'system', borderRadius: 'default' },
            globalSettings: {}
        },

        // UI state
        previewViewport: 'desktop',
        editingItem: null,
        showBrandingPanel: false,
        showAddElement: false,
        showColumnPicker: false,
        addElementTarget: null,
        columnPickerTarget: null,

        // Undo/Redo
        history: [],
        historyIndex: -1,

        // Save state
        saving: false,
        showToast: false,
        toastMessage: '',
        toastError: false,

        // Color presets
        colorPresets: [
            { hex: '#4CAF50', name: 'Green' },
            { hex: '#5E8B45', name: 'Clover Green' },
            { hex: '#2196F3', name: 'Blue' },
            { hex: '#FF5722', name: 'Deep Orange' },
            { hex: '#9C27B0', name: 'Purple' },
            { hex: '#D32F2F', name: 'Red' },
            { hex: '#FF9800', name: 'Amber' },
            { hex: '#607D8B', name: 'Blue Grey' }
        ],

        // Element defaults
        elementDefaults: {
            text: { content: '<p>Enter text here...</p>', fontSize: '16px', color: '', textAlign: 'left', padding: '16px' },
            image: { imageUrl: '', altText: '', linkUrl: '', width: '100%', borderRadius: '8px' },
            menu: { productViewMode: 'list', navPosition: 'sidebar', cardStyle: 'default' },
            announcement: { text: 'Your announcement here', bgColor: '#FFF3E0', textColor: '#E65100' },
            hours: { showIcon: true },
            address: { showMap: false, showCopyButton: true },
            phone: { showCopyButton: true },
            social: { links: [], layout: 'horizontal' },
            spacer: { height: '40px', showDivider: false, dividerColor: '#e0e0e0' },
            map: { googleMapsEmbedUrl: '', height: '300px' },
            custom_html: { htmlContent: '' },
        },

        elementLabels: {
            text: 'Text',
            image: 'Image',
            menu: 'Product Menu',
            announcement: 'Announcement',
            hours: 'Hours',
            address: 'Address',
            phone: 'Phone',
            social: 'Social Links',
            spacer: 'Spacer',
            map: 'Map',
            custom_html: 'Custom HTML',
        },

        // Init
        async init() {
            await this.loadConfig();
            this.pushHistory();
        },

        async loadConfig() {
            try {
                const res = await fetch('/api/settings/storefront');
                if (res.ok) {
                    const data = await res.json();
                    if (data.version === 2 && data.sections) {
                        this.config = data;
                    } else {
                        this.config = this.getDefaultConfig();
                    }
                } else {
                    this.config = this.getDefaultConfig();
                }
            } catch (err) {
                console.error('Failed to load config:', err);
                this.config = this.getDefaultConfig();
            }
            if (!this.config.branding) {
                this.config.branding = { accentColor: '#4CAF50', fontFamily: 'system', borderRadius: 'default' };
            }
            if (!this.config.globalSettings) {
                this.config.globalSettings = {};
            }
        },

        getDefaultConfig() {
            return {
                version: 2,
                sections: [
                    {
                        id: this.uid(), label: 'Menu', collapsed: false, visible: true, sort_order: 0, settings: {},
                        rows: [{
                            id: this.uid(), visible: true, sort_order: 0, settings: {},
                            columns: [{
                                id: this.uid(), width: '1/1', sort_order: 0, settings: {},
                                elements: [{
                                    id: this.uid(), type: 'menu', label: 'Product Menu', visible: true, sort_order: 0,
                                    settings: { productViewMode: 'list', navPosition: 'sidebar', cardStyle: 'default' }
                                }]
                            }]
                        }]
                    },
                    {
                        id: this.uid(), label: 'Footer', collapsed: false, visible: true, sort_order: 1, settings: {},
                        rows: [{
                            id: this.uid(), visible: true, sort_order: 0, settings: {},
                            columns: [
                                {
                                    id: this.uid(), width: '1/3', sort_order: 0, settings: {},
                                    elements: [{ id: this.uid(), type: 'hours', label: 'Hours', visible: true, sort_order: 0, settings: { showIcon: true } }]
                                },
                                {
                                    id: this.uid(), width: '1/3', sort_order: 1, settings: {},
                                    elements: [{ id: this.uid(), type: 'address', label: 'Address', visible: true, sort_order: 0, settings: { showMap: false, showCopyButton: true } }]
                                },
                                {
                                    id: this.uid(), width: '1/3', sort_order: 2, settings: {},
                                    elements: [{ id: this.uid(), type: 'phone', label: 'Phone', visible: true, sort_order: 0, settings: { showCopyButton: true } }]
                                }
                            ]
                        }]
                    }
                ],
                branding: { accentColor: '#4CAF50', fontFamily: 'system', borderRadius: 'default' },
                globalSettings: {}
            };
        },

        uid() {
            return Math.random().toString(36).substring(2, 10);
        },

        // ---- CRUD ----

        addSection() {
            this.pushHistory();
            this.config.sections.push({
                id: this.uid(),
                label: 'New Section',
                collapsed: false,
                visible: true,
                sort_order: this.config.sections.length,
                settings: {},
                rows: [{
                    id: this.uid(), visible: true, sort_order: 0, settings: {},
                    columns: [{
                        id: this.uid(), width: '1/1', sort_order: 0, settings: {},
                        elements: []
                    }]
                }]
            });
        },

        addRow(sectionIndex) {
            this.pushHistory();
            const section = this.config.sections[sectionIndex];
            section.rows.push({
                id: this.uid(),
                visible: true,
                sort_order: section.rows.length,
                settings: {},
                columns: [{
                    id: this.uid(), width: '1/1', sort_order: 0, settings: {},
                    elements: []
                }]
            });
        },

        openAddElement(si, ri, ci) {
            this.addElementTarget = { si, ri, ci };
            this.showAddElement = true;
        },

        addElement(type) {
            if (!this.addElementTarget) return;
            this.pushHistory();
            const { si, ri, ci } = this.addElementTarget;
            const col = this.config.sections[si].rows[ri].columns[ci];
            const defaults = JSON.parse(JSON.stringify(this.elementDefaults[type] || {}));
            col.elements.push({
                id: this.uid(),
                type: type,
                label: this.elementLabels[type] || type,
                visible: true,
                sort_order: col.elements.length,
                settings: defaults
            });
            this.showAddElement = false;
            this.addElementTarget = null;
        },

        deleteSection(si) {
            this.pushHistory();
            this.config.sections.splice(si, 1);
            this.editingItem = null;
        },

        deleteRow(si, ri) {
            this.pushHistory();
            this.config.sections[si].rows.splice(ri, 1);
            this.editingItem = null;
        },

        deleteElement(si, ri, ci, ei) {
            this.pushHistory();
            this.config.sections[si].rows[ri].columns[ci].elements.splice(ei, 1);
            this.editingItem = null;
        },

        duplicateSection(si) {
            this.pushHistory();
            const clone = JSON.parse(JSON.stringify(this.config.sections[si]));
            this.reassignIds(clone);
            clone.label += ' (copy)';
            this.config.sections.splice(si + 1, 0, clone);
        },

        duplicateRow(si, ri) {
            this.pushHistory();
            const clone = JSON.parse(JSON.stringify(this.config.sections[si].rows[ri]));
            this.reassignIds(clone);
            this.config.sections[si].rows.splice(ri + 1, 0, clone);
        },

        duplicateElement(si, ri, ci, ei) {
            this.pushHistory();
            const clone = JSON.parse(JSON.stringify(this.config.sections[si].rows[ri].columns[ci].elements[ei]));
            clone.id = this.uid();
            clone.label += ' (copy)';
            this.config.sections[si].rows[ri].columns[ci].elements.splice(ei + 1, 0, clone);
        },

        reassignIds(obj) {
            if (obj.id) obj.id = this.uid();
            if (obj.rows) obj.rows.forEach(r => this.reassignIds(r));
            if (obj.columns) obj.columns.forEach(c => this.reassignIds(c));
            if (obj.elements) obj.elements.forEach(e => { e.id = this.uid(); });
        },

        moveElement(si, ri, ci, ei, direction) {
            const elements = this.config.sections[si].rows[ri].columns[ci].elements;
            const newIndex = ei + direction;
            if (newIndex < 0 || newIndex >= elements.length) return;
            this.pushHistory();
            const el = elements.splice(ei, 1)[0];
            elements.splice(newIndex, 0, el);
        },

        // ---- Column Layout ----

        openColumnLayoutPicker(section, row) {
            this.columnPickerTarget = { section, row };
            this.showColumnPicker = true;
        },

        setColumnLayout(widths) {
            if (!this.columnPickerTarget) return;
            this.pushHistory();
            const row = this.columnPickerTarget.row;
            const existingElements = [];
            row.columns.forEach(col => {
                existingElements.push(...col.elements);
            });

            row.columns = widths.map((w, i) => ({
                id: this.uid(),
                width: w,
                sort_order: i,
                settings: {},
                elements: i === 0 ? existingElements : []
            }));

            this.showColumnPicker = false;
            this.columnPickerTarget = null;
        },

        getColumnFlex(width) {
            const map = { '1/1': 1, '1/2': 1, '1/3': 1, '2/3': 2, '1/4': 1, '3/4': 3 };
            return map[width] || 1;
        },

        // ---- Settings Panel ----

        openSectionSettings(section) {
            this.showBrandingPanel = false;
            section._settingsType = 'section';
            this.editingItem = section;
        },

        openRowSettings(section, row) {
            this.showBrandingPanel = false;
            row._settingsType = 'row';
            this.editingItem = row;
        },

        openElementSettings(section, row, col, element) {
            this.showBrandingPanel = false;
            element._settingsType = 'element';
            this.editingItem = element;
        },

        getSettingsPanelTitle() {
            if (!this.editingItem) return '';
            if (this.editingItem._settingsType === 'section') return 'Section: ' + this.editingItem.label;
            if (this.editingItem._settingsType === 'row') return 'Row Settings';
            if (this.editingItem._settingsType === 'element') return this.getElementLabel(this.editingItem.type) + ' Settings';
            return 'Settings';
        },

        editSectionLabel(section) {
            const newLabel = prompt('Section label:', section.label);
            if (newLabel !== null && newLabel.trim()) {
                this.pushHistory();
                section.label = newLabel.trim();
            }
        },

        highlightSection(section) {
            // Could highlight the section in the tree
        },

        // ---- Element Icons & Labels ----

        getElementLabel(type) {
            return this.elementLabels[type] || type;
        },

        getElementIcon(type) {
            const icons = {
                text: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M5,4V7H10.5V19H13.5V7H19V4H5Z"/></svg>',
                image: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19,19H5V5H19M19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3M13.96,12.29L11.21,15.83L9.25,13.47L6.5,17H17.5L13.96,12.29Z"/></svg>',
                menu: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M3,5H9V11H3V5M5,7V9H7V7H5M11,7H21V9H11V7M11,15H21V17H11V15M5,20L1.5,16.5L2.91,15.09L5,17.17L9.59,12.59L11,14L5,20Z"/></svg>',
                announcement: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M20,2H4A2,2 0 0,0 2,4V22L6,18H20A2,2 0 0,0 22,16V4A2,2 0 0,0 20,2M20,16H6L4,18V4H20"/></svg>',
                hours: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M16.2,16.2L11,13V7H12.5V12.2L17,14.9L16.2,16.2Z"/></svg>',
                address: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5M12,2A7,7 0 0,0 5,9C5,14.25 12,22 12,22C12,22 19,14.25 19,9A7,7 0 0,0 12,2Z"/></svg>',
                phone: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M6.62,10.79C8.06,13.62 10.38,15.94 13.21,17.38L15.41,15.18C15.69,14.9 16.08,14.82 16.43,14.93C17.55,15.3 18.75,15.5 20,15.5A1,1 0 0,1 21,16.5V20A1,1 0 0,1 20,21A17,17 0 0,1 3,4A1,1 0 0,1 4,3H7.5A1,1 0 0,1 8.5,4C8.5,5.25 8.7,6.45 9.07,7.57C9.18,7.92 9.1,8.31 8.82,8.59L6.62,10.79Z"/></svg>',
                social: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M18,16.08C17.24,16.08 16.56,16.38 16.04,16.85L8.91,12.7C8.96,12.47 9,12.24 9,12C9,11.76 8.96,11.53 8.91,11.3L15.96,7.19C16.5,7.69 17.21,8 18,8A3,3 0 0,0 21,5A3,3 0 0,0 18,2A3,3 0 0,0 15,5C15,5.24 15.04,5.47 15.09,5.7L8.04,9.81C7.5,9.31 6.79,9 6,9A3,3 0 0,0 3,12A3,3 0 0,0 6,15C6.79,15 7.5,14.69 8.04,14.19L15.16,18.34C15.11,18.55 15.08,18.77 15.08,19C15.08,20.61 16.39,21.91 18,21.91C19.61,21.91 20.92,20.61 20.92,19C20.92,17.39 19.61,16.08 18,16.08Z"/></svg>',
                spacer: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M18,18H6V6H18V18M18,4H6A2,2 0 0,0 4,6V18A2,2 0 0,0 6,20H18A2,2 0 0,0 20,18V6A2,2 0 0,0 18,4M11,10H13V14H11V10Z"/></svg>',
                map: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M15,19L9,16.89V5L15,7.11M20.5,3C20.44,3 20.39,3 20.34,3L15,5.1L9,3L3.36,4.9C3.15,4.97 3,5.15 3,5.38V20.5A0.5,0.5 0 0,0 3.5,21L9,18.9L15,21L20.64,19.1C20.85,19 21,18.85 21,18.62V3.5A0.5,0.5 0 0,0 20.5,3Z"/></svg>',
                custom_html: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M14.6,16.6L19.2,12L14.6,7.4L16,6L22,12L16,18L14.6,16.6M9.4,16.6L4.8,12L9.4,7.4L8,6L2,12L8,18L9.4,16.6Z"/></svg>',
            };
            return icons[type] || icons.text;
        },

        // ---- Preview Rendering ----

        getSectionStyles(section) {
            const s = section.settings || {};
            let style = '';
            if (s.bgColor) style += 'background-color:' + s.bgColor + ';';
            if (s.paddingY) style += 'padding-top:' + s.paddingY + ';padding-bottom:' + s.paddingY + ';';
            return style;
        },

        getRowStyles(row) {
            const s = row.settings || {};
            let style = 'display:flex;';
            if (s.gap) style += 'gap:' + s.gap + ';';
            else style += 'gap:16px;';
            if (s.alignment) style += 'align-items:' + s.alignment + ';';
            if (s.bgColor) style += 'background-color:' + s.bgColor + ';';
            return style;
        },

        renderElement(el) {
            const s = el.settings || {};
            switch (el.type) {
                case 'text':
                    return `<div style="font-size:${s.fontSize || '16px'};color:${s.color || 'inherit'};text-align:${s.textAlign || 'left'};padding:${s.padding || '16px'}">${s.content || '<p>Text</p>'}</div>`;

                case 'image':
                    if (!s.imageUrl) return '<div class="pe-placeholder pe-image-ph">Image placeholder</div>';
                    return `<img src="${this.escapeHtml(s.imageUrl)}" alt="${this.escapeHtml(s.altText || '')}" style="width:${s.width || '100%'};border-radius:${s.borderRadius || '8px'};display:block">`;

                case 'menu':
                    return `<div class="pe-placeholder pe-menu-ph">
                        <div class="pe-menu-icon"><svg viewBox="0 0 24 24" width="32" height="32"><path fill="currentColor" d="M3,5H9V11H3V5M5,7V9H7V7H5M11,7H21V9H11V7M11,15H21V17H11V15M5,20L1.5,16.5L2.91,15.09L5,17.17L9.59,12.59L11,14L5,20Z"/></svg></div>
                        <div>Product Menu</div>
                        <small>${s.productViewMode || 'list'} / ${s.navPosition || 'sidebar'} / ${s.cardStyle || 'default'}</small>
                    </div>`;

                case 'announcement':
                    return `<div style="background:${s.bgColor || '#FFF3E0'};color:${s.textColor || '#E65100'};padding:10px 20px;text-align:center;font-weight:600;font-size:0.9rem;border-radius:4px">${this.escapeHtml(s.text || 'Announcement')}</div>`;

                case 'hours':
                    return '<div class="pe-placeholder pe-info-ph"><svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M16.2,16.2L11,13V7H12.5V12.2L17,14.9L16.2,16.2Z"/></svg> Operating Hours</div>';

                case 'address':
                    return '<div class="pe-placeholder pe-info-ph"><svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5M12,2A7,7 0 0,0 5,9C5,14.25 12,22 12,22C12,22 19,14.25 19,9A7,7 0 0,0 12,2Z"/></svg> Address</div>';

                case 'phone':
                    return '<div class="pe-placeholder pe-info-ph"><svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M6.62,10.79C8.06,13.62 10.38,15.94 13.21,17.38L15.41,15.18C15.69,14.9 16.08,14.82 16.43,14.93C17.55,15.3 18.75,15.5 20,15.5A1,1 0 0,1 21,16.5V20A1,1 0 0,1 20,21A17,17 0 0,1 3,4A1,1 0 0,1 4,3H7.5A1,1 0 0,1 8.5,4C8.5,5.25 8.7,6.45 9.07,7.57C9.18,7.92 9.1,8.31 8.82,8.59L6.62,10.79Z"/></svg> Phone</div>';

                case 'social':
                    const links = (s.links || []).map(l => l.platform).join(', ') || 'No links';
                    return `<div class="pe-placeholder pe-info-ph"><svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M18,16.08C17.24,16.08 16.56,16.38 16.04,16.85L8.91,12.7C8.96,12.47 9,12.24 9,12C9,11.76 8.96,11.53 8.91,11.3L15.96,7.19C16.5,7.69 17.21,8 18,8A3,3 0 0,0 21,5A3,3 0 0,0 18,2A3,3 0 0,0 15,5C15,5.24 15.04,5.47 15.09,5.7L8.04,9.81C7.5,9.31 6.79,9 6,9A3,3 0 0,0 3,12A3,3 0 0,0 6,15C6.79,15 7.5,14.69 8.04,14.19L15.16,18.34C15.11,18.55 15.08,18.77 15.08,19C15.08,20.61 16.39,21.91 18,21.91C19.61,21.91 20.92,20.61 20.92,19C20.92,17.39 19.61,16.08 18,16.08Z"/></svg> Social: ${this.escapeHtml(links)}</div>`;

                case 'spacer':
                    const divider = s.showDivider ? `<hr style="border:none;border-top:1px solid ${s.dividerColor || '#e0e0e0'};margin:0">` : '';
                    return `<div style="height:${s.height || '40px'};display:flex;align-items:center">${divider}</div>`;

                case 'map':
                    if (!s.googleMapsEmbedUrl) return '<div class="pe-placeholder pe-map-ph">Map placeholder</div>';
                    return `<iframe src="${this.escapeHtml(s.googleMapsEmbedUrl)}" style="width:100%;height:${s.height || '300px'};border:0;border-radius:8px" allowfullscreen loading="lazy"></iframe>`;

                case 'custom_html':
                    return s.htmlContent || '<div class="pe-placeholder">Custom HTML</div>';

                default:
                    return `<div class="pe-placeholder">${el.type}</div>`;
            }
        },

        escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        },

        // ---- Undo/Redo ----

        pushHistory() {
            this.history = this.history.slice(0, this.historyIndex + 1);
            this.history.push(JSON.parse(JSON.stringify(this.config)));
            this.historyIndex++;
            if (this.history.length > 50) {
                this.history.shift();
                this.historyIndex--;
            }
        },

        undo() {
            if (this.historyIndex > 0) {
                this.historyIndex--;
                this.config = JSON.parse(JSON.stringify(this.history[this.historyIndex]));
                this.editingItem = null;
            }
        },

        redo() {
            if (this.historyIndex < this.history.length - 1) {
                this.historyIndex++;
                this.config = JSON.parse(JSON.stringify(this.history[this.historyIndex]));
                this.editingItem = null;
            }
        },

        handleKeyboard(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                this.undo();
            }
            if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
                e.preventDefault();
                this.redo();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.saveConfig();
            }
        },

        // ---- Save ----

        async saveConfig() {
            this.saving = true;
            try {
                const res = await fetch('/api/settings/storefront', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.config)
                });
                if (res.ok) {
                    this.showNotification('Design saved successfully');
                } else {
                    this.showNotification('Failed to save', true);
                }
            } catch (err) {
                console.error('Save error:', err);
                this.showNotification('Failed to save', true);
            } finally {
                this.saving = false;
            }
        },

        showNotification(message, isError = false) {
            this.toastMessage = message;
            this.toastError = isError;
            this.showToast = true;
            setTimeout(() => { this.showToast = false; }, 3000);
        }
    };
}
