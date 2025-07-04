// content-base.js
// Base content script that handles communication between page scripts and background

// Create a communication bridge for the page scripts
window.tribalsBot = {
  config: null,
  isActive: false,
  scriptName: null,
  isDesignatedTab: false,
  
  // Initialize the bot for a specific script
  async init(scriptName) {
    this.scriptName = scriptName;
    
    // Request initial config from background
    const response = await chrome.runtime.sendMessage({
      type: 'GET_SCRIPT_CONFIG',
      scriptName: scriptName
    });
    
    this.config = response.config;
    this.isActive = response.globalActive;
    this.activeStartHour = response.activeStartHour;
    this.activeEndHour = response.activeEndHour;
    this.isDesignatedTab = response.isDesignatedTab;
    
    // If not the designated tab, don't initialize
    if (!this.isDesignatedTab) {
      console.log(`[${scriptName}] This is not the designated tab for this script. Script will not run.`);
      return {
        config: this.config,
        isActive: false,
        activeStartHour: this.activeStartHour,
        activeEndHour: this.activeEndHour,
        isDesignatedTab: false
      };
    }
    
    return {
      config: this.config,
      isActive: this.isActive,
      activeStartHour: this.activeStartHour,
      activeEndHour: this.activeEndHour,
      isDesignatedTab: true
    };
  },
  
  // Update script state
  async updateState(enabled) {
    if (!this.isDesignatedTab) return;
    
    await chrome.runtime.sendMessage({
      type: 'TOGGLE_SCRIPT',
      scriptName: this.scriptName,
      enabled: enabled
    });
  },
  
  // Update script config
  async updateConfig(configUpdate) {
    if (!this.isDesignatedTab) return;
    
    await chrome.runtime.sendMessage({
      type: 'UPDATE_SCRIPT_CONFIG',
      scriptName: this.scriptName,
      scriptConfig: configUpdate
    });
  },
  
  // Check if within active hours
  isWithinActiveHours() {
    const now = new Date();
    const currentHour = now.getHours();
    
    if (this.activeStartHour < this.activeEndHour) {
      return currentHour >= this.activeStartHour && currentHour < this.activeEndHour;
    } else {
      return currentHour >= this.activeStartHour || currentHour < this.activeEndHour;
    }
  },
  
  // Get time until active (in seconds)
  getTimeUntilActive() {
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    const currentSecond = now.getSeconds();
    
    if (this.isWithinActiveHours()) {
      return 0;
    }
    
    let hoursUntilStart = this.activeStartHour - currentHour;
    if (hoursUntilStart <= 0) {
      hoursUntilStart += 24;
    }
    
    const totalSeconds = (hoursUntilStart * 3600) - (currentMinute * 60) - currentSecond;
    return totalSeconds;
  }
};

// Listen for messages from background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Only process messages if we're the designated tab
  if (!window.tribalsBot.isDesignatedTab && request.type !== 'SCRIPT_STATE_CHANGED') {
    return;
  }
  
  switch (request.type) {
    case 'SCRIPT_STATE_CHANGED':
      // Notify the page script if it's for this script
      if (window.tribalsBot.scriptName === request.scriptName) {
        window.dispatchEvent(new CustomEvent('tribalsbot:stateChanged', {
          detail: {
            enabled: request.enabled,
            isActive: request.isActive
          }
        }));
      }
      break;
      
    case 'CONFIG_UPDATED':
      // Update local config if it's for this script
      if (window.tribalsBot.scriptName === request.scriptName) {
        window.tribalsBot.config = request.config;
        window.dispatchEvent(new CustomEvent('tribalsbot:configUpdated', {
          detail: { config: request.config }
        }));
      }
      break;
      
    case 'ACTIVE_STATUS_UPDATE':
      // Update active status
      window.tribalsBot.isActive = request.isActive;
      window.dispatchEvent(new CustomEvent('tribalsbot:activeStatusUpdate', {
        detail: {
          isActive: request.isActive,
          timeUntilActive: request.timeUntilActive
        }
      }));
      break;
      
    case 'GLOBAL_CONFIG_UPDATED':
      // Update global config
      window.tribalsBot.isActive = request.isActive;
      window.tribalsBot.activeStartHour = request.config.activeStartHour;
      window.tribalsBot.activeEndHour = request.config.activeEndHour;
      
      if (window.tribalsBot.scriptName && request.config.scripts[window.tribalsBot.scriptName]) {
        window.tribalsBot.config = request.config.scripts[window.tribalsBot.scriptName];
      }
      
      window.dispatchEvent(new CustomEvent('tribalsbot:globalConfigUpdated', {
        detail: {
          config: request.config,
          isActive: request.isActive
        }
      }));
      break;
  }
});