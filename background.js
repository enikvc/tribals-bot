// background.js
// Centralized scheduling and state management for all automation scripts

const DEFAULT_CONFIG = {
  activeStartHour: 8,  // 8:00 AM
  activeEndHour: 3,    // 3:00 AM (next day)
  debugMode: false,    // Debug mode - keeps tabs open
  scripts: {
    autoBuyer: {
      enabled: false,
      minPP: 3000,
      minStock: 64,
      postBuyDelay: 4800
    },
    autoFarmer: {
      enabled: false,
      intervalSeconds: 600,
      planDelay: 700,
      iconStartDelay: 1000,
      iconClickInterval: 300  // 300ms = ~3.3 attacks per second (safe margin)
    },
    autoScavenger: {
      enabled: false,
      baseIntervalSeconds: 600,
      intervalJitterSeconds: 60,
      clickMinDelay: 200,
      clickMaxDelay: 800,
      secondClickMin: 300,
      secondClickMax: 1000
    }
  }
};

// Script URL patterns
const SCRIPT_URLS = {
  autoFarmer: {
    pattern: /https:\/\/it\d+\.tribals\.it\/game\.php\?.*screen=am_farm/,
    createUrl: (server) => `https://${server}.tribals.it/game.php?village=300&screen=am_farm#`
  },
  autoScavenger: {
    pattern: /https:\/\/it\d+\.tribals\.it\/game\.php\?.*screen=place&mode=scavenge_mass/,
    createUrl: (server) => `https://${server}.tribals.it/game.php?village=300&screen=place&mode=scavenge_mass`
  },
  autoBuyer: {
    pattern: /https:\/\/it\d+\.tribals\.it\/game\.php\?.*screen=market&mode=exchange/,
    createUrl: (server) => `https://${server}.tribals.it/game.php?village=300&screen=market&mode=exchange`
  }
};

let config = { ...DEFAULT_CONFIG };
let scriptTabs = new Map(); // Map scriptName -> tabId
let tabScripts = new Map(); // Map tabId -> scriptName
let reopenTimeouts = new Map(); // Map scriptName -> timeoutId

// Load saved config on startup
chrome.storage.local.get('config', (result) => {
  if (result.config) {
    config = { ...DEFAULT_CONFIG, ...result.config };
  }
});

// Save config whenever it changes
function saveConfig() {
  chrome.storage.local.set({ config });
}

// Extract server from URL (e.g., "it94" from "https://it94.tribals.it/...")
function getServerFromUrl(url) {
  const match = url.match(/https:\/\/(it\d+)\.tribals\.it/);
  return match ? match[1] : null;
}

// Check if current time is within allowed hours
function isWithinActiveHours() {
  const now = new Date();
  const currentHour = now.getHours();
  
  if (config.activeStartHour < config.activeEndHour) {
    return currentHour >= config.activeStartHour && currentHour < config.activeEndHour;
  } else {
    return currentHour >= config.activeStartHour || currentHour < config.activeEndHour;
  }
}

// Get time until next active period in seconds
function getTimeUntilActive() {
  const now = new Date();
  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();
  const currentSecond = now.getSeconds();
  
  if (isWithinActiveHours()) {
    return 0;
  }
  
  let hoursUntilStart = config.activeStartHour - currentHour;
  if (hoursUntilStart <= 0) {
    hoursUntilStart += 24;
  }
  
  const totalSeconds = (hoursUntilStart * 3600) - (currentMinute * 60) - currentSecond;
  return totalSeconds;
}

