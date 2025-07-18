use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    routing::{get, post, delete},
    Router,
};
use chrono::{DateTime, Local};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    sync::Arc,
    time::{Duration, Instant},
};
use tokio::{
    sync::{Mutex, RwLock},
    time::sleep_until,
};
use tracing::{info, warn, error, debug};
use tracing_subscriber::fmt::writer::MakeWriterExt;
use uuid::Uuid;

mod attack;
mod sniper;
mod session;

use attack::{AttackRequest, AttackResponse, AttackType};
use sniper::{SniperEngine, ScheduledAttack};
use session::SessionManager;

#[derive(Clone)]
pub struct AppState {
    sniper: Arc<SniperEngine>,
    session: Arc<SessionManager>,
}

#[derive(Serialize, Deserialize)]
pub struct ScheduleRequest {
    pub target_village_id: u64,
    pub source_village_id: u64,
    pub attack_type: AttackType,
    pub units: HashMap<String, u32>,
    pub execute_at: DateTime<Local>,
    pub priority: Option<u8>, // 0-255, higher = more priority
}

#[derive(Serialize, Deserialize)]
pub struct ScheduleResponse {
    pub attack_id: Uuid,
    pub scheduled_for: DateTime<Local>,
    pub status: String,
}

#[derive(Serialize, Deserialize)]
pub struct StatusResponse {
    pub service_status: String,
    pub active_attacks: usize,
    pub completed_attacks: usize,
    pub failed_attacks: usize,
    pub session_valid: bool,
}

#[derive(Serialize, Deserialize)]
pub struct AttackStatus {
    pub attack_id: Uuid,
    pub status: String,
    pub scheduled_for: DateTime<Local>,
    pub executed_at: Option<DateTime<Local>>,
    pub success: Option<bool>,
    pub error: Option<String>,
    pub source_village_id: u64,
    pub target_village_id: u64,
    pub attack_type: AttackType,
    pub units: HashMap<String, u32>,
    pub priority: u8,
    pub payload: Option<HashMap<String, String>>,
    pub response: Option<String>,
    pub response_time_ms: Option<u64>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing with file output
    use tracing_subscriber::fmt::writer::MakeWriterExt;
    let file = std::fs::File::create("sniper_debug.log").expect("Failed to create log file");
    let file_writer = file.with_max_level(tracing::Level::DEBUG);
    
    tracing_subscriber::fmt()
        .with_writer(file_writer.and(std::io::stdout))
        .with_ansi(false)
        .init();
    
    info!("🎯 Starting Tribals Sniper Service v0.1.0");
    
    // Parse command line arguments
    let args = parse_args();
    
    // Initialize components
    let session_manager = Arc::new(SessionManager::new());
    let sniper_engine = Arc::new(SniperEngine::new(session_manager.clone()));
    
    let app_state = AppState {
        sniper: sniper_engine.clone(),
        session: session_manager,
    };
    
    // Start the sniper engine
    tokio::spawn({
        let engine = sniper_engine.clone();
        async move {
            engine.run().await;
        }
    });
    
    // Create router
    let app = Router::new()
        .route("/health", get(health_check))
        .route("/status", get(get_status))
        .route("/session", post(update_session))
        .route("/attack/schedule", post(schedule_attack))
        .route("/attack/:id", get(get_attack_status))
        .route("/attack/:id", delete(cancel_attack))
        .route("/attacks", get(list_attacks))
        .with_state(app_state)
        .layer(
            tower_http::trace::TraceLayer::new_for_http()
                .make_span_with(tower_http::trace::DefaultMakeSpan::default())
                .on_response(tower_http::trace::DefaultOnResponse::default())
        )
        .layer(
            tower_http::cors::CorsLayer::new()
                .allow_origin(tower_http::cors::Any)
                .allow_methods(tower_http::cors::Any)
                .allow_headers(tower_http::cors::Any)
        );
    
    // Start server
    let addr = format!("{}:{}", args.host, args.port);
    info!("🚀 Sniper service listening on {}", addr);
    
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;
    
    Ok(())
}

async fn health_check() -> &'static str {
    "🎯 Tribals Sniper Service - Ready to Fire!"
}

async fn get_status(State(state): State<AppState>) -> Json<StatusResponse> {
    let stats = state.sniper.get_stats().await;
    let session_valid = state.session.is_valid().await;
    
    Json(StatusResponse {
        service_status: "running".to_string(),
        active_attacks: stats.active_attacks,
        completed_attacks: stats.completed_attacks,
        failed_attacks: stats.failed_attacks,
        session_valid,
    })
}

async fn update_session(
    State(state): State<AppState>,
    Json(session_data): Json<serde_json::Value>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    info!("🔐 Session update request received");
    
    // Log key session data fields
    if let Some(csrf) = session_data.get("csrf_token") {
        info!("  CSRF token: {} chars", csrf.as_str().unwrap_or("").len());
    }
    if let Some(cookies) = session_data.get("cookies") {
        if let Some(obj) = cookies.as_object() {
            info!("  Cookies: {} entries", obj.len());
        }
    }
    if let Some(world) = session_data.get("world_url") {
        info!("  World URL: {}", world.as_str().unwrap_or("unknown"));
    }
    
    match state.session.update_session(session_data).await {
        Ok(_) => {
            info!("✅ Session successfully updated");
            Ok(Json(serde_json::json!({"status": "session_updated"})))
        },
        Err(e) => {
            error!("❌ Failed to update session: {}", e);
            Err(StatusCode::BAD_REQUEST)
        }
    }
}

