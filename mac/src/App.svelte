<script>
  import { onMount } from 'svelte';

  let ws;
  let status = 'Daemon offline — run: cd mac && uv run python -m daemon.main';
  let daemonOnline = false;
  let listening = false;
  let health = { xnch: null, nexi: null, media: null };
  let transcript = '';
  let response = '';

  function connect() {
    ws = new WebSocket('ws://127.0.0.1:9001');
    ws.onopen = () => {
      daemonOnline = true;
      status = 'Connected — hold the button or Caps Lock to talk';
    };
    ws.onclose = () => {
      daemonOnline = false;
      status = 'Daemon offline — run: cd mac && uv run python -m daemon.main';
    };
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.type === 'status') status = m.text || status;
      if (m.type === 'health') health = m.health;
      if (m.type === 'voice_result') {
        transcript = m.transcript || '';
        response = m.response || '';
        listening = false;
      }
    };
  }

  function send(cmd) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(cmd));
  }

  function arm() {
    if (ws && ws.readyState === 1) {
      listening = true;
      send({ type: 'arm' });
    }
  }

  function disarm() {
    listening = false;
    send({ type: 'disarm' });
  }

  onMount(() => {
    connect();
    return () => ws?.close();
  });
</script>

<main class="cc">
  <header>
    <span class="dot {daemonOnline ? 'ok' : 'down'}"></span>
    <span class="status">{status}</span>
  </header>

  <section class="health">
    {#each ['xnch', 'nexi', 'media'] as name}
      <div class="card">
        <span class="label">{name}</span>
        <span class="val {health[name] === 'ok' ? 'ok' : health[name] ? 'err' : 'unknown'}">
          {health[name] ?? '…'}
        </span>
      </div>
    {/each}
  </section>

  <button
    class="ptt {listening ? 'active' : ''}"
    on:mousedown={arm}
    on:mouseup={disarm}
    on:mouseleave={disarm}
    on:touchstart={(e) => { e.preventDefault(); arm(); }}
    on:touchend={disarm}
  >
    {listening ? 'Listening…' : 'Hold to talk'}
  </button>

  {#if transcript}<p class="you">you: {transcript}</p>{/if}
  {#if response}<p class="nexi">nexi: {response}</p>{/if}
</main>

<style>
  :global(body) { margin: 0; background: #0b0f14; color: #e6edf3; font-family: -apple-system, 'SF Pro Text', sans-serif; }
  .cc { display: flex; flex-direction: column; gap: 16px; padding: 20px; min-height: 100vh; box-sizing: border-box; }
  header { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #8b949e; }
  .dot { width: 10px; height: 10px; border-radius: 50%; }
  .dot.ok { background: #3fb950; }
  .dot.down { background: #f85149; }
  .health { display: flex; gap: 12px; }
  .card { flex: 1; border: 1px solid #21262d; border-radius: 10px; padding: 12px 14px; background: #161b22; }
  .label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; margin-bottom: 4px; }
  .val.ok { color: #3fb950; font-weight: 600; }
  .val.err { color: #d29922; }
  .val.unknown { color: #8b949e; }
  .ptt { margin-top: auto; padding: 18px; border-radius: 12px; border: none; background: #21262d; color: #e6edf3; font-size: 16px; font-weight: 600; cursor: pointer; }
  .ptt.active { background: #1f6feb; }
  .you { color: #8b949e; font-size: 13px; }
  .nexi { color: #e6edf3; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }
</style>
