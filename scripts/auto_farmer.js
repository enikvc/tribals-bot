(function() {
    'use strict';

    // ---- CONFIG ----
    const INTERVAL_SECONDS = 600;           // 15 minutes
    const SCRIPT_URL = 'https://cdn.jsdelivr.net/gh/enikvc/tribals_it_scripts@refs/tags/1.2/farmgod.js';
    const PLAN_DELAY = 700;                 // ms after script load before clicking Plan farms
    const ICON_START_DELAY = 1000;          // ms after Plan farms click before selecting icons
    const ICON_CLICK_INTERVAL = 527;       // ms between each farm icon click
    const ACTIVE_START_HOUR = 2;            // 8:00 AM
    const ACTIVE_END_HOUR = 2;              // 3:00 AM (next day)
    // ----------------

    let isRunning = false;
    let nextTimeout = null;

    // Load an external script while respecting page CSP by fetching the
    // code and injecting it via a Blob URL which inherits the extension's
    // origin. This avoids CSP restrictions on external scripts.
    function loadExternalScript(src) {
        return new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ type: 'fetch-script', src }, (resp) => {
                if (chrome.runtime.lastError) {
                    reject(chrome.runtime.lastError);
                    return;
                }
                if (resp && resp.code) {
                    try {
                        new Function(resp.code)();
                        resolve();
                    } catch (e) {
                        reject(e);
                    }
                } else {
                    reject(resp && resp.error);
                }
            });
        });
    }

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

    // Initialize the control panel
    function initPanel() {
        const panel = document.createElement('div');
        Object.assign(panel.style, {
            position: 'fixed', bottom: '120px', right: '20px',
            padding: '10px', background: 'rgba(0,0,0,0.7)', color: '#fff',
            borderRadius: '5px', zIndex: 10000, fontFamily: 'sans-serif', textAlign: 'center'
        });
        panel.innerHTML = `
            <div style="margin-bottom:8px; font-weight:bold;">Auto Farmer</div>
            <div id="timeStatus" style="margin-bottom:8px; font-size:12px;"></div>
            <button id="autoFarmToggle" style="padding:5px 10px;">Start</button>
        `;
        document.body.appendChild(panel);
        document.getElementById('autoFarmToggle').addEventListener('click', toggle);
        updateTimeStatus();

        // Update time status every minute
        setInterval(updateTimeStatus, 60000);
    }

    // Update the time status display
    function updateTimeStatus() {
        const statusDiv = document.getElementById('timeStatus');
        const now = new Date();
        const timeStr = now.toLocaleTimeString();

        if (isWithinActiveHours()) {
            statusDiv.innerHTML = `<span style="color:#2ecc71;">Active</span><br>${timeStr}`;
        } else {
            const secondsUntil = getTimeUntilActive();
            const hoursUntil = Math.floor(secondsUntil / 3600);
            const minutesUntil = Math.floor((secondsUntil % 3600) / 60);
            statusDiv.innerHTML = `<span style="color:#e74c3c;">Inactive</span><br>${timeStr}<br>Active in ${hoursUntil}h ${minutesUntil}m`;
        }
    }

    // Main run: loads script, clicks Plan farms, then farm icons
    function runFarming() {
        // Check if we're still within active hours before running
        if (!isWithinActiveHours()) {
            console.log('[Auto-Farmer] Outside active hours, stopping...');
            if (isRunning) {
                const btn = document.getElementById('autoFarmToggle');
                isRunning = false;
                btn.textContent = 'Start';
                btn.style.background = '';
                clearTimeout(nextTimeout);
            }
            scheduleNextActiveCheck();
            return;
        }

        loadExternalScript(SCRIPT_URL)
            .then(() => {
                console.log(`[Auto-Farmer] Script loaded at ${new Date().toLocaleTimeString()}`);
                setTimeout(() => {
                    const planBtn = document.querySelector('input.btn.optionButton[value="Plan farms"]');
                    if (planBtn) {
                        planBtn.click();
                        console.log('[Auto-Farmer] Clicked Plan farms');
                        setTimeout(clickIconsInModal, ICON_START_DELAY);
                    } else {
                        console.warn('[Auto-Farmer] "Plan farms" button not found');
                        scheduleNext();
                    }
                }, PLAN_DELAY);
            })
            .catch((e) => {
                console.error('[Auto-Farmer] Failed to load script:', e);
                scheduleNext();
            });
    }

    // Finds and clicks each farm icon sequentially
    function clickIconsInModal() {
        const container = document.querySelector('div.farmGodContent');
        const icons = container
            ? container.querySelectorAll('a.farmGod_icon.farm_icon.farm_icon_a')
            : document.querySelectorAll('a.farmGod_icon.farm_icon.farm_icon_a');
        console.log(`[Auto-Farmer] Found ${icons.length} farm icons`);
        if (icons.length === 0) {
            console.warn('[Auto-Farmer] No farm icons found to click');
            scheduleNext();
            return;
        }
        icons.forEach((icon, idx) => {
            setTimeout(() => {
                icon.click();
                console.log(`[Auto-Farmer] Clicked farm icon #${idx+1} at ${new Date().toLocaleTimeString()}`);
                if (idx === icons.length - 1) scheduleNext();
            }, ICON_CLICK_INTERVAL * idx);
        });
    }

    // Schedule next run (only if within active hours)
    function scheduleNext() {
        if (!isRunning) return;

        if (!isWithinActiveHours()) {
            console.log('[Auto-Farmer] Outside active hours, will resume at 8:00 AM');
            scheduleNextActiveCheck();
            return;
        }

        console.log(`[Auto-Farmer] Next run in ${INTERVAL_SECONDS} seconds`);
        nextTimeout = setTimeout(runFarming, INTERVAL_SECONDS * 1000);
    }

    // Schedule check for when active period begins
    function scheduleNextActiveCheck() {
        const secondsUntil = getTimeUntilActive();
        if (secondsUntil > 0) {
            console.log(`[Auto-Farmer] Will check again in ${Math.floor(secondsUntil/60)} minutes`);
            nextTimeout = setTimeout(() => {
                if (isRunning && isWithinActiveHours()) {
                    runFarming();
                } else {
                    scheduleNextActiveCheck();
                }
            }, Math.min(secondsUntil * 1000, 300000)); // Check at least every 5 minutes
        }
    }

    // Toggle start/stop
    function toggle() {
        const btn = document.getElementById('autoFarmToggle');
        if (!isRunning) {
            if (!isWithinActiveHours()) {
                alert(`Auto Farmer is only active between ${ACTIVE_START_HOUR}:00 and ${ACTIVE_END_HOUR}:00. It will start automatically when the active period begins.`);
            }
            isRunning = true;
            btn.textContent = 'Stop';
            btn.style.background = '#e74c3c';

            if (isWithinActiveHours()) {
                runFarming();
            } else {
                scheduleNextActiveCheck();
            }
        } else {
            isRunning = false;
            btn.textContent = 'Start';
            btn.style.background = '';
            clearTimeout(nextTimeout);
            console.log('[Auto-Farmer] Stopped');
        }
    }

    // On load, init panel
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPanel);
    } else {
        initPanel();
    }
})();
