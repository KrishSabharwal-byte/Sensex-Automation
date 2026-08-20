/**
 * app.js - BSE Sensex 30 Pro Algo Terminal Client
 * Real-time WebSocket streaming, live indicator gauges, sparkline charting & audio cues.
 */

let ws = null;
let isAutoRunning = false;
let audioCtx = null;
let isAudioEnabled = true;
let priceHistory = [];
let emaHistory = [];
let allTradesHistory = [];

let prevCallConditionsMet = false;
let prevPutConditionsMet = false;
let lastConditionSoundTime = 0;

// Auto-unlock Web Audio API on first user interaction
if (typeof window !== 'undefined') {
    ['click', 'touchstart', 'keydown'].forEach(evt => {
        window.addEventListener(evt, () => {
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
        }, { once: true });
    });
}

function speakVoiceAlert(text) {
    if (!isAudioEnabled || !('speechSynthesis' in window)) return;
    try {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        utter.rate = 1.15;
        utter.pitch = 1.05;
        utter.volume = 0.95;
        window.speechSynthesis.speak(utter);
    } catch (e) {
        console.debug('Speech synthesis error:', e);
    }
}

// Sound Synthesizer via Web Audio API (Always On)
function testTradeAlertSound() {
    isAudioEnabled = true;
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        playSoundAlert('CALL_ACTIVATED');
        speakVoiceAlert('Trade activated. All four conditions met.');
        showToast('🔔 Testing Trade Activation Alert Sound...', 'win');
    } catch (e) {
        console.warn('Audio test failed:', e);
    }
}
const toggleAudio = testTradeAlertSound;

async function triggerTestCall() {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const res = await fetch('/api/trigger_trade?side=CALL', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            playSoundAlert('CALL_ACTIVATED');
            speakVoiceAlert('Call trade activated. All four conditions met.');
            showToast(`🚀 Opened ${data.trade.side} on Strike ${data.trade.strike} at ₹${data.trade.entry_price.toFixed(2)} (SL: ₹${data.trade.stop_loss.toFixed(2)}, TP: ₹${data.trade.target.toFixed(2)})`, 'win');
        } else {
            playSoundAlert('LOSS');
            showToast(`⛔ ${data.message || 'Cannot open CALL trade: alternation rule violated.'}`, 'loss');
        }
    } catch (e) {
        showToast('Error triggering test trade: ' + e.message, 'loss');
    }
}

async function triggerTestPut() {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const res = await fetch('/api/trigger_trade?side=PUT', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            playSoundAlert('PUT_ACTIVATED');
            speakVoiceAlert('Put trade activated. All four conditions met.');
            showToast(`🚀 Opened ${data.trade.side} on Strike ${data.trade.strike} at ₹${data.trade.entry_price.toFixed(2)} (SL: ₹${data.trade.stop_loss.toFixed(2)}, TP: ₹${data.trade.target.toFixed(2)})`, 'win');
        } else {
            playSoundAlert('LOSS');
            showToast(`⛔ ${data.message || 'Cannot open PUT trade: alternation rule violated.'}`, 'loss');
        }
    } catch (e) {
        showToast('Error triggering test trade: ' + e.message, 'loss');
    }
}

async function manualExitTrade() {
    try {
        const res = await fetch('/api/exit_trade', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'SUCCESS') {
            const t = data.trade || {};
            const pts = Number(t.pnl_points || 0);
            const inr = Number(t.pnl_rupees || 0);
            if (pts >= 0) {
                playSoundAlert('WIN');
                showToast(`🛑 MANUAL EXIT: Realized +${pts.toFixed(2)} pts (+₹${inr.toFixed(2)})`, 'win');
            } else {
                playSoundAlert('LOSS');
                showToast(`🛑 MANUAL EXIT: Realized ${pts.toFixed(2)} pts (₹${inr.toFixed(2)})`, 'loss');
            }
            refreshTradeHistory();
            const stateRes = await fetch('/api/state');
            const stateData = await stateRes.json();
            handleInitState(stateData);
        } else {
            showToast(data.message || 'No active position to exit.', 'info');
        }
    } catch (e) {
        showToast('Error exiting trade: ' + e.message, 'loss');
    }
}

