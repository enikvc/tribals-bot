use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    routing::{get, post, delete},
    Router,
};
use chrono::{DateTime, Utc};
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
    pub execute_at: DateTime<Utc>,
    pub priority: Option<u8>, // 0-255, higher = more priority
}

#[derive(Serialize, Deserialize)]
pub struct ScheduleResponse {
    pub attack_id: Uuid,
    pub scheduled_for: DateTime<Utc>,
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
    pub scheduled_for: DateTime<Utc>,
    pub executed_at: Option<DateTime<Utc>>,
    pub success: Option<bool>,
    pub error: Option<String>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt::init();
    
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
    match state.session.update_session(session_data).await {
        Ok(_) => Ok(Json(serde_json::json!({"status": "session_updated"}))),
        Err(e) => {
            error!("Failed to update session: {}", e);
            Err(StatusCode::BAD_REQUEST)
        }
    }
}

async fn schedule_attack(
    State(state): State<AppState>,
    Json(request): Json<ScheduleRequest>,
) -> Result<Json<ScheduleResponse>, StatusCode> {
    // Validate request
    if request.execute_at <= Utc::now() {
        warn!("Attempt to schedule attack in the past");
        return Err(StatusCode::BAD_REQUEST);
    }
    
    if request.units.is_empty() {
        warn!("Attempt to schedule attack with no units");
        return Err(StatusCode::BAD_REQUEST);
    }
    
    // Create scheduled attack
    let attack = ScheduledAttack {
        id: Uuid::new_v4(),
        target_village_id: request.target_village_id,
        source_village_id: request.source_village_id,
        attack_type: request.attack_type,
        units: request.units,
        execute_at: request.execute_at,
        priority: request.priority.unwrap_or(100),
        created_at: Utc::now(),
        status: "scheduled".to_string(),
        executed_at: None,
        success: None,
        error: None,
    };
    
    let attack_id = attack.id;
    let execute_at = attack.execute_at;
    
    // Schedule the attack
    state.sniper.schedule_attack(attack).await;
    
    info!("📅 Scheduled attack {} for {}", attack_id, execute_at);
    
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
    let attacks = state.sniper.list_attacks().await;
    let statuses = attacks
        .into_iter()
        .map(|attack| AttackStatus {
            attack_id: attack.id,
            status: attack.status,
            scheduled_for: attack.execute_at,
            executed_at: attack.executed_at,
            success: attack.success,
            error: attack.error,
        })
        .collect();
    
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