// Open or focus tab for a script
async function openScriptTab(scriptName) {
  // Check if tab already exists
  const existingTabId = scriptTabs.get(scriptName);
  
  if (existingTabId) {
    try {
      // Just verify the tab exists, don't focus it
      await chrome.tabs.get(existingTabId);
      return existingTabId;
    } catch (e) {
      // Tab was closed, remove from maps
      scriptTabs.delete(scriptName);
      tabScripts.delete(existingTabId);
    }
  }
  
  // Need to create new tab
  // First, find an existing tribals tab to get the server
  const tabs = await chrome.tabs.query({ url: "*://*.tribals.it/*" });
  let server = "it94"; // Default server
  
  if (tabs.length > 0) {
    const foundServer = getServerFromUrl(tabs[0].url);
    if (foundServer) {
      server = foundServer;
    }
  }
  
  // Create the URL for the script
  const url = SCRIPT_URLS[scriptName].createUrl(server);
  
  // Create new tab in background (active: false)
  const tab = await chrome.tabs.create({ url, active: false });
  
  // Store tab mapping
  scriptTabs.set(scriptName, tab.id);
  tabScripts.set(tab.id, scriptName);
  
  return tab.id;
}

// Close tab for a script
async function closeScriptTab(scriptName) {
  const tabId = scriptTabs.get(scriptName);
  if (tabId) {
    try {
      await chrome.tabs.remove(tabId);
    } catch (e) {
      // Tab already closed
    }
    scriptTabs.delete(scriptName);
    tabScripts.delete(tabId);
  }
}

// Clean up when tab is closed
chrome.tabs.onRemoved.addListener((tabId) => {
  const scriptName = tabScripts.get(tabId);
  if (scriptName) {
    scriptTabs.delete(scriptName);
    tabScripts.delete(tabId);
    
    // Don't update state if it was a scheduled close
    if (!reopenTimeouts.has(scriptName)) {
      // Manual close - update script state
      config.scripts[scriptName].enabled = false;
      saveConfig();
      
      // Notify popup if open
      chrome.runtime.sendMessage({
        type: 'SCRIPT_TAB_CLOSED',
        scriptName
      }).catch(() => {});
    }
  }
});

