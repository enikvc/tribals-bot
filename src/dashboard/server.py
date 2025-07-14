"""
Dashboard Server - FastAPI backend for bot control and monitoring
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from ..utils.logger import setup_logger
from ..utils.screenshot_manager import screenshot_manager

logger = setup_logger(__name__)


class DashboardServer:
    """Web dashboard server for bot control and monitoring"""
    
    def __init__(self, scheduler, config_manager):
        self.scheduler = scheduler
        self.config_manager = config_manager
        self.app = FastAPI(title="Tribals Bot Dashboard")
        self.websocket_connections: List[WebSocket] = []
        self.running = False
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        # Mount static files for frontend
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/")
        async def dashboard():
            """Serve dashboard HTML"""
            html_path = Path(__file__).parent / "static" / "index.html"
            if html_path.exists():
                return FileResponse(html_path)
            return HTMLResponse(self._get_basic_dashboard_html())
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
        
        @self.app.get("/api/status")
        async def get_status():
            """Get current bot status"""
            return await self._get_bot_status()
        
        @self.app.post("/api/automation/{name}/start")
        async def start_automation(name: str):
            """Start specific automation"""
            return await self._control_automation(name, "start")
        
        @self.app.post("/api/automation/{name}/stop")
        async def stop_automation(name: str):
            """Stop specific automation"""
            return await self._control_automation(name, "stop")
        
        @self.app.post("/api/emergency-stop")
        async def emergency_stop():
            """Emergency stop all automations"""
            await self.scheduler.emergency_stop("Emergency stop from dashboard")
            await self._broadcast_status()
            return {"status": "success", "message": "Emergency stop activated"}
        
        @self.app.post("/api/pause-all")
        async def pause_all():
            """Pause all automations"""
            await self.scheduler.pause_all_automations("Paused from dashboard")
            await self._broadcast_status()
            return {"status": "success", "message": "All automations paused"}
        
        @self.app.post("/api/resume-all")
        async def resume_all():
            """Resume all automations"""
            await self.scheduler.resume_after_captcha()
            await self._broadcast_status()
            return {"status": "success", "message": "All automations resumed"}
        
        @self.app.post("/api/shutdown")
        async def shutdown():
            """Shutdown the entire bot"""
            logger.info("🛑 Shutdown requested from dashboard")
            # Schedule shutdown after response
            asyncio.create_task(self._shutdown_bot())
            return {"status": "success", "message": "Bot shutting down..."}
        
        @self.app.get("/api/screenshots")
        async def get_screenshots():
            """Get recent screenshots"""
            return self._get_recent_screenshots()
        
        @self.app.get("/api/screenshot/{category}/{filename}")
        async def get_screenshot(category: str, filename: str):
            """Serve specific screenshot"""
            screenshot_path = Path("screenshots") / category / filename
            if screenshot_path.exists():
                return FileResponse(screenshot_path)
            raise HTTPException(status_code=404, detail="Screenshot not found")
        
        @self.app.get("/api/logs")
        async def get_logs():
            """Get recent log entries"""
            return self._get_recent_logs()
        
        @self.app.get("/api/config")
        async def get_config():
            """Get current configuration"""
            return self.config_manager.config
        
        @self.app.post("/api/config")
        async def update_config(config: Dict[str, Any]):
            """Update configuration"""
            try:
                # Merge with existing config
                self.config_manager.config.update(config)
                self.config_manager.save_config()
                await self._broadcast_status()
                return {"status": "success", "message": "Configuration updated"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        # Sniper service endpoints
        @self.app.get("/api/sniper/status")
        async def get_sniper_status():
            """Get sniper service status"""
            try:
                status = await self.scheduler.sniper_manager.get_service_status()
                return {"success": True, "data": status}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/sniper/attacks")
        async def list_attacks():
            """List all scheduled attacks"""
            try:
                logger.info("📋 Dashboard requesting sniper attacks list...")
                if not self.scheduler or not self.scheduler.sniper_manager:
                    logger.warning("⚠️ Sniper manager not available")
                    return {"success": False, "error": "Sniper service not available"}
                
                attacks = await self.scheduler.sniper_manager.list_scheduled_attacks()
                logger.info(f"📋 Found {len(attacks)} scheduled attacks")
                return {"success": True, "data": attacks}
            except Exception as e:
                logger.error(f"❌ Error listing attacks: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/sniper/attack")
        async def schedule_attack(request: Request):
            """Schedule a new attack"""
            try:
                data = await request.json()
                
                # Extract and validate data
                target_village_id = data.get("target_village_id")
                source_village_id = data.get("source_village_id") 
                attack_type = data.get("attack_type", "attack")
                units = data.get("units", {})
                execute_at_str = data.get("execute_at")
                priority = data.get("priority", 100)
                
                if not all([target_village_id, source_village_id, execute_at_str, units]):
                    return {"success": False, "error": "Missing required fields"}
                
                # Parse datetime
                from datetime import datetime
                try:
                    execute_at = datetime.fromisoformat(execute_at_str.replace('Z', '+00:00'))
                except ValueError:
                    return {"success": False, "error": "Invalid datetime format"}
                
                # Schedule attack
                attack_id = await self.scheduler.sniper_manager.schedule_attack(
                    target_village_id=target_village_id,
                    source_village_id=source_village_id,
                    attack_type=attack_type,
                    units=units,
                    execute_at=execute_at,
                    priority=priority
                )
                
                if attack_id:
                    return {"success": True, "data": {"attack_id": attack_id}}
                else:
                    return {"success": False, "error": "Failed to schedule attack"}
                    
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.app.delete("/api/sniper/attack/{attack_id}")
        async def cancel_attack(attack_id: str):
            """Cancel a scheduled attack"""
            try:
                success = await self.scheduler.sniper_manager.cancel_attack(attack_id)
                return {"success": success}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/sniper/logs")
        async def get_sniper_logs():
            """Get sniper service logs"""
            try:
                # Try to get logs from the Rust service if available
                if self.scheduler and self.scheduler.sniper_manager and self.scheduler.sniper_manager.client:
                    # For now, return Python sniper logs from our log file
                    import os
                    from pathlib import Path
                    
                    # Look for sniper-related logs in our log file
                    log_file = Path("logs/bot.log")
                    if log_file.exists():
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                        
                        # Filter for sniper-related logs
                        sniper_lines = [line for line in lines[-500:] if 'sniper' in line.lower() or '🎯' in line]
                        
                        return {"success": True, "data": ''.join(sniper_lines[-100:])}  # Last 100 sniper logs
                    
                return {"success": True, "data": "No sniper logs available"}
                
            except Exception as e:
                logger.error(f"Error getting sniper logs: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/sniper/debug")
        async def debug_sniper():
            """Debug sniper service - get detailed status"""
            try:
                if not self.scheduler or not self.scheduler.sniper_manager:
                    return {"success": False, "error": "Sniper service not available"}
                
                # Get service status
                status = await self.scheduler.sniper_manager.get_service_status()
                
                # Try direct connection to Rust service
                rust_status = None
                rust_attacks = None
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        # Get status from Rust service
                        async with session.get('http://127.0.0.1:9001/status') as resp:
                            if resp.status == 200:
                                rust_status = await resp.json()
                        
                        # Get attacks from Rust service
                        async with session.get('http://127.0.0.1:9001/attacks') as resp:
                            if resp.status == 200:
                                rust_attacks = await resp.json()
                except Exception as e:
                    logger.error(f"Direct Rust connection failed: {e}")
                
                return {
                    "success": True, 
                    "data": {
                        "python_status": status,
                        "rust_status": rust_status,
                        "rust_attacks": rust_attacks,
                        "rust_attacks_count": len(rust_attacks) if rust_attacks else 0
                    }
                }
                
            except Exception as e:
                logger.error(f"Error debugging sniper: {e}")
                return {"success": False, "error": str(e)}
        
        # Captcha testing endpoint
        @self.app.post("/api/captcha/test")
        async def test_captcha():
            """Test hCaptcha solver on demo site"""
            try:
                if not self.scheduler or not self.scheduler.browser_manager:
                    return {"success": False, "error": "Browser manager not available"}
                
                logger.info("🔴 Starting LIVE hCaptcha test from dashboard...")
                
                # Run the live hCaptcha test
                test_page = await self.scheduler.browser_manager.test_hcaptcha_live()
                
                if test_page:
                    return {"success": True, "message": "Live hCaptcha test started! Check browser and logs. The captcha detector will automatically solve any challenges."}
                else:
                    return {"success": False, "error": "Failed to start live test"}
                
            except Exception as e:
                logger.error(f"Error running hCaptcha test: {e}")
                return {"success": False, "error": str(e)}
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection for real-time updates"""
        await websocket.accept()
        self.websocket_connections.append(websocket)
        # logger.info(f"📱 Dashboard client connected. Active connections: {len(self.websocket_connections)}")
        
        try:
            # Send initial status
            status = await self._get_bot_status()
            await websocket.send_text(json.dumps({
                "type": "status",
                "data": status
            }))
            
            # Keep connection alive and handle incoming messages
            while True:
                try:
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    
                    # Handle different message types
                    if data.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    elif data.get("type") == "request_status":
                        status = await self._get_bot_status()
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "data": status
                        }))
                        
                except Exception as e:
                    # Only log non-disconnect errors
                    if not isinstance(e, WebSocketDisconnect) and "1001" not in str(e):
                        logger.error(f"WebSocket message error: {e}")
                    break
                    
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if websocket in self.websocket_connections:
                self.websocket_connections.remove(websocket)
            # logger.info(f"📱 Dashboard client disconnected. Active connections: {len(self.websocket_connections)}")
    
    async def _broadcast_status(self):
        """Broadcast status update to all connected clients"""
        if not self.websocket_connections:
            return
            
        status = await self._get_bot_status()
        message = json.dumps({
            "type": "status",
            "data": status
        })
        
        # Send to all connected clients
        disconnected = []
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            self.websocket_connections.remove(websocket)
    
    async def _get_bot_status(self) -> Dict[str, Any]:
        """Get comprehensive bot status"""
        automation_status = {}
        
        for name, automation in self.scheduler.automations.items():
            automation_status[name] = {
                "enabled": self.config_manager.config.get('scripts', {}).get(name, {}).get('enabled', False),
                "running": automation.running,
                "paused": getattr(automation, 'paused', False),
                "last_run": getattr(automation, 'last_run_time', None).isoformat() if getattr(automation, 'last_run_time', None) else None,
                "next_run": getattr(automation, 'next_run_time', None).isoformat() if getattr(automation, 'next_run_time', None) else None,
                "run_count": getattr(automation, 'run_count', 0),
                "error_count": getattr(automation, 'error_count', 0)
            }
        
        # Get browser status
        browser_status = {
            "connected": self.scheduler.browser_manager.browser is not None,
            "pages_open": len(getattr(self.scheduler.browser_manager, 'pages', [])),
            "stealth_active": getattr(self.scheduler.browser_manager, 'stealth_active', False)
        }
        
        # Get screenshot stats
        screenshot_stats = screenshot_manager.get_stats()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "scheduler": {
                "running": self.scheduler.running,
                "paused": self.scheduler.paused,
                "emergency_stopped": self.scheduler.emergency_stopped,
                "in_sleep_mode": self.scheduler.in_sleep_mode,
                "within_active_hours": self.scheduler.is_within_active_hours()
            },
            "automations": automation_status,
            "browser": browser_status,
            "screenshots": screenshot_stats,
            "active_hours": self.config_manager.config.get('active_hours', {}),
            "uptime": self._get_uptime()
        }
    
    async def _control_automation(self, name: str, action: str) -> Dict[str, Any]:
        """Control individual automation"""
        if name not in self.scheduler.automations:
            raise HTTPException(status_code=404, detail=f"Automation '{name}' not found")
        
        automation = self.scheduler.automations[name]
        
        try:
            if action == "start":
                if not automation.running:
                    asyncio.create_task(automation.start())
                    message = f"Started {name}"
                else:
                    message = f"{name} is already running"
            elif action == "stop":
                if automation.running:
                    await automation.stop()
                    message = f"Stopped {name}"
                else:
                    message = f"{name} is not running"
            else:
                raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
            
            await self._broadcast_status()
            return {"status": "success", "message": message}
            
        except Exception as e:
            logger.error(f"Error controlling {name}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def _get_recent_screenshots(self) -> List[Dict[str, Any]]:
        """Get list of recent screenshots"""
        screenshots = []
        screenshots_dir = Path("screenshots")
        
        if screenshots_dir.exists():
            for category_dir in screenshots_dir.iterdir():
                if category_dir.is_dir():
                    for screenshot in category_dir.glob("*.png"):
                        stat = screenshot.stat()
                        screenshots.append({
                            "filename": screenshot.name,
                            "category": category_dir.name,
                            "timestamp": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "size": stat.st_size,
                            "url": f"/api/screenshot/{category_dir.name}/{screenshot.name}"
                        })
        
        # Sort by timestamp, newest first
        screenshots.sort(key=lambda x: x["timestamp"], reverse=True)
        return screenshots[:50]  # Limit to 50 most recent
    
    def _get_recent_logs(self) -> List[str]:
        """Get recent log entries"""
        logs = []
        log_file = Path("logs") / f"tribals_bot_{datetime.now().strftime('%Y%m%d')}.log"
        
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Return last 100 lines
                    logs = [line.strip() for line in lines[-100:]]
            except Exception as e:
                logger.error(f"Error reading log file: {e}")
        
        return logs
    
    def _get_uptime(self) -> Optional[str]:
        """Get bot uptime"""
        # This would need to be tracked from when the bot starts
        # For now, return None
        return None
    
    def _get_basic_dashboard_html(self) -> str:
        """Basic HTML dashboard if static files don't exist"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Tribals Bot Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
                .running { background-color: #d4edda; }
                .stopped { background-color: #f8d7da; }
                .paused { background-color: #fff3cd; }
                button { padding: 10px; margin: 5px; border: none; border-radius: 3px; cursor: pointer; }
                .start { background-color: #28a745; color: white; }
                .stop { background-color: #dc3545; color: white; }
                .emergency { background-color: #dc3545; color: white; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>🤖 Tribals Bot Dashboard</h1>
            <div id="status">Loading...</div>
            <div id="controls">
                <button class="emergency" onclick="emergencyStop()">🚨 Emergency Stop</button>
                <button onclick="pauseAll()">⏸️ Pause All</button>
                <button onclick="resumeAll()">▶️ Resume All</button>
            </div>
            <div id="automations"></div>
            
            <script>
                let ws = new WebSocket('ws://localhost:8080/ws');
                
                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    if (data.type === 'status') {
                        updateStatus(data.data);
                    }
                };
                
                function updateStatus(status) {
                    document.getElementById('status').innerHTML = 
                        `<div class="status ${status.scheduler.running ? 'running' : 'stopped'}">
                            Scheduler: ${status.scheduler.running ? 'Running' : 'Stopped'} | 
                            Sleep Mode: ${status.scheduler.in_sleep_mode ? 'Yes' : 'No'} |
                            Active Hours: ${status.scheduler.within_active_hours ? 'Yes' : 'No'}
                        </div>`;
                    
                    let automationsHtml = '<h2>Automations</h2>';
                    for (const [name, auto] of Object.entries(status.automations)) {
                        automationsHtml += `
                            <div class="status ${auto.running ? 'running' : 'stopped'}">
                                <strong>${name}</strong>: ${auto.running ? 'Running' : 'Stopped'} | 
                                Enabled: ${auto.enabled ? 'Yes' : 'No'} | 
                                Runs: ${auto.run_count}
                                <button class="${auto.running ? 'stop' : 'start'}" 
                                        onclick="${auto.running ? 'stopAutomation' : 'startAutomation'}('${name}')">
                                    ${auto.running ? 'Stop' : 'Start'}
                                </button>
                            </div>`;
                    }
                    document.getElementById('automations').innerHTML = automationsHtml;
                }
                
                function emergencyStop() {
                    fetch('/api/emergency-stop', {method: 'POST'});
                }
                
                function pauseAll() {
                    fetch('/api/pause-all', {method: 'POST'});
                }
                
                function resumeAll() {
                    fetch('/api/resume-all', {method: 'POST'});
                }
                
                function startAutomation(name) {
                    fetch(`/api/automation/${name}/start`, {method: 'POST'});
                }
                
                function stopAutomation(name) {
                    fetch(`/api/automation/${name}/stop`, {method: 'POST'});
                }
                
                // Request initial status
                fetch('/api/status').then(r => r.json()).then(updateStatus);
            </script>
        </body>
        </html>
        """
    
    async def start(self, host: str = "127.0.0.1", port: int = 8080):
        """Start the dashboard server"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"🌐 Starting dashboard server at http://{host}:{port}")
        
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="warning"  # Reduce uvicorn logging
        )
        server = uvicorn.Server(config)
        
        # Start server in background task
        asyncio.create_task(server.serve())
        
        # Start periodic status broadcast
        asyncio.create_task(self._periodic_broadcast())
    
    async def stop(self):
        """Stop the dashboard server"""
        self.running = False
        logger.info("🌐 Dashboard server stopped")
    
    async def _periodic_broadcast(self):
        """Periodically broadcast status to connected clients"""
        while self.running:
            try:
                if self.websocket_connections:
                    await self._broadcast_status()
                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                logger.error(f"Error in periodic broadcast: {e}")
                await asyncio.sleep(5)
    
    async def _shutdown_bot(self):
        """Shutdown the entire bot"""
        await asyncio.sleep(1)  # Give time for response
        os._exit(0)  # Force exit