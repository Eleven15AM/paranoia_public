// Event stream panel. Owns:
//   - card rendering with source and category tags
//   - keyword burn-in derived from event tags (not a hardcoded word list)
//   - client-side filtering
//   - dossier drawer
//   - the bottom ticker
//
// Layer 1: severity tiers. Thresholds mirror config.py (SEVERITY_MEDIUM/HIGH).
// Layer 2: VELOCITY category renders like any event (severity 75 → red tier).
//          NEWS and VELOCITY cards show the full date; other feeds keep HH:MM:SSZ.
// Keep thresholds in sync with config.py — api/routes.py does not currently
// expose /api/config.
(function () {
    const SEVERITY_MEDIUM = 40;
    const SEVERITY_HIGH = 70;

    const logTerminal = document.getElementById('log-terminal');
    const logCount = document.getElementById('log-count');
    const tickerContent = document.getElementById('ticker-content');
    const dossierPanel = document.getElementById('dossier-panel');
    const dossierTitle = document.getElementById('dossier-title');
    const dossierBody = document.getElementById('dossier-body');
    const dossierClose = document.getElementById('dossier-close');

    const filterBtns = Array.from(document.querySelectorAll('.filter-btn'));

    const CAT_COLOR = {
        NEWS:   'text-nix-magenta',
        VELOCITY: 'text-nix-red',
        SPACE:  'text-nix-yellow',
        QUAKE:  'text-nix-amber',
        FLIGHT: 'text-nix-cyan',
        NEO:    'text-nix-yellow',
        COMMODITY: 'text-nix-green',
        SQUAWK: 'text-nix-red',
    };
    const TAG_CLASS = {
        // tag value → burn-in class; unknown tags get no highlight
        M4: 'kw-amber', M5: 'kw-amber', M6: 'kw-amber', M7: 'kw-amber', M8: 'kw-amber',
        M9: 'kw-red',
        X: 'kw-red',
        TSUNAMI: 'kw-red',
        HAZARD: 'kw-red',
        MIL: 'kw-cyan',
        '7500': 'kw-red', '7600': 'kw-red', '7700': 'kw-red',
        SURGE: 'kw-red',
    };
    // Map a full tag like "M6.2" to its class by first two chars
    function tagClass(tag) {
        if (TAG_CLASS[tag]) return TAG_CLASS[tag];
        const prefix = tag.slice(0, 2);
        if (TAG_CLASS[prefix]) return TAG_CLASS[prefix];
        if (tag.startsWith('X')) return 'kw-red';
        return null;
    }

    // Filter state
    let filter = 'ALL';
    // The most recent merged event list from the server
    let events = [];
    // Rendered event IDs so we don't re-insert the same card on each poll
    const rendered = new Set();
    let totalCount = 0;

    function eventId(e) {
        return e.source_url + '|' + e.title + '|' + e.timestamp;
    }

    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // Time display. NEWS and VELOCITY (news-derived) show the full date;
    // other feeds keep the compact HH:MM:SSZ. Server sends ISO; this is a
    // display-only transform and never touches user-supplied text.
    function fmtTime(e) {
        const iso = new Date(e.timestamp).toISOString(); // YYYY-MM-DDTHH:MM:SS.sssZ
        if (e.category === 'NEWS' || e.category === 'VELOCITY') {
            // YYYY-MM-DD HH:MM:SSZ
            return iso.slice(0, 10) + ' ' + iso.slice(11, 19) + 'Z';
        }
        return iso.slice(11, 19) + 'Z';
    }

    // Very narrow sanitizer: we build a small allowlist of <span class="...">
    // for tags. Everything else is escaped, so no user data reaches innerHTML
    // unescaped. This preserves the prototype's XSS guard.
    function renderTags(tags) {
        if (!tags || !tags.length) return '';
        return tags
            .map((t) => {
                const cls = tagClass(t);
                const safe = escapeHtml(t);
                return cls
                    ? `<span class="${cls}">${safe}</span>`
                    : `<span class="tag-pill cat">${safe}</span>`;
            })
            .join(' ');
    }

    // Severity tier for NEWS/VELOCITY only; other categories → 'low'.
    function severityTier(e) {
        if (e.category !== 'NEWS' && e.category !== 'VELOCITY') return 'low';
        const s = Number(e.severity) || 0;
        if (s > SEVERITY_HIGH) return 'high';
        if (s > SEVERITY_MEDIUM) return 'medium';
        return 'low';
    }

    function renderCard(e) {
        const time = fmtTime(e);
        const catColor = CAT_COLOR[e.category] || 'text-nix-cyan';
        const src = escapeHtml(e.source_name);
        const title = escapeHtml(e.title);
        const desc = escapeHtml(e.description || '');
        const cat = escapeHtml(e.category);
        const tier = severityTier(e);
        const loc = e.lat != null && e.lon != null
            ? `${e.lat.toFixed(1)}°, ${e.lon.toFixed(1)}°`
            : '';

        const div = document.createElement('div');
        let cls = 'border-b border-nix-border/40 pb-1.5 hover:bg-white/5 transition-colors cursor-pointer';
        if (tier === 'high') {
            cls += ' border-l-4 border-l-nix-red pl-2';
        } else if (tier === 'medium') {
            cls += ' border-l-4 border-l-nix-amber pl-2';
        }
        div.className = cls;
        div.dataset.filter = e.category;
        div.dataset.eventId = eventId(e);
        div.dataset.severity = String(Number(e.severity) || 0);

        const titleCls = tier === 'high' ? 'text-gray-100 mt-0.5 font-bold' : 'text-gray-200 mt-0.5';
        const pin = tier === 'high' ? '<span class="text-nix-red font-bold mr-1">[PIN]</span>' : '';

        div.innerHTML = `
            <div class="flex justify-between text-[10px] text-gray-500 gap-2">
                <span class="truncate">
                    ${time}
                    <strong class="${catColor}">[${cat}]</strong>
                    <span class="text-gray-300">${src}</span>
                </span>
                <span class="text-gray-400 shrink-0">${loc}</span>
            </div>
            <div class="${titleCls}">${pin}${title}</div>
            <div class="text-gray-400 mt-0.5">${desc.slice(0, 180)}${desc.length > 180 ? '…' : ''}</div>
            <div class="text-gray-500 mt-0.5">
                ${loc ? `<span class="tag-pill cat">${loc}</span>` : ''}
                ${renderTags(e.tags)}
            </div>
        `;

        div.addEventListener('click', () => {
            window.audio.playClick();
            openDossier(e);
        });
        return div;
    }

    function applyFilter() {
        Array.from(logTerminal.querySelectorAll('[data-event-id]')).forEach((el) => {
            const ok = filter === 'ALL' || el.dataset.filter === filter;
            el.style.display = ok ? '' : 'none';
        });
    }

    function setFilter(next, btn) {
        filter = next;
        filterBtns.forEach((b) => {
            b.className = 'filter-btn bg-black text-gray-400 border border-nix-border px-1.5 py-0.5';
        });
        btn.className = 'filter-btn active bg-nix-cyan text-black px-1.5 py-0.5 font-bold';
        applyFilter();
    }

    filterBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            window.audio.playClick();
            setFilter(btn.getAttribute('data-filter'), btn);
        });
    });

    function pushTicker(e) {
        const bit = `--- [${e.category}] ${e.source_name}: ${e.title}`;
        tickerContent.textContent = bit + ' ' + tickerContent.textContent.slice(0, 500);
    }

    function openDossier(e) {
        dossierTitle.textContent = `> ${e.title || 'DOSSIER'} (${e.category || '?'})`;
        // Full date for NEWS/VELOCITY; compact time for the rest (matches card).
        const ts = e.timestamp ? fmtTime(e) : 'LIVE';
        const lat = e.lat != null ? e.lat.toFixed(2) : '—';
        const lon = e.lon != null ? e.lon.toFixed(2) : '—';
        dossierBody.innerHTML = `
            <div><strong>CATEGORY:</strong> ${escapeHtml(e.category || '')}</div>
            <div><strong>SOURCE:</strong> ${escapeHtml(e.source_name || '')}</div>
            <div><strong>TIMESTAMP:</strong> ${escapeHtml(ts)}</div>
            <div><strong>COORDS:</strong> ${lat}, ${lon}</div>
            <div><strong>SEVERITY:</strong> ${Number(e.severity) || 0}</div>
            <div><strong>DETAIL:</strong> ${escapeHtml(e.description || e.text || '')}</div>
            <div class="mt-1">
                <a href="${escapeHtml(e.source_url || '#')}" target="_blank" rel="noopener"
                   class="text-nix-cyan underline">[open source]</a>
            </div>
        `;
        dossierPanel.classList.remove('hidden');
    }

    dossierClose.addEventListener('click', () => {
        window.audio.playClick();
        dossierPanel.classList.add('hidden');
    });

    // Stable sort: high-severity cards first, relative order preserved within
    // each tier. Runs after the per-category cap trim, before applyFilter().
    function sortBySeverity() {
        const cards = Array.from(logTerminal.children);
        cards.sort((a, b) => {
            const sa = Number(a.dataset.severity) || 0;
            const sb = Number(b.dataset.severity) || 0;
            const ha = sa > SEVERITY_HIGH ? 1 : 0;
            const hb = sb > SEVERITY_HIGH ? 1 : 0;
            return hb - ha;
        });
        cards.forEach((el) => logTerminal.appendChild(el));
    }

    window.stream = {
        openDossier,
        ingest(newEvents, isInitial) {
            // Server sends newest-first; we render newest-first into the DOM
            // by inserting at the top. Track what's already on screen.
            const fresh = newEvents.filter((e) => !rendered.has(eventId(e)));

            if (isInitial) {
                logTerminal.innerHTML = '';
                rendered.clear();
                totalCount = 0;
            }

            if (!fresh.length && !isInitial) return;

            // Render oldest → newest so prepending each keeps newest at top
            fresh.slice().reverse().forEach((e) => {
                logTerminal.insertBefore(renderCard(e), logTerminal.firstChild);
                rendered.add(eventId(e));
                totalCount++;
                pushTicker(e);
                if (isInitial) return;
                // Audio triggers on genuinely new, high-severity events only.
                // VELOCITY is intentionally quiet: it fires from news cards
                // already on screen, not as a new alert tone.
                if (e.category === 'SPACE' && e.tags && e.tags.some((t) => t.startsWith('X'))) {
                    window.audio.playAlert();
                }
                if (e.category === 'QUAKE' && e.tags && e.tags.some((t) => /^M[6-9]/.test(t))) {
                    window.audio.playAlert();
                }
                if (e.category === 'SQUAWK') {
                    window.audio.playAlert();
                }
            });

            // Trim old cards per category, and prune `rendered` in lockstep
            // so the cap is a true rolling window and filtered views do not
            // starve. Without pruning `rendered`, once an event ID is seen it
            // can never be re-admitted, and after enough polling the more
            // frequent feeds (flights) crowd out the rarer ones (quakes, neos).
            const perCategoryCap = 40;
            const byCategory = {};
            Array.from(logTerminal.children).forEach((el) => {
                const cat = el.dataset.filter || 'UNKNOWN';
                (byCategory[cat] = byCategory[cat] || []).push(el);
            });
            Object.values(byCategory).forEach((cards) => {
                for (let i = perCategoryCap; i < cards.length; i++) {
                    const el = cards[i];
                    if (el.dataset && el.dataset.eventId) {
                        rendered.delete(el.dataset.eventId);
                    }
                    logTerminal.removeChild(el);
                }
            });

            // Layer 1: high-severity cards rise to the top of the stream.
            sortBySeverity();

            logCount.textContent = `${String(totalCount).padStart(4, '0')} EVTS`;
            applyFilter();
        },
    };
})();