async fn schedule_attack(
    State(state): State<AppState>,
    Json(request): Json<ScheduleRequest>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    info!("📥 Received schedule attack request:");
    info!("  Target: {} -> {}", request.source_village_id, request.target_village_id);
    info!("  Type: {:?}", request.attack_type);
    info!("  Execute at: {} (local)", request.execute_at.format("%Y-%m-%d %H:%M:%S"));
    info!("  Current time: {} (local)", Local::now().format("%Y-%m-%d %H:%M:%S"));
    info!("  Units: {:?}", request.units);
    info!("  Priority: {:?}", request.priority);
    
    // Validate request
    if request.execute_at <= Local::now() {
        warn!("❌ Attempt to schedule attack in the past - Execute: {}, Now: {}", 
              request.execute_at.format("%Y-%m-%d %H:%M:%S"),
              Local::now().format("%Y-%m-%d %H:%M:%S"));
        return Err(StatusCode::BAD_REQUEST);
    }
    
    if request.units.is_empty() {
        warn!("❌ Attempt to schedule attack with no units");
        return Err(StatusCode::BAD_REQUEST);
    }
    
    // Log queue state before scheduling
    let pre_queue_size = state.sniper.get_queue_size().await;
    info!("📊 Queue state before scheduling: {} attacks", pre_queue_size);
    
    // Create scheduled attack
    let attack = ScheduledAttack {
        id: Uuid::new_v4(),
        target_village_id: request.target_village_id,
        source_village_id: request.source_village_id,
        attack_type: request.attack_type,
        units: request.units,
        execute_at: request.execute_at,
        priority: request.priority.unwrap_or(100),
        created_at: Local::now(),
        status: "scheduled".to_string(),
        executed_at: None,
        success: None,
        error: None,
        payload: None,
        response: None,
        response_time_ms: None,
    };
    
    let attack_id = attack.id;
    let execute_at = attack.execute_at;
    
    info!("🔨 Created attack object with ID: {}", attack_id);
    
    // Schedule the attack
    state.sniper.schedule_attack(attack).await;
    
    // Log queue state after scheduling
    let post_queue_size = state.sniper.get_queue_size().await;
    info!("📊 Queue state after scheduling: {} attacks (was {})", post_queue_size, pre_queue_size);
    
    if post_queue_size <= pre_queue_size {
        error!("⚠️ Attack was scheduled but queue size didn't increase!");
    }
    
    info!("✅ Successfully scheduled attack {} for {}", attack_id, execute_at.format("%Y-%m-%d %H:%M:%S"));
    
    // List all attacks after scheduling
    let all_attacks = state.sniper.list_attacks().await;
    info!("📋 Total attacks in system: {}", all_attacks.len());
    for (i, atk) in all_attacks.iter().enumerate() {
        info!("  [{}] ID: {}, Status: {}, Time: {}", 
              i + 1, atk.id, atk.status, atk.execute_at.format("%Y-%m-%d %H:%M:%S"));
    }
    
    Ok(Json(ScheduleResponse {
        attack_id,
        scheduled_for: execute_at,
        status: "scheduled".to_string(),
    }))
}

async fn get_attack_status(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<AttackStatus>, StatusCode> {
    match state.sniper.get_attack_status(id).await {
        Some(attack) => Ok(Json(AttackStatus {
            attack_id: attack.id,
            status: attack.status,
            scheduled_for: attack.execute_at,
            executed_at: attack.executed_at,
            success: attack.success,
            error: attack.error,
            source_village_id: attack.source_village_id,
            target_village_id: attack.target_village_id,
            attack_type: attack.attack_type,
            units: attack.units,
            priority: attack.priority,
            payload: attack.payload,
            response: attack.response,
            response_time_ms: attack.response_time_ms,
        })),
        None => Err(StatusCode::NOT_FOUND),
    }
}

async fn cancel_attack(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    if state.sniper.cancel_attack(id).await {
        info!("❌ Cancelled attack {}", id);
        Ok(Json(serde_json::json!({"status": "cancelled"})))
    } else {
        Err(StatusCode::NOT_FOUND)
    }
}

async fn list_attacks(State(state): State<AppState>) -> Json<Vec<AttackStatus>> {
    info!("📋 List attacks endpoint called");
    
    let attacks = state.sniper.list_attacks().await;
    info!("📊 Found {} total attacks", attacks.len());
    
    // Log each attack
    for (i, attack) in attacks.iter().enumerate() {
        info!("  Attack [{}]:", i + 1);
        info!("    ID: {}", attack.id);
        info!("    Status: {}", attack.status);
        info!("    Target: {} -> {}", attack.source_village_id, attack.target_village_id);
        info!("    Execute at: {}", attack.execute_at.format("%Y-%m-%d %H:%M:%S"));
        if let Some(exec) = &attack.executed_at {
            info!("    Executed at: {}", exec.format("%Y-%m-%d %H:%M:%S"));
        }
    }
    
    let statuses: Vec<AttackStatus> = attacks
        .into_iter()
        .map(|attack| AttackStatus {
            attack_id: attack.id,
            status: attack.status,
            scheduled_for: attack.execute_at,
            executed_at: attack.executed_at,
            success: attack.success,
            error: attack.error,
            source_village_id: attack.source_village_id,
            target_village_id: attack.target_village_id,
            attack_type: attack.attack_type.clone(),
            units: attack.units.clone(),
            priority: attack.priority,
            payload: attack.payload.clone(),
            response: attack.response.clone(),
            response_time_ms: attack.response_time_ms,
        })
        .collect();
    
    info!("📤 Returning {} attack statuses", statuses.len());
    Json(statuses)
}

#[derive(clap::Parser)]
struct Args {
    #[arg(long, default_value = "127.0.0.1")]
    host: String,
    
    #[arg(long, default_value = "9001")]
    port: u16,
}

fn parse_args() -> Args {
    use clap::Parser;
    Args::parse()
}