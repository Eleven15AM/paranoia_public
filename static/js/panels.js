// Health list + session stats + ALERTS panel. Pure rendering; no fetching.
(function () {
    const healthList = document.getElementById('health-list');
    const healthSummary = document.getElementById('health-summary');
    const lastPollElem = document.getElementById('last-poll');
    const nextPollElem = document.getElementById('next-poll');
    const alertsList = document.getElementById('alerts-list');
    const alertsCount = document.getElementById('alerts-count');

    // Layer 1: ALERTS count = events above this threshold (mirror config.py).
    const SEVERITY_HIGH = 70;
    // Layer 3: ALERTS panel capacity (mirror config.py: ALERTS_PANEL_LIMIT).
    const ALERTS_PANEL_LIMIT = 5;

    const statsEls = {
        total:  document.getElementById('stat-total'),
        alerts: document.getElementById('stat-alerts'),
        NEWS:   document.getElementById('stat-news'),
        VELOCITY: document.getElementById('stat-velocity'),
        SPACE:  document.getElementById('stat-space'),
        QUAKE:  document.getElementById('stat-quake'),
        FLIGHT: document.getElementById('stat-flight'),
        NEO:    document.getElementById('stat-neo'),
        COMMODITY: document.getElementById('stat-commodity'),
    };

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function relAge(iso) {
        const t = new Date(iso).getTime();
        const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
        if (s < 60) return `${s}s`;
        if (s < 3600) return `${Math.floor(s / 60)}m`;
        return `${Math.floor(s / 3600)}h`;
    }

    // Display-only time formatting. Kept in sync with stream.js: NEWS and
    // VELOCITY show the full date; other feeds keep HH:MM:SSZ. Duplicating
    // ~8 lines is cheaper than a shared module (CONTEXT.md: minimal surface).
    function fmtTime(e) {
        const iso = new Date(e.timestamp).toISOString();
        if (e.category === 'NEWS' || e.category === 'VELOCITY') {
            return iso.slice(0, 10) + ' ' + iso.slice(11, 19) + 'Z';
        }
        return iso.slice(11, 19) + 'Z';
    }

    window.panels = {
        updateHealth(health, feedMeta) {
            // health = { feed_name: {ok, error, fetched_at, event_count} }
            // feedMeta = { feed_name: {label, category} }
            const names = Object.keys(feedMeta);
            let okCount = 0;

            healthList.innerHTML = '';
            names.forEach((name) => {
                const h = health[name];
                const meta = feedMeta[name];
                const label = (meta && meta.label) || name;

                let dot = '●';
                let colorCls = 'health-err';
                let detail = 'no poll yet';

                if (h) {
                    const age = relAge(h.fetched_at);
                    if (h.ok && !h.error) {
                        dot = '●';
                        colorCls = 'health-ok';
                        detail = `${h.event_count} evt · ${age} ago`;
                        okCount++;
                    } else if (h.ok && h.error) {
                        colorCls = 'health-stale';
                        detail = `stale: ${age}`;
                    } else {
                        colorCls = 'health-err';
                        detail = h.error ? `err: ${escapeHtml(h.error).slice(0, 40)}` : 'error';
                    }
                }

                const row = document.createElement('div');
                row.className = 'health-row';
                row.innerHTML = `
                    <span class="${colorCls}">
                        <span class="mr-1">${dot}</span>${escapeHtml(label)}
                    </span>
                    <span class="text-gray-500 text-[10px]">${detail}</span>
                `;
                healthList.appendChild(row);
            });

            healthSummary.textContent = `${okCount}/${names.length} OK`;

            // Play a stale tone once when a feed transitions to error, but
            // only if it previously had data (avoid firing on first-ever poll)
            names.forEach((name) => {
                const h = health[name];
                if (!h) return;
                const was = window.__prevHealth && window.__prevHealth[name];
                if (was && was.ok && !h.ok && h.error) {
                    window.audio.playStale();
                }
            });
            window.__prevHealth = health;
        },

        updateStats(events) {
            // Initialize every category explicitly. Adding a category here
            // is required when a new feed (or synthetic event type) starts
            // emitting it; unknown categories are counted in `unknown` and
            // logged once so the next addition is not a silent zero.
            const byCat = {
                NEWS: 0, VELOCITY: 0, SPACE: 0, QUAKE: 0, FLIGHT: 0, NEO: 0, COMMODITY: 0,
            };
            let unknown = 0;
            let alerts = 0;
            const unknownSeen = new Set();
            events.forEach((e) => {
                if ((Number(e.severity) || 0) > SEVERITY_HIGH) alerts++;
                if (byCat[e.category] != null) {
                    byCat[e.category]++;
                } else {
                    unknown++;
                    if (!unknownSeen.has(e.category)) {
                        unknownSeen.add(e.category);
                        console.warn('stats: uncounted category', e.category);
                    }
                }
            });

            statsEls.total.textContent = String(events.length);
            if (statsEls.alerts) statsEls.alerts.textContent = String(alerts);
            Object.entries(byCat).forEach(([k, v]) => {
                const el = statsEls[k];
                if (el) el.textContent = String(v);
            });
            if (unknown > 0) {
                console.warn(`stats: ${unknown} events in unknown categories`);
            }
        },

        // Layer 3: dedicated ALERTS panel above the stream. Compact one-line
        // rows; newest first; capped at ALERTS_PANEL_LIMIT; click opens the
        // existing dossier. The stream still shows every event — this panel
        // is additive, not a replacement.
        updateAlerts(events) {
            const highs = events
                .filter((e) => (Number(e.severity) || 0) > SEVERITY_HIGH)
                .sort((a, b) => String(b.timestamp).localeCompare(String(a.timestamp)));

            const shown = highs.slice(0, ALERTS_PANEL_LIMIT);
            const overflow = highs.length - shown.length;

            alertsList.innerHTML = '';
            if (shown.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'text-gray-500 italic';
                empty.textContent = 'no active alerts';
                alertsList.appendChild(empty);
            } else {
                shown.forEach((e) => {
                    const row = document.createElement('div');
                    row.className = 'text-nix-red cursor-pointer hover:bg-white/5 px-1 py-0.5 truncate';
                    row.dataset.eventId = e.source_url + '|' + e.title + '|' + e.timestamp;
                    row.innerHTML =
                        `<span class="text-nix-red">[${escapeHtml(e.category)}]</span> ` +
                        `<span class="text-gray-500">${fmtTime(e)}</span> ` +
                        `<span class="text-gray-300">${escapeHtml(e.source_name || '')}</span> ` +
                        `<span class="text-gray-200">— ${escapeHtml(e.title || '')}</span>`;
                    row.addEventListener('click', () => {
                        window.audio.playClick();
                        window.stream.openDossier(e);
                    });
                    alertsList.appendChild(row);
                });
            }

            const suffix = overflow > 0 ? ` (+${overflow} more)` : '';
            alertsCount.textContent = `${highs.length} active${suffix}`;
        },

        setPollTiming(lastIso, nextSeconds) {
            if (lastIso) {
                lastPollElem.textContent = new Date(lastIso).toLocaleTimeString();
            }
            nextPollElem.textContent = nextSeconds != null ? `${nextSeconds}s` : '--';
        },
    };

    // Countdown ticker (independent of the fetch interval)
    let lastPollMs = null;
    let intervalMs = 20000;
    setInterval(() => {
        if (lastPollMs == null) return;
        const remain = Math.max(0, Math.round((intervalMs - (Date.now() - lastPollMs)) / 1000));
        nextPollElem.textContent = `${remain}s`;
    }, 1000);

    // Allow app.js to update the countdown anchors
    window.panels.setPollAnchor = (ms, interval) => {
        lastPollMs = ms;
        intervalMs = interval;
        lastPollElem.textContent = new Date(ms).toLocaleTimeString();
        nextPollElem.textContent = `${Math.round(interval / 1000)}s`;
    };
})();