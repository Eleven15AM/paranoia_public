// Orchestrator. Fetches /api/config once, then /api/events on a fixed
// interval. Wires controls, clock, and pause. This is the only file that
// knows about the server.
(function () {
    const POLL_MS = 60000;
    const clockElem = document.getElementById('clock-display');
    const sysStatus = document.getElementById('sys-status');

    const state = {
        scanlines: true,
        paused: false,
        feedMeta: {},
    };

    // --- Clock ---
    function tickClock() {
        clockElem.textContent = new Date().toUTCString().split(' ')[4] + ' UTC';
    }
    setInterval(tickClock, 1000);
    tickClock();

    // --- Controls ---
    const btnScanlines = document.getElementById('btn-scanlines');
    const btnAudio = document.getElementById('btn-audio');
    const btnPause = document.getElementById('btn-pause');

    btnScanlines.addEventListener('click', () => {
        window.audio.playClick();
        state.scanlines = !state.scanlines;
        if (state.scanlines) {
            document.body.classList.add('crt');
            btnScanlines.textContent = '[CRT: ON]';
            btnScanlines.classList.remove('text-gray-500');
        } else {
            document.body.classList.remove('crt');
            btnScanlines.textContent = '[CRT: OFF]';
            btnScanlines.classList.add('text-gray-500');
        }
    });

    btnAudio.addEventListener('click', () => {
        window.audio.enabled = !window.audio.enabled;
        if (window.audio.enabled) {
            window.audio.playClick();
            btnAudio.textContent = '[AUDIO: ON]';
            btnAudio.classList.remove('text-gray-500');
        } else {
            btnAudio.textContent = '[AUDIO: OFF]';
            btnAudio.classList.add('text-gray-500');
        }
    });

    btnPause.addEventListener('click', () => {
        window.audio.playClick();
        state.paused = !state.paused;
        if (state.paused) {
            btnPause.textContent = '[FEED: PAUSED]';
            btnPause.classList.add('text-nix-amber');
            sysStatus.textContent = '● PAUSED';
            sysStatus.className = 'text-nix-amber font-bold glow-amber';
        } else {
            btnPause.textContent = '[FEED: LIVE]';
            btnPause.classList.remove('text-nix-amber');
            sysStatus.textContent = '● ONLINE';
            sysStatus.className = 'text-nix-green font-bold blinking glow-green';
            poll();
        }
    });

    // --- Fetching ---
    let firstLoad = true;

    async function loadConfig() {
        try {
            const r = await fetch('/api/config');
            if (!r.ok) throw new Error(r.statusText);
            const data = await r.json();
            state.feedMeta = data.feeds || {};
        } catch (e) {
            console.warn('config fetch failed', e);
        }
    }

    async function poll() {
        if (state.paused) return;
        const startedAt = Date.now();
        try {
            const r = await fetch('/api/events');
            if (!r.ok) throw new Error(r.statusText);
            const data = await r.json();
            const events = data.events || [];
            const health = data.health || {};

            window.stream.ingest(events, firstLoad);
            window.panels.updateHealth(health, state.feedMeta);
            window.panels.updateStats(events);
            window.panels.setPollAnchor(startedAt, POLL_MS);

            firstLoad = false;
        } catch (e) {
            console.error('poll failed', e);
            sysStatus.textContent = '● DEGRADED';
            sysStatus.className = 'text-nix-red font-bold glow-red';
        }
    }

    // --- Boot ---
    (async () => {
        await loadConfig();
        await poll();
        setInterval(poll, POLL_MS);
    })();
})();