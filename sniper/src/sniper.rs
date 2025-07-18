use crate::{attack::{AttackRequest, AttackResponse, AttackType}, session::SessionManager};
use chrono::{DateTime, Local};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::{
    collections::{BinaryHeap, HashMap},
    sync::Arc,
    time::{Duration, Instant},
    cmp::Ordering,
};
use tokio::{
    sync::{Mutex, RwLock},
    time::{sleep_until, Instant as TokioInstant},
};
use tracing::{info, warn, error, debug};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduledAttack {
    pub id: Uuid,
    pub target_village_id: u64,
    pub source_village_id: u64,
    pub attack_type: AttackType,
    pub units: HashMap<String, u32>,
    pub execute_at: DateTime<Local>,
    pub priority: u8,
    pub created_at: DateTime<Local>,
    pub status: String,
    pub executed_at: Option<DateTime<Local>>,
    pub success: Option<bool>,
    pub error: Option<String>,
    pub payload: Option<HashMap<String, String>>,
    pub response: Option<String>,
    pub response_time_ms: Option<u64>,
}

impl PartialEq for ScheduledAttack {
    fn eq(&self, other: &Self) -> bool {
        self.execute_at == other.execute_at && self.priority == other.priority
    }
}

impl Eq for ScheduledAttack {}

impl PartialOrd for ScheduledAttack {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ScheduledAttack {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse order for min-heap behavior (earliest first)
        // If times are equal, higher priority goes first
        other.execute_at.cmp(&self.execute_at)
            .then_with(|| self.priority.cmp(&other.priority))
    }
}

#[derive(Debug, Clone)]
pub struct SniperStats {
    pub active_attacks: usize,
    pub completed_attacks: usize,
    pub failed_attacks: usize,
}

#[derive(Clone)]
pub struct SniperEngine {
    attack_queue: Arc<Mutex<BinaryHeap<ScheduledAttack>>>,
    processing_attacks: Arc<RwLock<HashMap<Uuid, ScheduledAttack>>>,
    completed_attacks: Arc<RwLock<HashMap<Uuid, ScheduledAttack>>>,
    session_manager: Arc<SessionManager>,
    http_client: Client,
    stats: Arc<RwLock<SniperStats>>,
    base_url: Arc<RwLock<String>>,
}

impl SniperEngine {
    pub fn new(session_manager: Arc<SessionManager>) -> Self {
        let http_client = Client::builder()
            .timeout(Duration::from_secs(30))
            .connect_timeout(Duration::from_secs(10))
            .tcp_keepalive(Duration::from_secs(60))
            .http2_keep_alive_timeout(Duration::from_secs(30))
            .http2_keep_alive_interval(Duration::from_secs(15))
            .http2_adaptive_window(true)
            .gzip(true)  // Enable automatic gzip decompression
            .brotli(true) // Enable brotli decompression too
            .build()
            .expect("Failed to create HTTP client");

        Self {
            attack_queue: Arc::new(Mutex::new(BinaryHeap::new())),
            processing_attacks: Arc::new(RwLock::new(HashMap::new())),
            completed_attacks: Arc::new(RwLock::new(HashMap::new())),
            session_manager,
            http_client,
            stats: Arc::new(RwLock::new(SniperStats {
                active_attacks: 0,
                completed_attacks: 0,
                failed_attacks: 0,
            })),
            base_url: Arc::new(RwLock::new("https://it94.tribals.it".to_string())),
        }
    }

    pub async fn set_base_url(&self, url: String) {
        *self.base_url.write().await = url;
    }

    pub async fn schedule_attack(&self, attack: ScheduledAttack) {
        info!("🎯 schedule_attack called for attack ID: {}", attack.id);
        info!("  Target: {} -> {}", attack.source_village_id, attack.target_village_id);
        info!("  Execute at: {}", attack.execute_at.format("%Y-%m-%d %H:%M:%S"));
        
        let mut queue = self.attack_queue.lock().await;
        let pre_size = queue.len();
        info!("🔓 Acquired queue lock. Current size: {}", pre_size);
        
        // Log existing queue contents
        if pre_size > 0 {
            info!("  Existing attacks in queue:");
            for (i, existing) in queue.iter().enumerate() {
                info!("    [{}] ID: {}, Time: {}", 
                      i + 1, existing.id, existing.execute_at.format("%Y-%m-%d %H:%M:%S"));
            }
        }
        
        // Ensure attack has proper scheduled status
        let mut scheduled_attack = attack.clone();
        scheduled_attack.status = "scheduled".to_string();
        // Initialize tracking fields
        scheduled_attack.payload = None;
        scheduled_attack.response = None;
        scheduled_attack.response_time_ms = None;
        queue.push(scheduled_attack);
        let post_size = queue.len();
        info!("➕ Pushed attack to queue. New size: {} (was {})", post_size, pre_size);
        
        if post_size <= pre_size {
            error!("⚠️ Queue size didn't increase after push! Something is wrong!");
        }
        
        let mut stats = self.stats.write().await;
        stats.active_attacks = post_size;
        info!("📊 Updated stats. Active attacks: {}", stats.active_attacks);
        
        info!("✅ Attack {} successfully queued. Queue size: {}", attack.id, post_size);
    }
    