function playSoundAlert(type) {
    if (!isAudioEnabled) return;
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const now = audioCtx.currentTime;

        if (type === 'CALL_ACTIVATED') {
            // Bright, ascending 4-note chime for CALL activation (C5 -> E5 -> G5 -> C6)
            const freqs = [523.25, 659.25, 783.99, 1046.50];
            freqs.forEach((f, idx) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(f, now + idx * 0.07);
                gain.gain.setValueAtTime(0.35, now + idx * 0.07);
                gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.07 + 0.3);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(now + idx * 0.07);
                osc.stop(now + idx * 0.07 + 0.3);
            });
        } else if (type === 'PUT_ACTIVATED') {
            // Powerful, descending 4-note chime for PUT activation (C6 -> A5 -> F5 -> C5)
            const freqs = [1046.50, 880.00, 698.46, 523.25];
            freqs.forEach((f, idx) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(f, now + idx * 0.07);
                gain.gain.setValueAtTime(0.3, now + idx * 0.07);
                gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.07 + 0.3);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(now + idx * 0.07);
                osc.stop(now + idx * 0.07 + 0.3);
            });
        } else if (type === 'OPEN') {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.exponentialRampToValueAtTime(880, now + 0.2);
            gain.gain.setValueAtTime(0.2, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
            osc.start(now);
            osc.stop(now + 0.3);
        } else if (type === 'WIN') {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.frequency.setValueAtTime(523.25, now);
            osc.frequency.exponentialRampToValueAtTime(1046.50, now + 0.25);
            gain.gain.setValueAtTime(0.25, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);
            osc.start(now);
            osc.stop(now + 0.35);
        } else if (type === 'LOSS') {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.frequency.setValueAtTime(300, now);
            osc.frequency.exponentialRampToValueAtTime(150, now + 0.25);
            gain.gain.setValueAtTime(0.2, now);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);
            osc.start(now);
            osc.stop(now + 0.3);
        }
    } catch (e) {
        console.warn("Audio disabled or blocked:", e);
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast-item ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Canvas Sparkline Chart
function renderSparkline() {
    const canvas = document.getElementById('sparklineCanvas');
    if (!canvas || priceHistory.length < 2) return;

    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio || 300;
    canvas.height = rect.height * window.devicePixelRatio || 140;

    const ctx = canvas.getContext('2d');
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const prices = priceHistory.slice(-50);
    const emas = emaHistory.slice(-50);

    const allVals = [...prices, ...emas.filter(v => v !== null && v !== undefined)];
    const min = Math.min(...allVals) - 10;
    const max = Math.max(...allVals) + 10;
    const range = max - min || 1;

    const getX = (i) => (i / (prices.length - 1)) * (rect.width - 20) + 10;
    const getY = (v) => rect.height - 15 - ((v - min) / range) * (rect.height - 30);

    // Draw Grid Lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, rect.height / 2);
    ctx.lineTo(rect.width, rect.height / 2);
    ctx.stroke();

    // 1. Draw EMA20 Line if available
    if (emas.some(v => v !== null)) {
        ctx.beginPath();
        ctx.strokeStyle = '#ffb703';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        let first = true;
        for (let i = 0; i < emas.length; i++) {
            if (emas[i] !== null && emas[i] !== undefined) {
                const x = getX(i);
                const y = getY(emas[i]);
                if (first) { ctx.moveTo(x, y); first = false; }
                else { ctx.lineTo(x, y); }
            }
        }
        ctx.stroke();
        ctx.setLineDash([]);
    }

    // 2. Draw Price Area Gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, rect.height);
    gradient.addColorStop(0, 'rgba(0, 245, 160, 0.25)');
    gradient.addColorStop(1, 'rgba(0, 245, 160, 0.0)');

    ctx.beginPath();
    ctx.moveTo(getX(0), getY(prices[0]));
    for (let i = 1; i < prices.length; i++) {
        ctx.lineTo(getX(i), getY(prices[i]));
    }
    ctx.lineTo(getX(prices.length - 1), rect.height);
    ctx.lineTo(getX(0), rect.height);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // 3. Draw Price Line
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(prices[0]));
    for (let i = 1; i < prices.length; i++) {
        ctx.lineTo(getX(i), getY(prices[i]));
    }
    ctx.strokeStyle = '#00f5a0';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 4. Draw Current Price Dot
    const lastX = getX(prices.length - 1);
    const lastY = getY(prices[prices.length - 1]);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.strokeStyle = '#00f5a0';
    ctx.lineWidth = 2;
    ctx.stroke();
}

