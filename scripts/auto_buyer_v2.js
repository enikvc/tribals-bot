// scripts/auto_buyer_v2.js
(function() {
  'use strict';

  let config = null;
  let running = false;
  let attempts = 0;
  let observer;
  let nextActiveCheckTimeout;

  // Initialize
  async function init() {
    const botConfig = await window.tribalsBot.init('autoBuyer');
    config = botConfig.config;
    
    createUI();
    
    // Check if should auto-start
    if (config.enabled && window.tribalsBot.isWithinActiveHours()) {
      startAutobuyer();
    }
    
    // Listen for state changes
    window.addEventListener('tribalsbot:stateChanged', (e) => {
      const { enabled, isActive } = e.detail;
      if (enabled && isActive && !running) {
        startAutobuyer();
      } else if (!enabled && running) {
        stopAutobuyer();
      }
    });
    
    // Listen for config updates
    window.addEventListener('tribalsbot:configUpdated', (e) => {
      config = e.detail.config;
      log('⚙️', 'Config updated');
    });
    
    // Listen for active status updates
    window.addEventListener('tribalsbot:activeStatusUpdate', (e) => {
      const { isActive } = e.detail;
      updateTimeStatus();
      
      if (config.enabled) {
        if (isActive && !running) {
          log('🟢', 'Active hours started, resuming autobuyer');
          startAutobuyer();
        } else if (!isActive && running) {
          log('⏰', 'Active hours ended, pausing autobuyer');
          stopAutobuyer();
          scheduleNextActiveCheck();
        }
      }
    });
  }

  // Minimal logging with ms timestamps and emojis
  function log(emoji, message) {
    const now = new Date();
    const ts = now.toISOString().substr(11,12);
    console.log(`${emoji} [${ts}] ${message}`);
  }

  const resources = ['wood', 'stone', 'iron'];

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

  function updateTimeStatus() {
    const statusDiv = document.getElementById('timeStatus');
    if (!statusDiv) return;

    const now = new Date();
    const timeStr = now.toLocaleTimeString();

    if (window.tribalsBot.isWithinActiveHours()) {
      statusDiv.innerHTML = `<span style="color:#28a745;">Active</span><br>${timeStr}`;
    } else {
      const secondsUntil = window.tribalsBot.getTimeUntilActive();
      const hoursUntil = Math.floor(secondsUntil / 3600);
      const minutesUntil = Math.floor((secondsUntil % 3600) / 60);
      statusDiv.innerHTML = `<span style="color:#dc3545;">Inactive</span><br>${timeStr}<br>Active in ${hoursUntil}h ${minutesUntil}m`;
    }
  }

  function scheduleNextActiveCheck() {
    const secondsUntil = window.tribalsBot.getTimeUntilActive();
    if (secondsUntil > 0) {
      log('⏰', `Will check again in ${Math.floor(secondsUntil/60)} minutes`);
      nextActiveCheckTimeout = setTimeout(() => {
        if (config.enabled && window.tribalsBot.isWithinActiveHours()) {
          log('🟢', 'Resuming autobuyer - now in active hours');
          startAutobuyer();
        } else {
          scheduleNextActiveCheck();
        }
      }, Math.min(secondsUntil * 1000, 300000));
    }
  }

  function createUI() {
    const c = document.createElement('div');
    Object.assign(c.style, {
      position: 'fixed', top: '150px', right: '25px', zIndex: '9999',
      padding: '5px', background: 'rgba(255,255,255,0.9)',
      border: '1px solid #ccc', borderRadius: '4px', fontSize: '12px'
    });

    const statusBadge = document.createElement('div');
    statusBadge.style.cssText = 'background:#3498db;color:white;padding:2px 6px;border-radius:3px;font-size:10px;margin-bottom:5px;text-align:center;';
    statusBadge.textContent = 'Managed by Tribals Bot';
    c.appendChild(statusBadge);

    const timeStatus = document.createElement('div');
    timeStatus.id = 'timeStatus';
    timeStatus.style.marginBottom = '5px';
    timeStatus.style.textAlign = 'center';
    timeStatus.style.fontSize = '11px';
    c.appendChild(timeStatus);

    const info = document.createElement('div');
    info.style.cssText = 'margin-top:5px;font-size:11px;color:#666;text-align:center;';
    info.innerHTML = `PP: ≥${config.minPP}<br>Stock: ≥${config.minStock}<br>Delay: ${config.postBuyDelay}ms`;
    c.appendChild(info);

    document.body.appendChild(c);

    updateTimeStatus();
    setInterval(updateTimeStatus, 60000);

    log('⚙️', 'UI ready (managed mode)');
  }

  function startAutobuyer() {
    if (running) return;
    
    attempts = 0;
    running = true;
    log('🟢', 'Autobuyer started');

    if (!window.tribalsBot.isWithinActiveHours()) {
      log('⏰', 'Outside active hours, will start when active period begins');
      scheduleNextActiveCheck();
      return;
    }

    dismissQuest();
    observeStocks();
    handleMutation();
  }

  function stopAutobuyer() {
    if (!running) return;
    
    running = false;
    if (observer) observer.disconnect();
    if (nextActiveCheckTimeout) clearTimeout(nextActiveCheckTimeout);
    log('🔴', 'Autobuyer stopped');
  }

  function handleMutation() {
    if (!running) return;

    if (!window.tribalsBot.isWithinActiveHours()) {
      log('⏰', 'Outside active hours, pausing until active period');
      if (observer) observer.disconnect();
      scheduleNextActiveCheck();
      return;
    }

    dismissQuest();
    const pp = getPP();
    if (pp < config.minPP) {
      log('⚠️', `PP ${pp}<${config.minPP}, stopping`);
      running = false;
      stopAutobuyer();
      window.tribalsBot.updateState(false);
      return;
    }

    const opts = resources.map(r => {
      const stock = getStock(r);
      const rate = getRate(r);
      let amount = 0;
      if (stock >= config.minStock) {
        if (stock >= rate) {
          amount = Math.floor(stock / rate) * rate;
        } else {
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
        if (window.tribalsBot.isWithinActiveHours()) {
          observeStocks();
          handleMutation();
        } else {
          log('⏰', 'Outside active hours, pausing');
          scheduleNextActiveCheck();
        }
      }
    }, config.postBuyDelay);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();