/**
 * WebSocket Hook for Real-Time Updates
 * Replaces polling with push notifications
 * 
 * Usage:
 * ```typescript
 * const { subscribe, unsubscribe, isConnected } = useWebSocket();
 * 
 * useEffect(() => {
 *   subscribe('events', (data) => {
 *     if (data.type === 'RECALCULATION') {
 *       // Update UI
 *     }
 *   });
 * 
 *   return () => unsubscribe('events');
 * }, []);
 * ```
 */

import { useEffect, useRef, useState, useCallback } from 'react';

type MessageHandler = (data: any) => void;

interface WebSocketMessage {
    type: string;
    payload?: any;
    timestamp?: string;
}

// Global singleton WebSocket connection
let ws: WebSocket | null = null;
let reconnectTimeout: NodeJS.Timeout | null = null;
let connectionId: string | null = null;

// Channel subscriptions: channel -> Set of handlers
const subscriptions = new Map<string, Set<MessageHandler>>();

// Connection state listeners
const connectionListeners = new Set<(connected: boolean) => void>();

function notifyConnectionListeners(connected: boolean) {
    connectionListeners.forEach(listener => listener(connected));
}

function createConnection() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        return; // Already connected
    }

    // Generate connection ID if not exists
    if (!connectionId) {
        connectionId = `user_${Math.random().toString(36).substring(2, 11)}`;
    }

    // Use environment variable or build dynamic URL based on current host
    const getWebSocketUrl = () => {
        if (import.meta.env.VITE_WS_URL) {
            return import.meta.env.VITE_WS_URL;
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname === 'localhost' 
            ? 'localhost:8000' 
            : window.location.host;
        
        return `${protocol}//${host}/ws`;
    };

    const wsUrl = `${getWebSocketUrl()}?connection_id=${connectionId}`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('✅ WebSocket connected');
        notifyConnectionListeners(true);

        // Resubscribe to all channels
        subscriptions.forEach((handlers, channel) => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: 'subscribe',
                    channel
                }));
            }
        });
    };

    ws.onmessage = (event) => {
        try {
            const data: WebSocketMessage = JSON.parse(event.data);

            // Handle connection acknowledgment
            if (data.type === 'CONNECTED' || data.type === 'SUBSCRIBED') {
                console.log('WebSocket:', data.type);
                return;
            }

            // Route message to appropriate channel handlers
            if (data.type === 'NEW_MESSAGE') {
                const handlers = subscriptions.get('community');
                handlers?.forEach(handler => handler(data));
            } else if (data.type === 'RECALCULATION' || data.type === 'LINE_MOVEMENT') {
                const handlers = subscriptions.get('events');
                handlers?.forEach(handler => handler(data));
            } else if (data.type === 'CORRELATION_UPDATE') {
                // Extract parlay_id from payload
                const parlayId = data.payload?.parlay_id;
                if (parlayId) {
                    const handlers = subscriptions.get(`parlay_${parlayId}`);
                    handlers?.forEach(handler => handler(data));
                }
            }
        } catch (err) {
            console.error('WebSocket message parse error:', err);
        }
    };

    ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting in 3s...');
        notifyConnectionListeners(false);
        ws = null;

        // Auto-reconnect after 3 seconds
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(() => {
            createConnection();
        }, 3000);
    };
}

export function useWebSocket() {
    const [isConnected, setIsConnected] = useState(false);
    const listenersRef = useRef(new Set<MessageHandler>());

    useEffect(() => {
        // Register connection state listener
        const listener = (connected: boolean) => setIsConnected(connected);
        connectionListeners.add(listener);

        // Create connection if not exists
        if (!ws || ws.readyState === WebSocket.CLOSED) {
            createConnection();
        } else if (ws.readyState === WebSocket.OPEN) {
            setIsConnected(true);
        }

        return () => {
            connectionListeners.delete(listener);
        };
    }, []);

    const subscribe = useCallback((channel: string, handler: MessageHandler) => {
        // Add handler to channel subscriptions
        if (!subscriptions.has(channel)) {
            subscriptions.set(channel, new Set());
        }
        subscriptions.get(channel)!.add(handler);
        listenersRef.current.add(handler);

        // Send subscribe message to server
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                action: 'subscribe',
                channel
            }));
        }

        console.log(`Subscribed to channel: ${channel}`);
    }, []);

    const unsubscribe = useCallback((channel: string, handler?: MessageHandler) => {
        if (handler) {
            // Remove specific handler
            subscriptions.get(channel)?.delete(handler);
            listenersRef.current.delete(handler);

            // If no more handlers, unsubscribe from server
            if (subscriptions.get(channel)?.size === 0) {
                subscriptions.delete(channel);
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        action: 'unsubscribe',
                        channel
                    }));
                }
            }
        } else {
            // Remove all handlers for channel
            subscriptions.get(channel)?.forEach(h => listenersRef.current.delete(h));
            subscriptions.delete(channel);

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    action: 'unsubscribe',
                    channel
                }));
            }
        }

        console.log(`Unsubscribed from channel: ${channel}`);
    }, []);

    const disconnect = useCallback(() => {
        if (ws) {
            ws.close();
            ws = null;
        }
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }
    }, []);

    return {
        subscribe,
        unsubscribe,
        disconnect,
        isConnected
    };
}
