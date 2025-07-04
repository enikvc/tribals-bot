// scripts/auto_scavenger_v2.js
(function() {
    'use strict';

    let config = null;
    let isRunning = false;
    let nextTimeout = null;

    async function init() {
        const botConfig = await window.tribalsBot.init('autoScavenger');
        config = botConfig.config;
        
        createPanel();
        
        // Check if should auto-start
        if (config.enabled && window.tribalsBot.isWithinActiveHours()) {
            toggle(true);
        }
        
        // Listen for state changes
        window.addEventListener('tribalsbot:stateChanged', (e) => {
            const { enabled, isActive } = e.detail;
            if (enabled && isActive && !isRunning) {
                toggle(true);
            } else if (!enabled && isRunning) {
                toggle(false);
            }
        });
        
        // Listen for config updates
        window.addEventListener('tribalsbot:configUpdated', (e) => {
            config = e.detail.config;
            console.log('[Auto-Scavenger] Config updated');
            updateInfoDisplay();
        });
        
        // Listen for active status updates
        window.addEventListener('tribalsbot:activeStatusUpdate', (e) => {
            const { isActive } = e.detail;
            updateTimeStatus();
            
            if (config.enabled) {
                if (isActive && !isRunning) {
                    console.log('[Auto-Scavenger] Active hours started, resuming');
                    toggle(true);
                } else if (!isActive && isRunning) {
                    console.log('[Auto-Scavenger] Active hours ended, pausing');
                    toggle(false);
                    scheduleNextActiveCheck();
                }
            }
        });
    }

    function loadExternalScript(src) {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            if (src.includes('massScavenge.js')) {
                s.src = chrome.runtime.getURL('vendor/massScavenge.js');
            } else {
                s.src = src;
            }
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    function createPanel() {
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
            <div style="background:#3498db;color:white;padding:2px 6px;border-radius:3px;font-size:10px;margin-bottom:5px;">Managed by Tribals Bot</div>
            <div id="timeStatus" style="margin-bottom:8px; font-size:12px;"></div>
            <div id="scavengerInfo" style="font-size:11px;color:#aaa;"></div>
        `;
        
        document.body.appendChild(panel);
        
        updateTimeStatus();
        updateInfoDisplay();
        setInterval(updateTimeStatus, 60000);
    }

    function updateInfoDisplay() {
        const info = document.getElementById('scavengerInfo');
        if (info) {
            info.innerHTML = `Base interval: ${config.baseIntervalSeconds}s<br>Jitter: ±${config.intervalJitterSeconds}s<br>Status: ${config.enabled ? 'Enabled' : 'Disabled'}`;
        }
    }

    function updateTimeStatus() {
        const statusDiv = document.getElementById('timeStatus');
        const now = new Date();
        const timeStr = now.toLocaleTimeString();

        if (window.tribalsBot.isWithinActiveHours()) {
            statusDiv.innerHTML = `<span style="color:#2ecc71;">Active</span><br>${timeStr}`;
        } else {
            const secondsUntil = window.tribalsBot.getTimeUntilActive();
            const hoursUntil = Math.floor(secondsUntil / 3600);
            const minutesUntil = Math.floor((secondsUntil % 3600) / 60);
            statusDiv.innerHTML = `<span style="color:#e74c3c;">Inactive</span><br>${timeStr}<br>Active in ${hoursUntil}h ${minutesUntil}m`;
        }
    }

    function clickSequence() {
        const firstDelay = config.clickMinDelay + Math.random() * (config.clickMaxDelay - config.clickMinDelay);
        const secondOffset = config.secondClickMin + Math.random() * (config.secondClickMax - config.secondClickMin);

        setTimeout(() => {
            const el1 = document.querySelector('input.btnSophie[onclick="readyToSend()"]');
            if (el1) {
                el1.click();
                console.log(`[Auto-Scavenger] Clicked readyToSend() after ${Math.round(firstDelay)} ms at ${new Date().toLocaleTimeString()}`);
            } else {
                console.warn('[Auto-Scavenger] readyToSend() button not found');
            }
        }, firstDelay);

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

    function runScavenger() {
        if (!window.tribalsBot.isWithinActiveHours()) {
            console.log('[Auto-Scavenger] Outside active hours, stopping...');
            if (isRunning) {
                toggle(false);
            }
            scheduleNextActiveCheck();
            return;
        }

        loadExternalScript('massScavenge.js')
            .then(() => {
                console.log(`[Auto-Scavenger] Script loaded at ${new Date().toLocaleTimeString()}`);
                clickSequence();
            })
            .catch((e) => {
                console.error('[Auto-Scavenger] Failed to load script:', e);
            })
            .finally(scheduleNext);
    }

    function scheduleNext() {
        if (!isRunning) return;

        if (!window.tribalsBot.isWithinActiveHours()) {
            console.log('[Auto-Scavenger] Outside active hours, will resume when active');
            scheduleNextActiveCheck();
            return;
        }

        const jitter = Math.random() * config.intervalJitterSeconds;
        const interval = (config.baseIntervalSeconds + jitter) * 1000;
        console.log(`[Auto-Scavenger] Next run in ${Math.round(interval/1000)} seconds`);
        nextTimeout = setTimeout(runScavenger, interval);
    }

    function scheduleNextActiveCheck() {
        const secondsUntil = window.tribalsBot.getTimeUntilActive();
        if (secondsUntil > 0) {
            console.log(`[Auto-Scavenger] Will check again in ${Math.floor(secondsUntil/60)} minutes`);
            nextTimeout = setTimeout(() => {
                if (config.enabled && window.tribalsBot.isWithinActiveHours()) {
                    toggle(true);
                } else {
                    scheduleNextActiveCheck();
                }
            }, Math.min(secondsUntil * 1000, 300000));
        }
    }

    function toggle(forceState = null) {
        if (forceState !== null) {
            isRunning = forceState;
        } else {
            isRunning = !isRunning;
        }
        
        if (isRunning) {
            console.log('[Auto-Scavenger] Started');
            if (window.tribalsBot.isWithinActiveHours()) {
                runScavenger();
            } else {
                scheduleNextActiveCheck();
            }
        } else {
            console.log('[Auto-Scavenger] Stopped');
            clearTimeout(nextTimeout);
        }
        
        updateInfoDisplay();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();