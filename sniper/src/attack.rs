use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AttackType {
    Attack,
    Support,
    Spy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttackRequest {
    pub target_village_id: u64,
    pub source_village_id: u64,
    pub attack_type: AttackType,
    pub units: HashMap<String, u32>,
    pub csrf_token: String,
    pub session_cookies: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttackResponse {
    pub success: bool,
    pub response_time_ms: u64,
    pub server_response: Option<String>,
    pub error: Option<String>,
}

impl AttackRequest {
    /// Convert attack request to form data for HTTP POST
    pub fn to_form_data(&self) -> HashMap<String, String> {
        let mut form_data = HashMap::new();
        
        // Core parameters matching TWB approach
        form_data.insert("ajaxaction".to_string(), "popup_command".to_string());
        form_data.insert("village".to_string(), self.source_village_id.to_string());
        form_data.insert("screen".to_string(), "place".to_string());
        
        // For popup_command, we can send the target village ID directly
        // The game will handle the conversion to coordinates
        form_data.insert("target".to_string(), self.target_village_id.to_string());
        
        // Attack type parameter - TWB uses actual button value
        let attack_type_param = match self.attack_type {
            AttackType::Attack => "attack",
            AttackType::Support => "support", 
            AttackType::Spy => "spy",
        };
        form_data.insert(attack_type_param.to_string(), "true".to_string());
        
        // Add units - using simple unit names without array notation
        for (unit_type, count) in &self.units {
            if *count > 0 {
                form_data.insert(unit_type.clone(), count.to_string());
            }
        }
        
        // CSRF token
        form_data.insert("h".to_string(), self.csrf_token.clone());
        
        // Source village parameter (some servers use this)
        form_data.insert("source_village".to_string(), self.source_village_id.to_string());
        
        form_data
    }
    
    /// Get HTTP headers for the attack request
    pub fn get_headers(&self) -> HashMap<String, String> {
        let mut headers = HashMap::new();
        
        // Essential headers from TWB reference
        headers.insert("Accept".to_string(), "*/*".to_string());
        headers.insert("Accept-Language".to_string(), "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7".to_string());
        // Don't request compressed responses to avoid decompression issues
        headers.insert("Accept-Encoding".to_string(), "identity".to_string());
        headers.insert("Content-Type".to_string(), "application/x-www-form-urlencoded; charset=UTF-8".to_string());
        headers.insert("X-Requested-With".to_string(), "XMLHttpRequest".to_string());
        headers.insert("TribalWars-Ajax".to_string(), "1".to_string());
        headers.insert("Cache-Control".to_string(), "no-cache".to_string());
        headers.insert("Pragma".to_string(), "no-cache".to_string());
        
        // User agent - match real Chrome
        headers.insert("User-Agent".to_string(), 
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36".to_string()
        );
        
        headers
    }
    
    /// Get cookie header string
    pub fn get_cookie_header(&self) -> String {
        self.session_cookies
            .iter()
            .map(|(k, v)| format!("{}={}", k, v))
            .collect::<Vec<_>>()
            .join("; ")
    }
}