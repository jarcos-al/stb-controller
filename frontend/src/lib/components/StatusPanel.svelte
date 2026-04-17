<script>
  import { stbStatus, wsConnected, wsReconnecting, stbConnected } from '../stores/websocket.js';
  import { api } from '../utils/api.js';

  let toggling = false;

  async function toggleConnection() {
    toggling = true;
    try {
      if ($stbConnected) {
        await api.disconnectDevice();
        $stbConnected = false;
      } else {
        const res = await api.connectDevice();
        $stbConnected = res.connected;
      }
    } catch (e) {
      console.error('Connection toggle failed:', e);
    } finally {
      toggling = false;
    }
  }

  $: progressPercent = (() => {
    if (!$stbStatus.program_start || !$stbStatus.program_end) return 0;
    const now = Date.now();
    const start = new Date($stbStatus.program_start).getTime();
    const end = new Date($stbStatus.program_end).getTime();
    if (end <= start) return 0;
    return Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100));
  })();

  function formatTime(isoString) {
    if (!isoString) return '--:--';
    try {
      return new Date(isoString).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    } catch { return '--:--'; }
  }
</script>

<div class="status-panel glass-card">
  <!-- Connection indicator -->
  <div class="connection-bar">
    <div class="conn-dot" class:connected={$wsConnected && $stbConnected} class:reconnecting={$wsReconnecting} class:stb-offline={$wsConnected && !$stbConnected}></div>
    <span class="conn-text">
      {#if !$wsConnected}
        {#if $wsReconnecting}
          Reconectando...
        {:else}
          Desconectado
        {/if}
      {:else if $stbConnected}
        Conectado
      {:else}
        STB desconectado
      {/if}
    </span>
    {#if $stbStatus.in_standby}
      <span class="badge badge-warning" style="margin-left: auto;">STANDBY</span>
    {/if}
    {#if $stbStatus.is_recording}
      <span class="badge badge-rec" style="margin-left: var(--space-2);">● REC</span>
    {/if}
  </div>

  <!-- Current Channel -->
  <div class="current-channel">
    <h3 class="channel-name">
      {#if $stbConnected}
        {$stbStatus.current_channel || 'Sin canal'}
      {:else}
        Sin conexión
      {/if}
    </h3>
    {#if $stbStatus.current_program}
      <p class="program-name">{$stbStatus.current_program}</p>
    {/if}
  </div>

  <!-- Connect / Disconnect button -->
  <button class="conn-btn" class:connected={$stbConnected} on:click={toggleConnection} disabled={toggling || !$wsConnected}>
    {#if toggling}
      <span class="btn-spinner"></span>
    {:else if $stbConnected}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18.36 6.64A9 9 0 0 1 20.77 15"/><path d="M6.16 6.16a9 9 0 1 0 12.68 12.68"/><line x1="2" y1="2" x2="22" y2="22"/></svg>
      Desconectar
    {:else}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><circle cx="12" cy="20" r="1"/></svg>
      Conectar
    {/if}
  </button>

  <!-- Program Time Bar -->
  {#if $stbStatus.program_start && $stbStatus.program_end}
    <div class="program-time">
      <div class="time-labels">
        <span>{formatTime($stbStatus.program_start)}</span>
        <span>{formatTime($stbStatus.program_end)}</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" style="width: {progressPercent}%"></div>
      </div>
    </div>
  {/if}

  <!-- Quick Stats -->
  <div class="stats-row">


    {#if $stbStatus.signal_strength !== null}
      <div class="stat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M2 20h.01M7 20v-4M12 20v-8M17 20v-12M22 20V8"/>
        </svg>
        <span>{$stbStatus.signal_strength}%</span>
      </div>
    {/if}

    {#if $stbStatus.signal_snr !== null}
      <div class="stat">
        <span class="stat-label">SNR</span>
        <span>{$stbStatus.signal_snr}%</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .status-panel {
    animation: fadeIn var(--transition-base) ease-out;
  }

  .connection-bar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border-subtle);
  }

  .conn-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-danger);
    transition: background var(--transition-base);
  }

  .conn-dot.connected {
    background: var(--accent-success);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
  }

  .conn-dot.stb-offline {
    background: var(--accent-warning);
    animation: pulse-badge 2s ease-in-out infinite;
  }

  .conn-dot.reconnecting {
    background: var(--accent-warning);
    animation: pulse-badge 1s ease-in-out infinite;
  }

  .conn-text {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .current-channel {
    margin-bottom: var(--space-4);
  }

  .channel-name {
    font-size: var(--font-size-2xl);
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .program-name {
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
    margin-top: var(--space-1);
  }

  .program-time {
    margin-bottom: var(--space-4);
  }

  .time-labels {
    display: flex;
    justify-content: space-between;
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    margin-bottom: var(--space-1);
  }

  .progress-bar {
    height: 4px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-full);
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--gradient-brand);
    border-radius: var(--radius-full);
    transition: width 1s linear;
  }

  .stats-row {
    display: flex;
    gap: var(--space-6);
  }

  .stat {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
  }

  .stat svg {
    color: var(--text-muted);
  }

  .stat-label {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    font-weight: 600;
  }

  .conn-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    margin-top: var(--space-4);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    cursor: pointer;
    transition: all var(--transition-base);
  }

  .conn-btn:hover:not(:disabled) {
    background: var(--bg-secondary);
    color: var(--text-primary);
    border-color: var(--accent-primary);
  }

  .conn-btn.connected {
    border-color: var(--accent-success);
    color: var(--accent-success);
  }

  .conn-btn.connected:hover:not(:disabled) {
    border-color: var(--accent-danger);
    color: var(--accent-danger);
    background: rgba(239, 68, 68, 0.1);
  }

  .conn-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--text-muted);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
