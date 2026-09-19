document.addEventListener('DOMContentLoaded', () => {
    const btnAnalyze = document.getElementById('analyze-btn');
    const tickerInput = document.getElementById('ticker');
    const companySearch = document.getElementById('company-search');
    const suggestionsBox = document.getElementById('company-suggestions');
    const selectedLabel = document.getElementById('selected-company');
    const deviceSelect = document.getElementById('device');
    const forceRefreshCheck = document.getElementById('force-refresh');

    const loadingOverlay = document.getElementById('loading-overlay');
    const dashboardContent = document.getElementById('dashboard-content');
    const emptyState = document.getElementById('empty-state');
    const reportView = document.getElementById('report-view');

    const tabs = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    let latestData = null;
    let gpuTimer = null;
    let searchTimer = null;
    let cachedCompanies = [];

    const PLOTLY_CFG = { responsive: true, displaylogo: false };

    function showTab(targetId) {
        tabs.forEach(t => t.classList.toggle('active', t.dataset.target === targetId));
        tabContents.forEach(c => {
            const on = c.id === targetId;
            c.classList.toggle('active', on);
            c.classList.toggle('hidden', !on);
            c.style.display = on ? 'block' : '';
        });
        const target = document.getElementById(targetId);
        requestAnimationFrame(() => {
            if (!target) return;
            target.querySelectorAll('.js-plotly-plot').forEach(gd => {
                try { Plotly.Plots.resize(gd); } catch (e) { /* empty plot */ }
            });
        });
        if (targetId === 'tab-compare') renderComparePicker();
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => showTab(tab.dataset.target));
    });

    function paddedRange(values, absMin, absMax, minSpan) {
        const nums = values.filter(v => typeof v === 'number' && !Number.isNaN(v));
        if (!nums.length) return [absMin, absMax];
        let lo = Math.min(...nums);
        let hi = Math.max(...nums);
        const span = Math.max(hi - lo, minSpan);
        const pad = span * 0.25;
        lo = Math.max(absMin, lo - pad);
        hi = Math.min(absMax, hi + pad);
        if (hi - lo < minSpan) {
            const mid = (lo + hi) / 2;
            lo = Math.max(absMin, mid - minSpan / 2);
            hi = Math.min(absMax, lo + minSpan);
        }
        return [lo, hi];
    }

    function drawNativeChart(el, points, opts = {}) {
        if (!el) return;
        const color = opts.color || '#3b82f6';
        const format = opts.format || ((v) => Number(v).toFixed(3));
        const mode = opts.mode || 'line';
        const onClick = opts.onClick;
        if (!points || !points.length) {
            el.innerHTML = '<p class="nc-hint">No data</p>';
            return;
        }
        const w = 720;
        const h = 260;
        const pad = { l: 52, r: 18, t: 18, b: 44 };
        const ys = points.map(p => p.y);
        let yMin = opts.yMin != null ? opts.yMin : Math.min(...ys);
        let yMax = opts.yMax != null ? opts.yMax : Math.max(...ys);
        if (yMax === yMin) {
            yMin -= 0.05;
            yMax += 0.05;
        }
        if (mode === 'bar') {
            yMin = Math.min(yMin, 0);
            yMax = Math.max(yMax, 0);
        }
        const innerW = w - pad.l - pad.r;
        const innerH = h - pad.t - pad.b;
        const xPos = (i) => pad.l + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
        const yPos = (v) => pad.t + (1 - (v - yMin) / (yMax - yMin)) * innerH;
        const ticks = 4;
        let grid = '';
        for (let i = 0; i <= ticks; i++) {
            const val = yMin + (yMax - yMin) * (i / ticks);
            const y = yPos(val);
            grid += `<line x1="${pad.l}" x2="${w - pad.r}" y1="${y}" y2="${y}" stroke="rgba(255,255,255,0.06)"/>`;
            grid += `<text x="${pad.l - 8}" y="${y + 4}" text-anchor="end" fill="#94a3b8" font-size="11">${format(val)}</text>`;
        }
        let body = '';
        if (mode === 'bar') {
            const bw = Math.max(6, innerW / points.length * 0.55);
            points.forEach((p, i) => {
                const x = xPos(i);
                const zero = yPos(0);
                const y = yPos(p.y);
                const top = Math.min(zero, y);
                const bh = Math.max(2, Math.abs(zero - y));
                const fill = p.y >= 0 ? '#10b981' : '#ef4444';
                body += `<rect class="nc-dot" data-i="${i}" x="${x - bw / 2}" y="${top}" width="${bw}" height="${bh}" rx="3" fill="${fill}" opacity="0.9"/>`;
            });
        } else {
            const d = points.map((p, i) => `${i ? 'L' : 'M'}${xPos(i).toFixed(1)},${yPos(p.y).toFixed(1)}`).join(' ');
            if (opts.fill) {
                const area = `${d} L${xPos(points.length - 1)},${h - pad.b} L${xPos(0)},${h - pad.b} Z`;
                body += `<path d="${area}" fill="${color}" opacity="0.16"/>`;
            }
            body += `<path d="${d}" fill="none" stroke="${color}" stroke-width="2.6" stroke-linejoin="round"/>`;
            points.forEach((p, i) => {
                body += `<circle class="nc-dot" data-i="${i}" cx="${xPos(i)}" cy="${yPos(p.y)}" r="5" fill="${color}" stroke="#0f111a" stroke-width="2"/>`;
            });
        }
        const labels = points.map((p, i) => {
            if (points.length > 14 && i % 2) return '';
            return `<text x="${xPos(i)}" y="${h - 14}" text-anchor="middle" fill="#94a3b8" font-size="10">${p.label}</text>`;
        }).join('');
        el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img">${grid}${body}${labels}</svg><p class="nc-hint">${opts.hint || 'Click a quarter to open that filing'}</p>`;
        el.querySelectorAll('[data-i]').forEach(node => {
            node.addEventListener('click', () => {
                const i = Number(node.getAttribute('data-i'));
                if (onClick) onClick(points[i], i);
            });
            node.addEventListener('mouseenter', () => {
                const hint = el.querySelector('.nc-hint');
                if (hint) hint.textContent = `${points[node.getAttribute('data-i')].label}: ${format(points[node.getAttribute('data-i')].y)}`;
            });
            node.addEventListener('mouseleave', () => {
                const hint = el.querySelector('.nc-hint');
                if (hint) hint.textContent = opts.hint || 'Click a quarter to open that filing';
            });
        });
    }

    function getLayout(title, xaxis = {}, yaxis = {}) {
        return {
            title: { text: title, font: { color: '#f8fafc', family: 'Outfit', size: 16 } },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#94a3b8', family: 'Inter' },
            xaxis: { gridcolor: 'rgba(255,255,255,0.05)', ...xaxis },
            yaxis: { gridcolor: 'rgba(255,255,255,0.05)', zerolinecolor: 'rgba(255,255,255,0.12)', ...yaxis },
            margin: { l: 52, r: 24, t: 48, b: 48 },
            hovermode: 'x unified',
            legend: { orientation: 'h', y: -0.2 }
        };
    }

    function setCompany(ticker, name) {
        tickerInput.value = ticker;
        companySearch.value = name ? `${name} (${ticker})` : ticker;
        selectedLabel.textContent = `Selected: ${name || ticker} (${ticker})`;
        suggestionsBox.classList.add('hidden');
    }

    async function fetchCompanies(q) {
        const res = await fetch(`/api/companies?q=${encodeURIComponent(q || '')}`);
        const data = await res.json();
        return data.companies || [];
    }

    function renderSuggestions(items) {
        if (!items.length) {
            suggestionsBox.classList.add('hidden');
            suggestionsBox.innerHTML = '';
            return;
        }
        suggestionsBox.innerHTML = items.map(c => `
            <div class="suggestion-item" data-ticker="${c.ticker}" data-name="${c.title.replace(/"/g, '&quot;')}">
                <strong>${c.title}</strong>
                <span>${c.ticker}</span>
            </div>
        `).join('');
        suggestionsBox.classList.remove('hidden');
        suggestionsBox.querySelectorAll('.suggestion-item').forEach(el => {
            el.addEventListener('mousedown', (e) => {
                e.preventDefault();
                setCompany(el.dataset.ticker, el.dataset.name);
            });
        });
    }

    function tickerFromSearch(value) {
        const v = (value || '').trim();
        const paren = v.match(/\(([A-Za-z][A-Za-z0-9.]{0,6})\)\s*$/);
        if (paren) return paren[1].toUpperCase();
        if (/^[A-Za-z][A-Za-z0-9.]{0,6}$/.test(v)) return v.toUpperCase();
        return (tickerInput.value || '').trim().toUpperCase();
    }

    companySearch.addEventListener('input', () => {
        const q = companySearch.value.trim();
        const guessed = tickerFromSearch(q);
        if (guessed) {
            tickerInput.value = guessed;
            selectedLabel.textContent = `Selected: ${guessed}`;
        }
        clearTimeout(searchTimer);
        searchTimer = setTimeout(async () => {
            try {
                renderSuggestions(await fetchCompanies(q));
            } catch (e) {
                renderSuggestions([]);
            }
        }, 180);
    });
    companySearch.addEventListener('focus', async () => {
        if (!companySearch.value.trim()) renderSuggestions(await fetchCompanies(''));
    });
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.autocomplete')) suggestionsBox.classList.add('hidden');
    });

    async function refreshGpu() {
        try {
            const info = await (await fetch('/api/gpu')).json();
            const nameEl = document.getElementById('gpu-name');
            const utilEl = document.getElementById('gpu-util');
            const fill = document.getElementById('gpu-bar-fill');
            const hint = document.getElementById('gpu-hint');
            const liveUtil = document.getElementById('gpu-util-live');
            const liveFill = document.getElementById('gpu-bar-live');
            const name = info.device_name || 'No NVIDIA GPU reported';
            const util = info.utilization ?? 0;
            nameEl.textContent = name;
            utilEl.textContent = info.cuda_available
                ? `${util}% · ${info.memory_used_mb ?? '—'} / ${info.memory_total_mb ?? '—'} MB`
                : 'CUDA unavailable';
            fill.style.width = `${Math.min(util, 100)}%`;
            if (liveUtil) liveUtil.textContent = `${util}%`;
            if (liveFill) liveFill.style.width = `${Math.min(util, 100)}%`;
            if (!info.cuda_available) {
                hint.textContent = info.note || 'This Python env cannot use the GPU.';
                const cudaOpt = deviceSelect.querySelector('option[value="cuda"]');
                if (cudaOpt) cudaOpt.disabled = true;
                deviceSelect.value = 'cpu';
            }
        } catch (e) {
            document.getElementById('gpu-name').textContent = 'GPU status unavailable';
        }
    }
    refreshGpu();
    setInterval(refreshGpu, 4000);

    btnAnalyze.addEventListener('click', async () => {
        const ticker = tickerFromSearch(companySearch.value) || tickerInput.value.trim().toUpperCase();
        tickerInput.value = ticker;
        if (!ticker) {
            alert('Pick a company from the search results');
            return;
        }

        emptyState.classList.add('hidden');
        dashboardContent.classList.add('hidden');
        reportView.classList.add('hidden');
        loadingOverlay.classList.remove('hidden');
        document.getElementById('loading-text').textContent = 'Analyzing transcripts…';
        document.getElementById('loading-sub').textContent =
            deviceSelect.value === 'cuda'
                ? 'FinBERT is running on GPU in batches. Cached filings skip the GPU unless Force Fresh is on.'
                : 'This may take a few moments depending on history length.';

        clearInterval(gpuTimer);
        gpuTimer = setInterval(refreshGpu, 800);

        try {
            const limitVal = document.getElementById('limit').value;
            const res = await fetch(`/api/analyze?ticker=${ticker}&device=${deviceSelect.value}&limit=${limitVal}&force_refresh=${forceRefreshCheck.checked}`);
            const payload = await res.json();
            if (!res.ok) throw new Error(payload.detail || 'Server error occurred');

            latestData = payload;
            renderDashboard(payload);
            if (payload.from_cache) {
                document.getElementById('dashboard-subtitle').innerText += ' · loaded from cache (instant). Enable Force Fresh to re-run NLP.';
            }

            loadingOverlay.classList.add('hidden');
            dashboardContent.classList.remove('hidden');
            window.dispatchEvent(new Event('resize'));
            forceRefreshCheck.checked = false;
            loadCachedTickers();
        } catch (error) {
            alert(`Error: ${error.message}`);
            loadingOverlay.classList.add('hidden');
            emptyState.classList.remove('hidden');
        } finally {
            clearInterval(gpuTimer);
            refreshGpu();
        }
    });

    async function loadCachedTickers() {
        try {
            const res = await fetch('/api/cached');
            const data = await res.json();
            cachedCompanies = data.cached || (data.cached_tickers || []).map(t => ({ ticker: t, company: t }));
            const list = document.getElementById('cached-list');
            if (!cachedCompanies.length) {
                list.innerHTML = '<em style="color: var(--text-secondary); font-size:0.82rem">No cached data yet</em>';
            } else {
                list.innerHTML = cachedCompanies.map(c =>
                    `<span class="cached-tag" title="${c.company}" data-ticker="${c.ticker}" data-name="${(c.company || c.ticker).replace(/"/g, '&quot;')}">${c.company && c.company !== c.ticker ? c.ticker : c.ticker}</span>`
                ).join('');
                list.querySelectorAll('.cached-tag').forEach(el => {
                    el.addEventListener('click', () => {
                        setCompany(el.dataset.ticker, el.dataset.name);
                        loadCachedAnalysis(el.dataset.ticker);
                    });
                });
            }
            renderComparePicker();
        } catch (e) {
            document.getElementById('cached-list').innerHTML = '<em style="color:var(--text-secondary)">Failed to load cache</em>';
        }
    }

    async function loadCachedAnalysis(ticker) {
        emptyState.classList.add('hidden');
        dashboardContent.classList.add('hidden');
        reportView.classList.add('hidden');
        loadingOverlay.classList.remove('hidden');
        document.getElementById('loading-text').textContent = 'Loading cached analysis…';
        document.getElementById('loading-sub').textContent = 'No NLP rerun. Instant load from disk.';
        try {
            const res = await fetch(`/api/load?ticker=${encodeURIComponent(ticker)}`);
            const payload = await res.json();
            if (!res.ok) throw new Error(payload.detail || 'No cached analysis');
            latestData = payload;
            renderDashboard(payload);
            loadingOverlay.classList.add('hidden');
            dashboardContent.classList.remove('hidden');
            window.dispatchEvent(new Event('resize'));
        } catch (error) {
            loadingOverlay.classList.add('hidden');
            emptyState.classList.remove('hidden');
            alert(`Error: ${error.message}`);
        }
    }

    loadCachedTickers();

    (async () => {
        try {
            const popular = await fetchCompanies('');
            const wrap = document.getElementById('quick-companies');
            if (!wrap) return;
            wrap.innerHTML = popular.slice(0, 6).map(c =>
                `<button class="quick-btn" data-ticker="${c.ticker}" data-name="${(c.title || c.ticker).replace(/"/g, '&quot;')}">${c.title.split(' ')[0]}</button>`
            ).join('');
            wrap.querySelectorAll('.quick-btn').forEach(btn => {
                btn.addEventListener('click', () => setCompany(btn.dataset.ticker, btn.dataset.name));
            });
        } catch (e) { /* popular chips are optional */ }
        setCompany('AAPL', 'Apple Inc.');
    })();

    function uniqueQuarterSeries(transcripts) {
        const byKey = new Map();
        const sorted = [...transcripts].sort((a, b) =>
            String((a.metadata || {}).date || '').localeCompare(String((b.metadata || {}).date || ''))
        );
        sorted.forEach(t => {
            const m = t.metadata || {};
            const key = `${m.year || ''}|${m.quarter || ''}|${m.date || ''}`;
            const qKey = `${m.year || ''}|${String(m.quarter || '').toUpperCase()}`;
            byKey.set(qKey, t);
        });
        return [...byKey.values()].sort((a, b) =>
            String((a.metadata || {}).date || '').localeCompare(String((b.metadata || {}).date || ''))
        );
    }

    function quarterLabel(t) {
        const m = t.metadata || {};
        return `${m.year || ''} ${m.quarter || ''}`.trim() || m.date || '';
    }

    function renderDashboard(data) {
        const { temporal, ticker, company } = data;
        const transcripts = uniqueQuarterSeries(data.transcripts || []);
        latestData = { ...data, transcripts };
        const name = company || ticker;
        const n = (data.transcripts || []).length;
        document.getElementById('dashboard-title').innerText = `${name} (${ticker})`;
        document.getElementById('dashboard-subtitle').innerText =
            `${transcripts.length} unique quarters loaded` +
            (n && transcripts.length < n ? ` (${n} raw filings before dedupe)` : '') +
            ` · click any chart point to open that release` +
            (data.device_used ? ` · ran on ${data.device_used}` : '');

        renderSummary(transcripts, ticker);
        renderTemporal(transcripts, temporal, ticker);
        renderRiskFactors(transcripts);
        renderTopics(temporal);
        renderAlerts(transcripts, temporal);

        if (temporal?.trading_signal) renderSignal(temporal.trading_signal);
    }

    function renderSignal(signal) {
        const banner = document.getElementById('signal-banner');
        const badge = document.getElementById('signal-badge');
        const rationale = document.getElementById('signal-rationale');
        banner.classList.remove('hidden');
        badge.innerText = signal.signal;
        badge.style.color = signal.color;
        badge.style.borderColor = signal.color;
        badge.style.boxShadow = `0 0 20px ${signal.color}44`;
        rationale.innerText = signal.rationale;
    }

    function splitRiskQuotes(cautions) {
        const out = [];
        (cautions || []).forEach(raw => {
            const text = String(raw || '').replace(/\s+/g, ' ').trim();
            if (!text) return;
            if (text.length < 500) {
                out.push(text);
                return;
            }
            text.split(/(?<=[.!?])\s+/).forEach(part => {
                const p = part.trim();
                if (p.split(/\s+/).length >= 8 && p.split(/\s+/).length <= 70 && !/^EX-99/i.test(p)) {
                    out.push(p);
                }
            });
        });
        return out.slice(0, 10);
    }

    function renderRiskFactors(transcripts) {
        const container = document.getElementById('risks-container');
        container.innerHTML = '';
        if (!transcripts.length) return;
        const latest = transcripts[transcripts.length - 1];
        const cautions = splitRiskQuotes(latest.prepared_remarks?.uncertainty?.extracted_cautions || []);
        if (!cautions.length) {
            container.innerHTML = '<p style="color: var(--text-secondary)">No short caution sentences found in the latest filing. The extractor ignores tables, TOC, and giant blobs.</p>';
            return;
        }
        cautions.forEach(quote => {
            const div = document.createElement('div');
            div.className = 'risk-quote';
            div.innerText = `"${quote}"`;
            container.appendChild(div);
        });
    }

    function renderTopics(temporal) {
        const container = document.getElementById('topics-container');
        container.innerHTML = '';
        const topics = temporal?.trending_topics;
        const select = document.getElementById('topic-select');
        if (!topics || !topics.length) {
            container.innerHTML = '<p style="color: var(--text-secondary)">No topic data available.</p>';
            if (select) select.innerHTML = '';
            return;
        }
        const maxCount = Math.max(...topics.map(t => t.latest_count), 1);
        topics.slice(0, 8).forEach(t => {
            const pct = (t.latest_count / maxCount) * 100;
            const changePct = t.change_pct;
            const changeClass = changePct > 5 ? 'up' : changePct < -5 ? 'down' : 'flat';
            const changeLabel = changePct > 0 ? `+${changePct.toFixed(0)}%` : `${changePct.toFixed(0)}%`;
            const row = document.createElement('div');
            row.className = 'topic-row';
            row.innerHTML = `
                <span class="topic-name">${t.topic}</span>
                <div class="topic-bar-wrap">
                    <div class="topic-bar-fill" style="width: ${pct}%"></div>
                </div>
                <span class="topic-count">${t.latest_count}</span>
                <span class="topic-change ${changeClass}">${t.historical_avg > 0 ? changeLabel : 'New'}</span>
            `;
            container.appendChild(row);
        });

        if (select) {
            select.innerHTML = topics.map(t => `<option value="${t.topic}">${t.topic}</option>`).join('');
            const drawTopic = () => {
                const chosen = topics.find(t => t.topic === select.value) || topics[0];
                const series = (chosen.series || []).map(s => ({
                    label: `${s.year || ''} ${s.quarter || ''}`.trim() || s.date || '',
                    y: s.count || 0,
                    date: s.date
                }));
                drawNativeChart(document.getElementById('topic-series-chart'), series, {
                    color: '#8b5cf6',
                    fill: true,
                    format: (v) => Math.round(v).toString(),
                    hint: `${chosen.topic} — mentions per quarter`,
                    yMin: 0
                });
            };
            select.onchange = drawTopic;
            drawTopic();
        }
    }

    function metricsOf(t) {
        const conf = t.executive_confidence?.executive_confidence_indicator?.confidence_score ?? 0.5;
        const sent = t.prepared_remarks?.sentiment_score ?? 0;
        const uncert = t.prepared_remarks?.uncertainty?.uncertainty_score ?? 0;
        return { conf, sent, uncert };
    }

    function renderSummary(transcripts, ticker) {
        let avgConf = 0, avgSent = 0, avgUncert = 0;
        transcripts.forEach(t => {
            const m = metricsOf(t);
            avgConf += m.conf;
            avgSent += m.sent;
            avgUncert += m.uncert;
        });
        const count = transcripts.length || 1;
        avgConf /= count;
        avgSent /= count;
        avgUncert /= count;

        const confCard = document.getElementById('card-confidence');
        confCard.className = 'metric-card glass-panel';
        if (avgConf > 0.7) confCard.classList.add('conf-high');
        else if (avgConf > 0.4) confCard.classList.add('conf-medium');
        else confCard.classList.add('conf-low');

        document.getElementById('val-confidence').innerText = (avgConf * 100).toFixed(1) + '%';
        const sentText = avgSent > 0.2 ? 'Positive' : avgSent > -0.2 ? 'Neutral' : 'Negative';
        document.getElementById('val-sentiment').innerHTML = `
            <span style="font-size: 1.2rem; display:block; margin-bottom: 5px; color: ${avgSent > 0.2 ? 'var(--success)' : avgSent > -0.2 ? 'var(--warning)' : 'var(--danger)'}">${sentText}</span>
            <span>${avgSent.toFixed(3)}</span>
        `;
        document.getElementById('val-uncertainty').innerText = (avgUncert * 100).toFixed(2) + '%';
        document.querySelector('#card-uncertainty .metric-desc').innerText =
            'Share of hedging / evasive language (typically a few percent)';

        if (!transcripts.length) return;
        const latest = transcripts[transcripts.length - 1];
        const prev = transcripts.length > 1 ? transcripts[transcripts.length - 2] : null;
        const L = metricsOf(latest);
        const P = prev ? metricsOf(prev) : L;
        const A = { conf: avgConf, sent: avgSent, uncert: avgUncert };

        const categories = ['Sentiment (−1 to 1)', 'Uncertainty', 'Confidence'];
        const traces = [
            {
                type: 'bar',
                name: 'Latest',
                x: categories,
                y: [L.sent, L.uncert, L.conf],
                marker: { color: '#8b5cf6' },
                text: [L.sent.toFixed(3), (L.uncert * 100).toFixed(2) + '%', (L.conf * 100).toFixed(1) + '%'],
                textposition: 'outside'
            },
            {
                type: 'bar',
                name: 'Previous',
                x: categories,
                y: [P.sent, P.uncert, P.conf],
                marker: { color: '#64748b' },
                text: [P.sent.toFixed(3), (P.uncert * 100).toFixed(2) + '%', (P.conf * 100).toFixed(1) + '%'],
                textposition: 'outside'
            },
            {
                type: 'bar',
                name: 'Company avg',
                x: categories,
                y: [A.sent, A.uncert, A.conf],
                marker: { color: '#22d3ee' },
                text: [A.sent.toFixed(3), (A.uncert * 100).toFixed(2) + '%', (A.conf * 100).toFixed(1) + '%'],
                textposition: 'outside'
            }
        ];

        const allY = traces.flatMap(tr => tr.y);
        Plotly.newPlot('radar-chart', traces, {
            ...getLayout('', {}, { range: paddedRange(allY, -1, 1, 0.04), tickformat: '.3f' }),
            barmode: 'group',
            title: { text: `${latest.metadata?.quarter || ''} ${latest.metadata?.year || ''} vs history`, font: { color: '#f8fafc', family: 'Outfit', size: 16 } }
        }, PLOTLY_CFG);
    }

    function bindChartClicks(divId, transcripts, ticker) {
        const el = document.getElementById(divId);
        el.on('plotly_click', (ev) => {
            const pt = ev.points && ev.points[0];
            if (!pt) return;
            const idx = typeof pt.pointIndex === 'number' ? pt.pointIndex : pt.pointNumber;
            const t = transcripts[idx];
            if (!t) return;
            openReport(ticker, t);
        });
    }

    function renderTemporal(transcripts, temporal, ticker) {
        const series = uniqueQuarterSeries(transcripts || []);
        if (!temporal || series.length < 2) {
            const n = series.length;
            document.getElementById('overall-assessment').innerHTML =
                `<i>Need at least 2 earnings releases for a timeline. This load has ${n}. ` +
                `NVIDIA and others often file Exhibit 99.1 as PDF — use Analyze + Force Fresh Download to fetch more years.</i>`;
            document.getElementById('overall-assessment').className = 'assessment-box glass-panel';
            ['sentiment-chart', 'uncertainty-chart', 'confidence-chart'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.innerHTML = '';
            });
            const mEl = document.getElementById('market-reaction-chart');
            if (mEl) Plotly.purge(mEl);
            return;
        }

        let assessment = temporal.overall_assessment || '';
        assessment = assessment.replace('ALERTA:', 'ALERT:')
            .replace('SITUACIÓN ESTABLE:', 'STABLE:')
            .replace('Sin cambios significativos detectados.', 'No significant changes detected.');
        const assessmentDiv = document.getElementById('overall-assessment');
        assessmentDiv.innerText = assessment;
        assessmentDiv.className = assessment.includes('ALERT')
            ? 'assessment-box assessment-alert glass-panel'
            : 'assessment-box assessment-success glass-panel';

        const open = (_p, i) => openReport(ticker, series[i]);
        const sentPts = series.map(t => ({
            label: quarterLabel(t),
            y: t.prepared_remarks?.sentiment_score || 0,
            date: t.metadata?.date
        }));
        const uncertPts = series.map(t => ({
            label: quarterLabel(t),
            y: t.prepared_remarks?.uncertainty?.uncertainty_score || 0,
            date: t.metadata?.date
        }));
        const deltaPts = series.map((t, i) => {
            const cur = t.prepared_remarks?.sentiment_score || 0;
            const prev = i ? (series[i - 1].prepared_remarks?.sentiment_score || 0) : cur;
            return { label: quarterLabel(t), y: i ? cur - prev : 0, date: t.metadata?.date };
        }).slice(1);

        drawNativeChart(document.getElementById('sentiment-chart'), sentPts, {
            color: '#3b82f6', onClick: open, format: (v) => v.toFixed(2)
        });
        document.getElementById('uncertainty-chart-container').classList.remove('hidden');
        drawNativeChart(document.getElementById('uncertainty-chart'), uncertPts, {
            color: '#f59e0b', fill: true, onClick: open,
            format: (v) => `${(v * 100).toFixed(2)}%`, yMin: 0
        });
        drawNativeChart(document.getElementById('confidence-chart'), deltaPts, {
            color: '#10b981', mode: 'bar',
            onClick: (_p, i) => openReport(ticker, series[i + 1]),
            format: (v) => (v >= 0 ? '+' : '') + v.toFixed(3),
            hint: 'Green = tone improved vs last quarter · click a bar to open that filing'
        });

        renderMarketReaction(ticker, series);
    }

    async function renderMarketReaction(ticker, series) {
        const el = document.getElementById('market-reaction-chart');
        const help = document.getElementById('market-help');
        if (!el) return;
        try {
            const res = await fetch(`/api/market?ticker=${encodeURIComponent(ticker)}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'market failed');
            const events = (data.events || []).filter(e => e.ret_1d != null);
            const s = data.summary || {};
            const corr = s.corr_sentiment_ret1d;
            const hit = s.hit_rate;
            if (help) {
                help.textContent = events.length
                    ? `Pearson(tone, next-session return) = ${corr == null ? 'n/a' : corr.toFixed(2)} · ` +
                      `same-direction hit rate ${hit == null ? 'n/a' : (hit * 100).toFixed(0)}% ` +
                      `(${s.confirmed || 0} confirmed / ${s.faded || 0} faded). ` +
                      `Avg return after positive tone: ${s.avg_ret_when_positive_tone == null ? 'n/a' : (s.avg_ret_when_positive_tone * 100).toFixed(2)}%` +
                      `; after negative: ${s.avg_ret_when_negative_tone == null ? 'n/a' : (s.avg_ret_when_negative_tone * 100).toFixed(2)}%.`
                    : 'No overlapping price history for these filing dates.';
            }
            if (!events.length) {
                Plotly.purge(el);
                return;
            }
            Plotly.newPlot(el, [
                {
                    x: events.map(e => e.date),
                    y: events.map(e => e.sentiment),
                    name: 'Tone',
                    type: 'scatter',
                    mode: 'lines+markers',
                    yaxis: 'y',
                    line: { color: '#8b5cf6', width: 2 }
                },
                {
                    x: events.map(e => e.date),
                    y: events.map(e => e.ret_1d),
                    name: 'Next-session return',
                    type: 'bar',
                    yaxis: 'y2',
                    marker: { color: events.map(e => e.ret_1d >= 0 ? 'rgba(16,185,129,0.65)' : 'rgba(239,68,68,0.65)') }
                }
            ], {
                ...getLayout('', { type: 'date', tickformat: '%Y-%m' }, { tickformat: '.2f' }),
                yaxis: { title: 'Sentiment', gridcolor: 'rgba(255,255,255,0.06)' },
                yaxis2: { title: 'Return', overlaying: 'y', side: 'right', tickformat: '.1%', gridcolor: 'rgba(255,255,255,0.02)' },
                legend: { orientation: 'h', y: 1.12 },
                margin: { t: 40, r: 56, l: 48, b: 40 }
            }, PLOTLY_CFG);
        } catch (err) {
            if (help) help.textContent = 'Could not load prices (Yahoo Finance). Charts still show NLP scores.';
            Plotly.purge(el);
        }
    }

    function renderAlerts(transcripts, temporal) {
        const container = document.getElementById('alerts-container');
        const timeline = document.getElementById('alerts-timeline');
        container.innerHTML = '';
        if (timeline) timeline.innerHTML = '';
        const alerts = (temporal && temporal.alerts && temporal.alerts.length)
            ? temporal.alerts
            : [];

        const series = uniqueQuarterSeries(transcripts || []);
        if (timeline && series.length) {
            const byDate = {};
            alerts.forEach(a => {
                const key = String(a.date || '');
                if (!byDate[key] || a.type === 'critical') byDate[key] = a;
            });
            series.forEach(t => {
                const label = quarterLabel(t);
                const meta = t.metadata || {};
                const hit = byDate[meta.date] || byDate[label] || byDate[`${meta.year} ${meta.quarter}`];
                const item = document.createElement('div');
                item.className = 'tl-item';
                const kind = hit ? (hit.type || 'moderate') : '';
                item.innerHTML = `<div class="tl-stem"></div><div class="tl-dot ${kind}"></div><div class="tl-label">${label}</div>`;
                item.title = hit ? hit.msg : 'No anomaly';
                item.addEventListener('click', () => openReport(tickerInput.value, t));
                timeline.appendChild(item);
            });
        }

        if (!alerts.length) {
            container.innerHTML = '<div class="alert-item alert-info">No anomalies versus this company’s own history.</div>';
            return;
        }
        alerts.forEach(al => {
            const div = document.createElement('div');
            const cls = al.type === 'critical' ? 'alert-critical'
                : al.type === 'positive' ? 'alert-positive'
                : al.type === 'info' ? 'alert-info'
                : 'alert-moderate';
            div.className = `alert-item ${cls}`;
            const tag = (al.type || 'moderate').toUpperCase();
            div.innerHTML = `<strong>${tag}</strong> — ${al.date || ''}<br>${al.msg}`;
            container.appendChild(div);
        });
    }

    function renderComparePicker() {
        const wrap = document.getElementById('compare-picks');
        if (!wrap) return;
        const current = tickerInput.value;
        wrap.innerHTML = cachedCompanies.map(c => {
            const checked = c.ticker === current ? 'checked' : '';
            return `<label class="compare-chip"><input type="checkbox" value="${c.ticker}" ${checked}> ${c.company || c.ticker} <span style="color:var(--text-secondary)">${c.ticker}</span></label>`;
        }).join('') || '<em style="color:var(--text-secondary)">Analyze companies first to compare them.</em>';
    }

    document.getElementById('compare-run').addEventListener('click', async () => {
        const picked = [...document.querySelectorAll('#compare-picks input:checked')].map(i => i.value);
        if (picked.length < 2) {
            alert('Select at least two cached companies');
            return;
        }
        const btn = document.getElementById('compare-run');
        const prev = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Joining prices…';
        try {
        const align = document.getElementById('compare-align')?.checked ? 'true' : 'false';
        const res = await fetch(`/api/compare?tickers=${picked.join(',')}&align=${align}`);
        const data = await res.json();
        if (!res.ok) {
            alert(data.detail || 'Compare failed');
            return;
        }
        const palette = ['#8b5cf6', '#22d3ee', '#f59e0b', '#10b981', '#f43f5e', '#60a5fa'];
        const sentTraces = [];
        const uncertTraces = [];
        const scatterTraces = [];
        const rows = [`<div class="compare-row head"><div>Company</div><div>Sentiment</div><div>Uncertainty</div><div>Confidence</div><div>Next session</div><div>Signal</div></div>`];
        const help = document.getElementById('compare-help');
        if (help) {
            const cov = data.companies.map(c => `${c.ticker}: ${c.coverage?.n || 0} filings ${c.coverage?.start || ''}→${c.coverage?.end || ''}`).join(' · ');
            help.textContent = data.align && data.aligned_from
                ? `Common window ${data.aligned_from} → ${data.aligned_to}. Full coverage: ${cov}`
                : `Uneven starts (first extracted 8-K per ticker). ${cov}`;
        }
        data.companies.forEach((c, i) => {
            const color = palette[i % palette.length];
            const uniq = [];
            const seen = new Set();
            [...c.series].sort((a, b) => String(a.date).localeCompare(String(b.date))).forEach(s => {
                const k = `${s.year}|${s.quarter}`;
                if (seen.has(k)) return;
                seen.add(k);
                uniq.push(s);
            });
            sentTraces.push({
                x: uniq.map(s => s.date), y: uniq.map(s => s.sentiment),
                type: 'scatter', mode: 'lines+markers', name: c.ticker,
                line: { color, width: 3, shape: 'linear' }, marker: { size: 8 },
                connectgaps: false
            });
            uncertTraces.push({
                x: uniq.map(s => s.date), y: uniq.map(s => s.uncertainty),
                type: 'scatter', mode: 'lines+markers', name: c.ticker,
                line: { color, width: 3, shape: 'linear' }, marker: { size: 8 },
                connectgaps: false
            });
            const withPx = uniq.filter(s => s.ret_1d != null);
            scatterTraces.push({
                x: withPx.map(s => s.sentiment),
                y: withPx.map(s => s.ret_1d),
                text: withPx.map(s => `${c.ticker} ${s.quarter} ${s.year}<br>excess vs SPY: ${s.excess_1d == null ? 'n/a' : (s.excess_1d * 100).toFixed(2)}%`),
                hovertemplate: '%{text}<br>tone=%{x:.2f}<br>return=%{y:.2%}<extra></extra>',
                mode: 'markers',
                type: 'scatter',
                name: c.ticker,
                marker: { color, size: 10 }
            });
            const L = c.latest || {};
            const ret = L.ret_1d == null ? '—' : `${(L.ret_1d * 100).toFixed(2)}%`;
            rows.push(`<div class="compare-row"><div><strong>${c.company}</strong><br><span style="color:var(--text-secondary)">${c.ticker}</span></div><div>${(L.sentiment ?? 0).toFixed(3)}</div><div>${((L.uncertainty ?? 0) * 100).toFixed(2)}%</div><div>${((L.confidence ?? 0) * 100).toFixed(1)}%</div><div>${ret}</div><div>${c.signal?.signal || '—'}</div></div>`);
        });
        document.getElementById('compare-table').innerHTML = rows.join('');
        const note = document.getElementById('compare-market-note');
        const mkt = data.market || {};
        if (note) {
            note.textContent = mkt.n
                ? `Pooled Pearson(tone, next-session return) = ${mkt.corr == null ? 'n/a' : mkt.corr.toFixed(2)} across ${mkt.n} filings.`
                : '';
        }
        const sentVals = sentTraces.flatMap(t => t.y);
        const uVals = uncertTraces.flatMap(t => t.y);
        Plotly.newPlot('compare-sentiment', sentTraces, getLayout('Sentiment', { type: 'date', tickformat: '%Y-%m' }, {
            range: paddedRange(sentVals, -1, 1, 0.08), tickformat: '.2f'
        }), PLOTLY_CFG);
        Plotly.newPlot('compare-uncertainty', uncertTraces, getLayout('Uncertainty', { type: 'date', tickformat: '%Y-%m' }, {
            range: paddedRange(uVals, 0, 1, 0.008), tickformat: '.2%'
        }), PLOTLY_CFG);
        const mEl = document.getElementById('compare-market');
        if (mEl && scatterTraces.length) {
            Plotly.newPlot(mEl, scatterTraces, {
                ...getLayout('Next-session return', { title: 'Sentiment', range: [-1, 1] }, { tickformat: '.1%' }),
                shapes: [{ type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, yref: 'paper', line: { color: 'rgba(255,255,255,0.15)', dash: 'dot' } },
                         { type: 'line', y0: 0, y1: 0, x0: 0, x1: 1, xref: 'paper', line: { color: 'rgba(255,255,255,0.15)', dash: 'dot' } }]
            }, PLOTLY_CFG);
        }
        } catch (err) {
            alert(err.message || 'Compare failed');
        } finally {
            btn.disabled = false;
            btn.textContent = prev;
        }
    });

    document.getElementById('report-back').addEventListener('click', () => {
        reportView.classList.add('hidden');
        dashboardContent.classList.remove('hidden');
        window.dispatchEvent(new Event('resize'));
    });

    async function openReport(ticker, transcript) {
        const meta = transcript.metadata || {};
        dashboardContent.classList.add('hidden');
        emptyState.classList.add('hidden');
        reportView.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        let full = transcript;
        try {
            const res = await fetch(`/api/report?ticker=${ticker}&year=${meta.year}&quarter=${meta.quarter}`);
            if (res.ok) full = await res.json();
        } catch (e) { /* use in-memory transcript */ }

        const m = metricsOf(full);
        const name = full.company_name || full.metadata?.company || ticker;
        document.getElementById('report-title').textContent = `${name} · ${meta.quarter} ${meta.year}`;
        document.getElementById('report-meta').textContent = `${meta.date || ''} · ticker ${ticker}`;
        document.getElementById('report-metrics').innerHTML = `
            <div class="metric-card glass-panel"><h3>Sentiment</h3><div class="metric-value">${m.sent.toFixed(3)}</div><p class="metric-desc">${full.prepared_remarks?.sentiment?.label || ''}</p></div>
            <div class="metric-card glass-panel"><h3>Uncertainty</h3><div class="metric-value">${(m.uncert * 100).toFixed(2)}%</div><p class="metric-desc">${full.prepared_remarks?.uncertainty?.interpretation || ''}</p></div>
            <div class="metric-card glass-panel"><h3>Confidence</h3><div class="metric-value">${(m.conf * 100).toFixed(1)}%</div><p class="metric-desc">${full.executive_confidence?.executive_confidence_indicator?.confidence_level || ''}</p></div>
        `;

        const chunks = full.prepared_remarks?.chunks || [];
        const byChunk = full.prepared_remarks?.sentiment_by_chunk || [];
        const chunkWrap = document.getElementById('report-chunks');
        chunkWrap.innerHTML = chunks.map((text, i) => {
            const s = byChunk[i] || {};
            const label = s.label || 'neutral';
            const score = s.probabilities
                ? (s.probabilities.positive - s.probabilities.negative)
                : 0;
            return `<article class="chunk-card ${label}">
                <header><span>Chunk ${i + 1}</span><span>${label} · ${score.toFixed(3)}</span></header>
                <p>${escapeHtml(text.slice(0, 900))}${text.length > 900 ? '…' : ''}</p>
            </article>`;
        }).join('') || '<p style="color:var(--text-secondary)">No chunks stored for this filing.</p>';

        if (byChunk.length) {
            Plotly.newPlot('report-chunks-chart', [{
                x: byChunk.map((_, i) => `C${i + 1}`),
                y: byChunk.map(s => (s.probabilities?.positive || 0) - (s.probabilities?.negative || 0)),
                type: 'bar',
                marker: { color: byChunk.map(s => s.label === 'positive' ? '#10b981' : s.label === 'negative' ? '#ef4444' : '#f59e0b') }
            }], getLayout('Sentiment by chunk', {}, { range: [-1, 1] }), PLOTLY_CFG);
        } else {
            Plotly.purge('report-chunks-chart');
        }

        const raw = full.prepared_remarks?.text || full.full_transcript || '';
        const cautions = full.prepared_remarks?.uncertainty?.extracted_cautions || [];
        let html = escapeHtml(raw);
        cautions.forEach(c => {
            const snippet = escapeHtml(c).slice(0, 180);
            if (snippet.length > 20) {
                html = html.replace(snippet, `<mark>${snippet}</mark>`);
            }
        });
        document.getElementById('report-text').innerHTML = html || '<em>No text available.</em>';
    }

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }
});
