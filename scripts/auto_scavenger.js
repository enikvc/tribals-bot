(function() {
    'use strict';

    // ---- CONFIG ----
    const BASE_INTERVAL_SECONDS = 600;  // base interval between runs in seconds
    const INTERVAL_JITTER_SECONDS = 60; // jitter up to this many seconds
    const SCRIPT_URL = 'https://shinko-to-kuma.com/scripts/massScavenge.js';
    const CLICK_MIN_DELAY = 200;   // minimum ms before first click
    const CLICK_MAX_DELAY = 800;   // maximum ms before first click
    const SECOND_CLICK_MIN = 300;  // minimum ms after first click
    const SECOND_CLICK_MAX = 1000; // maximum ms after first click
    const ACTIVE_START_HOUR = 2;  // 8:00 AM
    const ACTIVE_END_HOUR = 2;    // 3:00 AM (next day)
    // ----------------

    let isRunning = false;
    let nextTimeout = null;

    // Load an external script while respecting page CSP by fetching the
    // code and injecting it as a Blob URL from the extension's origin.
    function loadExternalScript(src) {
        return fetch(src)
            .then(r => r.text())
            .then(code => {
                const blob = new Blob([code], { type: 'text/javascript' });
                const blobUrl = URL.createObjectURL(blob);
                return new Promise((resolve, reject) => {
                    const s = document.createElement('script');
                    s.src = blobUrl;
                    s.onload = () => {
                        URL.revokeObjectURL(blobUrl);
                        resolve();
                    };
                    s.onerror = e => {
                        URL.revokeObjectURL(blobUrl);
                        reject(e);
                    };
                    document.head.appendChild(s);
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

    // Create floating control panel
    const panel = document.createElement('div');
    Object.assign(panel.style, {
        position:     'fixed',
        bottom:       '220px',
        right:        '20px',
        padding:      '10px',
        background:   'rgba(0,0,0,0.7)',
        color:        '#fff',
        borderRadius: '5px',
        zIndex:       10000,
        fontFamily:   'sans-serif',
        textAlign:    'center'
    });
    panel.innerHTML = `
        <div style="margin-bottom:8px; font-weight:bold;">Auto Scavenger</div>
        <div id="timeStatus" style="margin-bottom:8px; font-size:12px;"></div>
        <button id="autoScavengeToggle" style="padding:5px 10px;">Start</button>
    `;
    document.body.appendChild(panel);

    const btn = document.getElementById('autoScavengeToggle');

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

    // Initialize time status and update every minute
    updateTimeStatus();
    setInterval(updateTimeStatus, 60000);

    // Schedule the two clicks: first then second after offset
    function clickSequence() {
        const firstDelay = CLICK_MIN_DELAY + Math.random() * (CLICK_MAX_DELAY - CLICK_MIN_DELAY);
        const secondOffset = SECOND_CLICK_MIN + Math.random() * (SECOND_CLICK_MAX - SECOND_CLICK_MIN);

        // First button: readyToSend()
        setTimeout(() => {
            const el1 = document.querySelector('input.btnSophie[onclick="readyToSend()"]');
            if (el1) {
                el1.click();
                console.log(`[Auto-Scavenger] Clicked readyToSend() after ${Math.round(firstDelay)} ms at ${new Date().toLocaleTimeString()}`);
            } else {
                console.warn('[Auto-Scavenger] readyToSend() button not found');
            }
        }, firstDelay);

        // Second button: sendGroup(0,false)
        setTimeout(() => {
            const el2 = document.querySelector('input.btnSophie[onclick="sendGroup(0,false)"]');
            if (el2) {
                el2.click();
                console.log(`[Auto-Scavenger] Clicked sendGroup(0,false) after ${Math.round(firstDelay + secondOffset)} ms at ${new Date().toLocaleTimeString()}`);
            } else {
                console.warn('[Auto-Scavenger] sendGroup(0,false) button not found');
            }
        }, firstDelay + secondOffset);
    }

    // Run sequence: load script, then click buttons
    function runScavenger() {
        // Check if we're still within active hours before running
        if (!isWithinActiveHours()) {
            console.log('[Auto-Scavenger] Outside active hours, stopping...');
            if (isRunning) {
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
                console.log(`[Auto-Scavenger] Script loaded at ${new Date().toLocaleTimeString()}`);
                clickSequence();
            })
            .catch((e) => {
                console.error('[Auto-Scavenger] Failed to load script:', e);
            })
            .finally(scheduleNext);
    }

    // Schedule next run with jitter (only if within active hours)
    function scheduleNext() {
        if (!isRunning) return;

        if (!isWithinActiveHours()) {
            console.log('[Auto-Scavenger] Outside active hours, will resume at 8:00 AM');
            scheduleNextActiveCheck();
            return;
        }

        const jitter = Math.random() * INTERVAL_JITTER_SECONDS;
        const interval = (BASE_INTERVAL_SECONDS + jitter) * 1000;
        console.log(`[Auto-Scavenger] Next run in ${Math.round(interval/1000)} seconds`);
        nextTimeout = setTimeout(runScavenger, interval);
    }

    // Schedule check for when active period begins
    function scheduleNextActiveCheck() {
        const secondsUntil = getTimeUntilActive();
        if (secondsUntil > 0) {
            console.log(`[Auto-Scavenger] Will check again in ${Math.floor(secondsUntil/60)} minutes`);
            nextTimeout = setTimeout(() => {
                if (isRunning && isWithinActiveHours()) {
                    runScavenger();
                } else {
                    scheduleNextActiveCheck();
                }
            }, Math.min(secondsUntil * 1000, 300000)); // Check at least every 5 minutes
        }
    }

    // Toggle start/stop
    btn.addEventListener('click', () => {
        if (!isRunning) {
            if (!isWithinActiveHours()) {
                alert(`Auto Scavenger is only active between ${ACTIVE_START_HOUR}:00 and ${ACTIVE_END_HOUR}:00. It will start automatically when the active period begins.`);
            }
            isRunning = true;
            btn.textContent = 'Stop';
            btn.style.background = '#e74c3c';

            if (isWithinActiveHours()) {
                runScavenger();  // start immediately
            } else {
                scheduleNextActiveCheck();
            }
        } else {
            isRunning = false;
            btn.textContent = 'Start';
            btn.style.background = '';
            clearTimeout(nextTimeout);
            console.log('[Auto-Scavenger] Stopped');
        }
    });
})();