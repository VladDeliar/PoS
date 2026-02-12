function trackOrderApp(orderId) {
    return {
        orderId: orderId,
        order: null,
        loading: true,
        error: null,
        wsConnected: false,
        ws: null,
        showCallWaiter: false,
        waiterPhone: '',
        callingWaiter: false,
        showToast: false,
        toastMessage: '',
        pollingInterval: null,

        async init() {
            await this.loadOrder();
            this.connectWebSocket();

            // Fallback polling if WebSocket fails
            this.pollingInterval = setInterval(() => {
                if (!this.wsConnected) {
                    this.loadOrder();
                }
            }, 10000); // Poll every 10 seconds
        },

        async loadOrder() {
            try {
                const response = await fetch(`/api/orders/${this.orderId}`);
                if (!response.ok) {
                    if (response.status === 404) {
                        this.error = 'Замовлення не знайдено';
                    } else {
                        this.error = 'Помилка завантаження замовлення';
                    }
                    this.loading = false;
                    return;
                }

                this.order = await response.json();
                this.loading = false;
                this.error = null;
            } catch (error) {
                console.error('Error loading order:', error);
                this.error = 'Помилка мережі. Перевірте підключення.';
                this.loading = false;
            }
        },

        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.wsConnected = true;
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    // Filter messages for this order
                    if (data.type === 'order_updated' && data.order_id === this.orderId) {
                        console.log('Order status updated:', data.status);
                        this.order.status = data.status;

                        // Show notification when order is ready
                        if (data.status === 'ready') {
                            this.showNotification('Ваше замовлення готове! ✅');

                            // Browser notification if permitted
                            if ('Notification' in window && Notification.permission === 'granted') {
                                new Notification('Замовлення готове!', {
                                    body: `Замовлення ${this.order.order_number} готове до видачі`,
                                    icon: '/static/img/logo.png'
                                });
                            }
                        }
                    }
                } catch (e) {
                    // Ignore ping/pong messages
                }
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.wsConnected = false;
                // Reconnect after 3 seconds
                setTimeout(() => this.connectWebSocket(), 3000);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        },

        async callWaiter() {
            if (this.callingWaiter) return;

            this.callingWaiter = true;
            try {
                const response = await fetch(`/api/orders/${this.orderId}/call-waiter?phone=${encodeURIComponent(this.waiterPhone)}`, {
                    method: 'POST'
                });

                if (response.ok) {
                    this.showCallWaiter = false;
                    this.showNotification('Офіціант буде зараз!');
                    this.waiterPhone = '';
                } else {
                    alert('Помилка виклику офіціанта');
                }
            } catch (error) {
                console.error('Error calling waiter:', error);
                alert('Помилка виклику офіціанта');
            } finally {
                this.callingWaiter = false;
            }
        },

        showNotification(message) {
            this.toastMessage = message;
            this.showToast = true;
            setTimeout(() => {
                this.showToast = false;
            }, 3000);
        },

        formatTime(dateStr) {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleString('uk-UA', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        },

        destroy() {
            // Cleanup
            if (this.ws) {
                this.ws.close();
            }
            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
            }
        }
    };
}
