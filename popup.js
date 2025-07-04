// popup.js
// Handle the management UI for the Tribals Bot extension

let currentConfig = null;

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  // Populate hour selects
  populateHourSelects();
  
  // Load current config
  const response = await chrome.runtime.sendMessage({ type: 'GET_CONFIG' });
  currentConfig = response.config;
  
  // Set initial values
  updateUI(response);
  
  // Update time every second
  updateTime();
  setInterval(updateTime, 1000);
  
  // Setup event listeners
  setupEventListeners();
});

function populateHourSelects() {
  const startSelect = document.getElementById('startHour');
  const endSelect = document.getElementById('endHour');
  
  for (let i = 0; i < 24; i++) {
    const hour = i.toString().padStart(2, '0') + ':00';
    startSelect.innerHTML += `<option value="${i}">${hour}</option>`;
    endSelect.innerHTML += `<option value="${i}">${hour}</option>`;
  }
}

function updateUI(response) {
  const { config, isActive } = response;
  
  // Update status
  const statusDot = document.getElementById('statusDot');
  const statusText = document.getElementById('statusText');
  
  if (isActive) {
    statusDot.classList.add('active');
    statusText.textContent = 'Active';
    document.getElementById('nextActive').textContent = '';
  } else {
    statusDot.classList.remove('active');
    statusText.textContent = 'Inactive';
    updateNextActiveTime();
  }
  
  // Update hour selects
  document.getElementById('startHour').value = config.activeStartHour;
  document.getElementById('endHour').value = config.activeEndHour;
  
  // Update script toggles
  document.getElementById('autoBuyerToggle').checked = config.scripts.autoBuyer.enabled;
  document.getElementById('autoFarmerToggle').checked = config.scripts.autoFarmer.enabled;
  document.getElementById('autoScavengerToggle').checked = config.scripts.autoScavenger.enabled;
  
  // Update script settings
  updateScriptSettings('autoBuyer', config.scripts.autoBuyer);
  updateScriptSettings('autoFarmer', config.scripts.autoFarmer);
  updateScriptSettings('autoScavenger', config.scripts.autoScavenger);
}

function updateScriptSettings(scriptName, settings) {
  switch (scriptName) {
    case 'autoBuyer':
      document.getElementById('minPP').value = settings.minPP;
      document.getElementById('minStock').value = settings.minStock;
      document.getElementById('postBuyDelay').value = settings.postBuyDelay;
      break;
    case 'autoFarmer':
      document.getElementById('intervalSeconds').value = settings.intervalSeconds;
      document.getElementById('planDelay').value = settings.planDelay;
      document.getElementById('iconStartDelay').value = settings.iconStartDelay;
      document.getElementById('iconClickInterval').value = settings.iconClickInterval;
      break;
    case 'autoScavenger':
      document.getElementById('baseIntervalSeconds').value = settings.baseIntervalSeconds;
      document.getElementById('intervalJitterSeconds').value = settings.intervalJitterSeconds;
      document.getElementById('clickMinDelay').value = settings.clickMinDelay;
      document.getElementById('clickMaxDelay').value = settings.clickMaxDelay;
      break;
  }
}

function updateTime() {
  const now = new Date();
  document.getElementById('currentTime').textContent = now.toLocaleTimeString();
}

async function updateNextActiveTime() {
  const response = await chrome.runtime.sendMessage({ type: 'CHECK_ACTIVE_STATUS' });
  const { timeUntilActive } = response;
  
  if (timeUntilActive > 0) {
    const hours = Math.floor(timeUntilActive / 3600);
    const minutes = Math.floor((timeUntilActive % 3600) / 60);
    document.getElementById('nextActive').textContent = `Active in ${hours}h ${minutes}m`;
  }
}

function setupEventListeners() {
  // Hour save button
  document.getElementById('saveHours').addEventListener('click', async () => {
    const startHour = parseInt(document.getElementById('startHour').value);
    const endHour = parseInt(document.getElementById('endHour').value);
    
    await chrome.runtime.sendMessage({
      type: 'UPDATE_CONFIG',
      config: {
        activeStartHour: startHour,
        activeEndHour: endHour
      }
    });
    
    // Refresh UI
    const response = await chrome.runtime.sendMessage({ type: 'GET_CONFIG' });
    updateUI(response);
  });
  
  // Script toggles
  document.getElementById('autoBuyerToggle').addEventListener('change', async (e) => {
    await chrome.runtime.sendMessage({
      type: 'TOGGLE_SCRIPT',
      scriptName: 'autoBuyer',
      enabled: e.target.checked
    });
  });
  
  document.getElementById('autoFarmerToggle').addEventListener('change', async (e) => {
    await chrome.runtime.sendMessage({
      type: 'TOGGLE_SCRIPT',
      scriptName: 'autoFarmer',
      enabled: e.target.checked
    });
  });
  
  document.getElementById('autoScavengerToggle').addEventListener('change', async (e) => {
    await chrome.runtime.sendMessage({
      type: 'TOGGLE_SCRIPT',
      scriptName: 'autoScavenger',
      enabled: e.target.checked
    });
  });
  
  // Expand buttons
  document.querySelectorAll('.expand-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const scriptName = e.target.dataset.script;
      const settings = document.getElementById(`${scriptName}Settings`);
      settings.classList.toggle('visible');
      e.target.textContent = settings.classList.contains('visible') ? 'Settings ▲' : 'Settings ▼';
    });
  });
  
  // Save settings buttons
  document.querySelectorAll('.save-btn[data-script]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const scriptName = e.target.dataset.script;
      const settings = getScriptSettings(scriptName);
      
      await chrome.runtime.sendMessage({
        type: 'UPDATE_SCRIPT_CONFIG',
        scriptName: scriptName,
        scriptConfig: settings
      });
      
      // Show feedback
      e.target.textContent = 'Saved!';
      setTimeout(() => {
        e.target.textContent = 'Save Settings';
      }, 1500);
    });
  });
}

function getScriptSettings(scriptName) {
  switch (scriptName) {
    case 'autoBuyer':
      return {
        minPP: parseInt(document.getElementById('minPP').value),
        minStock: parseInt(document.getElementById('minStock').value),
        postBuyDelay: parseInt(document.getElementById('postBuyDelay').value)
      };
    case 'autoFarmer':
      return {
        intervalSeconds: parseInt(document.getElementById('intervalSeconds').value),
        planDelay: parseInt(document.getElementById('planDelay').value),
        iconStartDelay: parseInt(document.getElementById('iconStartDelay').value),
        iconClickInterval: parseInt(document.getElementById('iconClickInterval').value)
      };
    case 'autoScavenger':
      return {
        baseIntervalSeconds: parseInt(document.getElementById('baseIntervalSeconds').value),
        intervalJitterSeconds: parseInt(document.getElementById('intervalJitterSeconds').value),
        clickMinDelay: parseInt(document.getElementById('clickMinDelay').value),
        clickMaxDelay: parseInt(document.getElementById('clickMaxDelay').value)
      };
  }
}