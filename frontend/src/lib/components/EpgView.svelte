<script>
  import { onMount } from 'svelte';
  import { api } from '../utils/api.js';
  import { showToast } from '../stores/app.js';

  let epgData = [];
  let loading = true;
  let selectedChannel = null;
  let channelEpg = [];
  let loadingDetail = false;

  onMount(async () => {
    await loadEpgNowNext();
  });

  async function loadEpgNowNext() {
    loading = true;
    try {
      epgData = await api.getEpgNowNext();
    } catch (err) {
      showToast('Error cargando EPG', 'error');
    }
    loading = false;
  }

  async function showChannelEpg(item) {
    selectedChannel = item;
    loadingDetail = true;
    try {
      channelEpg = await api.getEpgService(item.service_ref);
    } catch (err) {
      showToast('Error cargando programación', 'error');
      channelEpg = [];
    }
    loadingDetail = false;
  }

  function closeDetail() {
    selectedChannel = null;
    channelEpg = [];
  }

  function formatTime(isoString) {
    if (!isoString) return '--:--';
    try {
      return new Date(isoString).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    } catch { return '--:--'; }
  }

  function formatDuration(seconds) {
    if (!seconds) return '';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}min` : `${m}min`;
  }

  function isNow(startTime, duration) {
    if (!startTime) return false;
    const start = new Date(startTime).getTime();
    const end = start + (duration * 1000);
    const now = Date.now();
    return now >= start && now < end;
  }
</script>

<div class="epg-view">
  <div class="epg-header">
    <h2>
      {#if selectedChannel}
        <button class="back-btn" on:click={closeDetail}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
        </button>
        {selectedChannel.channel_name}
      {:else}
        Guía de Programación
      {/if}
    </h2>
    {#if !selectedChannel}
      <button class="btn btn-ghost" on:click={loadEpgNowNext}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M23 4v6h-6M1 20v-6h6"/>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
        </svg>
        Actualizar
      </button>
    {/if}
  </div>

  {#if loading}
    <div class="loading-indicator">
      <div class="spinner"></div>
      <span>Cargando programación...</span>
    </div>
  {:else if selectedChannel}
    <!-- Channel Detail EPG -->
    <div class="epg-detail">
      {#if loadingDetail}
        <div class="loading-indicator">
          <div class="spinner"></div>
        </div>
      {:else}
        <div class="epg-timeline stagger">
          {#each channelEpg as event}
            <div class="epg-event glass-card" class:now={isNow(event.start_time, event.duration)}>
              <div class="event-time">
                <span class="event-start">{formatTime(event.start_time)}</span>
                <span class="event-duration">{formatDuration(event.duration)}</span>
              </div>
              <div class="event-info">
                <span class="event-title">{event.title}</span>
                {#if event.description}
                  <span class="event-desc">{event.description}</span>
                {/if}
                {#if event.genre}
                  <span class="badge badge-hd" style="margin-top: var(--space-1)">{event.genre}</span>
                {/if}
              </div>
              {#if isNow(event.start_time, event.duration)}
                <span class="badge badge-live">AHORA</span>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <!-- Now/Next Grid -->
    <div class="epg-grid stagger">
      {#each epgData as item}
        <button class="epg-card glass-card" on:click={() => showChannelEpg(item)}>
          <div class="epg-channel-name">{item.channel_name}</div>
          {#if item.now}
            <div class="epg-now">
              <span class="epg-time">{formatTime(item.now.start_time)}</span>
              <span class="epg-title">{item.now.title}</span>
              <span class="badge badge-live" style="margin-left: auto; flex-shrink: 0;">AHORA</span>
            </div>
          {/if}
          {#if item.next}
            <div class="epg-next">
              <span class="epg-time">{formatTime(item.next.start_time)}</span>
              <span class="epg-title next-title">{item.next.title}</span>
            </div>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .epg-view {
    animation: fadeIn var(--transition-base) ease-out;
  }

  .epg-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
  }

  .epg-header h2 {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-xl);
    font-weight: 600;
    background: var(--gradient-brand);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .back-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: var(--bg-glass);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    color: var(--text-secondary);
    -webkit-text-fill-color: initial;
    transition: all var(--transition-fast);
  }

  .back-btn:hover {
    background: var(--bg-glass-hover);
    color: var(--text-primary);
  }

  /* Now/Next Grid */
  .epg-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: calc(100vh - 200px);
    overflow-y: auto;
  }

  .epg-card {
    text-align: left;
    width: 100%;
    cursor: pointer;
    padding: var(--space-3) var(--space-4);
    font-family: var(--font-sans);
  }

  .epg-channel-name {
    font-size: var(--font-size-sm);
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: var(--space-2);
  }

  .epg-now, .epg-next {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
  }

  .epg-time {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    font-weight: 600;
    font-family: var(--font-mono);
    flex-shrink: 0;
    width: 44px;
  }

  .epg-title {
    font-size: var(--font-size-sm);
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .next-title {
    color: var(--text-secondary);
  }

  /* Timeline Detail */
  .epg-timeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: calc(100vh - 200px);
    overflow-y: auto;
  }

  .epg-event {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
  }

  .epg-event.now {
    border-color: var(--accent-primary);
    background: rgba(59, 130, 246, 0.06);
  }

  .event-time {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 50px;
  }

  .event-start {
    font-size: var(--font-size-sm);
    font-weight: 700;
    color: var(--text-primary);
    font-family: var(--font-mono);
  }

  .event-duration {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
  }

  .event-info {
    flex: 1;
    min-width: 0;
  }

  .event-title {
    display: block;
    font-size: var(--font-size-sm);
    font-weight: 600;
    color: var(--text-primary);
  }

  .event-desc {
    display: block;
    font-size: var(--font-size-xs);
    color: var(--text-secondary);
    margin-top: var(--space-1);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

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
</style>
