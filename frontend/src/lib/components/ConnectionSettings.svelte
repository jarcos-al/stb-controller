<script>
  import { stbConnected } from '../stores/websocket.js';
  import { api } from '../utils/api.js';
  import { showToast } from '../stores/app.js';

  let host = '';
  let port = 20000;
  let loading = false;
  let scanning = false;
  let scanResults = [];
  let connectionInfo = null;

  // Load current connection info on mount
  import { onMount } from 'svelte';
  onMount(async () => {
    try {
      connectionInfo = await api.getConnectionInfo();
      if (connectionInfo.configured) {
        host = connectionInfo.host;
        port = connectionInfo.port;
      }
    } catch (e) {
      console.error('Failed to get connection info:', e);
    }
  });

  async function scanNetwork() {
    scanning = true;
    scanResults = [];
    try {
      const res = await api.scanNetwork(null, port);
      scanResults = res.devices || [];
      if (scanResults.length === 0) {
        showToast('No se encontraron dispositivos', 'warning');
      } else {
        showToast(`${scanResults.length} dispositivo(s) encontrado(s)`, 'success');
      }
    } catch (e) {
      showToast('Error al escanear la red', 'error');
    } finally {
      scanning = false;
    }
  }

  async function connectTo(h, p) {
    loading = true;
    try {
      const res = await api.configureDevice(h, p);
      if (res.connected) {
        host = h;
        port = p;
        // Refresh full connection info (includes serial, name, version)
        try {
          connectionInfo = await api.getConnectionInfo();
        } catch {
          connectionInfo = { configured: true, host: h, port: p, connected: true };
        }
        showToast(`Conectado a ${h}:${p}`, 'success');
      } else {
        showToast(`No se pudo conectar a ${h}:${p}`, 'error');
      }
    } catch (e) {
      showToast('Error de conexión', 'error');
    } finally {
      loading = false;
    }
  }

  async function connectManual() {
    if (!host.trim()) return;
    await connectTo(host.trim(), port);
  }

  function selectDevice(device) {
    host = device.host;
    port = device.port;
    connectTo(device.host, device.port);
  }
</script>

