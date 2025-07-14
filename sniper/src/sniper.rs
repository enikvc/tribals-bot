use crate::{attack::{AttackRequest, AttackResponse, AttackType}, session::SessionManager};
use chrono::{DateTime, Utc};
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
    pub execute_at: DateTime<Utc>,
    pub priority: u8,
    pub created_at: DateTime<Utc>,
    pub status: String,
    pub executed_at: Option<DateTime<Utc>>,
    pub success: Option<bool>,
    pub error: Option<String>,
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

pub struct SniperEngine {
    attack_queue: Arc<Mutex<BinaryHeap<ScheduledAttack>>>,
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
            .build()
            .expect("Failed to create HTTP client");

        Self {
            attack_queue: Arc::new(Mutex::new(BinaryHeap::new())),
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
        let mut queue = self.attack_queue.lock().await;
        queue.push(attack);
        
        let mut stats = self.stats.write().await;
        stats.active_attacks = queue.len();
        
        debug!("Attack queued. Queue size: {}", queue.len());
    }

    pub async fn cancel_attack(&self, attack_id: Uuid) -> bool {
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
        
        let cancelled = original_len != queue.len();
        
        if cancelled {
            let mut stats = self.stats.write().await;
            stats.active_attacks = queue.len();
            info!("❌ Cancelled attack {}", attack_id);
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
        
        // Check completed attacks
        let completed = self.completed_attacks.read().await;
        completed.get(&attack_id).cloned()
    }

    pub async fn list_attacks(&self) -> Vec<ScheduledAttack> {
        let mut attacks = Vec::new();
        
        // Add active attacks
        {
            let queue = self.attack_queue.lock().await;
            attacks.extend(queue.iter().cloned());
        }
        
        // Add completed attacks
        {
            let completed = self.completed_attacks.read().await;
            attacks.extend(completed.values().cloned());
        }
        
        // Sort by execute time
        attacks.sort_by(|a, b| a.execute_at.cmp(&b.execute_at));
        attacks
    }

    pub async fn get_stats(&self) -> SniperStats {
        self.stats.read().await.clone()
    }

    pub async fn run(&self) {
        info!("🎯 Sniper engine started - monitoring attack queue");
        
        loop {
            // Get next attack
            let next_attack = {
                let mut queue = self.attack_queue.lock().await;
                queue.pop()
            };
            
            match next_attack {
                Some(attack) => {
                    // Update active count
                    {
                        let mut stats = self.stats.write().await;
                        let queue_len = self.attack_queue.lock().await.len();
                        stats.active_attacks = queue_len;
                    }
                    
                    // Calculate wait time with high precision
                    let now = Utc::now();
                    if attack.execute_at > now {
                        let wait_duration = (attack.execute_at - now).to_std()
                            .unwrap_or(Duration::from_millis(0));
                        
                        debug!("⏰ Waiting {:?} for attack {}", wait_duration, attack.id);
                        
                        // High precision sleep
                        let target_time = TokioInstant::now() + wait_duration;
                        sleep_until(target_time).await;
                    }
                    
                    // Execute attack
                    self.execute_attack(attack).await;
                }
                None => {
                    // No attacks in queue, sleep for a short time
                    tokio::time::sleep(Duration::from_millis(100)).await;
                }
            }
        }
    }

    async fn execute_attack(&self, mut attack: ScheduledAttack) {
        let start_time = Instant::now();
        let execute_time = Utc::now();
        
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
        
        // Execute HTTP request with maximum speed
        let result = self.fire_attack(attack_req).await;
        let response_time = start_time.elapsed();
        
        match result {
            Ok(response) => {
                info!("✅ Attack {} executed in {:?} - Success: {}", 
                      attack.id, response_time, response.success);
                
                attack.status = if response.success { "completed" } else { "failed" }.to_string();
                attack.success = Some(response.success);
                
                if let Some(error) = response.error {
                    attack.error = Some(error);
                }
                
                self.complete_attack(attack, response.success).await;
            }
            Err(e) => {
                error!("❌ Attack {} failed in {:?}: {}", attack.id, response_time, e);
                
                attack.status = "failed".to_string();
                attack.success = Some(false);
                attack.error = Some(e.to_string());
                
                self.complete_attack(attack, false).await;
            }
        }
    }

    async fn fire_attack(&self, request: AttackRequest) -> anyhow::Result<AttackResponse> {
        let start_time = Instant::now();
        
        // Build URL
        let base_url = self.base_url.read().await;
        let url = format!("{}/game.php", *base_url);
        
        // Prepare form data
        let form_data = request.to_form_data();
        let headers = request.get_headers();
        let cookie_header = request.get_cookie_header();
        
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
        let response_text = response.text().await?;
        
        debug!("Attack response ({:?}): Status {}, Body: {}", 
               response_time, status, response_text.chars().take(200).collect::<String>());
        
        // Analyze response for success/failure
        let success = status.is_success() && 
                     !response_text.contains("error") && 
                     !response_text.contains("failed") &&
                     (response_text.contains("success") || 
                      response_text.contains("command_sent") ||
                      response_text.contains("popup_command"));
        
        Ok(AttackResponse {
            success,
            response_time_ms: response_time.as_millis() as u64,
            server_response: Some(response_text),
            error: if success { None } else { Some("Server indicated failure".to_string()) },
        })
    }

    async fn complete_attack(&self, attack: ScheduledAttack, success: bool) {
        // Store in completed attacks
        {
            let mut completed = self.completed_attacks.write().await;
            completed.insert(attack.id, attack);
        }
        
        // Update stats
        {
            let mut stats = self.stats.write().await;
            if success {
                stats.completed_attacks += 1;
            } else {
                stats.failed_attacks += 1;
            }
        }
    }
}