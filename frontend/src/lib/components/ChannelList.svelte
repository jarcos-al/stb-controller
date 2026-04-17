<script>
  import { onMount } from 'svelte';
  import { api } from '../utils/api.js';
  import { showToast } from '../stores/app.js';
  import { stbStatus } from '../stores/websocket.js';

  let channels = [];
  let bouquets = [];
  let selectedBouquet = 'Astra TV';
  let searchQuery = '';
  let loading = false;
  let zapping = null; // service_ref currently zapping

  onMount(async () => {
    await loadBouquets();
    await loadChannels();
  });

  async function loadBouquets() {
    try {
      const all = await api.getBouquets();
      // Only show named bouquets (not generic FAV xx)
      bouquets = all.filter(b => !b.name.match(/^FAV \d+$/));
    } catch {
      bouquets = [];
    }
  }

  async function loadChannels() {
    loading = true;
    try {
      channels = await api.getChannels(selectedBouquet || null);
    } catch (err) {
      showToast('Error cargando canales', 'error');
      channels = [];
    }
    loading = false;
  }

  async function onBouquetChange() {
    await loadChannels();
  }

  async function zapChannel(channel) {
    zapping = channel.service_ref;
    try {
      const result = await api.zapChannel(channel.service_ref);
      if (result.result) {
        showToast(`Cambiado a ${channel.name}`, 'success');
        stbStatus.update(s => ({
          ...s,
          current_channel: channel.name,
          current_channel_ref: channel.service_ref,
        }));
      } else {
        showToast(result.message || 'Error', 'error');
      }
    } catch (err) {
      showToast('Error cambiando canal', 'error');
    }
    zapping = null;
  }

  $: filteredChannels = searchQuery
    ? channels.filter(ch =>
        ch.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : channels;
</script>

<div class="channel-list">
  <div class="cl-header">
    <div class="cl-title-row">
      <h2>Canales</h2>
      {#if channels.length > 0}
        <span class="ch-count">{filteredChannels.length} / {channels.length}</span>
      {/if}
    </div>
    {#if bouquets.length > 0}
      <div class="bouquet-selector">
        <select bind:value={selectedBouquet} on:change={onBouquetChange}>
          <option value="">Todos los canales</option>
          {#each bouquets as bq}
            <option value={bq.service_ref}>{bq.name}</option>
          {/each}
        </select>
      </div>
    {/if}
    <div class="search-box">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
      </svg>
      <input
        type="text"
        placeholder="Buscar canal..."
        bind:value={searchQuery}
        id="channel-search"
      />
      {#if searchQuery}
        <button class="search-clear" on:click={() => searchQuery = ''}>✕</button>
      {/if}
    </div>
  </div>

  <!-- Channel Grid -->
  <div class="channels-container">
    {#if loading}
      <div class="loading-indicator">
        <div class="spinner"></div>
        <span>Escaneando canales del decodificador...</span>
      </div>
    {:else if filteredChannels.length === 0}
      <div class="empty-state">
        <p>No se encontraron canales</p>
      </div>
    {:else}
      <div class="channels-grid">
        {#each filteredChannels as channel, i}
          <button
            class="channel-item glass-card"
            class:active={$stbStatus.current_channel_ref === channel.service_ref}
            class:zapping={zapping === channel.service_ref}
            on:click={() => zapChannel(channel)}
            id="channel-{i}"
          >
            <div class="ch-number">{channel.channel_number || i + 1}</div>
            <div class="ch-info">
              <span class="ch-name">{channel.name}</span>
            </div>
            {#if channel.is_hd}
              <span class="badge badge-hd">HD</span>
            {/if}
            {#if $stbStatus.current_channel_ref === channel.service_ref}
              <span class="badge badge-playing">▶</span>
            {/if}
            {#if zapping === channel.service_ref}
              <div class="zap-spinner"></div>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .channel-list {
    animation: fadeIn var(--transition-base) ease-out;
  }

  .cl-header {
    margin-bottom: var(--space-4);
  }

  .cl-title-row {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .bouquet-selector {
    margin-bottom: var(--space-3);
  }

  .bouquet-selector select {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    cursor: pointer;
    transition: border-color var(--transition-base);
  }

  .bouquet-selector select:hover {
    border-color: var(--accent-primary);
  }

  .bouquet-selector select:focus {
    outline: none;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
  }

  .cl-header h2 {
    font-size: var(--font-size-xl);
    font-weight: 600;
    background: var(--gradient-brand);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .ch-count {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    font-weight: 500;
  }

  .search-box {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    transition: border-color var(--transition-fast);
  }

  .search-box:focus-within {
    border-color: var(--accent-primary);
    box-shadow: var(--shadow-glow);
  }

  .search-box svg {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .search-box input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: var(--font-size-sm);
  }

  .search-box input::placeholder {
    color: var(--text-muted);
  }

  .search-clear {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: var(--font-size-sm);
    padding: 2px 6px;
  }

  .search-clear:hover {
    color: var(--text-primary);
  }

  /* Channels Grid */
  .channels-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: calc(100vh - 280px);
    overflow-y: auto;
  }

  .channel-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-lg);
    cursor: pointer;
    text-align: left;
    width: 100%;
    font-family: var(--font-sans);
    transition: all var(--transition-fast);
  }

  .channel-item:active {
    transform: scale(0.98);
  }

  .channel-item.active {
    border-color: var(--accent-primary);
    background: rgba(59, 130, 246, 0.08);
    box-shadow: inset 0 0 0 1px var(--accent-primary);
  }

  .channel-item.active .ch-number {
    background: var(--gradient-brand);
    color: white;
  }

  .channel-item.zapping {
    opacity: 0.7;
    pointer-events: none;
  }

  .ch-number {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
    font-weight: 700;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .ch-info {
    flex: 1;
    min-width: 0;
  }

  .ch-name {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .badge-hd {
    font-size: 9px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    background: rgba(59, 130, 246, 0.15);
    color: var(--accent-primary);
  }

  .badge-playing {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    background: rgba(16, 185, 129, 0.15);
    color: var(--accent-success);
  }

  .zap-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-subtle);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    flex-shrink: 0;
  }

  /* Loading */
  .loading-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-12);
    color: var(--text-muted);
    font-size: var(--font-size-sm);
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-subtle);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .empty-state {
    padding: var(--space-12);
    text-align: center;
    color: var(--text-muted);
  }
</style>