<div class="connection-settings">
  <h2 class="section-title">Conexión</h2>

  <!-- Current status -->
  {#if connectionInfo?.configured}
    <div class="current-connection glass-card">
      <div class="conn-header">
        <div class="conn-status-dot" class:connected={$stbConnected}></div>
        <span class="conn-label">Conexión actual</span>
      </div>
      <div class="conn-details">
        <span class="conn-host">{connectionInfo.host}</span>
        <span class="conn-port">:{connectionInfo.port}</span>
      </div>
      {#if connectionInfo.name || connectionInfo.serial}
        <div class="conn-device-info">
          {#if connectionInfo.name}
            <span class="conn-device-name">{connectionInfo.name}</span>
          {/if}
          {#if connectionInfo.serial}
            <span class="conn-device-serial">S/N: {connectionInfo.serial}</span>
          {/if}
          {#if connectionInfo.version}
            <span class="conn-device-version">v{connectionInfo.version}</span>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  <!-- Auto-detect -->
  <div class="section glass-card">
    <h3 class="subsection-title">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      </svg>
      Detectar en red
    </h3>
    <p class="section-desc">Busca decodificadores G-MScreen en la red local.</p>
    <button class="btn btn-scan" on:click={scanNetwork} disabled={scanning}>
      {#if scanning}
        <span class="btn-spinner"></span>
        Escaneando...
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        Buscar dispositivos
      {/if}
    </button>

    {#if scanResults.length > 0}
      <div class="scan-results">
        {#each scanResults as device}
          <button class="device-item" on:click={() => selectDevice(device)} disabled={loading}>
            <div class="device-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="7" width="20" height="15" rx="2" ry="2"/>
                <polyline points="17 2 12 7 7 2"/>
              </svg>
            </div>
            <div class="device-info">
              <span class="device-host">{device.host}</span>
              <span class="device-port">
                {#if device.name}
                  {device.name}
                {:else}
                  Puerto {device.port}
                {/if}
                {#if device.connected}
                  <span class="device-connected-badge">conectado</span>
                {/if}
              </span>
              {#if device.serial}
                <span class="device-serial">S/N: {device.serial}</span>
              {/if}
            </div>
            <svg class="device-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Manual connection -->
  <div class="section glass-card">
    <h3 class="subsection-title">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
      </svg>
      Conexión manual
    </h3>
    <p class="section-desc">Introduce la dirección IP y puerto del decodificador.</p>
    <div class="manual-form">
      <div class="input-group">
        <label for="host-input">IP</label>
        <input id="host-input" type="text" bind:value={host} placeholder="192.168.1.100" class="text-input" />
      </div>
      <div class="input-group input-port">
        <label for="port-input">Puerto</label>
        <input id="port-input" type="number" bind:value={port} placeholder="20000" class="text-input" />
      </div>
      <button class="btn btn-connect" on:click={connectManual} disabled={loading || !host.trim()}>
        {#if loading}
          <span class="btn-spinner"></span>
        {:else}
          Conectar
        {/if}
      </button>
    </div>
  </div>
</div>

<style>
  .connection-settings {
    animation: fadeIn var(--transition-base) ease-out;
  }

  .section-title {
    font-size: var(--font-size-xl);
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: var(--space-6);
  }

  .current-connection {
    margin-bottom: var(--space-4);
    padding: var(--space-4);
  }

  .conn-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }

  .conn-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-danger);
    transition: background var(--transition-base);
  }

  .conn-status-dot.connected {
    background: var(--accent-success);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
  }

  .conn-label {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .conn-details {
    font-size: var(--font-size-lg);
    font-weight: 600;
    color: var(--text-primary);
    font-family: var(--font-mono, monospace);
  }

  .conn-port {
    color: var(--text-muted);
  }

  .conn-device-info {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--text-muted);
  }

  .conn-device-name {
    color: var(--text-secondary);
    font-weight: 600;
  }

  .conn-device-serial {
    font-family: var(--font-mono, monospace);
  }

  .conn-device-version {
    opacity: 0.7;
  }

  .section {
    margin-bottom: var(--space-4);
    padding: var(--space-5);
  }

  .subsection-title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-base);
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-2);
  }

  .section-desc {
    font-size: var(--font-size-sm);
    color: var(--text-muted);
    margin-bottom: var(--space-4);
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-lg);
    font-family: var(--font-sans);
    font-size: var(--font-size-sm);
    font-weight: 600;
    cursor: pointer;
    border: 1px solid var(--border-subtle);
    transition: all var(--transition-fast);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-scan {
    background: var(--bg-glass);
    color: var(--text-primary);
    width: 100%;
    justify-content: center;
    padding: var(--space-3) var(--space-4);
  }

  .btn-scan:hover:not(:disabled) {
    background: var(--bg-glass-hover);
    border-color: var(--border-accent);
  }

  .btn-connect {
    background: var(--accent-primary);
    color: white;
    border-color: var(--accent-primary);
    padding: var(--space-3) var(--space-6);
    white-space: nowrap;
  }

  .btn-connect:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .scan-results {
    margin-top: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .device-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-sans);
    color: var(--text-primary);
    width: 100%;
    text-align: left;
  }

  .device-item:hover:not(:disabled) {
    background: var(--bg-glass-hover);
    border-color: var(--accent-primary);
  }

  .device-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: var(--bg-glass-active);
    border-radius: var(--radius-md);
    color: var(--accent-primary);
    flex-shrink: 0;
  }

  .device-info {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .device-host {
    font-weight: 600;
    font-size: var(--font-size-sm);
    font-family: var(--font-mono, monospace);
  }

  .device-port {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
  }

  .device-serial {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    font-family: var(--font-mono, monospace);
  }

  .device-connected-badge {
    display: inline-block;
    padding: 0 var(--space-1);
    background: rgba(16, 185, 129, 0.15);
    color: var(--accent-success);
    border-radius: var(--radius-sm);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .device-arrow {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .manual-form {
    display: flex;
    gap: var(--space-3);
    align-items: flex-end;
    flex-wrap: wrap;
  }

  .input-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    flex: 1;
    min-width: 120px;
  }

  .input-group label {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
  }

  .input-port {
    max-width: 100px;
    flex: 0 0 auto;
  }

  .text-input {
    padding: var(--space-2) var(--space-3);
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-family: var(--font-mono, monospace);
    font-size: var(--font-size-sm);
    outline: none;
    transition: border-color var(--transition-fast);
    width: 100%;
  }

  .text-input:focus {
    border-color: var(--accent-primary);
  }

  .text-input::placeholder {
    color: var(--text-muted);
    opacity: 0.5;
  }

  @media (max-width: 480px) {
    .manual-form {
      flex-direction: column;
    }
    .input-port {
      max-width: none;
    }
  }
</style>
