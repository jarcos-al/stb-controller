<script>
  import { sendKeypress } from '../stores/websocket.js';
  import { api } from '../utils/api.js';
  import { stbStatus } from '../stores/websocket.js';
  import { showToast } from '../stores/app.js';

  let pressing = '';

  async function handleKey(key) {
    pressing = key;

    // Haptic feedback on mobile
    if (navigator.vibrate) {
      navigator.vibrate(30);
    }

    try {
      sendKeypress(key);
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    }

    setTimeout(() => { pressing = ''; }, 150);
  }

  function keyClass(key) {
    let base = 'rc-btn';
    if (pressing === key) base += ' pressing';
    return base;
  }
</script>

<div class="remote-control">
  <div class="rc-header">
    <h2>Control Remoto</h2>
    <div class="rc-device-info">
      <span class="device-name">{$stbStatus.device_name || 'STB'}</span>
    </div>
  </div>

  <!-- Power & Input Row -->
  <div class="rc-row rc-top-row">
    <button class={keyClass('POWER')} on:click={() => handleKey('POWER')} id="btn-power">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2v10M18.36 6.64a9 9 0 1 1-12.73 0"/>
      </svg>
    </button>
    <button class={keyClass('MUTE')} on:click={() => handleKey('MUTE')} id="btn-mute">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        {#if $stbStatus.is_muted}
          <path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>
        {:else}
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
        {/if}
      </svg>
    </button>
  </div>

  <!-- Number Pad -->
  <div class="rc-numpad">
    {#each ['1','2','3','4','5','6','7','8','9','0'] as num}
      <button class="{keyClass(num)} rc-num" on:click={() => handleKey(num)} id="btn-{num}">
        {num}
      </button>
    {/each}
  </div>

  <!-- Volume & Channel -->
  <div class="rc-volch">
    <div class="rc-rocker">
      <span class="rocker-label">VOL</span>
      <button class={keyClass('VOL_UP')} on:click={() => handleKey('VOL_UP')} id="btn-volup">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M7 14l5-5 5 5z"/></svg>
      </button>
      <button class={keyClass('VOL_DOWN')} on:click={() => handleKey('VOL_DOWN')} id="btn-voldown">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>
      </button>
    </div>

    <div class="rc-rocker">
      <span class="rocker-label">CH</span>
      <button class={keyClass('CH_UP')} on:click={() => handleKey('CH_UP')} id="btn-chup">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M7 14l5-5 5 5z"/></svg>
      </button>
      <button class={keyClass('CH_DOWN')} on:click={() => handleKey('CH_DOWN')} id="btn-chdown">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>
      </button>
    </div>
  </div>

  <!-- D-Pad + OK -->
  <div class="rc-dpad-container">
    <div class="rc-dpad">
      <button class="{keyClass('UP')} dpad-up" on:click={() => handleKey('UP')} id="btn-up">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M7 14l5-5 5 5z"/></svg>
      </button>
      <button class="{keyClass('LEFT')} dpad-left" on:click={() => handleKey('LEFT')} id="btn-left">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M14 7l-5 5 5 5z"/></svg>
      </button>
      <button class="{keyClass('OK')} dpad-ok" on:click={() => handleKey('OK')} id="btn-ok">
        OK
      </button>
      <button class="{keyClass('RIGHT')} dpad-right" on:click={() => handleKey('RIGHT')} id="btn-right">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M10 17l5-5-5-5z"/></svg>
      </button>
      <button class="{keyClass('DOWN')} dpad-down" on:click={() => handleKey('DOWN')} id="btn-down">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>
      </button>
    </div>
  </div>

  <!-- Navigation Row -->
  <div class="rc-row rc-nav-row">
    <button class="{keyClass('MENU')} rc-nav" on:click={() => handleKey('MENU')} id="btn-menu">MENU</button>
    <button class="{keyClass('EXIT')} rc-nav" on:click={() => handleKey('EXIT')} id="btn-exit">EXIT</button>
    <button class="{keyClass('EPG')} rc-nav" on:click={() => handleKey('EPG')} id="btn-epg">EPG</button>
    <button class="{keyClass('INFO')} rc-nav" on:click={() => handleKey('INFO')} id="btn-info">INFO</button>
  </div>

  <!-- Color Buttons -->
  <div class="rc-row rc-color-row">
    <button class="{keyClass('RED')} rc-color color-red" on:click={() => handleKey('RED')} id="btn-red"></button>
    <button class="{keyClass('GREEN')} rc-color color-green" on:click={() => handleKey('GREEN')} id="btn-green"></button>
    <button class="{keyClass('YELLOW')} rc-color color-yellow" on:click={() => handleKey('YELLOW')} id="btn-yellow"></button>
    <button class="{keyClass('BLUE')} rc-color color-blue" on:click={() => handleKey('BLUE')} id="btn-blue"></button>
  </div>

  <!-- Playback Controls -->
  <div class="rc-row rc-playback-row">
    <button class="{keyClass('REW')} rc-play" on:click={() => handleKey('REW')} id="btn-rew">⏪</button>
    <button class="{keyClass('PLAY')} rc-play" on:click={() => handleKey('PLAY')} id="btn-play">▶</button>
    <button class="{keyClass('PAUSE')} rc-play" on:click={() => handleKey('PAUSE')} id="btn-pause">⏸</button>
    <button class="{keyClass('STOP')} rc-play" on:click={() => handleKey('STOP')} id="btn-stop">⏹</button>
    <button class="{keyClass('FF')} rc-play" on:click={() => handleKey('FF')} id="btn-ff">⏩</button>
    <button class="{keyClass('REC')} rc-play rc-rec" on:click={() => handleKey('REC')} id="btn-rec">⏺</button>
  </div>
</div>

<style>
  .remote-control {
    max-width: 360px;
    margin: 0 auto;
    padding: var(--space-4);
    animation: fadeIn var(--transition-base) ease-out;
  }

  .rc-header {
    text-align: center;
    margin-bottom: var(--space-6);
  }

  .rc-header h2 {
    font-size: var(--font-size-xl);
    font-weight: 600;
    background: var(--gradient-brand);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .device-name {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  /* Base button */
  .rc-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-subtle);
    background: var(--bg-glass);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
    -webkit-tap-highlight-color: transparent;
    user-select: none;
    outline: none;
    font-family: var(--font-sans);
    font-weight: 500;
  }

  .rc-btn:hover {
    background: var(--bg-glass-hover);
    color: var(--text-primary);
    border-color: var(--border-default);
  }

  .rc-btn:active, .rc-btn.pressing {
    background: var(--bg-glass-active);
    transform: scale(0.93);
    border-color: var(--accent-primary);
    box-shadow: var(--shadow-glow);
  }

  /* Rows */
  .rc-row {
    display: flex;
    justify-content: center;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  /* Top Row (Power, Mute) */
  .rc-top-row .rc-btn {
    width: 56px;
    height: 44px;
    border-radius: var(--radius-lg);
  }

  #btn-power {
    color: var(--accent-danger);
    border-color: rgba(239, 68, 68, 0.15);
  }
  #btn-power:hover {
    background: rgba(239, 68, 68, 0.1);
  }

  /* Number Pad */
  .rc-numpad {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-2);
    max-width: 240px;
    margin: 0 auto var(--space-4);
  }

  .rc-num {
    height: 48px;
    border-radius: var(--radius-lg);
    font-size: var(--font-size-lg);
    font-weight: 600;
  }

  .rc-numpad .rc-num:last-child {
    grid-column: 2;
  }

  /* Volume & Channel Rockers */
  .rc-volch {
    display: flex;
    justify-content: space-between;
    padding: 0 var(--space-6);
    margin-bottom: var(--space-6);
  }

  .rc-rocker {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
  }

  .rocker-label {
    font-size: var(--font-size-xs);
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .rc-rocker .rc-btn {
    width: 56px;
    height: 40px;
    border-radius: var(--radius-md);
  }

  /* D-Pad */
  .rc-dpad-container {
    display: flex;
    justify-content: center;
    margin-bottom: var(--space-6);
  }

  .rc-dpad {
    display: grid;
    grid-template-columns: 60px 72px 60px;
    grid-template-rows: 54px 72px 54px;
    gap: var(--space-1);
    grid-template-areas:
      ".     up    .    "
      "left  ok    right"
      ".     down  .    ";
  }

  .dpad-up    { grid-area: up; border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-sm); }
  .dpad-down  { grid-area: down; border-radius: var(--radius-sm) var(--radius-sm) var(--radius-lg) var(--radius-lg); }
  .dpad-left  { grid-area: left; border-radius: var(--radius-lg) var(--radius-sm) var(--radius-sm) var(--radius-lg); }
  .dpad-right { grid-area: right; border-radius: var(--radius-sm) var(--radius-lg) var(--radius-lg) var(--radius-sm); }

  .dpad-ok {
    grid-area: ok;
    border-radius: var(--radius-full);
    font-size: var(--font-size-base);
    font-weight: 700;
    background: var(--gradient-brand);
    color: white;
    border-color: transparent;
    box-shadow: var(--shadow-glow);
  }

  .dpad-ok:hover {
    filter: brightness(1.15);
    box-shadow: var(--shadow-glow-strong);
  }

  .dpad-ok:active, .dpad-ok.pressing {
    transform: scale(0.9);
  }

  /* Nav Row */
  .rc-nav {
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* Color Buttons */
  .rc-color {
    flex: 1;
    height: 12px;
    border-radius: var(--radius-full);
    border: none !important;
    max-width: 60px;
  }

  .color-red    { background: #ef4444; }
  .color-green  { background: #22c55e; }
  .color-yellow { background: #eab308; }
  .color-blue   { background: #3b82f6; }

  .rc-color:hover { filter: brightness(1.3); }
  .rc-color:active { filter: brightness(0.8); }

  /* Playback */
  .rc-playback-row {
    flex-wrap: wrap;
  }

  .rc-play {
    width: 44px;
    height: 38px;
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
  }

  .rc-rec {
    color: var(--accent-danger);
  }

  @media (max-width: 400px) {
    .remote-control {
      padding: var(--space-2);
    }
    .rc-dpad {
      grid-template-columns: 50px 64px 50px;
      grid-template-rows: 46px 64px 46px;
    }
  }
</style>