    pub async fn get_queue_size(&self) -> usize {
        let queue = self.attack_queue.lock().await;
        let size = queue.len();
        info!("🔍 get_queue_size called. Current size: {}", size);
        size
    }

    pub async fn cancel_attack(&self, attack_id: Uuid) -> bool {
        // Try to cancel from queue first
        let cancelled_from_queue = {
            let mut queue = self.attack_queue.lock().await;
            let original_len = queue.len();
            
            // Convert to vector, filter, and rebuild heap
            let attacks: Vec<_> = queue.drain().collect();
            let filtered: Vec<_> = attacks.into_iter()
                .filter(|attack| attack.id != attack_id)
                .collect();
            
            for attack in filtered {
                queue.push(attack);
            }
            
            original_len != queue.len()
        };
        
        // If not in queue, try to cancel from processing
        let cancelled_from_processing = if !cancelled_from_queue {
            let mut processing = self.processing_attacks.write().await;
            processing.remove(&attack_id).is_some()
        } else {
            false
        };
        
        let cancelled = cancelled_from_queue || cancelled_from_processing;
        
        if cancelled {
            // Update stats
            let mut stats = self.stats.write().await;
            let queue_len = self.attack_queue.lock().await.len();
            let processing_len = self.processing_attacks.read().await.len();
            stats.active_attacks = queue_len + processing_len;
            
            info!("❌ Cancelled attack {} (from {}) - Active attacks: {}", 
                  attack_id, 
                  if cancelled_from_queue { "queue" } else { "processing" },
                  stats.active_attacks);
        }
        
        cancelled
    }

    pub async fn get_attack_status(&self, attack_id: Uuid) -> Option<ScheduledAttack> {
        // Check active queue first
        {
            let queue = self.attack_queue.lock().await;
            for attack in queue.iter() {
                if attack.id == attack_id {
                    return Some(attack.clone());
                }
            }
        }
        
        // Check processing attacks
        {
            let processing = self.processing_attacks.read().await;
            if let Some(attack) = processing.get(&attack_id) {
                return Some(attack.clone());
            }
        }
        
        // Check completed attacks
        let completed = self.completed_attacks.read().await;
        completed.get(&attack_id).cloned()
    }

    pub async fn list_attacks(&self) -> Vec<ScheduledAttack> {
        info!("📋 list_attacks called");
        let mut attacks = Vec::new();
        
        // Add active attacks
        {
            let queue = self.attack_queue.lock().await;
            let queue_size = queue.len();
            info!("🔓 Acquired queue lock. Active attacks in queue: {}", queue_size);
            
            for (i, attack) in queue.iter().enumerate() {
                info!("  Active [{}]: ID: {}, Status: {}, Time: {}", 
                      i + 1, attack.id, attack.status, attack.execute_at.format("%Y-%m-%d %H:%M:%S"));
            }
            
            attacks.extend(queue.iter().cloned());
            info!("📦 Added {} attacks from active queue", queue_size);
        }
        
        // Add processing attacks
        {
            let processing = self.processing_attacks.read().await;
            let processing_size = processing.len();
            info!("⏳ Checking processing attacks. Found: {}", processing_size);
            
            for (i, (id, attack)) in processing.iter().enumerate() {
                info!("  Processing [{}]: ID: {}, Status: {}, Time: {}", 
                      i + 1, id, attack.status, attack.execute_at.format("%Y-%m-%d %H:%M:%S"));
            }
            
            attacks.extend(processing.values().cloned());
            info!("📦 Added {} attacks from processing map", processing_size);
        }
        
        // Add completed attacks
        {
            let completed = self.completed_attacks.read().await;
            let completed_size = completed.len();
            info!("📁 Checking completed attacks. Found: {}", completed_size);
            
            for (i, (id, attack)) in completed.iter().enumerate() {
                info!("  Completed [{}]: ID: {}, Status: {}, Time: {}", 
                      i + 1, id, attack.status, attack.execute_at.format("%Y-%m-%d %H:%M:%S"));
            }
            
            attacks.extend(completed.values().cloned());
            info!("📦 Added {} attacks from completed map", completed_size);
        }
        
        info!("📊 Total attacks before sorting: {}", attacks.len());
        
        // Sort by execute time
        attacks.sort_by(|a, b| a.execute_at.cmp(&b.execute_at));
        
        info!("✅ Returning {} total attacks", attacks.len());
        attacks
    }

