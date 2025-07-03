(function() {
  'use strict';

  // ---- TIME CONFIG ----
  const ACTIVE_START_HOUR = 8;  // 8:00 AM
  const ACTIVE_END_HOUR = 2;    // 3:00 AM (next day)
  // ---------------------

  // Check if current time is within allowed hours (8:00 AM to 3:00 AM)
  function isWithinActiveHours() {
    const now = new Date();
    const currentHour = now.getHours();

    // Active from 8:00 AM to 3:00 AM (next day)
    // This means: hour >= 8 OR hour < 3
    return currentHour >= ACTIVE_START_HOUR || currentHour < ACTIVE_END_HOUR;
  }

  // Get time until next active period
  function getTimeUntilActive() {
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const currentSecond = now.getSeconds();

    if (isWithinActiveHours()) {
      return 0; // Already in active period
    }

    // Inactive period is 3:00 AM to 8:00 AM
    // Calculate seconds until 8:00 AM
    const hoursUntil8AM = ACTIVE_START_HOUR - currentHour;
    const minutesUntil8AM = -currentMinute;
    const secondsUntil8AM = -currentSecond;

    return (hoursUntil8AM * 3600) + (minutesUntil8AM * 60) + secondsUntil8AM;
  }

  // Minimal logging with ms timestamps and emojis
  function log(emoji, message) {
    const now = new Date();
    const ts = now.toISOString().substr(11,12);
    console.log(`${emoji} [${ts}] ${message}`);
  }

  const resources = ['wood', 'stone', 'iron'];
  let minPP = 3000;
  let minStock = 64;
  let postBuyDelay = 4800;
  let attempts = 0;
  let observer;
  let running = false;
  let timeStatusInterval;
  let nextActiveCheckTimeout;

  function dismissQuest() {
    const btn = document.querySelector('.quest-complete-btn');
    if (btn) btn.click();
  }

  function observeStocks() {
    if (observer) observer.disconnect();
    observer = new MutationObserver(handleMutation);
    const cfg = { childList: true, subtree: true };
    resources.forEach(r => {
      const el = document.getElementById(`premium_exchange_stock_${r}`);
      if (el) observer.observe(el, cfg);
    });
  }

  // Update the time status display
  function updateTimeStatus() {
    const statusDiv = document.getElementById('timeStatus');
    if (!statusDiv) return;

    const now = new Date();
    const timeStr = now.toLocaleTimeString();

    if (isWithinActiveHours()) {
      statusDiv.innerHTML = `<span style="color:#28a745;">Active</span><br>${timeStr}`;
    } else {
      const secondsUntil = getTimeUntilActive();
      const hoursUntil = Math.floor(secondsUntil / 3600);
      const minutesUntil = Math.floor((secondsUntil % 3600) / 60);
      statusDiv.innerHTML = `<span style="color:#dc3545;">Inactive</span><br>${timeStr}<br>Active in ${hoursUntil}h ${minutesUntil}m`;
    }
  }

  // Schedule check for when active period begins
  function scheduleNextActiveCheck() {
    const secondsUntil = getTimeUntilActive();
    if (secondsUntil > 0) {
      log('⏰', `Will check again in ${Math.floor(secondsUntil/60)} minutes`);
      nextActiveCheckTimeout = setTimeout(() => {
        if (running && isWithinActiveHours()) {
          log('🟢', 'Resuming autobuyer - now in active hours');
          observeStocks();
          handleMutation();
        } else {
          scheduleNextActiveCheck();
        }
      }, Math.min(secondsUntil * 1000, 300000)); // Check at least every 5 minutes
    }
  }

  function createUI() {
    const c = document.createElement('div');
    Object.assign(c.style, {
      position: 'fixed', top: '150px', right: '25px', zIndex: '9999',
      padding: '5px', background: 'rgba(255,255,255,0.9)',
      border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px'
    });

    // Time status display
    const timeStatus = document.createElement('div');
    timeStatus.id = 'timeStatus';
    timeStatus.style.marginBottom = '5px';
    timeStatus.style.textAlign = 'center';
    timeStatus.style.fontSize = '11px';
    c.appendChild(timeStatus);

    const btn = document.createElement('button');
    btn.id = 'autoBuyerToggle';
    btn.textContent = 'Start Autobuyer';
    Object.assign(btn.style, { padding: '5px 10px', marginBottom: '5px', width: '100%', cursor: 'pointer' });
    btn.style.background = '#28a745';
    btn.addEventListener('click', () => {
      if (!running) {
        if (!isWithinActiveHours()) {
          alert(`Premium Autobuyer is only active between ${ACTIVE_START_HOUR}:00 and ${ACTIVE_END_HOUR}:00. It will start automatically when the active period begins.`);
        }
        running = true;
        btn.textContent = 'Stop Autobuyer';
        btn.style.background = '#dc3545';
        startAutobuyer();
      } else {
        running = false;
        btn.textContent = 'Start Autobuyer';
        btn.style.background = '#28a745';
        stopAutobuyer();
      }
    });
    c.appendChild(btn);

    function addInput(label, value, onChange) {
      const l = document.createElement('label');
      l.textContent = label;
      l.style.display = 'block';
      l.style.margin = '4px 0 2px';
      c.appendChild(l);
      const i = document.createElement('input');
      i.type = 'number';
      i.value = value;
      i.style.width = '100%';
      i.addEventListener('change', () => {
        const v = parseInt(i.value, 10);
        if (!isNaN(v) && v >= 0) {
          onChange(v);
          log('⚙️', `${label}=${v}`);
        } else {
          i.value = value;
        }
      });
      c.appendChild(i);
    }

    addInput('minStock', minStock, v => minStock = v);
    addInput('postBuyDelay', postBuyDelay, v => postBuyDelay = v);
    document.body.appendChild(c);

    // Initialize time status and update every minute
    updateTimeStatus();
    timeStatusInterval = setInterval(updateTimeStatus, 60000);

    log('⚙️', 'UI ready');
  }

  function startAutobuyer() {
    attempts = 0;
    log('🟢', 'Autobuyer started');

    if (!isWithinActiveHours()) {
      log('⏰', 'Outside active hours, will start when active period begins');
      scheduleNextActiveCheck();
      return;
    }

    dismissQuest();
    observeStocks();
    handleMutation();
  }

  function stopAutobuyer() {
    if (observer) observer.disconnect();
    if (nextActiveCheckTimeout) clearTimeout(nextActiveCheckTimeout);
    log('🔴', 'Autobuyer stopped');
  }

  function handleMutation() {
    if (!running) return;

    // Check if we're still within active hours
    if (!isWithinActiveHours()) {
      log('⏰', 'Outside active hours, pausing until 8:00 AM');
      if (observer) observer.disconnect();
      scheduleNextActiveCheck();
      return;
    }

    dismissQuest();
    const pp = getPP();
    if (pp < minPP) {
      log('⚠️', `PP ${pp}<${minPP}, stopping`);
      running = false;
      stopAutobuyer();
      const btn = document.getElementById('autoBuyerToggle');
      if (btn) {
        btn.textContent = 'Start Autobuyer';
        btn.style.background = '#28a745';
      }
      return;
    }

    const opts = resources.map(r => {
      const stock = getStock(r);
      const rate = getRate(r);
      let amount = 0;
      if (stock >= minStock) {
        if (stock >= rate) {
          // full bundles only when meeting minStock
          amount = Math.floor(stock / rate) * rate;
        } else {
          // remainder when stock < rate but >= minStock
          amount = stock;
          log('ℹ️', `${r}: stock<rate, using remainder ${amount}`);
        }
      }
      return { r, amount, rate };
    }).filter(o => o.amount > 0);

    if (opts.length === 0) return;
    opts.sort((a, b) => b.amount - a.amount);
    const { r, amount, rate } = opts[0];

    attempts++;
    log('🔄', `#${attempts} buy ${amount}${r}@${rate}`);
    if (observer) observer.disconnect();
    clearInputs();
    fillAndCalc(r, amount, rate);
  }

  function getPP() {
    const e = document.getElementById('premium_points');
    return e ? parseInt(e.textContent.trim(), 10) : 0;
  }

  function getStock(r) {
    const e = document.getElementById(`premium_exchange_stock_${r}`);
    return e ? parseInt(e.textContent.trim(), 10) : 0;
  }

  function getRate(r) {
    const m = document.getElementById(`premium_exchange_rate_${r}`).innerText.match(/(\d+)/);
    return m ? parseInt(m[1], 10) : Infinity;
  }

  function clearInputs() {
    document.querySelectorAll('input.premium-exchange-input[data-type="buy"]').forEach(i => i.value = '');
  }

  function fillAndCalc(r, amount, rate) {
    if (!running) return;
    const inp = document.querySelector(`input.premium-exchange-input[data-resource="${r}"][data-type="buy"]`);
    if (!inp) return;
    inp.value = amount;
    const btn = document.querySelector('input.btn-premium-exchange-buy');
    if (!btn) return;
    log('➡️', `calc ${r}`);
    btn.click();
    awaitConfirmation(rate, amount);
  }

  function awaitConfirmation(minRate, req) {
    const interval = setInterval(() => {
      if (!running) { clearInterval(interval); return; }
      const box = document.getElementById('premium_exchange');
      if (!box) return;
      clearInterval(interval);
      if (box.querySelector('td.warn')) {
        log('⚠️', 'trade warning');
        box.querySelector('.evt-cancel-btn.btn-confirm-no')?.click();
        clearInputs();
        return scheduleNext();
      }
      const txt = box.querySelector('table.vis tr.row_a td:nth-child(2)')?.textContent.trim() || '';
      const best = parseInt(txt.match(/(\d+)/)?.[1] || '0', 10);
      const ok = best > 0 && best >= req;
      box.querySelector(ok ? '.evt-confirm-btn.btn-confirm-yes' : '.evt-cancel-btn.btn-confirm-no')?.click();
      log(ok ? '✅' : '❌', `trade ${best}`);
      clearInputs();
      scheduleNext();
    }, 200);
  }

  function scheduleNext() {
    setTimeout(() => {
      if (running) {
        // Check if still in active hours before continuing
        if (isWithinActiveHours()) {
          observeStocks();
          handleMutation();
        } else {
          log('⏰', 'Outside active hours, pausing');
          scheduleNextActiveCheck();
        }
      }
    }, postBuyDelay);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createUI);
  } else {
    createUI();
  }
})();