// WebSocket Connection
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("WebSocket connected to Sensex backend.");
        const pingStatus = document.getElementById('pingStatus');
        if (pingStatus) pingStatus.textContent = "CONNECTED (WS)";
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'INIT_STATE') {
                handleInitState(msg.data);
            } else if (msg.type === 'TICK_UPDATE') {
                handleTickUpdate(msg.data);
            } else if (msg.type === 'RESET') {
                handleInitState(msg.data);
                showToast("Simulation session reset successfully.", "info");
            } else if (msg.type === 'CONFIG_UPDATE') {
                if (msg.data?.config) {
                    populateConfig(msg.data.config);
                }
                const badge = document.getElementById('mongoSavedBadge');
                if (badge) {
                    badge.classList.add('saved-pulse');
                    setTimeout(() => badge.classList.remove('saved-pulse'), 1500);
                }
            } else if (msg.type === 'TRADES_CLEARED') {
                allTradesHistory = msg.data?.trade_history || [];
                renderTradeHistory(allTradesHistory);
                if (msg.data?.portfolio_summary) {
                    updatePortfolioMetrics(msg.data.portfolio_summary);
                }
                showToast("🗑 Closed Trades Audit Log cleared for today.", "info");
            }
        } catch (e) {
            console.error("Error parsing WebSocket message:", e);
        }
    };

    ws.onclose = () => {
        const pingStatus = document.getElementById('pingStatus');
        if (pingStatus) pingStatus.textContent = "RECONNECTING...";
        setTimeout(connectWebSocket, 2000);
    };
}

function handleInitState(data) {
    if (!data) return;

    if (data.config) {
        populateConfig(data.config);
    }

    if (data.portfolio_summary) {
        updatePortfolioMetrics(data.portfolio_summary);
    }

    if (data.trade_history) {
        allTradesHistory = data.trade_history;
        renderTradeHistory(data.trade_history);
    }

    if (data.is_auto_running !== undefined) {
        isAutoRunning = data.is_auto_running;
        updateAutoButton();
    }

    if (data.latest_tick) {
        handleTickUpdate(data.latest_tick);
    }
}

function handleTickUpdate(data) {
    if (!data) return;

    // 0. Market Status Pill
    const marketOpen = data.market_open ?? (data.market_status === 'OPEN');
    const sourcePill = document.getElementById('feedSourceStatus');
    const sourceText = document.getElementById('feedSourceText');
    if (sourcePill && sourceText) {
        if (marketOpen === false || data.market_status === 'CLOSED') {
            sourcePill.classList.add('market-closed');
            sourceText.textContent = "MARKET CLOSED (LATEST SENSEX VALUES)";
        } else {
            sourcePill.classList.remove('market-closed');
            sourceText.textContent = "BSE LIVE FEED";
        }
    }

    // 1. Session Time
    const timeEl = document.getElementById('marketSessionTime');
    if (timeEl && data.timestamp) {
        const timePart = data.timestamp.includes(' ') ? data.timestamp.split(' ')[1] : data.timestamp;
        timeEl.textContent = `${timePart} IST`;
    }

    // 2. Sensex Spot Price
    const spotVal = data.sensex_mid ?? data.sensex_ltp ?? data.banknifty_mid ?? data.banknifty_ltp;
    if (spotVal !== undefined) {
        const mid = Number(spotVal);
        const spotEl = document.getElementById('spotLtpVal');
        if (spotEl) {
            const prevText = spotEl.textContent.replace(/,/g, '');
            const prev = parseFloat(prevText);
            spotEl.textContent = mid.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

            if (!isNaN(prev) && Math.abs(mid - prev) >= 0.05) {
                spotEl.classList.remove('flash-up', 'flash-down');
                if (mid > prev) spotEl.classList.add('flash-up');
                else if (mid < prev) spotEl.classList.add('flash-down');
                setTimeout(() => {
                    spotEl.classList.remove('flash-up', 'flash-down');
                }, 400);
            }
        }

        if (priceHistory.length === 0 || Math.abs(priceHistory[priceHistory.length - 1] - mid) > 0.001) {
            priceHistory.push(mid);
            if (priceHistory.length > 100) priceHistory.shift();
        }
    }

    // 3. Indicators
    if (data.indicators) {
        updateIndicatorsHero(data.indicators, spotVal || 0);
        if (data.indicators.ema20_5m !== undefined) {
            emaHistory.push(data.indicators.ema20_5m);
            if (emaHistory.length > 100) emaHistory.shift();
        }
    }

    // 4. Strikes
    if (data.strikes) {
        const callEl = document.getElementById('strikeCallVal');
        const putEl = document.getElementById('strikePutVal');
        if (callEl && data.strikes.call_strike) callEl.textContent = `${data.strikes.call_strike} CE`;
        if (putEl && data.strikes.put_strike) putEl.textContent = `${data.strikes.put_strike} PE`;

        // Authentic calibrated option premiums — always use strike-specific key first
        // so an active locked trade on a different strike never pollutes the display
        const callPrem = document.getElementById('callPremiumVal');
        const putPrem = document.getElementById('putPremiumVal');

        if (callPrem && data.strikes?.call_strike) {
            const strikeKey = `${data.strikes.call_strike}_CE`;
            const quote = data.option_quotes?.[strikeKey] || data.option_quotes?.CALL;
            const price = quote?.ltp ?? quote?.mid_price;
            if (price !== undefined && price !== null && Number(price) > 0) {
                callPrem.textContent = `₹${Number(price).toFixed(2)}`;
            } else if (quote?.source === 'PENDING') {
                callPrem.textContent = `--`;
            }
        }
        if (putPrem && data.strikes?.put_strike) {
            const strikeKey = `${data.strikes.put_strike}_PE`;
            const quote = data.option_quotes?.[strikeKey] || data.option_quotes?.PUT;
            const price = quote?.ltp ?? quote?.mid_price;
            if (price !== undefined && price !== null && Number(price) > 0) {
                putPrem.textContent = `₹${Number(price).toFixed(2)}`;
            } else if (quote?.source === 'PENDING') {
                putPrem.textContent = `--`;
            }
        }
    }

    // Render Canvas Sparkline
    renderSparkline();

    // 5. Conditions & Signal Matrix
    if (data.conditions) {
        updateConditionMatrix(data.conditions, data.active_trade);
    }

    // 6. Alternation State
    if (data.trade_manager) {
        updateAlternationShield(data.trade_manager);
    }

    // 7. Active Trade Card
    updateActiveTradeCard(data.active_trade);

    // 8. Session Performance Metrics
    if (data.portfolio_summary) {
        updatePortfolioMetrics(data.portfolio_summary);
    }

    // 9. Event Sound & Toast Handling
    if (data.event === 'TRADE_OPENED') {
        playSoundAlert('OPEN');
        showToast(`⚡ Opened ${data.engine_result?.trade?.side || 'trade'} on ${data.engine_result?.trade?.symbol || ''}`, 'info');
    } else if (data.event === 'TRADE_CLOSED') {
        const trade = data.engine_result?.trade;
        if (trade) {
            if (trade.pnl_points > 0) {
                playSoundAlert('WIN');
                showToast(`🎯 TARGET HIT: +${trade.pnl_points} pts (₹${trade.pnl_rupees})`, 'win');
            } else {
                playSoundAlert('LOSS');
                showToast(`🛑 STOP LOSS HIT: ${trade.pnl_points} pts (₹${trade.pnl_rupees})`, 'loss');
            }
            refreshTradeHistory();
        }
    }
}

