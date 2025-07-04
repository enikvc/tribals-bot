// background.js
// Centralized scheduling and state management for all automation scripts

const DEFAULT_CONFIG = {
  activeStartHour: 8,  // 8:00 AM
  activeEndHour: 3,    // 3:00 AM (next day)
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
      iconClickInterval: 527
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

let config = { ...DEFAULT_CONFIG };
let activeTabStates = new Map(); // Track state per tab

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

// Check if current time is within allowed hours
function isWithinActiveHours() {
  const now = new Date();
  const currentHour = now.getHours();
  
  // Active from startHour to endHour (can cross midnight)
  if (config.activeStartHour < config.activeEndHour) {
    return currentHour >= config.activeStartHour && currentHour < config.activeEndHour;
  } else {
    // Crosses midnight (e.g., 8 AM to 3 AM)
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
  
  // Calculate hours until start time
  let hoursUntilStart = config.activeStartHour - currentHour;
  if (hoursUntilStart <= 0) {
    hoursUntilStart += 24;
  }
  
  const totalSeconds = (hoursUntilStart * 3600) - (currentMinute * 60) - currentSecond;
  return totalSeconds;
}

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
      config.scripts[scriptName].enabled = enabled;
      saveConfig();
      
      // Notify the relevant tab
      if (sender.tab) {
        chrome.tabs.sendMessage(sender.tab.id, {
          type: 'SCRIPT_STATE_CHANGED',
          scriptName,
          enabled,
          isActive: isWithinActiveHours()
        });
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
      const scriptConfig = config.scripts[request.scriptName];
      sendResponse({ 
        config: scriptConfig,
        globalActive: isWithinActiveHours(),
        activeStartHour: config.activeStartHour,
        activeEndHour: config.activeEndHour
      });
      break;
      
    case 'UPDATE_SCRIPT_CONFIG':
      config.scripts[request.scriptName] = {
        ...config.scripts[request.scriptName],
        ...request.scriptConfig
      };
      saveConfig();
      
      // Notify the content script
      if (sender.tab) {
        chrome.tabs.sendMessage(sender.tab.id, {
          type: 'CONFIG_UPDATED',
          scriptName: request.scriptName,
          config: config.scripts[request.scriptName]
        });
      }
      
      sendResponse({ success: true });
      break;
  }
  
  return true; // Keep message channel open for async responses
});

// Broadcast config updates to all tabs
function broadcastConfigUpdate() {
  chrome.tabs.query({}, (tabs) => {
    tabs.forEach(tab => {
      if (tab.url && tab.url.includes('tribals.it')) {
        chrome.tabs.sendMessage(tab.id, {
          type: 'GLOBAL_CONFIG_UPDATED',
          config,
          isActive: isWithinActiveHours()
        }).catch(() => {
          // Tab might not have content script loaded
        });
      }
    });
  });
}

// Check active status periodically and notify tabs
setInterval(() => {
  const isActive = isWithinActiveHours();
  
  chrome.tabs.query({ url: '*://*.tribals.it/*' }, (tabs) => {
    tabs.forEach(tab => {
      chrome.tabs.sendMessage(tab.id, {
        type: 'ACTIVE_STATUS_UPDATE',
        isActive,
        timeUntilActive: getTimeUntilActive()
      }).catch(() => {
        // Tab might not have content script loaded
      });
    });
  });
}, 60000); // Check every minute

// Handle extension icon click to open management popup
chrome.action.onClicked.addListener((tab) => {
  chrome.action.openPopup();
});