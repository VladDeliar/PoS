const STYLE_DEFAULT = { fillOpacity: 0.25, weight: 2, opacity: 0.8, dashArray: null };
const STYLE_HIGHLIGHT = { weight: 4, dashArray: '5, 5', opacity: 1, fillOpacity: 0.35 };
const STYLE_EDIT = { fillOpacity: 0.4, weight: 3, dashArray: null, opacity: 1 };

function deliveryZonesApp() {
    return {
        zones: [],
        center: { lat: 48.9219, lng: 24.7082, address: '' },
        form: {},
        editingZone: null,
        map: null,
        circles: {},
        centerMarker: null,
        isDrawing: false,
        drawnPolygon: null,
        showToast: false,
        toastMessage: '',
        toastError: false,
        _annularCache: {},
        _resizeTimeout: null,

        async init() {
            this.initMap();

            // Fetch both in parallel (network is the bottleneck)
            const [centerRes, zonesRes] = await Promise.all([
                fetch('/api/delivery-zones/center/info').catch(() => null),
                fetch('/api/delivery-zones/').catch(() => null)
            ]);

            // Apply center first (renderZonesOnMap depends on this.center)
            if (centerRes?.ok) {
                this.center = await centerRes.json();
                this._setupCenterMarker();
                this.map.setView([this.center.lat, this.center.lng], 13);
            }

            // Then zones
            if (zonesRes?.ok) {
                this.zones = await zonesRes.json();
                this.renderZonesOnMap();
            }

            this.newZone();
        },

        initMap() {
            this.map = L.map('map').setView([this.center.lat, this.center.lng], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>'
            }).addTo(this.map);

            this.map.pm.setGlobalOptions({
                allowSelfIntersection: false,
                finishOn: 'dblclick',
            });

            this.map.on('pm:create', (e) => this.onPolygonDrawn(e));

            const mapContainer = document.getElementById('map');
            let firstResize = true;
            this._resizeObserver = new ResizeObserver(() => {
                if (firstResize) {
                    firstResize = false;
                    this.map.invalidateSize({ animate: false });
                    return;
                }
                clearTimeout(this._resizeTimeout);
                this._resizeTimeout = setTimeout(() => {
                    this.map.invalidateSize({ animate: false });
                }, 150);
            });
            this._resizeObserver.observe(mapContainer);

            this.map.whenReady(() => {
                requestAnimationFrame(() => this.map.invalidateSize({ animate: false }));
            });
        },

        _setupCenterMarker() {
            if (this.centerMarker) {
                this.centerMarker.setLatLng([this.center.lat, this.center.lng]);
                return;
            }

            this.centerMarker = L.marker([this.center.lat, this.center.lng], {
                draggable: true,
                icon: L.divIcon({
                    className: 'center-marker-icon',
                    html: '<div class="center-marker">📍</div>',
                    iconSize: [30, 30],
                    iconAnchor: [15, 30]
                })
            }).addTo(this.map);

            this.centerMarker.bindTooltip('Центр доставки (перетягніть)', { permanent: false });

            this.centerMarker.on('dragend', async (e) => {
                const pos = e.target.getLatLng();
                await this.updateCenter(pos.lat, pos.lng);
            });
        },

        async loadCenter() {
            try {
                const res = await fetch('/api/delivery-zones/center/info');
                if (!res.ok) return;
                this.center = await res.json();
                this._setupCenterMarker();
                this.map.setView([this.center.lat, this.center.lng], 13);
            } catch (err) {
                console.error('Failed to load center:', err);
            }
        },

        async updateCenter(lat, lng) {
            try {
                await fetch('/api/delivery-zones/center/info', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ lat, lng, address: this.center.address })
                });

                await fetch('/api/delivery-zones/recalculate-all', { method: 'POST' });

                this.center.lat = lat;
                this.center.lng = lng;
                this._annularCache = {};

                await this.loadZones();
                this.showNotification('Центр оновлено');
            } catch (err) {
                console.error('Failed to update center:', err);
                this.showNotification('Помилка оновлення центру', true);
            }
        },

        async loadZones() {
            try {
                const res = await fetch('/api/delivery-zones/');
                if (res.ok) {
                    this.zones = await res.json();
                    this.renderZonesOnMap();
                }
            } catch (err) {
                console.error('Failed to load zones:', err);
            }
        },

        createAnnularZone(center, outerRadiusKm, innerRadiusKm = 0, numPoints = 64) {
            const key = `${center.lat}_${center.lng}_${outerRadiusKm}_${innerRadiusKm}`;
            if (this._annularCache[key]) return this._annularCache[key];

            const toRad = (deg) => deg * Math.PI / 180;
            const toDeg = (rad) => rad * 180 / Math.PI;
            const EARTH_R = 6371;

            const generateCircle = (radiusKm) => {
                const points = [];
                const angDist = radiusKm / EARTH_R;
                const latRad = toRad(center.lat);
                const lngRad = toRad(center.lng);
                const sinLat = Math.sin(latRad);
                const cosLat = Math.cos(latRad);
                const cosAng = Math.cos(angDist);
                const sinAng = Math.sin(angDist);

                for (let i = 0; i <= numPoints; i++) {
                    const bearingRad = toRad(i * 360 / numPoints);
                    const lat2 = Math.asin(sinLat * cosAng + cosLat * sinAng * Math.cos(bearingRad));
                    const lng2 = lngRad + Math.atan2(
                        Math.sin(bearingRad) * sinAng * cosLat,
                        cosAng - sinLat * Math.sin(lat2)
                    );
                    points.push([toDeg(lng2), toDeg(lat2)]);
                }
                return points;
            };

            const outerRing = generateCircle(outerRadiusKm);
            let result;

            if (innerRadiusKm === 0) {
                result = { type: 'Polygon', coordinates: [outerRing] };
            } else {
                const innerRing = generateCircle(innerRadiusKm).reverse();
                result = { type: 'Polygon', coordinates: [outerRing, innerRing] };
            }

            this._annularCache[key] = result;
            return result;
        },

        _addZoneLayer(zone, geometry, isGeoJSON = false) {
            const opts = {
                color: zone.color, fillColor: zone.color,
                ...STYLE_DEFAULT
            };
            const layer = isGeoJSON
                ? L.geoJSON(geometry, { style: opts })
                : L.polygon(geometry, opts);

            layer.addTo(this.map);
            layer.on('click', () => this.selectZone(zone));
            layer.bindTooltip(zone.name, { permanent: false, direction: 'center' });
            this.circles[zone._id] = layer;
            return layer;
        },

        renderZonesOnMap() {
            if (this.drawnPolygon && Object.values(this.circles).includes(this.drawnPolygon)) {
                this.drawnPolygon = null;
            }

            Object.values(this.circles).forEach(c => c.remove());
            this.circles = {};

            const radiusZones = [], polygonZones = [];
            this.zones.forEach(z => {
                (z.zone_type === 'polygon' ? polygonZones : radiusZones).push(z);
            });

            const sorted = [...radiusZones].sort((a, b) => a.radius_km - b.radius_km);
            let prevRadius = 0;

            sorted.forEach((zone) => {
                const geometry = this.createAnnularZone(this.center, zone.radius_km, prevRadius, 64);
                this._addZoneLayer(zone, geometry, true);
                prevRadius = zone.radius_km;
            });

            polygonZones.forEach((zone) => {
                if (!zone.geometry?.coordinates?.[0]) return;
                const leafletCoords = zone.geometry.coordinates[0].map(c => [c[1], c[0]]);
                this._addZoneLayer(zone, leafletCoords, false);
            });

            if (this.zones.length > 0) {
                const maxRadius = Math.max(...radiusZones.map(z => z.radius_km || 0), 10);
                this.map.setView([this.center.lat, this.center.lng], this.getZoomForRadius(maxRadius));
            }
        },

        getZoomForRadius(radiusKm) {
            if (radiusKm > 20) return 10;
            if (radiusKm > 10) return 11;
            if (radiusKm > 5) return 12;
            if (radiusKm > 2) return 13;
            return 14;
        },

        highlightZone(zoneId) {
            Object.entries(this.circles).forEach(([id, layer]) => {
                layer.setStyle(id === zoneId ? STYLE_HIGHLIGHT : STYLE_DEFAULT);
            });
        },

        _cleanupPolygonEditing() {
            if (!this.drawnPolygon) return;

            const isDisplayPolygon = Object.values(this.circles).includes(this.drawnPolygon);

            if (isDisplayPolygon) {
                this.drawnPolygon.setStyle(STYLE_DEFAULT);
            } else {
                this.drawnPolygon.remove();
            }

            this.drawnPolygon = null;
        },

        selectZone(zone) {
            this.editingZone = zone;
            this.form = { ...zone };

            this._cleanupPolygonEditing();
            this.highlightZone(zone._id);

            if (zone.zone_type === 'polygon' && zone.geometry) {
                const layer = this.circles[zone._id];
                if (layer) {
                    this.drawnPolygon = layer;
                    this.drawnPolygon.setStyle(STYLE_EDIT);

                    this.map.fitBounds(this.drawnPolygon.getBounds(), {
                        animate: false,
                        padding: [20, 20]
                    });
                    this.map.invalidateSize({ animate: false });
                }
            }
        },

        newZone() {
            this.editingZone = null;
            this.form = {
                name: '',
                zone_type: 'radius',
                radius_km: 2,
                color: '#22c55e',
                delivery_fee: 0,
                min_order_amount: 0,
                free_delivery_threshold: null,
                enabled: true,
                priority: this.zones.length + 1
            };

            this._cleanupPolygonEditing();
            this.highlightZone(null);
        },

        onZoneTypeChange() {
            if (this.isDrawing) {
                this.cancelDrawing();
            }

            if (this.form.zone_type !== 'polygon') {
                this._cleanupPolygonEditing();
            }

            if (this.form.zone_type === 'polygon') {
                this.form.radius_km = null;
            } else if (!this.form.radius_km) {
                this.form.radius_km = 2;
            }
        },

        startDrawing() {
            this.isDrawing = true;
            this._cleanupPolygonEditing();

            const color = this.form.color || '#22c55e';
            this.map.pm.enableDraw('Polygon', {
                snappable: true,
                snapDistance: 20,
                templineStyle: { color, weight: 3 },
                hintlineStyle: { color, dashArray: '5, 5' },
                pathOptions: { color, fillColor: color, fillOpacity: 0.3, weight: 2 }
            });

            this.showNotification('Клікайте на карті для створення точок полігону. Подвійний клік для завершення.');
        },

        cancelDrawing() {
            this.isDrawing = false;
            this.map.pm.disableDraw();
            this._cleanupPolygonEditing();
        },

        onPolygonDrawn(e) {
            this.isDrawing = false;
            this.map.pm.disableDraw();

            this.drawnPolygon = e.layer;
            this.form.custom_geometry = this.drawnPolygon.toGeoJSON().geometry;

            this.showNotification('Полігон створено.');
        },

        async saveZone() {
            try {
                if (this.form.zone_type === 'radius' && !this.form.radius_km) {
                    this.showNotification('Введіть радіус зони', true);
                    return;
                }

                if (this.form.zone_type === 'polygon' && !this.form.custom_geometry) {
                    this.showNotification('Намалюйте зону на карті', true);
                    return;
                }

                const method = this.editingZone ? 'PUT' : 'POST';
                const url = this.editingZone
                    ? `/api/delivery-zones/${this.editingZone._id}`
                    : '/api/delivery-zones/';

                const res = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.form)
                });

                if (res.ok) {
                    await this.loadZones();
                    this.showNotification(this.editingZone ? 'Зону оновлено' : 'Зону створено');
                    this.newZone();
                } else {
                    const error = await res.json();
                    this.showNotification(error.detail || 'Помилка збереження', true);
                }
            } catch (err) {
                console.error('Failed to save zone:', err);
                this.showNotification('Помилка збереження', true);
            }
        },

        async deleteZone() {
            if (!this.editingZone) return;
            if (!confirm(`Видалити зону "${this.editingZone.name}"?`)) return;

            try {
                const res = await fetch(`/api/delivery-zones/${this.editingZone._id}`, {
                    method: 'DELETE'
                });

                if (res.ok) {
                    await this.loadZones();
                    this.showNotification('Зону видалено');
                    this.newZone();
                } else {
                    this.showNotification('Помилка видалення', true);
                }
            } catch (err) {
                console.error('Failed to delete zone:', err);
                this.showNotification('Помилка видалення', true);
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
