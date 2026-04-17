<script>
  import { onMount, onDestroy } from 'svelte';
  import { connectWebSocket, disconnectWebSocket, wsConnected } from './lib/stores/websocket.js';
  import { activeView, sidebarOpen, toasts } from './lib/stores/app.js';

  import StatusPanel from './lib/components/StatusPanel.svelte';
  import RemoteControl from './lib/components/RemoteControl.svelte';
  import ChannelList from './lib/components/ChannelList.svelte';
  import EpgView from './lib/components/EpgView.svelte';
  import ConnectionSettings from './lib/components/ConnectionSettings.svelte';

  const NAV_ITEMS = [
    { id: 'remote', label: 'Mando', icon: 'remote' },
    { id: 'channels', label: 'Canales', icon: 'channels' },
    { id: 'epg', label: 'Guía TV', icon: 'epg' },
    { id: 'timers', label: 'Timers', icon: 'timers' },
    { id: 'settings', label: 'Ajustes', icon: 'settings' },
  ];

  onMount(() => {
    connectWebSocket();
  });

  onDestroy(() => {
    disconnectWebSocket();
  });

  function setView(view) {
    $activeView = view;
    $sidebarOpen = false;
  }

  function toggleSidebar() {
    $sidebarOpen = !$sidebarOpen;
  }
</script>

