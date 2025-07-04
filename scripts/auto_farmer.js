// scripts/auto_farmer.js
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
            console.log('[Auto-Farmer] Already initialized, skipping...');
            return;
        }
        
        const botConfig = await window.tribalsBot.init('autoFarmer');
        
        // Check if this is the designated tab
        if (!botConfig.isDesignatedTab) {
            console.log('[Auto-Farmer] Not the designated tab, exiting...');
            return;
        }
        
        isInitialized = true;
        isDesignatedTab = true;
        config = botConfig.config;
        
        initPanel();
        
        // Add human-like delay before auto-starting (2-5 seconds)
        const startDelay = 2000 + Math.random() * 3000;
        console.log(`[Auto-Farmer] Waiting ${Math.round(startDelay/1000)}s before starting...`);
        
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
                console.log('[Auto-Farmer] State changed to enabled, starting in', Math.round(delay/1000), 'seconds');
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
            console.log('[Auto-Farmer] Config updated');
            updateInfoDisplay();
        });
        
        // Listen for active status updates
        window.addEventListener('tribalsbot:activeStatusUpdate', (e) => {
            const { isActive } = e.detail;
            updateTimeStatus();
            
            if (config.enabled) {
                if (isActive && !isRunning) {
                    console.log('[Auto-Farmer] Active hours started, resuming');
                    toggle(true);
                } else if (!isActive && isRunning) {
                    console.log('[Auto-Farmer] Active hours ended, pausing');
                    toggle(false);
                    scheduleNextActiveCheck();
                }
            }
        });
        
        // Listen for debug reruns
        window.addEventListener('tribalsbot:debugRerun', (e) => {
            console.log('[Auto-Farmer] Debug mode - rerunning script');
            if (isRunning) {
                runFarming();
            }
        });
    }

    function loadExternalScript(src) {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            if (src.includes('farmgod.js')) {
                s.src = chrome.runtime.getURL('vendor/farmgod.js');
            } else {
                s.src = src;
            }
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    function initPanel() {
        const panel = document.createElement('div');
        Object.assign(panel.style, {
            position: 'fixed', bottom: '120px', right: '20px',
            padding: '10px', background: 'rgba(0,0,0,0.7)', color: '#fff',
            borderRadius: '5px', zIndex: 10000, fontFamily: 'sans-serif', textAlign: 'center'
        });
        
        panel.innerHTML = `
            <div style="margin-bottom:8px; font-weight:bold;">Auto Farmer</div>
            <div style="background:#3498db;color:white;padding:2px 6px;border-radius:3px;font-size:10px;margin-bottom:5px;">Managed by Tribals Bot</div>
            <div style="background:#2ecc71;color:white;padding:2px 6px;border-radius:3px;font-size:10px;margin-bottom:5px;">Auto Farmer Tab</div>
            <div id="timeStatus" style="margin-bottom:8px; font-size:12px;"></div>
            <div id="farmerInfo" style="font-size:11px;color:#aaa;margin-bottom:8px;"></div>
        `;
        
        document.body.appendChild(panel);
        
        updateTimeStatus();
        updateInfoDisplay();
        setInterval(updateTimeStatus, 60000);
    }

    function updateInfoDisplay() {
        const info = document.getElementById('farmerInfo');
        if (info) {
            info.innerHTML = `Interval: ${config.intervalSeconds}s<br>Status: ${config.enabled ? 'Enabled' : 'Disabled'}`;
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

    function runFarming() {
        if (!isDesignatedTab || !window.tribalsBot.isWithinActiveHours()) {
            console.log('[Auto-Farmer] Outside active hours or not designated tab, stopping...');
            if (isRunning) {
                toggle(false);
            }
            scheduleNextActiveCheck();
            return;
        }

        // Add random delay before loading script (1-3 seconds)
        const preLoadDelay = 1000 + Math.random() * 2000;
        console.log(`[Auto-Farmer] Waiting ${Math.round(preLoadDelay/1000)}s before loading script...`);
        
        setTimeout(() => {
            loadExternalScript('farmgod.js')
                .then(() => {
                    console.log(`[Auto-Farmer] Script loaded at ${new Date().toLocaleTimeString()}`);
                    setTimeout(() => {
                        const planBtn = document.querySelector('input.btn.optionButton[value="Plan farms"]');
                        if (planBtn) {
                            planBtn.click();
                            console.log('[Auto-Farmer] Clicked Plan farms');
                            // Wait longer and retry finding icons
                            waitForIcons();
                        } else {
                            console.warn('[Auto-Farmer] "Plan farms" button not found');
                            scheduleNext();
                        }
                    }, config.planDelay);
                })
                .catch((e) => {
                    console.error('[Auto-Farmer] Failed to load script:', e);
                    scheduleNext();
                });
        }, preLoadDelay);
    }

    function waitForIcons(attempts = 0) {
        const maxAttempts = 10;
        const retryDelay = 500;
        
        if (attempts >= maxAttempts) {
            console.warn('[Auto-Farmer] Max attempts reached, no icons found');
            scheduleNext();
            return;
        }
        
        setTimeout(() => {
            const icons = findFarmIcons();
            
            if (icons.length > 0) {
                console.log(`[Auto-Farmer] Found ${icons.length} farm icons after ${attempts + 1} attempts`);
                clickIconsInModal(icons);
            } else {
                console.log(`[Auto-Farmer] Attempt ${attempts + 1}/${maxAttempts}: No icons yet, retrying...`);
                waitForIcons(attempts + 1);
            }
        }, attempts === 0 ? config.iconStartDelay : retryDelay);
    }

    function findFarmIcons() {
        // Only look for icons inside the farmGodContent div
        const farmGodContainer = document.querySelector('div.farmGodContent');
        
        if (!farmGodContainer) {
            console.log('[Auto-Farmer] FarmGod container not found');
            return [];
        }
        
        // Look specifically for farmGod icons with the data attributes
        const icons = farmGodContainer.querySelectorAll('a.farmGod_icon.farm_icon.farm_icon_a[data-origin][data-target][data-template]');
        
        if (icons.length === 0) {
            // Try alternative selector if the first one doesn't work
            const altIcons = farmGodContainer.querySelectorAll('td a.farm_icon_a');
            return altIcons;
        }
        
        return icons;
    }

    function clickIconsInModal(icons) {
        if (!icons || icons.length === 0) {
            console.warn('[Auto-Farmer] No farm icons to click');
            scheduleNext();
            return;
        }
        
        // Calculate safe interval to avoid rate limit (5 attacks per second max)
        // Using 250ms minimum interval = 4 attacks per second to be safe
        const safeInterval = Math.max(config.iconClickInterval, 250);
        
        console.log(`[Auto-Farmer] Clicking ${icons.length} icons with ${safeInterval}ms interval`);
        
        icons.forEach((icon, idx) => {
            setTimeout(() => {
                icon.click();
                console.log(`[Auto-Farmer] Clicked farm icon #${idx+1} at ${new Date().toLocaleTimeString()}`);
                if (idx === icons.length - 1) {
                    // Add a small delay after last click before closing tab
                    setTimeout(() => {
                        console.log('[Auto-Farmer] Run complete, closing tab...');
                        // Notify background script to close tab and schedule reopening
                        chrome.runtime.sendMessage({
                            type: 'SCHEDULE_SCRIPT_REOPEN',
                            scriptName: 'autoFarmer',
                            delaySeconds: config.intervalSeconds
                        });
                    }, 1000);
                }
            }, safeInterval * idx);
        });
    }

    function scheduleNext() {
        if (!isRunning || !isDesignatedTab) return;

        if (!window.tribalsBot.isWithinActiveHours()) {
            console.log('[Auto-Farmer] Outside active hours, will resume when active');
            scheduleNextActiveCheck();
            return;
        }

        console.log(`[Auto-Farmer] Next run in ${config.intervalSeconds} seconds, closing tab...`);
        
        // Notify background to close tab and reopen after interval
        chrome.runtime.sendMessage({
            type: 'SCHEDULE_SCRIPT_REOPEN',
            scriptName: 'autoFarmer',
            delaySeconds: config.intervalSeconds
        });
    }

    function scheduleNextActiveCheck() {
        const secondsUntil = window.tribalsBot.getTimeUntilActive();
        if (secondsUntil > 0) {
            console.log(`[Auto-Farmer] Will check again in ${Math.floor(secondsUntil/60)} minutes`);
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
                console.log('[Auto-Farmer] Already in requested state:', forceState);
                return;
            }
            isRunning = forceState;
        } else {
            isRunning = !isRunning;
        }
        
        if (isRunning) {
            console.log('[Auto-Farmer] Started');
            if (window.tribalsBot.isWithinActiveHours()) {
                runFarming();
            } else {
                scheduleNextActiveCheck();
            }
        } else {
            console.log('[Auto-Farmer] Stopped');
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