function updateIndicatorsHero(ind, spot) {
    // 5M RSI
    const rsi5m = ind.rsi_5m;
    const rsi5mEl = document.getElementById('valHeroRsi5m');
    const rsi5mBadge = document.getElementById('badgeHeroRsi5m');
    const rsi5mGauge = document.getElementById('gaugeFillRsi5m');

    if (rsi5m !== null && rsi5m !== undefined) {
        const val = Number(rsi5m);
        if (rsi5mEl) rsi5mEl.textContent = val.toFixed(2);
        if (rsi5mGauge) rsi5mGauge.style.width = `${Math.min(100, Math.max(0, val))}%`;

        if (rsi5mBadge) {
            rsi5mBadge.className = "indicator-condition-tag " + (val > 60 ? "tag-bull" : val < 40 ? "tag-bear" : "tag-neutral");
            rsi5mBadge.textContent = (val > 60 ? "BULLISH (>60)" : val < 40 ? "BEARISH (<40)" : "NEUTRAL");
        }
    }

    // 15M RSI (MTF)
    const rsi15m = ind.rsi_15m;
    const rsi15mEl = document.getElementById('valHeroRsi15m');
    const rsi15mBadge = document.getElementById('badgeHeroRsi15m');
    const rsi15mGauge = document.getElementById('gaugeFillRsi15m');

    if (rsi15m !== null && rsi15m !== undefined) {
        const val = Number(rsi15m);
        if (rsi15mEl) rsi15mEl.textContent = val.toFixed(2);
        if (rsi15mGauge) rsi15mGauge.style.width = `${Math.min(100, Math.max(0, val))}%`;

        if (rsi15mBadge) {
            rsi15mBadge.className = "indicator-condition-tag " + (val > 60 ? "tag-bull" : val < 40 ? "tag-bear" : "tag-neutral");
            rsi15mBadge.textContent = (val > 60 ? "BULLISH (>60)" : val < 40 ? "BEARISH (<40)" : "NEUTRAL");
        }
    }

    // 5M EMA20
    const ema = ind.ema20_5m;
    const emaEl = document.getElementById('valHeroEma20');
    const emaBadge = document.getElementById('badgeHeroEma');
    const emaDiffEl = document.getElementById('emaDistanceText');
    const emaGauge = document.getElementById('gaugeFillEma');

    if (ema !== null && ema !== undefined) {
        const val = Number(ema);
        if (emaEl) emaEl.textContent = val.toFixed(2);
        const diff = (spot && ema) ? (spot - ema) : 0;
        if (emaDiffEl) emaDiffEl.textContent = `Diff: ${diff >= 0 ? '+' : ''}${diff.toFixed(2)} pts`;

        if (emaBadge) {
            emaBadge.className = "indicator-condition-tag " + (diff > 0 ? "tag-bull" : "tag-bear");
            emaBadge.textContent = diff > 0 ? "SPOT > EMA" : "SPOT < EMA";
        }
        if (emaGauge) {
            emaGauge.style.width = `${Math.min(100, Math.max(10, 50 + diff * 0.2))}%`;
        }
    }

    // 5M ADX
    const adx = ind.adx_5m;
    const adxEl = document.getElementById('valHeroAdx5m');
    const adxBadge = document.getElementById('badgeHeroAdx');
    const adxGauge = document.getElementById('gaugeFillAdx');

    if (adx !== null && adx !== undefined) {
        const val = Number(adx);
        if (adxEl) adxEl.textContent = val.toFixed(2);
        if (adxGauge) adxGauge.style.width = `${Math.min(100, Math.max(0, val * 2))}%`;

        if (adxBadge) {
            adxBadge.className = "indicator-condition-tag " + (val > 20 ? "tag-bull" : "tag-neutral");
            adxBadge.textContent = val > 20 ? "STRONG TREND" : "RANGING";
        }
    }
}