    pub async fn get_stats(&self) -> SniperStats {
        self.stats.read().await.clone()
    }

    pub async fn run(&self) {
        info!("🎯 Sniper engine started - monitoring attack queue");
        
        let mut loop_count = 0;
        loop {
            loop_count += 1;
            
            // Check queue state periodically
            if loop_count % 50 == 0 {  // Every 5 seconds when idle
                let queue_size = self.attack_queue.lock().await.len();
                let processing_size = self.processing_attacks.read().await.len();
                if queue_size > 0 || processing_size > 0 {
                    info!("🔁 Engine loop #{}: {} in queue, {} processing", 
                          loop_count, queue_size, processing_size);
                }
            }
            
            // Get next attack
            let next_attack = {
                let mut queue = self.attack_queue.lock().await;
                let popped = queue.pop();
                
                if let Some(ref attack) = popped {
                    info!("🎯 Popped attack {} from queue. Remaining: {}", attack.id, queue.len());
                }
                
                popped
            };
            
            match next_attack {
                Some(mut attack) => {
                    info!("🎯 Spawning task for attack {} execution", attack.id);
                    
                    // Move to processing map
                    {
                        attack.status = "processing".to_string();
                        let mut processing = self.processing_attacks.write().await;
                        processing.insert(attack.id, attack.clone());
                        info!("📤 Moved attack {} to processing map", attack.id);
                    }
                    
                    // Update active count
                    {
                        let mut stats = self.stats.write().await;
                        let queue_len = self.attack_queue.lock().await.len();
                        let processing_len = self.processing_attacks.read().await.len();
                        stats.active_attacks = queue_len + processing_len;
                        info!("📊 Updated active attacks count: {} (queue: {}, processing: {})", 
                              stats.active_attacks, queue_len, processing_len);
                    }
                    
                    // Spawn a new task to handle this attack
                    let self_clone = self.clone();
                    tokio::spawn(async move {
                        self_clone.process_attack(attack).await;
                    });
                    
                    // Continue immediately to process next attack
                    info!("✅ Attack task spawned, continuing to check for more attacks");
                }
                None => {
                    // No attacks in queue, sleep for a short time
                    tokio::time::sleep(Duration::from_millis(100)).await;
                }
            }
        }
    }
    
    async fn process_attack(&self, attack: ScheduledAttack) {
        let attack_id = attack.id;
        info!("🚀 Task started for attack {}", attack_id);
        
        // Calculate wait time with high precision
        let now = Local::now();
        if attack.execute_at > now {
            let wait_duration = (attack.execute_at - now).to_std()
                .unwrap_or(Duration::from_millis(0));
            
            info!("⏰ Task for attack {} waiting {:?} (executes at {})", 
                  attack_id, wait_duration, attack.execute_at.format("%Y-%m-%d %H:%M:%S"));
            
            // High precision sleep
            let target_time = TokioInstant::now() + wait_duration;
            sleep_until(target_time).await;
        } else {
            warn!("⚠️ Attack {} is already past execution time! (was scheduled for {})", 
                  attack_id, attack.execute_at.format("%Y-%m-%d %H:%M:%S"));
        }
        
        // Execute attack
        info!("🎯 Task executing attack {} now", attack_id);
        self.execute_attack(attack).await;
    }

