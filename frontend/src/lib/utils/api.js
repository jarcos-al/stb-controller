/**
 * API client for REST endpoints.
 */

const BASE_URL = '';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}/api${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      const err =
          await response.json().catch(() => ({detail: response.statusText}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    console.error(`[API] ${endpoint} failed:`, err);
    throw err;
  }
}

export const api = {
  // Status
  getStatus: () => request('/status'),
  getHealth: () => request('/health'),
  getDevices: () => request('/devices'),

  // Device connection
  connectDevice: (deviceId = 0) =>
      request(`/device/connect?device_id=${deviceId}`, {method: 'POST'}),
  disconnectDevice: (deviceId = 0) =>
      request(`/device/disconnect?device_id=${deviceId}`, {method: 'POST'}),

  // Remote Control
  sendKey: (key, keyType = 'short') => request('/remote/key', {
    method: 'POST',
    body: JSON.stringify({key, key_type: keyType}),
  }),

  // Channels
  getBouquets: () => request('/bouquets'),
  getChannels: (bouquetRef = null) => {
    const params =
        bouquetRef ? `?bouquet=${encodeURIComponent(bouquetRef)}` : '';
    return request(`/channels${params}`);
  },
  zapChannel: (serviceRef) => request('/channels/zap', {
    method: 'POST',
    body: JSON.stringify({service_ref: serviceRef}),
  }),

  // EPG
  getEpgNowNext: (bouquetRef = null) => {
    const params =
        bouquetRef ? `?bouquet=${encodeURIComponent(bouquetRef)}` : '';
    return request(`/epg/nownext${params}`);
  },
  getEpgService: (serviceRef) =>
      request(`/epg/service/${encodeURIComponent(serviceRef)}`),
  searchEpg: (query) => request(`/epg/search?q=${encodeURIComponent(query)}`),

  // Volume
  getVolume: () => request('/volume'),
  setVolume: (action, value = null) => request('/volume', {
    method: 'POST',
    body: JSON.stringify({action, value}),
  }),

  // Timers
  getTimers: () => request('/timers'),
  addTimer: (timer) => request('/timers', {
    method: 'POST',
    body: JSON.stringify(timer),
  }),
  deleteTimer: (serviceRef, beginTime, endTime) => request(
      `/timers?service_ref=${encodeURIComponent(serviceRef)}&begin_time=${
          encodeURIComponent(
              beginTime)}&end_time=${encodeURIComponent(endTime)}`,
      {
        method: 'DELETE',
      }),

  // Power
  setPower: (action) => request('/power', {
    method: 'POST',
    body: JSON.stringify({action}),
  }),

  // Stream
  getStreamUrl: (serviceRef) =>
      request(`/stream/url?service_ref=${encodeURIComponent(serviceRef)}`),

  // Network / Connection
  scanNetwork: (subnet = null, port = 20000) => {
    const params = new URLSearchParams();
    if (subnet) params.set('subnet', subnet);
    params.set('port', String(port));
    return request(`/network/scan?${params}`);
  },
  configureDevice: (host, port = 20000) => request('/device/configure', {
    method: 'POST',
    body: JSON.stringify({host, port}),
  }),
  getConnectionInfo: () => request('/device/connection'),
};