function updateConditionMatrix(cond, activeTrade = null) {
    if (!cond || !cond.details) return;
    const d = cond.details;

    const setStatus = (id, pass) => {
        const el = document.getElementById(id);
        if (el) {
            el.className = `rule-pill ${pass ? 'pass' : 'fail'}`;
            el.textContent = pass ? 'PASS' : 'FAIL';
        }
    };

    // CALL
    setStatus('badgeCallRsi5m', d.rsi_5m_call);
    setStatus('badgeCallRsi15m', d.rsi_15m_call);
    setStatus('badgeCallEma', d.ema_call);
    setStatus('badgeCallAdx', d.adx_call);

    // Check 4-condition activation states
    const callAllMet = Boolean(cond.call_conditions_met || cond.call_all_met || (d.rsi_5m_call && d.rsi_15m_call && d.ema_call && d.adx_call));
    const putAllMet = Boolean(cond.put_conditions_met || cond.put_all_met || (d.rsi_5m_put && d.rsi_15m_put && d.ema_put && d.adx_put));

    const callAllEl = document.getElementById('callAllStatus');
    if (callAllEl) {
        callAllEl.className = `rule-pill ${callAllMet ? 'pass' : 'fail'}`;
        callAllEl.textContent = callAllMet ? 'ACTIVATED' : 'WAITING';
    }

    // PUT
    setStatus('badgePutRsi5m', d.rsi_5m_put);
    setStatus('badgePutRsi15m', d.rsi_15m_put);
    setStatus('badgePutEma', d.ema_put);
    setStatus('badgePutAdx', d.adx_put);

    const putAllEl = document.getElementById('putAllStatus');
    if (putAllEl) {
        putAllEl.className = `rule-pill ${putAllMet ? 'pass' : 'fail'}`;
        putAllEl.textContent = putAllMet ? 'ACTIVATED' : 'WAITING';
    }

    // Global Decision Pill
    const decPill = document.getElementById('decisionPill');
    if (decPill) {
        decPill.className = `alt-badge ${cond.raw_signal}`;
        decPill.textContent = cond.raw_signal || 'NO_TRADE';
    }

    // Sound & Voice Alert Triggers on 4-Condition Activation:
    // STRICT RULE: NEVER interrupt with triggering sounds/toasts when a trade is already active
    const isTradeCurrentlyActive = Boolean(activeTrade && (activeTrade.trade_id || activeTrade.symbol || activeTrade.entry_price));

    if (!isTradeCurrentlyActive) {
        if (callAllMet && !prevCallConditionsMet) {
            playSoundAlert('CALL_ACTIVATED');
            speakVoiceAlert('Call trade activated. All four conditions met.');
            showToast('🚀 ALL 4 CALL CONDITIONS MET: CALL Trade Activated!', 'win');
        }

        if (putAllMet && !prevPutConditionsMet) {
            playSoundAlert('PUT_ACTIVATED');
            speakVoiceAlert('Put trade activated. All four conditions met.');
            showToast('⚡ ALL 4 PUT CONDITIONS MET: PUT Trade Activated!', 'loss');
        }
    }

    prevCallConditionsMet = callAllMet;
    prevPutConditionsMet = putAllMet;
}