<div class="app-layout">
  <!-- Mobile Header -->
  <header class="app-header">
    <button class="menu-toggle" on:click={toggleSidebar} id="menu-toggle">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        {#if $sidebarOpen}
          <path d="M18 6L6 18M6 6l12 12"/>
        {:else}
          <path d="M3 12h18M3 6h18M3 18h18"/>
        {/if}
      </svg>
    </button>
    <div class="header-brand">
      <div class="brand-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="7" width="20" height="15" rx="2" ry="2"/>
          <polyline points="17 2 12 7 7 2"/>
        </svg>
      </div>
      <span class="brand-text">STB Control</span>
    </div>
    <div class="header-status">
      <div class="status-dot" class:online={$wsConnected}></div>
    </div>
  </header>

  <!-- Sidebar -->
  <aside class="sidebar" class:open={$sidebarOpen}>
    <div class="sidebar-brand">
      <div class="brand-icon-lg">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="url(#brandGrad)" stroke-width="2">
          <defs>
            <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#3b82f6"/>
              <stop offset="100%" style="stop-color:#8b5cf6"/>
            </linearGradient>
          </defs>
          <rect x="2" y="7" width="20" height="15" rx="2" ry="2"/>
          <polyline points="17 2 12 7 7 2"/>
        </svg>
      </div>
      <div>
        <h1 class="brand-title">STB Control</h1>
        <span class="brand-subtitle">Panel de Control</span>
      </div>
    </div>

    <nav class="sidebar-nav">
      {#each NAV_ITEMS as item}
        <button
          class="nav-item"
          class:active={$activeView === item.id}
          on:click={() => setView(item.id)}
          id="nav-{item.id}"
        >
          <div class="nav-icon">
            {#if item.icon === 'remote'}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="5" y="2" width="14" height="20" rx="3"/><circle cx="12" cy="14" r="2"/>
                <line x1="12" y1="6" x2="12" y2="6.01"/>
              </svg>
            {:else if item.icon === 'channels'}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            {:else if item.icon === 'epg'}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
            {:else if item.icon === 'timers'}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
              </svg>
            {:else if item.icon === 'settings'}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            {/if}
          </div>
          <span class="nav-label">{item.label}</span>
          {#if $activeView === item.id}
            <div class="nav-indicator"></div>
          {/if}
        </button>
      {/each}
    </nav>

    <!-- Sidebar Status -->
    <div class="sidebar-footer">
      <StatusPanel />
    </div>
  </aside>

  <!-- Backdrop (mobile) -->
  {#if $sidebarOpen}
    <div class="backdrop" on:click={() => $sidebarOpen = false}></div>
  {/if}

  <!-- Main Content -->
  <main class="main-content">
    {#if $activeView === 'remote'}
      <StatusPanel />
      <RemoteControl />
    {:else if $activeView === 'channels'}
      <ChannelList />
    {:else if $activeView === 'epg'}
      <EpgView />
    {:else if $activeView === 'timers'}
      <div class="placeholder-view glass-card">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        <h3>Timers</h3>
        <p>Gestión de temporizadores de grabación — próximamente en v0.2</p>
      </div>
    {:else if $activeView === 'settings'}
      <ConnectionSettings />
    {/if}
  </main>

  <!-- Bottom Nav (mobile) -->
  <nav class="bottom-nav">
    {#each NAV_ITEMS.slice(0, 4) as item}
      <button
        class="bottom-nav-item"
        class:active={$activeView === item.id}
        on:click={() => setView(item.id)}
      >
        <div class="bnav-icon">
          {#if item.icon === 'remote'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="5" y="2" width="14" height="20" rx="3"/><circle cx="12" cy="14" r="2"/>
            </svg>
          {:else if item.icon === 'channels'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
          {:else if item.icon === 'epg'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/>
            </svg>
          {:else if item.icon === 'timers'}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          {/if}
        </div>
        <span class="bnav-label">{item.label}</span>
      </button>
    {/each}
  </nav>
</div>

<!-- Toasts -->
{#each $toasts as toast (toast.id)}
  <div class="toast toast-{toast.type}" role="alert">
    {toast.message}
  </div>
{/each}

<style>
  .app-layout {
    display: flex;
    min-height: 100vh;
  }

  /* ──── Header (Mobile) ──── */
  .app-header {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: var(--header-height);
    background: rgba(10, 14, 26, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border-subtle);
    z-index: 50;
    padding: 0 var(--space-4);
    align-items: center;
    justify-content: space-between;
  }

  .menu-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .header-brand {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .brand-icon {
    color: var(--accent-primary);
  }

  .brand-text {
    font-weight: 700;
    font-size: var(--font-size-lg);
    background: var(--gradient-brand);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .header-status {
    display: flex;
    align-items: center;
  }

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent-danger);
    transition: background var(--transition-base);
  }

  .status-dot.online {
    background: var(--accent-success);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
  }

  /* ──── Sidebar ──── */
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: var(--sidebar-width);
    background: rgba(10, 14, 26, 0.95);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-right: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    z-index: 40;
    overflow-y: auto;
  }

  .sidebar-brand {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-6);
    border-bottom: 1px solid var(--border-subtle);
  }

  .brand-icon-lg {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    background: var(--bg-glass);
    border-radius: var(--radius-lg);
    flex-shrink: 0;
  }

  .brand-title {
    font-size: var(--font-size-lg);
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .brand-subtitle {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .sidebar-nav {
    padding: var(--space-4);
    flex: 1;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-lg);
    background: none;
    border: 1px solid transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-sans);
    font-size: var(--font-size-sm);
    font-weight: 500;
    position: relative;
    margin-bottom: var(--space-1);
  }

  .nav-item:hover {
    background: var(--bg-glass-hover);
    color: var(--text-primary);
  }

  .nav-item.active {
    background: var(--bg-glass-active);
    color: var(--text-primary);
    border-color: var(--border-accent);
  }

  .nav-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    flex-shrink: 0;
  }

  .nav-indicator {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 3px;
    height: 20px;
    background: var(--gradient-brand);
    border-radius: var(--radius-full);
  }

  .sidebar-footer {
    padding: var(--space-4);
    border-top: 1px solid var(--border-subtle);
  }

  /* ──── Main Content ──── */
  .main-content {
    flex: 1;
    margin-left: var(--sidebar-width);
    padding: var(--space-8);
    max-width: var(--max-content-width);
    min-height: 100vh;
  }

  .placeholder-view {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    padding: var(--space-12);
    text-align: center;
  }

  .placeholder-view h3 {
    font-size: var(--font-size-xl);
    font-weight: 600;
    color: var(--text-primary);
  }

  .placeholder-view p {
    color: var(--text-muted);
    font-size: var(--font-size-sm);
    max-width: 300px;
  }

  /* ──── Bottom Nav (Mobile) ──── */
  .bottom-nav {
    display: none;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 64px;
    background: rgba(10, 14, 26, 0.95);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-top: 1px solid var(--border-subtle);
    z-index: 50;
    justify-content: space-around;
    align-items: center;
    padding: 0 var(--space-2);
    padding-bottom: env(safe-area-inset-bottom, 0);
  }

  .bottom-nav-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: var(--space-2);
    transition: color var(--transition-fast);
    font-family: var(--font-sans);
    -webkit-tap-highlight-color: transparent;
  }

  .bottom-nav-item.active {
    color: var(--accent-primary);
  }

  .bnav-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 35;
  }

  /* ──── Responsive ──── */
  @media (max-width: 768px) {
    .app-header {
      display: flex;
    }

    .sidebar {
      transform: translateX(-100%);
      transition: transform var(--transition-base);
    }

    .sidebar.open {
      transform: translateX(0);
    }

    .sidebar-footer {
      display: none;
    }

    .backdrop {
      display: block;
    }

    .main-content {
      margin-left: 0;
      padding: var(--space-4);
      padding-top: calc(var(--header-height) + var(--space-4));
      padding-bottom: calc(64px + var(--space-4) + env(safe-area-inset-bottom, 0));
    }

    .bottom-nav {
      display: flex;
    }
  }

  @media (min-width: 769px) {
    .backdrop {
      display: none !important;
    }
  }
</style>
