use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::sync::RwLock;
use tracing::{info, warn, error, debug};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionData {
    pub cookies: HashMap<String, String>,
    pub csrf_token: String,
    pub village_id: u64,
    pub player_id: u64,
    pub world_url: String,
}

pub struct SessionManager {
    session_data: RwLock<Option<SessionData>>,
}

impl SessionManager {
    pub fn new() -> Self {
        Self {
            session_data: RwLock::new(None),
        }
    }

    pub async fn update_session(&self, data: serde_json::Value) -> anyhow::Result<()> {
        debug!("Updating session data: {:?}", data);
        
        let cookies: HashMap<String, String> = data
            .get("cookies")
            .and_then(|v| serde_json::from_value(v.clone()).ok())
            .unwrap_or_default();
        
        let csrf_token = data
            .get("csrf_token")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        
        let village_id = data
            .get("village_id")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        
        let player_id = data
            .get("player_id")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        
        let world_url = data
            .get("world_url")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        
        if csrf_token.is_empty() || cookies.is_empty() {
            return Err(anyhow::anyhow!("Invalid session data: missing csrf_token or cookies"));
        }
        
        let session = SessionData {
            cookies,
            csrf_token,
            village_id,
            player_id,
            world_url,
        };
        
        info!("📋 Session updated - Village: {}, Player: {}, World: {}", 
              session.village_id, session.player_id, session.world_url);
        
        *self.session_data.write().await = Some(session);
        
        Ok(())
    }

    pub async fn get_session_data(&self) -> anyhow::Result<SessionData> {
        match self.session_data.read().await.as_ref() {
            Some(data) => Ok(data.clone()),
            None => Err(anyhow::anyhow!("No session data available")),
        }
    }

    pub async fn is_valid(&self) -> bool {
        let session = self.session_data.read().await;
        
        match session.as_ref() {
            Some(data) => {
                !data.csrf_token.is_empty() && 
                !data.cookies.is_empty() &&
                !data.world_url.is_empty()
            }
            None => false,
        }
    }

    pub async fn clear_session(&self) {
        info!("🧹 Clearing session data");
        *self.session_data.write().await = None;
    }

    /// Extract session data from browser context for initialization
    pub async fn extract_from_cookies(&self, cookies: Vec<(String, String)>, csrf_token: String, village_id: u64, player_id: u64, world_url: String) -> anyhow::Result<()> {
        let cookie_map: HashMap<String, String> = cookies.into_iter().collect();
        
        let session = SessionData {
            cookies: cookie_map,
            csrf_token,
            village_id,
            player_id,
            world_url,
        };
        
        info!("🔐 Extracted session from browser - Village: {}, Player: {}", 
              session.village_id, session.player_id);
        
        *self.session_data.write().await = Some(session);
        
        Ok(())
    }

    /// Get specific cookie value
    pub async fn get_cookie(&self, name: &str) -> Option<String> {
        let session = self.session_data.read().await;
        session.as_ref()?.cookies.get(name).cloned()
    }

    /// Check if session has required authentication cookies
    pub async fn has_auth_cookies(&self) -> bool {
        let session = self.session_data.read().await;
        
        match session.as_ref() {
            Some(data) => {
                // Check for common Tribal Wars authentication cookies
                data.cookies.contains_key("sid") || 
                data.cookies.contains_key("session") ||
                data.cookies.contains_key("twauth") ||
                data.cookies.contains_key("locale")
            }
            None => false,
        }
    }
}