    async fn execute_attack(&self, mut attack: ScheduledAttack) {
        let start_time = Instant::now();
        let execute_time = Local::now();
        
        info!("🚀 Executing attack {} -> {}", 
              attack.source_village_id, attack.target_village_id);
        
        attack.status = "executing".to_string();
        attack.executed_at = Some(execute_time);
        
        // Get session data
        let session_data = match self.session_manager.get_session_data().await {
            Ok(data) => data,
            Err(e) => {
                error!("❌ Failed to get session data for attack {}: {}", attack.id, e);
                attack.status = "failed".to_string();
                attack.success = Some(false);
                attack.error = Some(format!("Session error: {}", e));
                self.complete_attack(attack, false).await;
                return;
            }
        };
        
        // Create attack request
        let attack_req = AttackRequest {
            target_village_id: attack.target_village_id,
            source_village_id: attack.source_village_id,
            attack_type: attack.attack_type.clone(),
            units: attack.units.clone(),
            csrf_token: session_data.csrf_token,
            session_cookies: session_data.cookies,
        };
        
        // Store the payload that will be sent
        attack.payload = Some(attack_req.to_form_data());
        
        // Execute HTTP request with maximum speed
        let result = self.fire_attack(attack_req).await;
        let response_time = start_time.elapsed();
        
        match result {
            Ok(response) => {
                info!("✅ Attack {} executed in {:?} - Success: {}", 
                      attack.id, response_time, response.success);
                
                attack.status = if response.success { "completed" } else { "failed" }.to_string();
                attack.success = Some(response.success);
                attack.response_time_ms = Some(response.response_time_ms);
                
                // Store response body (limit size for storage)
                if let Some(resp_body) = response.server_response {
                    attack.response = Some(if resp_body.len() > 10000 {
                        format!("{}... (truncated, {} chars total)", 
                                &resp_body[..10000], resp_body.len())
                    } else {
                        resp_body
                    });
                }
                
                if let Some(error) = response.error {
                    attack.error = Some(error);
                }
                
                info!("🔄 About to call complete_attack for {} with success={}", attack.id, response.success);
                self.complete_attack(attack, response.success).await;
                info!("🔄 complete_attack returned for {}", attack.id);
            }
            Err(e) => {
                error!("❌ Attack {} failed in {:?}: {}", attack.id, response_time, e);
                
                attack.status = "failed".to_string();
                attack.success = Some(false);
                attack.error = Some(e.to_string());
                attack.response_time_ms = Some(response_time.as_millis() as u64);
                
                self.complete_attack(attack, false).await;
            }
        }
    }

