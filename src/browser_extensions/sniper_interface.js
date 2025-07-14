/**
 * Tribal Wars Sniper Interface
 * Injects sniper controls into attack confirmation pages
 */

(function() {
    'use strict';
    
    // Configuration - will be dynamically updated
    let SNIPER_SERVICE_URL = 'http://127.0.0.1:9001';
    const DASHBOARD_URL = 'http://127.0.0.1:8080';
    
    // Check if we're on the attack confirmation page
    if (!window.location.href.includes('screen=place&try=confirm')) {
        console.log('🚫 Not on attack confirmation page:', window.location.href);
        return;
    }
    
    console.log('🎯 Tribals Sniper Interface - Initializing on confirmation page');
    
    // Main sniper interface class
    class TribalsSniperInterface {
        constructor() {
            this.attackData = null;
            this.sniperServiceOnline = false;
            this.init();
        }
        
        async init() {
            // Extract attack data from page
            this.extractAttackData();
            
            // Check sniper service status
            await this.checkSniperService();
            
            // Inject sniper UI
            this.injectSniperUI();
            
            // Setup event handlers
            this.setupEventHandlers();
            
            // Setup debugging
            this.debugExtractedData();
            
            console.log('✅ Sniper interface initialized', this.attackData);
        }
        
        extractAttackData() {
            try {
                console.log('🔍 Starting attack data extraction...');
                console.log('📄 Page analysis:', {
                    currentURL: window.location.href,
                    pageTitle: document.title,
                    allForms: Array.from(document.querySelectorAll('form')).map(f => ({
                        id: f.id,
                        action: f.action,
                        method: f.method,
                        inputCount: f.querySelectorAll('input').length
                    }))
                });
                
                // Extract data from the form and page elements
                let form = document.getElementById('command-data-form');
                if (!form) {
                    console.error('❌ command-data-form not found');
                    // Try alternative form selectors
                    form = document.querySelector('form[action*="place"]') || 
                           document.querySelector('form[action*="confirm"]') ||
                           document.querySelector('form');
                    
                    if (form) {
                        console.log('✅ Found alternative form:', {
                            id: form.id,
                            action: form.action,
                            method: form.method,
                            inputCount: form.querySelectorAll('input').length
                        });
                    } else {
                        console.error('❌ No forms found on page at all');
                        throw new Error('No attack forms found on page');
                    }
                } else {
                    console.log('✅ Found command-data-form');
                }
                
                // Get target coordinates from URL or form
                const urlParams = new URLSearchParams(window.location.search);
                const xInput = form?.querySelector('input[name="x"]');
                const yInput = form?.querySelector('input[name="y"]');
                const x = xInput?.value || urlParams.get('x');
                const y = yInput?.value || urlParams.get('y');
                
                console.log('🎯 Coordinate extraction:', {
                    xInput: xInput ? 'found' : 'missing',
                    yInput: yInput ? 'found' : 'missing',
                    xValue: x,
                    yValue: y,
                    urlParams: Object.fromEntries(urlParams.entries())
                });
                
                // Get source village ID
                const sourceVillageInput = form?.querySelector('input[name="source_village"]');
                const villageInput = form?.querySelector('input[name="village"]');
                const sourceVillage = sourceVillageInput?.value || villageInput?.value;
                
                console.log('🏘️ Village ID extraction:', {
                    sourceVillageInput: sourceVillageInput ? 'found' : 'missing',
                    villageInput: villageInput ? 'found' : 'missing',
                    sourceVillageValue: sourceVillage,
                    currentURL: window.location.href
                });
                
                // Get units being sent
                const units = {};
                const unitInputs = form?.querySelectorAll('input[type="hidden"][name]') || [];
                
                console.log('⚔️ Unit extraction:', {
                    totalHiddenInputs: unitInputs.length,
                    allInputNames: Array.from(unitInputs).map(i => ({ name: i.name, value: i.value }))
                });
                
                for (const input of unitInputs) {
                    const unitName = input.name;
                    const unitCount = parseInt(input.value) || 0;
                    
                    // Only include actual unit types
                    if (['spear', 'sword', 'axe', 'spy', 'light', 'heavy', 'ram', 'catapult', 'knight', 'snob'].includes(unitName)) {
                        if (unitCount > 0) {
                            units[unitName] = unitCount;
                        }
                    }
                }
                
                console.log('⚔️ Final units extracted:', units);
                
                // Get CSRF token
                const csrfInput = form?.querySelector('input[name="h"]');
                const chInput = form?.querySelector('input[name="ch"]');
                const csrfToken = csrfInput?.value || chInput?.value;
                
                console.log('🔐 CSRF token extraction:', {
                    csrfInput: csrfInput ? 'found' : 'missing',
                    chInput: chInput ? 'found' : 'missing',
                    csrfToken: csrfToken ? '***PRESENT***' : 'MISSING',
                    allFormInputs: form ? Array.from(form.querySelectorAll('input')).map(i => ({ 
                        name: i.name, 
                        type: i.type, 
                        value: i.name === 'h' || i.name === 'ch' ? '***TOKEN***' : i.value 
                    })) : 'NO_FORM'
                });
                
                // Calculate target village ID from coordinates (if not directly available)
                let targetVillageId = null;
                const villageLink = document.querySelector('a[href*="screen=info_village&id="]');
                if (villageLink) {
                    const match = villageLink.href.match(/id=(\d+)/);
                    if (match) {
                        targetVillageId = parseInt(match[1]);
                    }
                }
                
                // Get arrival time and travel duration
                const arrivalElement = document.querySelector('#date_arrival .relative_time');
                let arrivalTime = null;
                let travelDuration = null;
                
                if (arrivalElement && arrivalElement.dataset.duration) {
                    const duration = parseInt(arrivalElement.dataset.duration);
                    arrivalTime = new Date(Date.now() + (duration * 1000));
                }
                
                // Get travel duration from the page - comprehensive search
                let durationElement = null;
                let travelDurationText = null;
                
                // Method 1: Look for standard table patterns
                durationElement = Array.from(document.querySelectorAll('tr td')).find(td => 
                    td.textContent.includes('Durata:') || 
                    td.textContent.includes('Durata') ||
                    td.textContent.includes('Duration') ||
                    td.textContent.includes('Travel time') ||
                    td.textContent.includes('tempo di viaggio')
                );
                
                // Method 2: Look for specific Italian text patterns
                if (!durationElement) {
                    // Check for "Durata:" anywhere on the page
                    const allText = document.body.textContent;
                    const durataMatch = allText.match(/Durata:?\s*(\d{1,2}:\d{2}:\d{2})/);
                    if (durataMatch) {
                        travelDurationText = durataMatch[1];
                        console.log('🎯 Found duration in page text:', durataMatch[0]);
                    }
                }
                
                // Method 3: Look in common attack confirmation elements
                if (!durationElement && !travelDurationText) {
                    const possibleSelectors = [
                        '#attack_info_def table tr td',
                        '#attack_info table tr td', 
                        '.vis table tr td',
                        '.attack_info tr td',
                        'table tr td'
                    ];
                    
                    for (const selector of possibleSelectors) {
                        const cells = document.querySelectorAll(selector);
                        durationElement = Array.from(cells).find(td => 
                            td.textContent.toLowerCase().includes('durata')
                        );
                        if (durationElement) {
                            console.log('🎯 Found duration via selector:', selector);
                            break;
                        }
                    }
                }
                console.log('⏱️ Travel duration extraction:', {
                    durationElement: durationElement ? 'found' : 'missing',
                    durationText: durationElement?.nextElementSibling?.textContent?.trim(),
                    nextSiblingText: durationElement?.nextSibling?.textContent?.trim(),
                    allTableCells: Array.from(document.querySelectorAll('tr td')).map(td => td.textContent.trim()),
                    cellsWithDurata: Array.from(document.querySelectorAll('tr td')).filter(td => td.textContent.includes('Durata')).map(td => ({
                        text: td.textContent,
                        nextElementSibling: td.nextElementSibling?.textContent,
                        nextSibling: td.nextSibling?.textContent
                    }))
                });
                
                // Quick fix: Use the information from our debug logs
                if (durationElement && !travelDurationText) {
                    const debugCells = Array.from(document.querySelectorAll('tr td')).filter(td => td.textContent.includes('Durata'));
                    for (const cell of debugCells) {
                        if (cell.nextSibling && cell.nextSibling.textContent) {
                            const siblingText = cell.nextSibling.textContent.trim();
                            const timeMatch = siblingText.match(/\b\d{1,2}:\d{2}:\d{2}\b/);
                            if (timeMatch) {
                                travelDurationText = timeMatch[0];
                                console.log('🎯 Quick fix found duration:', travelDurationText);
                                break;
                            }
                        }
                    }
                }
                
                // Extract the duration text
                if (travelDurationText) {
                    // We found it via regex
                    travelDuration = this.parseDuration(travelDurationText);
                    console.log('⏱️ Parsed travel duration from regex:', travelDuration, 'seconds from text:', travelDurationText);
                } else if (durationElement) {
                    // Found via table element - try multiple methods to get the time
                    let durationText = '';
                    
                    // Method 1: Try nextElementSibling
                    let durationCell = durationElement.nextElementSibling;
                    if (durationCell && durationCell.textContent.trim()) {
                        durationText = durationCell.textContent.trim();
                        console.log('📍 Found via nextElementSibling:', durationText);
                    }
                    
                    // Method 2: Try nextSibling (text node)
                    if (!durationText && durationElement.nextSibling) {
                        const nextNode = durationElement.nextSibling;
                        if (nextNode.nodeType === Node.TEXT_NODE) {
                            durationText = nextNode.textContent.trim();
                            console.log('📍 Found via nextSibling (text):', durationText);
                        } else if (nextNode.textContent) {
                            durationText = nextNode.textContent.trim();
                            console.log('📍 Found via nextSibling (element):', durationText);
                        }
                    }
                    
                    // Method 3: Look in the same row for time pattern
                    if (!durationText) {
                        const row = durationElement.closest('tr');
                        if (row) {
                            const rowText = row.textContent;
                            const timeMatch = rowText.match(/\b\d{1,2}:\d{2}:\d{2}\b/);
                            if (timeMatch) {
                                durationText = timeMatch[0];
                                console.log('📍 Found via row search:', durationText);
                            }
                        }
                    }
                    
                    // Method 4: Look immediately after "Durata:" in the element's text
                    if (!durationText) {
                        const elementText = durationElement.textContent;
                        const afterDurata = elementText.split('Durata:')[1];
                        if (afterDurata) {
                            const timeMatch = afterDurata.match(/\b\d{1,2}:\d{2}:\d{2}\b/);
                            if (timeMatch) {
                                durationText = timeMatch[0];
                                console.log('📍 Found via text split:', durationText);
                            }
                        }
                    }
                    
                    if (durationText) {
                        travelDuration = this.parseDuration(durationText);
                        console.log('⏱️ Parsed travel duration from element:', travelDuration, 'seconds from text:', durationText);
                    } else {
                        console.log('❌ Could not extract duration text from element');
                    }
                } else {
                    // Final fallback: search for any time pattern that might be duration
                    console.log('⚠️ Duration not found, trying final fallback...');
                    const pageText = document.body.textContent;
                    
                    // Look for patterns like "0:17:39" that could be duration
                    const timeMatches = pageText.match(/\b\d{1,2}:\d{2}:\d{2}\b/g);
                    if (timeMatches && timeMatches.length > 0) {
                        console.log('🔍 Found time patterns on page:', timeMatches);
                        
                        // Try to find the one that's most likely to be duration (usually shorter times)
                        for (const timeMatch of timeMatches) {
                            const parsed = this.parseDuration(timeMatch);
                            if (parsed && parsed < 86400) { // Less than 24 hours, likely duration
                                travelDuration = parsed;
                                console.log('⏱️ Using fallback duration:', travelDuration, 'seconds from:', timeMatch);
                                break;
                            }
                        }
                    }
                }
                
                this.attackData = {
                    sourceVillageId: parseInt(sourceVillage),
                    targetVillageId: targetVillageId,
                    coordinates: { x: parseInt(x), y: parseInt(y) },
                    units: units,
                    csrfToken: csrfToken,
                    arrivalTime: arrivalTime,
                    travelDuration: travelDuration,
                    attackType: 'attack' // Default to attack type
                };
                
                // Debug logging
                console.log('📊 Extracted attack data:', {
                    sourceVillageId: this.attackData.sourceVillageId,
                    targetVillageId: this.attackData.targetVillageId,
                    coordinates: this.attackData.coordinates,
                    units: this.attackData.units,
                    csrfToken: this.attackData.csrfToken ? '***PRESENT***' : 'MISSING',
                    arrivalTime: this.attackData.arrivalTime,
                    travelDuration: this.attackData.travelDuration,
                    attackType: this.attackData.attackType
                });
                
            } catch (error) {
                console.error('❌ Failed to extract attack data:', error);
                console.error('❌ Error details:', {
                    message: error.message,
                    stack: error.stack,
                    currentURL: window.location.href,
                    pageTitle: document.title,
                    formCount: document.querySelectorAll('form').length
                });
                this.attackData = null;
            }
        }
        
        parseDuration(durationText) {
            /**
             * Parse duration string like "0:17:39" to total seconds
             * Returns the duration in seconds
             */
            try {
                const parts = durationText.split(':').map(p => parseInt(p));
                if (parts.length === 3) {
                    return parts[0] * 3600 + parts[1] * 60 + parts[2]; // hours:minutes:seconds
                } else if (parts.length === 2) {
                    return parts[0] * 60 + parts[1]; // minutes:seconds
                }
            } catch (error) {
                console.warn('Could not parse duration:', durationText);
            }
            return null;
        }
        
        async checkSniperService() {
            // First try to get the correct port from dashboard
            await this.discoverSniperPort();
            
            try {
                const response = await fetch(`${SNIPER_SERVICE_URL}/health`, {
                    method: 'GET',
                    timeout: 2000
                });
                
                if (response.ok) {
                    const text = await response.text();
                    this.sniperServiceOnline = text.includes('Sniper Service');
                    console.log('✅ Sniper service is online');
                } else {
                    this.sniperServiceOnline = false;
                }
            } catch (error) {
                console.log('⚠️ Sniper service offline:', error.message);
                this.sniperServiceOnline = false;
            }
        }
        
        async discoverSniperPort() {
            try {
                // Ask dashboard for sniper status to get the correct port
                const response = await fetch(`${DASHBOARD_URL}/api/sniper/status`, {
                    method: 'GET',
                    timeout: 2000
                });
                
                if (response.ok) {
                    const result = await response.json();
                    if (result.success && result.data.process_running) {
                        // Dashboard knows the sniper service is running, we can use dashboard as proxy
                        console.log('📡 Using dashboard as sniper service proxy');
                        return;
                    }
                }
            } catch (error) {
                console.log('📡 Dashboard not available, trying direct connection');
            }
            
            // Try alternative ports if default doesn't work
            const portsToTry = [9001, 9002, 9003, 9004, 9005];
            
            for (const port of portsToTry) {
                try {
                    const testUrl = `http://127.0.0.1:${port}`;
                    const response = await fetch(`${testUrl}/health`, {
                        method: 'GET',
                        timeout: 1000
                    });
                    
                    if (response.ok) {
                        const text = await response.text();
                        if (text.includes('Sniper Service')) {
                            SNIPER_SERVICE_URL = testUrl;
                            console.log(`✅ Found sniper service on port ${port}`);
                            return;
                        }
                    }
                } catch (error) {
                    // Port not available, try next
                    continue;
                }
            }
        }
        
        injectSniperUI() {
            // Find the submit button
            const submitButton = document.getElementById('troop_confirm_submit');
            if (!submitButton) {
                console.error('❌ Submit button not found');
                return;
            }
            
            // Create sniper container
            const sniperContainer = document.createElement('div');
            sniperContainer.id = 'sniper-interface';
            sniperContainer.style.cssText = `
                margin: 10px 0;
                padding: 15px;
                border: 2px solid #8B4513;
                border-radius: 5px;
                background: linear-gradient(135deg, #f4e4c1 0%, #e8d5b7 100%);
                box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
                font-family: Verdana, Arial, sans-serif;
                font-size: 11px;
            `;
            
            // Create sniper UI HTML
            const statusColor = this.sniperServiceOnline ? '#0a7c0a' : '#cc0000';
            const statusText = this.sniperServiceOnline ? 'Online' : 'Offline';
            const statusIcon = this.sniperServiceOnline ? '🟢' : '🔴';
            
            sniperContainer.innerHTML = `
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <img src="https://dsit.innogamescdn.com/asset/7d3266bc/graphic/command/attack.webp" 
                         style="width: 18px; height: 18px; margin-right: 8px;" alt="Sniper">
                    <strong style="color: #8B4513; font-size: 12px;">🎯 Sniper Precisione</strong>
                    <span style="margin-left: auto; color: ${statusColor}; font-weight: bold;">
                        ${statusIcon} ${statusText}
                    </span>
                </div>
                
                <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <div style="display: flex; align-items: center; gap: 5px;">
                        <label for="sniper-date" style="font-weight: bold; color: #5c4033;">
                            Data:
                        </label>
                        <input type="date" 
                               id="sniper-date" 
                               style="padding: 4px 6px; border: 1px solid #8B4513; border-radius: 3px; font-size: 11px; background: white; width: 120px;"
                               ${!this.sniperServiceOnline ? 'disabled' : ''}>
                    </div>
                    
                    <div style="display: flex; align-items: center; gap: 5px;">
                        <label for="sniper-arrival-time" style="font-weight: bold; color: #5c4033;">
                            Arrivo (HH:MM:SS:MS):
                        </label>
                        <input type="text" 
                               id="sniper-arrival-time" 
                               placeholder="15:30:45:500"
                               pattern="[0-9]{2}:[0-9]{2}:[0-9]{2}:[0-9]{1,3}"
                               style="padding: 4px 6px; border: 1px solid #8B4513; border-radius: 3px; font-size: 11px; background: white; width: 110px; font-family: monospace;"
                               ${!this.sniperServiceOnline ? 'disabled' : ''}>
                    </div>
                    
                    <div style="display: flex; align-items: center; gap: 5px;">
                        <label for="sniper-latency" style="font-weight: bold; color: #5c4033;">
                            Latenza ms:
                        </label>
                        <input type="number" 
                               id="sniper-latency" 
                               placeholder="150" 
                               min="0" 
                               max="2000" 
                               value="150"
                               style="width: 70px; padding: 4px; border: 1px solid #8B4513; border-radius: 3px; font-size: 11px; background: white;"
                               ${!this.sniperServiceOnline ? 'disabled' : ''}>
                    </div>
                </div>
                
                <div style="margin-top: 8px; font-size: 10px; color: #666;">
                    ${this.attackData?.travelDuration ? 
                        `⏱️ Durata viaggio rilevata: ${this.formatDuration(this.attackData.travelDuration)} | ` : 
                        '⚠️ Durata viaggio non rilevata automaticamente | '
                    }🌐 Il tempo di lancio sarà calcolato automaticamente sottraendo viaggio + latenza
                </div>
                
                ${!this.attackData?.travelDuration ? `
                <div style="margin-top: 8px; display: flex; gap: 5px; align-items: center;">
                    <label for="manual-duration" style="font-size: 10px; color: #666;">
                        Durata manuale (HH:MM:SS):
                    </label>
                    <input type="text" 
                           id="manual-duration" 
                           placeholder="0:17:39"
                           style="width: 80px; padding: 2px 4px; border: 1px solid #ccc; border-radius: 3px; font-size: 10px; font-family: monospace;">
                    <button type="button" 
                            id="set-manual-duration"
                            style="padding: 2px 6px; font-size: 10px; background: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">
                        Usa
                    </button>
                </div>
                ` : ''}
                
                <div style="margin-top: 10px; display: flex; gap: 8px; align-items: center;">
                    <button type="button" 
                            id="sniper-schedule-btn" 
                            style="padding: 6px 12px; background: linear-gradient(135deg, #ff6b35 0%, #ff4500 100%); 
                                   border: 1px solid #cc3700; border-radius: 4px; color: white; font-weight: bold; 
                                   font-size: 11px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"
                            ${!this.sniperServiceOnline ? 'disabled' : ''}
                            onmouseover="this.style.background='linear-gradient(135deg, #ff7a47 0%, #ff5722 100%)'"
                            onmouseout="this.style.background='linear-gradient(135deg, #ff6b35 0%, #ff4500 100%)'">
                        🎯 Programma Snipe
                    </button>
                    
                    <button type="button" 
                            id="sniper-auto-fill-btn" 
                            style="padding: 6px 12px; background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); 
                                   border: 1px solid #3d8b40; border-radius: 4px; color: white; font-weight: bold; 
                                   font-size: 11px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"
                            ${!this.attackData?.arrivalTime ? 'disabled' : ''}
                            onmouseover="this.style.background='linear-gradient(135deg, #5cbf60 0%, #4caf50 100%)'"
                            onmouseout="this.style.background='linear-gradient(135deg, #4CAF50 0%, #45a049 100%)'">
                        ⏱️ Auto-riempi Arrivo
                    </button>
                    
                    <button type="button" 
                            id="sniper-dashboard-btn" 
                            style="padding: 6px 12px; background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%); 
                                   border: 1px solid #1565C0; border-radius: 4px; color: white; font-weight: bold; 
                                   font-size: 11px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"
                            onmouseover="this.style.background='linear-gradient(135deg, #42A5F5 0%, #2196F3 100%)'"
                            onmouseout="this.style.background='linear-gradient(135deg, #2196F3 0%, #1976D2 100%)'">
                        📊 Dashboard
                    </button>
                </div>
                
                <div id="sniper-status" style="margin-top: 8px; font-weight: bold; min-height: 16px;">
                    ${!this.sniperServiceOnline ? 
                        '<span style="color: #cc0000;">⚠️ Servizio sniper non disponibile</span>' : 
                        '<span style="color: #666;">Pronto per programmare attacco di precisione</span>'
                    }
                </div>
            `;
            
            // Insert before submit button
            submitButton.parentNode.insertBefore(sniperContainer, submitButton);
            
            // Set default values
            this.setDefaultValues();
        }
        
        formatDuration(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        
        setDefaultValues() {
            // Set today's date as default
            const dateInput = document.getElementById('sniper-date');
            if (dateInput) {
                const today = new Date();
                dateInput.value = today.toISOString().split('T')[0];
            }
            
            // Auto-fill arrival time if available
            if (this.attackData?.arrivalTime) {
                this.fillArrivalTime();
            }
        }
        
        fillArrivalTime() {
            if (!this.attackData?.arrivalTime) return;
            
            const arrivalTime = new Date(this.attackData.arrivalTime);
            
            // Set date
            const dateInput = document.getElementById('sniper-date');
            if (dateInput) {
                dateInput.value = arrivalTime.toISOString().split('T')[0];
            }
            
            // Set time with milliseconds
            const timeInput = document.getElementById('sniper-arrival-time');
            if (timeInput) {
                const hours = arrivalTime.getHours().toString().padStart(2, '0');
                const minutes = arrivalTime.getMinutes().toString().padStart(2, '0');
                const seconds = arrivalTime.getSeconds().toString().padStart(2, '0');
                const milliseconds = arrivalTime.getMilliseconds().toString().padStart(3, '0');
                timeInput.value = `${hours}:${minutes}:${seconds}:${milliseconds}`;
            }
        }
        
        setupEventHandlers() {
            // Schedule snipe button
            const scheduleBtn = document.getElementById('sniper-schedule-btn');
            if (scheduleBtn) {
                scheduleBtn.addEventListener('click', () => this.scheduleSnipe());
            }
            
            // Auto-fill arrival time button
            const autoFillBtn = document.getElementById('sniper-auto-fill-btn');
            if (autoFillBtn) {
                autoFillBtn.addEventListener('click', () => this.fillArrivalTime());
            }
            
            // Dashboard button
            const dashboardBtn = document.getElementById('sniper-dashboard-btn');
            if (dashboardBtn) {
                dashboardBtn.addEventListener('click', () => this.openDashboard());
            }
            
            // Manual duration button
            const manualDurationBtn = document.getElementById('set-manual-duration');
            if (manualDurationBtn) {
                manualDurationBtn.addEventListener('click', () => this.setManualDuration());
            }
        }
        
        useArrivalTime() {
            if (!this.attackData?.arrivalTime) {
                this.showStatus('❌ Orario di arrivo non disponibile', 'error');
                return;
            }
            
            const timeInput = document.getElementById('sniper-time');
            if (timeInput) {
                const arrivalTime = new Date(this.attackData.arrivalTime);
                const localTime = new Date(arrivalTime.getTime() - arrivalTime.getTimezoneOffset() * 60000);
                timeInput.value = localTime.toISOString().slice(0, 16);
                this.showStatus('✅ Orario di arrivo impostato', 'success');
            }
        }
        
        openDashboard() {
            window.open(DASHBOARD_URL, '_blank', 'width=1200,height=800');
        }
        
        setManualDuration() {
            const manualInput = document.getElementById('manual-duration');
            if (!manualInput || !manualInput.value) {
                alert('Inserire durata nel formato HH:MM:SS (es: 0:17:39)');
                return;
            }
            
            const durationText = manualInput.value.trim();
            const parsedDuration = this.parseDuration(durationText);
            
            if (parsedDuration === null) {
                alert('Formato durata non valido. Usa HH:MM:SS (es: 0:17:39)');
                return;
            }
            
            // Update attack data with manual duration
            if (this.attackData) {
                this.attackData.travelDuration = parsedDuration;
                console.log('✅ Manual travel duration set:', parsedDuration, 'seconds');
                
                // Refresh the UI to show the updated duration
                this.injectSniperUI();
                this.setupEventHandlers();
                
                this.showStatus(`✅ Durata viaggio impostata: ${this.formatDuration(parsedDuration)}`, 'success');
            }
        }
        
        parseArrivalTime(dateStr, timeStr) {
            try {
                // Parse time format HH:MM:SS:MS
                const timeParts = timeStr.split(':').map(p => parseInt(p));
                if (timeParts.length !== 4) {
                    throw new Error('Formato tempo non valido. Usa HH:MM:SS:MS');
                }
                
                const [hours, minutes, seconds, milliseconds] = timeParts;
                
                // Validate ranges
                if (hours < 0 || hours > 23 || 
                    minutes < 0 || minutes > 59 || 
                    seconds < 0 || seconds > 59 || 
                    milliseconds < 0 || milliseconds > 999) {
                    throw new Error('Valori tempo non validi');
                }
                
                // Create date object
                const date = new Date(dateStr);
                date.setHours(hours, minutes, seconds, milliseconds);
                
                return date;
            } catch (error) {
                throw new Error(`Errore parsing tempo: ${error.message}`);
            }
        }
        
        async scheduleSnipe() {
            if (!this.sniperServiceOnline) {
                this.showStatus('❌ Servizio sniper offline', 'error');
                return;
            }
            
            if (!this.attackData) {
                this.showStatus('❌ Dati attacco non validi', 'error');
                console.error('❌ Attack data is null or undefined');
                return;
            }
            
            // Detailed validation with specific error messages
            const validationErrors = [];
            
            if (!this.attackData.sourceVillageId || isNaN(this.attackData.sourceVillageId)) {
                validationErrors.push('Source village ID missing or invalid');
            }
            
            if (!this.attackData.coordinates || !this.attackData.coordinates.x || !this.attackData.coordinates.y) {
                validationErrors.push('Target coordinates missing');
            }
            
            if (!this.attackData.units || Object.keys(this.attackData.units).length === 0) {
                validationErrors.push('No units selected');
            }
            
            if (!this.attackData.csrfToken) {
                validationErrors.push('CSRF token missing');
            }
            
            if (validationErrors.length > 0) {
                const errorMsg = '❌ Validation errors: ' + validationErrors.join(', ');
                this.showStatus(errorMsg, 'error');
                console.error('❌ Attack data validation failed:', validationErrors);
                console.log('Current attack data:', this.attackData);
                return;
            }
            
            // Get form values
            const dateInput = document.getElementById('sniper-date');
            const arrivalTimeInput = document.getElementById('sniper-arrival-time');
            const latencyInput = document.getElementById('sniper-latency');
            
            if (!dateInput.value || !arrivalTimeInput.value) {
                this.showStatus('❌ Inserire data e orario di arrivo', 'error');
                return;
            }
            
            try {
                // Parse arrival time
                const arrivalTime = this.parseArrivalTime(dateInput.value, arrivalTimeInput.value);
                
                // Validate time is in the future
                if (arrivalTime <= new Date()) {
                    this.showStatus('❌ L\'orario di arrivo deve essere nel futuro', 'error');
                    return;
                }
                
                // Calculate fire time
                const travelDuration = this.attackData.travelDuration || 0; // seconds
                const latency = parseInt(latencyInput.value) || 150; // milliseconds
                
                console.log('🧮 Fire time calculation:', {
                    arrivalTime: arrivalTime,
                    travelDuration: travelDuration,
                    latency: latency,
                    travelDurationMs: travelDuration * 1000,
                    totalSubtraction: (travelDuration * 1000) + latency
                });
                
                // Fire time = arrival time - travel duration - latency
                const fireTime = new Date(arrivalTime.getTime() - (travelDuration * 1000) - latency);
                
                console.log('🧮 Calculated times:', {
                    arrivalTime: arrivalTime.toISOString(),
                    fireTime: fireTime.toISOString(),
                    difference: (arrivalTime.getTime() - fireTime.getTime()) / 1000 + ' seconds'
                });
                
                // Validate fire time is in the future
                if (fireTime <= new Date()) {
                    this.showStatus('❌ Tempo di lancio calcolato è nel passato', 'error');
                    return;
                }
                
                // Prepare snipe request (no priority - all attacks parallel)
                const sniperRequest = {
                    target_village_id: this.attackData.targetVillageId,
                    source_village_id: this.attackData.sourceVillageId,
                    attack_type: this.attackData.attackType,
                    units: this.attackData.units,
                    execute_at: fireTime.toISOString(),
                    priority: 100 // Fixed priority for all attacks
                };
                
                this.showStatus('📡 Programmazione snipe...', 'info');
                
                // Send to sniper service via dashboard API (to handle session sync)
                const response = await fetch(`${DASHBOARD_URL}/api/sniper/attack`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(sniperRequest)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    const attackId = result.data.attack_id;
                    const fireTimeStr = fireTime.toLocaleString('it-IT', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    }) + `.${fireTime.getMilliseconds().toString().padStart(3, '0')}`;
                    
                    const arrivalTimeStr = arrivalTime.toLocaleString('it-IT', {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    }) + `.${arrivalTime.getMilliseconds().toString().padStart(3, '0')}`;
                    
                    this.showStatus(`✅ Snipe programmato! Lancio: ${fireTimeStr} → Arrivo: ${arrivalTimeStr}`, 'success');
                    
                    // Optional: Ask if user wants to cancel the normal attack
                    if (confirm('Snipe programmato con successo!\\n\\nVuoi annullare questo attacco normale e tornare indietro?')) {
                        window.history.back();
                    }
                } else {
                    this.showStatus(`❌ Errore: ${result.error}`, 'error');
                }
                
            } catch (error) {
                console.error('Sniper scheduling error:', error);
                this.showStatus(`❌ ${error.message}`, 'error');
            }
        }
        
        showStatus(message, type = 'info') {
            const statusEl = document.getElementById('sniper-status');
            if (!statusEl) return;
            
            const colors = {
                success: '#0a7c0a',
                error: '#cc0000',
                info: '#2196F3',
                warning: '#ff9800'
            };
            
            statusEl.innerHTML = `<span style="color: ${colors[type]};">${message}</span>`;
            
            // Auto-clear after 10 seconds for success messages
            if (type === 'success') {
                setTimeout(() => {
                    statusEl.innerHTML = '<span style="color: #666;">Pronto per programmare attacco di precisione</span>';
                }, 10000);
            }
        }
        
        debugExtractedData() {
            console.log('🐛 Manual debug - current attack data:', this.attackData);
            if (!this.attackData) {
                console.log('❌ Attack data is null - running extraction again...');
                this.extractAttackData();
                console.log('🔄 After re-extraction:', this.attackData);
            }
            
            // Make debugging available globally
            window.sniperDebug = {
                attackData: this.attackData,
                reExtract: () => {
                    this.extractAttackData();
                    return this.attackData;
                }
            };
        }
    }
    
    // Initialize when page is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new TribalsSniperInterface();
        });
    } else {
        new TribalsSniperInterface();
    }
    
})();