// Message handler for communication with content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.type) {
    case 'GET_CONFIG':
      sendResponse({ config, isActive: isWithinActiveHours() });
      break;
      
    case 'UPDATE_CONFIG':
      config = { ...config, ...request.config };
      saveConfig();
      broadcastConfigUpdate();
      sendResponse({ success: true });
      break;
      
    case 'TOGGLE_SCRIPT':
      const { scriptName, enabled } = request;
      
      // Clear any pending reopen if disabling
      if (!enabled && reopenTimeouts.has(scriptName)) {
        clearTimeout(reopenTimeouts.get(scriptName));
        reopenTimeouts.delete(scriptName);
      }
      
      if (enabled) {
        // Open tab for the script
        openScriptTab(scriptName).then(tabId => {
          config.scripts[scriptName].enabled = true;
          saveConfig();
          
          // Wait for tab to load, then notify only once
          setTimeout(() => {
            // Check if tab still exists before sending message
            chrome.tabs.get(tabId, (tab) => {
              if (chrome.runtime.lastError) {
                console.log(`[Background] Tab ${tabId} no longer exists`);
                return;
              }
              
              chrome.tabs.sendMessage(tabId, {
                type: 'SCRIPT_STATE_CHANGED',
                scriptName,
                enabled: true,
                isActive: isWithinActiveHours()
              }).catch(() => {
                console.log(`[Background] Failed to send message to tab ${tabId}`);
              });
            });
          }, 3000); // Increased delay to ensure page is fully loaded
        });
      } else {
        // Disable script and close tab
        config.scripts[scriptName].enabled = false;
        saveConfig();
        closeScriptTab(scriptName);
      }
      
      sendResponse({ success: true });
      break;
      
    case 'SCHEDULE_SCRIPT_REOPEN':
      // Handle scheduled tab close and reopen
      const tabId = scriptTabs.get(request.scriptName);
      if (tabId) {
        // Check if debug mode is enabled
        if (config.debugMode) {
          console.log(`[Background] Debug mode ON - keeping ${request.scriptName} tab open`);
          // Schedule rerun without closing tab
          setTimeout(() => {
            if (config.scripts[request.scriptName].enabled && isWithinActiveHours()) {
              console.log(`[Background] Debug mode - triggering ${request.scriptName} rerun`);
              chrome.tabs.sendMessage(tabId, {
                type: 'DEBUG_RERUN_SCRIPT',
                scriptName: request.scriptName
              }).catch(() => {});
            }
          }, request.delaySeconds * 1000);
        } else {
          // Normal mode - close and reopen
          // Clear any existing timeout
          if (reopenTimeouts.has(request.scriptName)) {
            clearTimeout(reopenTimeouts.get(request.scriptName));
          }
          
          // Schedule reopening
          const timeoutId = setTimeout(() => {
            reopenTimeouts.delete(request.scriptName);
            if (config.scripts[request.scriptName].enabled && isWithinActiveHours()) {
              console.log(`[Background] Reopening ${request.scriptName} tab after ${request.delaySeconds}s delay`);
              openScriptTab(request.scriptName);
            }
          }, request.delaySeconds * 1000);
          
          reopenTimeouts.set(request.scriptName, timeoutId);
          
          // Close the tab
          chrome.tabs.remove(tabId).catch(() => {});
        }
      }
      sendResponse({ success: true });
      break;
      
    case 'CHECK_ACTIVE_STATUS':
      sendResponse({ 
        isActive: isWithinActiveHours(),
        timeUntilActive: getTimeUntilActive()
      });
      break;
      
    case 'GET_SCRIPT_CONFIG':
      // Check if this tab is the designated tab for the script
      const scriptForTab = tabScripts.get(sender.tab.id);
      
      if (scriptForTab === request.scriptName) {
        const scriptConfig = config.scripts[request.scriptName];
        sendResponse({ 
          config: scriptConfig,
          globalActive: isWithinActiveHours(),
          activeStartHour: config.activeStartHour,
          activeEndHour: config.activeEndHour,
          isDesignatedTab: true
        });
      } else {
        // Not the designated tab for this script
        sendResponse({ 
          config: config.scripts[request.scriptName],
          globalActive: isWithinActiveHours(),
          activeStartHour: config.activeStartHour,
          activeEndHour: config.activeEndHour,
          isDesignatedTab: false
        });
      }
      break;
      
    case 'UPDATE_SCRIPT_CONFIG':
      config.scripts[request.scriptName] = {
        ...config.scripts[request.scriptName],
        ...request.scriptConfig
      };
      saveConfig();
      
      // Notify the designated tab for this script
      const designatedTabId = scriptTabs.get(request.scriptName);
      if (designatedTabId) {
        chrome.tabs.sendMessage(designatedTabId, {
          type: 'CONFIG_UPDATED',
          scriptName: request.scriptName,
          config: config.scripts[request.scriptName]
        }).catch(() => {});
      }
      
      sendResponse({ success: true });
      break;
  }
  
  return true; // Keep message channel open for async responses
});

// Broadcast config updates to designated tabs only
function broadcastConfigUpdate() {
  scriptTabs.forEach((tabId, scriptName) => {
    chrome.tabs.sendMessage(tabId, {
      type: 'GLOBAL_CONFIG_UPDATED',
      config,
      isActive: isWithinActiveHours()
    }).catch(() => {
      // Tab might not have content script loaded
    });
  });
}

// Check active status periodically and notify tabs
setInterval(() => {
  const isActive = isWithinActiveHours();
  
  scriptTabs.forEach((tabId, scriptName) => {
    chrome.tabs.sendMessage(tabId, {
      type: 'ACTIVE_STATUS_UPDATE',
      isActive,
      timeUntilActive: getTimeUntilActive()
    }).catch(() => {});
  });
}, 60000); // Check every minute

// Handle extension icon click to open management popup
chrome.action.onClicked.addListener((tab) => {
  chrome.action.openPopup();
});