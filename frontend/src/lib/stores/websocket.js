/**
 * WebSocket store for real-time STB state management.
 * Auto-reconnects with exponential backoff.
 */
import {derived, get, writable} from 'svelte/store';

// Connection state
export const wsConnected = writable(false);
export const wsReconnecting = writable(false);
export const stbConnected =
    writable(false);  // STB device connection (separate from WS)

// STB state from WebSocket
export const stbStatus = writable({
  in_standby: false,
  current_channel: '',
  current_channel_ref: '',
  current_program: '',
  program_description: '',
  program_start: null,
  program_end: null,
  volume: 50,
  is_muted: false,
  is_recording: false,
  signal_strength: null,
  signal_snr: null,
  device_name: '',
  device_model: '',
});

// Last received messages
export const lastMessage = writable(null);

// Derived stores
export const isOnline = derived(wsConnected, $c => $c);
export const currentChannel = derived(stbStatus, $s => $s.current_channel);
export const currentProgram = derived(stbStatus, $s => $s.current_program);
export const volume = derived(stbStatus, $s => $s.volume);
export const isMuted = derived(stbStatus, $s => $s.is_muted);

let ws = null;
let reconnectAttempts = 0;
let reconnectTimer = null;
const MAX_RECONNECT_DELAY = 30000;
const BASE_DELAY = 1000;

function getWsUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/ws`;
}

export function connectWebSocket() {
  if (ws &&
      (ws.readyState === WebSocket.CONNECTING ||
       ws.readyState === WebSocket.OPEN)) {
    return;
  }

  const url = getWsUrl();
  console.log('[WS] Connecting to', url);

  try {
    ws = new WebSocket(url);
  } catch (err) {
    console.error('[WS] Failed to create WebSocket:', err);
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    console.log('[WS] Connected');
    wsConnected.set(true);
    wsReconnecting.set(false);
    reconnectAttempts = 0;

    // Request initial status
    sendMessage({type: 'get_status', data: {}});

    // Start heartbeat
    startHeartbeat();
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      lastMessage.set(message);
      handleMessage(message);
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  };

  ws.onclose = (event) => {
    console.log('[WS] Disconnected', event.code, event.reason);
    wsConnected.set(false);
    stopHeartbeat();
    scheduleReconnect();
  };

  ws.onerror = (error) => {
    console.error('[WS] Error:', error);
  };
}

function handleMessage(message) {
  switch (message.type) {
    case 'status_update':
      if ('stb_connected' in message.data) {
        stbConnected.set(message.data.stb_connected);
      }
      if (message.data.current_channel !== undefined) {
        stbStatus.set(message.data);
      }
      break;
    case 'channel_changed':
      stbStatus.update(s => ({
                         ...s,
                         current_channel: message.data.channel_name,
                         current_channel_ref: message.data.service_ref,
                       }));
      break;
    case 'volume_changed':
      stbStatus.update(s => ({
                         ...s,
                         volume: message.data.volume,
                         is_muted: message.data.is_muted,
                       }));
      break;
    case 'keypress_result':
      // Handled by the component that sent the keypress
      break;
    case 'heartbeat':
      // Keep-alive acknowledged
      break;
    case 'error':
      console.error('[WS] Server error:', message.data.message);
      break;
  }
}

export function sendMessage(message) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
  }
}

export function sendKeypress(key, keyType = 'short') {
  sendMessage({
    type: 'keypress',
    data: {key, key_type: keyType},
  });
}

function scheduleReconnect() {
  if (reconnectTimer) return;

  reconnectAttempts++;
  const delay = Math.min(
      BASE_DELAY * Math.pow(2, reconnectAttempts - 1), MAX_RECONNECT_DELAY);

  console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
  wsReconnecting.set(true);

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, delay);
}

let heartbeatInterval = null;

function startHeartbeat() {
  stopHeartbeat();
  heartbeatInterval = setInterval(() => {
    sendMessage({type: 'heartbeat', data: {}});
  }, 30000);
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
}

export function disconnectWebSocket() {
  stopHeartbeat();
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  wsConnected.set(false);
  wsReconnecting.set(false);
}