    async fn fire_attack(&self, request: AttackRequest) -> anyhow::Result<AttackResponse> {
        let start_time = Instant::now();
        
        // Build URL - for popup_command we need the full parameters
        let base_url = self.base_url.read().await;
        
        // TWB style: First we need to get the place screen to extract form data
        // For now, we'll use the direct popup_command approach but with proper parameters
        let url = format!("{}/game.php?village={}&screen=place&ajaxaction=popup_command", 
                         *base_url, request.source_village_id);
        
        // Prepare form data
        let mut form_data = request.to_form_data();
        
        // Remove ajaxaction from form data since it's in URL
        form_data.remove("ajaxaction");
        
        let headers = request.get_headers();
        let cookie_header = request.get_cookie_header();
        
        // Log the request details
        info!("🔫 Firing attack to URL: {}", url);
        info!("📝 Form data: {:?}", form_data);
        info!("🍪 Cookie count: {}", request.session_cookies.len());
        
        // Build request with all headers
        let mut req_builder = self.http_client
            .post(&url)
            .form(&form_data);
        
        // Add headers
        for (key, value) in headers {
            req_builder = req_builder.header(&key, &value);
        }
        
        // Add cookies
        if !cookie_header.is_empty() {
            req_builder = req_builder.header("Cookie", &cookie_header);
        }
        
        // Execute with maximum speed
        let response = req_builder.send().await?;
        let response_time = start_time.elapsed();
        
        let status = response.status();
        
        // reqwest should handle gzip automatically with .gzip(true)
        // Just get the text directly - reqwest will decompress for us
        let response_text = response.text().await?;
        
        info!("🌐 HTTP Response ({:?}): Status {}", response_time, status);
        
        // ALWAYS print the full response to a file for debugging
        let debug_path = "/tmp/last_attack_response.html";
        std::fs::write(debug_path, &response_text)
            .unwrap_or_else(|e| error!("Failed to write response to file: {}", e));
        info!("📝 Full response written to {}", debug_path);
        
        // Log more of the response for debugging
        if response_text.len() <= 2000 {
            info!("📄 Full response body: {}", response_text);
        } else {
            info!("📄 Response body (first 2000 chars): {}", response_text.chars().take(2000).collect::<String>());
            info!("📄 Response body length: {} chars", response_text.len());
        }
        
        // Analyze response for success/failure using TWB-style detection
        let status_ok = status.is_success();
        
        // Primary error detection - check for error_box div (TWB method)
        let has_error_box = response_text.contains("<div class=\"error_box\"") || 
                           response_text.contains("<div class='error_box'") ||
                           response_text.contains("<div class=error_box");
        
        // Additional error indicators
        let response_lower = response_text.to_lowercase();
        let has_error_text = response_lower.contains("error") || response_lower.contains("errore");
        let has_failed = response_lower.contains("failed") || response_lower.contains("fallito");
        
        // Check for specific error messages
        let has_not_enough_units = response_lower.contains("not enough units") || 
                                  response_lower.contains("non hai abbastanza") ||
                                  response_lower.contains("truppe insufficienti");
        let has_target_not_exist = response_lower.contains("does not exist") || 
                                  response_lower.contains("non esiste") ||
                                  response_lower.contains("inesistente");
        
        // Success indicators for popup_command response
        // Check if we got a JSON response (popup_command returns JSON)
        let is_json = response_text.trim().starts_with('{') || response_text.trim().starts_with('[');
        
        // Check for command ID in various formats
        let has_command_id = response_text.contains("command_id") || 
                            response_text.contains("data-command-id") ||
                            response_text.contains("command-id");
        
        // Check for redirect or command confirmation
        let has_command_info = response_text.contains("command_info") || 
                              response_text.contains("info_command") ||
                              response_text.contains("screen=info_command");
        
        // Check if response contains the overview page (which might indicate success)
        let has_overview = response_text.contains("screen=overview") || 
                          response_text.contains("VillageOverview");
        
        // Check if it's a redirect to overview (common after successful attack)
        let is_overview_redirect = has_overview && !has_error_box;
        
        // For popup_command, several patterns indicate success:
        // 1. JSON response with command info
        // 2. Small response (redirect)
        // 3. Overview page without errors (redirect after attack)
        let success = status_ok && 
                     !has_error_box && 
                     !has_not_enough_units && 
                     !has_target_not_exist &&
                     (is_json || has_command_id || has_command_info || 
                      response_text.len() < 1000 || is_overview_redirect);
        
        // Log detailed error info if failed
        if !success {
            if has_error_box {
                error!("❌ Attack failed: error_box detected in response");
            }
            if has_not_enough_units {
                error!("❌ Attack failed: not enough units");
            }
            if has_target_not_exist {
                error!("❌ Attack failed: target does not exist");
            }
        }
        
        info!("🔍 Response analysis: status_ok={}, has_error_box={}, is_json={}, has_command_id={}, has_overview={}, response_len={} -> success={}", 
              status_ok, has_error_box, is_json, has_command_id, has_overview, response_text.len(), success);
        
        let error_msg = if !success {
            if has_error_box {
                Some("Error box detected in response".to_string())
            } else if has_not_enough_units {
                Some("Not enough units".to_string())
            } else if has_target_not_exist {
                Some("Target does not exist".to_string())
            } else if !has_command_id && !has_command_info && response_text.len() >= 500 {
                Some("No command confirmation found in response".to_string())
            } else {
                Some("Attack failed - unknown reason".to_string())
            }
        } else {
            None
        };
        
        Ok(AttackResponse {
            success,
            response_time_ms: response_time.as_millis() as u64,
            server_response: Some(response_text),
            error: error_msg,
        })
    }

    async fn complete_attack(&self, attack: ScheduledAttack, success: bool) {
        let attack_id = attack.id;
        info!("🏁 complete_attack called for {} with success={}", attack_id, success);
        
        // Remove from processing map
        {
            let mut processing = self.processing_attacks.write().await;
            let removed = processing.remove(&attack_id);
            info!("🔄 Removed attack {} from processing map: {:?}", attack_id, removed.is_some());
        }
        
        // Store in completed attacks
        {
            let mut completed = self.completed_attacks.write().await;
            completed.insert(attack_id, attack);
            info!("📥 Moved attack {} to completed map", attack_id);
        }
        
        // Update stats
        {
            let mut stats = self.stats.write().await;
            if success {
                stats.completed_attacks += 1;
            } else {
                stats.failed_attacks += 1;
            }
            
            // Update active count
            let queue_len = self.attack_queue.lock().await.len();
            let processing_len = self.processing_attacks.read().await.len();
            stats.active_attacks = queue_len + processing_len;
            
            info!("📊 Stats updated - Active: {}, Completed: {}, Failed: {}", 
                  stats.active_attacks, stats.completed_attacks, stats.failed_attacks);
        }
    }
}