function updateAlternationShield(tm) {
    if (!tm) return;
    const reqBadge = document.getElementById('nextRequiredBadge');
    if (reqBadge) {
        const side = tm.next_required || 'ANY';
        reqBadge.className = `alt-badge ${side}`;
        reqBadge.textContent = side === 'ANY' ? 'ANY (FIRST)' : side;
    }

    const skippedEl = document.getElementById('skippedCountVal');
    if (skippedEl) {
        skippedEl.textContent = tm.skipped_signals_count ?? 0;
    }
}

function updateActiveTradeCard(trade) {
    const card = document.getElementById('activeTradeCard');
    const noMsg = document.getElementById('noActivePositionMsg');
    const details = document.getElementById('activePositionDetails');
    const posBadge = document.getElementById('openPositionBadge');
    const sideBadge = document.getElementById('activeSideBadge');
    const tslBanner = document.getElementById('activeTrailingStatusBanner');
    const tslText = document.getElementById('activeTrailingStatusText');
    const labelSl = document.getElementById('labelSlOrTsl');

    if (!trade) {
        if (noMsg) noMsg.style.display = 'block';
        if (details) details.style.display = 'none';
        if (posBadge) {
            posBadge.className = 'position-status-pill no-pos';
            posBadge.textContent = 'No open position';
        }
        if (sideBadge) sideBadge.style.display = 'none';
        if (tslBanner) tslBanner.style.display = 'none';
        if (labelSl) labelSl.textContent = 'STOP-LOSS';
        if (card) card.className = 'apex-panel-box position-active-card';
        return;
    }

    if (noMsg) noMsg.style.display = 'none';
    if (details) details.style.display = 'flex';

    if (posBadge) {
        posBadge.className = 'position-status-pill active-pos';
        posBadge.textContent = `Active • ${trade.side}`;
    }

    if (sideBadge) {
        sideBadge.style.display = 'inline-block';
        sideBadge.className = `alt-badge ${trade.side}`;
        sideBadge.textContent = trade.side;
    }

    if (card) {
        card.className = `apex-panel-box position-active-card ${trade.side === 'CALL' ? 'active-call' : 'active-put'}`;
    }

    const symbolEl = document.getElementById('activeSymbol');
    if (symbolEl) symbolEl.textContent = trade.symbol || `SENSEX_${trade.strike}_${trade.side === 'CALL' ? 'CE' : 'PE'}`;

    const holdEl = document.getElementById('activeHoldTime');
    if (holdEl) holdEl.textContent = `${trade.update_count || 0} ticks (${Math.round(trade.duration_seconds || 0)}s)`;

    const pnlPtsEl = document.getElementById('activePnlPts');
    const pnlInrEl = document.getElementById('activePnlInr');
    const pts = Number(trade.unrealized_pnl_points || 0);
    const inr = Number(trade.unrealized_pnl_rupees || 0);

    if (pnlPtsEl) {
        pnlPtsEl.textContent = `${pts >= 0 ? '+' : ''}${pts.toFixed(2)} pts`;
        pnlPtsEl.className = `pnl-hero-pts ${pts >= 0 ? 'val-positive' : 'val-negative'}`;
    }
    if (pnlInrEl) {
        pnlInrEl.textContent = `₹${inr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        pnlInrEl.className = `pnl-hero-rupees ${inr >= 0 ? 'val-positive' : 'val-negative'}`;
    }

    // Trailing Stop Loss Telemetry Banner
    if (trade.trailing_active) {
        if (tslBanner) tslBanner.style.display = 'flex';
        if (tslText) tslText.textContent = `TSL Activated: Dynamic SL locked at ₹${(trade.stop_loss || 0).toFixed(2)}`;
        if (labelSl) {
            labelSl.textContent = 'TRAILING SL';
            labelSl.style.color = 'var(--neon-cyan)';
        }
    } else {
        if (tslBanner) tslBanner.style.display = 'none';
        if (labelSl) {
            labelSl.textContent = 'STOP-LOSS';
            labelSl.style.color = '';
        }
    }

    const entryEl = document.getElementById('activeEntryVal');
    const ltpEl = document.getElementById('activeLtpVal');
    const slEl = document.getElementById('activeSlVal');
    const tpEl = document.getElementById('activeTpVal');

    if (entryEl) entryEl.textContent = (trade.entry_price || 0).toFixed(2);
    if (ltpEl) ltpEl.textContent = (trade.current_price || trade.entry_price || 0).toFixed(2);
    if (slEl) slEl.textContent = (trade.stop_loss || 0).toFixed(2);
    if (tpEl) tpEl.textContent = (trade.target || 0).toFixed(2);
}

function updatePortfolioMetrics(summary) {
    if (!summary) return;

    const setVal = (id, val, isPnl = false) => {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = val;
            if (isPnl) {
                const num = parseFloat(String(val).replace(/[₹,]/g, ''));
                el.className = `metric-hud-val ${num > 0 ? 'val-positive' : num < 0 ? 'val-negative' : ''}`;
            }
        }
    };

    setVal('metricTotalPnlInr', `₹${(summary.total_pnl_rupees || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, true);
    setVal('metricTotalPnlPts', `${(summary.total_pnl_points || 0).toFixed(2)} pts`, true);
    setVal('metricTotalTrades', summary.total_trades || 0);
    setVal('metricWinRate', `${(summary.win_rate_pct || 0).toFixed(1)}%`);
    setVal('metricProfitFactor', (summary.profit_factor || 0).toFixed(2));
    setVal('metricBestTrade', `₹${(summary.best_trade_rupees || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`);
    setVal('metricWorstTrade', `₹${(summary.worst_trade_rupees || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`);
    setVal('metricMaxDd', `₹${(summary.max_drawdown_rupees || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`);
}

function renderTradeHistory(trades) {
    const tbody = document.getElementById('tradeHistoryBody');
    if (!tbody) return;

    if (!trades || trades.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-dim); padding:30px;">No completed trades in this session.</td></tr>`;
        return;
    }

    tbody.innerHTML = trades.slice().reverse().map(t => `
        <tr>
            <td>#${t.trade_id}</td>
            <td><span class="alt-badge ${t.side}" style="font-size:0.68rem; padding:2px 6px;">${t.side}</span></td>
            <td><strong>${t.strike}</strong></td>
            <td style="color:var(--neon-cyan);">${t.symbol}</td>
            <td>${(t.entry_price || 0).toFixed(2)}</td>
            <td>${(t.exit_price || 0).toFixed(2)}</td>
            <td class="${t.pnl_points >= 0 ? 'val-positive' : 'val-negative'}"><strong>${t.pnl_points >= 0 ? '+' : ''}${t.pnl_points.toFixed(2)}</strong></td>
            <td class="${t.pnl_rupees >= 0 ? 'val-positive' : 'val-negative'}">₹${(t.pnl_rupees || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
            <td style="font-size:0.68rem; color:var(--text-dim);">${t.exit_reason || ''}</td>
            <td style="color:var(--text-dim);">${(t.exit_time || '').split(' ')[1] || t.exit_time || ''}</td>
        </tr>
    `).join('');
}

async function refreshTradeHistory() {
    try {
        const res = await fetch('/api/state');
        const data = await res.json();
        if (data.trade_history) {
            allTradesHistory = data.trade_history;
            renderTradeHistory(data.trade_history);
        }
    } catch (e) {
        console.error("Error refreshing trade history:", e);
    }
}

function exportTradesCSV() {
    if (!allTradesHistory || allTradesHistory.length === 0) {
        showToast("No trades to export.", "info");
        return;
    }

    const headers = ["trade_id", "side", "strike", "symbol", "entry_time", "exit_time", "entry_price", "exit_price", "exit_reason", "pnl_points", "pnl_rupees", "lot_size"];
    const rows = allTradesHistory.map(t => headers.map(h => `"${t[h] ?? ''}"`).join(","));
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `sensex_simulation_trades_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function clearClosedTradesAuditLog() {
    try {
        const btn = document.getElementById('btnClearTradesLog');
        if (btn) btn.disabled = true;

        const res = await fetch('/api/clear_trades', { method: 'POST' });
        const data = await res.json();

        if (data.status === 'TRADES_CLEARED' || res.ok) {
            allTradesHistory = data.trade_history || [];
            renderTradeHistory(allTradesHistory);

            if (data.portfolio_summary) {
                updatePortfolioMetrics(data.portfolio_summary);
            } else {
                updatePortfolioMetrics({
                    total_trades: 0,
                    winning_trades: 0,
                    losing_trades: 0,
                    win_rate_pct: 0.0,
                    total_pnl_points: 0.0,
                    total_pnl_rupees: 0.0,
                    best_trade_rupees: 0.0,
                    worst_trade_rupees: 0.0,
                    profit_factor: 0.0,
                    max_drawdown_rupees: 0.0
                });
            }
            showToast("🗑 Closed Trades Audit Log cleared for today.", "win");
        } else {
            showToast("Failed to clear trades log.", "loss");
        }
    } catch (e) {
        console.error("Error clearing trades audit log:", e);
        showToast("Error clearing trades log: " + e.message, "loss");
    } finally {
        const btn = document.getElementById('btnClearTradesLog');
        if (btn) btn.disabled = false;
    }
}

function populateConfig(cfg) {
    if (!cfg) return;
    const setInp = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val;
    };
    const setCheck = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.checked = Boolean(val);
    };

    setInp('cfgTpPoints', cfg.target_points ?? 40);
    setInp('cfgSlPoints', cfg.stop_loss_points ?? 30);
    setInp('cfgTrailTrigger', cfg.trail_trigger_points ?? 25);
    setInp('cfgTrailLock', cfg.trail_lock_points ?? 15);
    setCheck('cfgEnableTrailing', cfg.enable_trailing_sl ?? true);
    setInp('cfgMaxTrades', cfg.max_trades_per_day ?? 5);
    setInp('cfgLotSize', cfg.lot_size ?? 65);
    setCheck('cfgAutoSchedule', cfg.auto_schedule ?? true);
}

// User Actions
async function toggleAutoPlay() {
    isAutoRunning = !isAutoRunning;
    updateAutoButton();
    try {
        await fetch(`/api/toggle_auto?enable=${isAutoRunning}&speed=1.0`, { method: 'POST' });
        showToast(isAutoRunning ? "▶ Live auto-simulation started" : "⏸ Auto-simulation paused", "info");
    } catch (e) {
        console.error("Failed to toggle auto:", e);
    }
}

function updateAutoButton() {
    const btn = document.getElementById('btnToggleAuto');
    if (btn) {
        if (isAutoRunning) {
            btn.innerHTML = '<span class="side-btn-icon">⏸</span><span>PAUSE AUTO</span>';
            btn.className = 'side-btn btn-action-danger btn-ctrl btn-ctrl-danger';
        } else {
            btn.innerHTML = '<span class="side-btn-icon">▶</span><span>START AUTO</span>';
            btn.className = 'side-btn btn-action-primary btn-ctrl btn-ctrl-primary';
        }
    }
}

async function stepSimulation() {
    try {
        const res = await fetch('/api/step', { method: 'POST' });
        const tick = await res.json();
        handleTickUpdate(tick);
    } catch (e) {
        console.error("Failed to step simulation:", e);
    }
}

async function loadReplay() {
    try {
        showToast("Loading BSE Sensex historical replay dataset...", "info");
        await fetch('/api/load_replay?ticks=300', { method: 'POST' });
    } catch (e) {
        console.error("Failed to load replay:", e);
    }
}

async function resetSession() {
    try {
        await fetch('/api/reset', { method: 'POST' });
    } catch (e) {
        console.error("Failed to reset session:", e);
    }
}

async function saveSettings(e) {
    if (e && e.preventDefault) e.preventDefault();
    const btn = document.getElementById('btnSaveSettings');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Saving...';
    }

    const payload = {
        target_points: parseFloat(document.getElementById('cfgTpPoints')?.value || 40),
        stop_loss_points: parseFloat(document.getElementById('cfgSlPoints')?.value || 30),
        trail_trigger_points: parseFloat(document.getElementById('cfgTrailTrigger')?.value || 25),
        trail_lock_points: parseFloat(document.getElementById('cfgTrailLock')?.value || 15),
        enable_trailing_sl: Boolean(document.getElementById('cfgEnableTrailing')?.checked),
        max_trades_per_day: parseInt(document.getElementById('cfgMaxTrades')?.value || 5),
        lot_size: parseInt(document.getElementById('cfgLotSize')?.value || 65),
        auto_schedule: Boolean(document.getElementById('cfgAutoSchedule')?.checked)
    };

    try {
        const res = await fetch('/api/update_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.status === 'CONFIG_UPDATED') {
            showToast("💾 Parameters saved successfully!", "win");
        } else {
            showToast("Parameters updated.", "info");
        }
    } catch (err) {
        console.error("Failed to update config:", err);
        showToast("Error saving settings: " + err.message, "loss");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = 'Save Settings';
        }
    }
}
const saveConfig = saveSettings;

// Initial Boot
window.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();

    const btnClear = document.getElementById('btnClearTradesLog');
    if (btnClear) {
        btnClear.addEventListener('click', clearClosedTradesAuditLog);
    }
});
