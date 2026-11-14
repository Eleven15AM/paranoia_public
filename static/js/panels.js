// Health list + session stats. Pure rendering; no fetching.
(function () {
    const healthList = document.getElementById('health-list');
    const healthSummary = document.getElementById('health-summary');
    const lastPollElem = document.getElementById('last-poll');
    const nextPollElem = document.getElementById('next-poll');

    // Layer 1: ALERTS count = events above this threshold (mirror config.py).
    const SEVERITY_HIGH = 70;

    const statsEls = {
        total:  document.getElementById('stat-total'),
        alerts: document.getElementById('stat-alerts'),
        NEWS:   document.getElementById('stat-news'),
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
            // is required when a new feed starts emitting it; unknown
            // categories are counted in `unknown` and logged once so the
            // next addition is not a silent zero.
            const byCat = {
                NEWS: 0, SPACE: 0, QUAKE: 0, FLIGHT: 0, NEO: 0, COMMODITY: 0,
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