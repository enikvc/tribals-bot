// scripts/auto_scavenger.js
(function() {
    'use strict';

    let config = null;
    let isRunning = false;
    let nextTimeout = null;
    let isDesignatedTab = false;
    let isInitialized = false; // Prevent multiple initializations

    async function init() {
        // Prevent multiple initializations
        if (isInitialized) {
            console.log('[Auto-Scavenger] Already initialized, skipping...');
            return;
        }
        
        const botConfig = await window.tribalsBot.init('autoScavenger');
        
        // Check if this is the designated tab
        if (!botConfig.isDesignatedTab) {
            console.log('[Auto-Scavenger] Not the designated tab, exiting...');
            return;
        }
        
        isInitialized = true;
        isDesignatedTab = true;
        config = botConfig.config;
        
        createPanel();
        
        // Add human-like delay before auto-starting (2-5 seconds)
        const startDelay = 2000 + Math.random() * 3000;
        console.log(`[Auto-Scavenger] Waiting ${Math.round(startDelay/1000)}s before starting...`);
        
        setTimeout(() => {
            // Check if should auto-start
            if (config.enabled && window.tribalsBot.isWithinActiveHours()) {
                toggle(true);
            }
        }, startDelay);
        
        // Listen for state changes
        window.addEventListener('tribalsbot:stateChanged', (e) => {
            const { enabled, isActive } = e.detail;
            if (enabled && isActive && !isRunning) {
                // Add delay when manually enabled too
                const delay = 1000 + Math.random() * 2000;
                console.log('[Auto-Scavenger] State changed to enabled, starting in', Math.round(delay/1000), 'seconds');
                setTimeout(() => {
                    if (!isRunning) { // Double check to prevent race conditions
                        toggle(true);
                    }
                }, delay);
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
        
        // Listen for debug reruns
        window.addEventListener('tribalsbot:debugRerun', (e) => {
            console.log('[Auto-Scavenger] Debug mode - rerunning script');
            if (isRunning) {
                runScavenger();
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
            <div style="background:#2ecc71;color:white;padding:2px 6px;border-radius:3px;font-size:10px;margin-bottom:5px;">Auto Scavenger Tab</div>
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
                
                // Schedule tab close and reopen after a short delay
                setTimeout(() => {
                    const jitter = Math.random() * config.intervalJitterSeconds;
                    const totalInterval = config.baseIntervalSeconds + jitter;
                    console.log(`[Auto-Scavenger] Run complete, closing tab. Next run in ${Math.round(totalInterval)} seconds`);
                    
                    // Notify background script to close tab and schedule reopening
                    chrome.runtime.sendMessage({
                        type: 'SCHEDULE_SCRIPT_REOPEN',
                        scriptName: 'autoScavenger',
                        delaySeconds: totalInterval
                    });
                }, 2000); // Wait 2 seconds to ensure the scavenge command is processed
            } else {
                console.warn('[Auto-Scavenger] sendGroup(0,false) button not found');
                // If button not found, still schedule next attempt
                scheduleNext();
            }
        }, firstDelay + secondOffset);
    }

    function runScavenger() {
        if (!isDesignatedTab || !window.tribalsBot.isWithinActiveHours()) {
            console.log('[Auto-Scavenger] Outside active hours or not designated tab, stopping...');
            if (isRunning) {
                toggle(false);
            }
            scheduleNextActiveCheck();
            return;
        }

        // Add random delay before loading script (1-3 seconds)
        const preLoadDelay = 1000 + Math.random() * 2000;
        console.log(`[Auto-Scavenger] Waiting ${Math.round(preLoadDelay/1000)}s before loading script...`);
        
        setTimeout(() => {
            loadExternalScript('massScavenge.js')
                .then(() => {
                    console.log(`[Auto-Scavenger] Script loaded at ${new Date().toLocaleTimeString()}`);
                    // Add another small delay before clicking (0.5-1.5 seconds)
                    const postLoadDelay = 500 + Math.random() * 1000;
                    setTimeout(() => {
                        clickSequence();
                    }, postLoadDelay);
                })
                .catch((e) => {
                    console.error('[Auto-Scavenger] Failed to load script:', e);
                    // On error, schedule retry
                    scheduleNext();
                });
        }, preLoadDelay);
    }

    function scheduleNext() {
        if (!isRunning || !isDesignatedTab) return;

        if (!window.tribalsBot.isWithinActiveHours()) {
            console.log('[Auto-Scavenger] Outside active hours, will resume when active');
            scheduleNextActiveCheck();
            return;
        }

        const jitter = Math.random() * config.intervalJitterSeconds;
        const interval = config.baseIntervalSeconds + jitter;
        console.log(`[Auto-Scavenger] Next run in ${Math.round(interval)} seconds, closing tab...`);
        
        // Notify background to close tab and reopen after interval
        chrome.runtime.sendMessage({
            type: 'SCHEDULE_SCRIPT_REOPEN',
            scriptName: 'autoScavenger',
            delaySeconds: interval
        });
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
        if (!isDesignatedTab) return;
        
        if (forceState !== null) {
            // Prevent toggling to same state
            if (isRunning === forceState) {
                console.log('[Auto-Scavenger] Already in requested state:', forceState);
                return;
            }
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