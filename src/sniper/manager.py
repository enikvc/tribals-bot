"""
Sniper Service Manager - Handles lifecycle and integration with the main bot
"""
import asyncio
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..utils.logger import setup_logger
from .client import SniperClient, AttackBuilder

logger = setup_logger(__name__)


class SniperManager:
    """Manages the Rust sniper service lifecycle and integration"""
    
    def __init__(self, config: Dict[str, Any], browser_manager=None):
        self.config = config
        self.browser_manager = browser_manager
        
        # Service configuration
        sniper_config = config.get('sniper', {})
        self.enabled = sniper_config.get('enabled', True)
        self.host = sniper_config.get('host', '127.0.0.1')
        self.port = sniper_config.get('port', 9001)
        self.auto_start = sniper_config.get('auto_start', True)
        
        # Process management
        self.process: Optional[subprocess.Popen] = None
        self.client: Optional[SniperClient] = None
        self.running = False
        
        # Paths
        self.project_root = Path(__file__).parent.parent.parent
        self.sniper_dir = self.project_root / "sniper"
        self.binary_path = self.sniper_dir / "target" / "release" / "tribals-sniper"
        
    async def initialize(self):
        """Initialize the sniper service"""
        if not self.enabled:
            logger.info("🎯 Sniper service disabled in configuration")
            return False
            
        logger.info("🎯 Initializing sniper service...")
        
        try:
            # Add timeout to prevent hanging
            return await asyncio.wait_for(self._do_initialize(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("❌ Sniper service initialization timed out after 60 seconds")
            return False
        except Exception as e:
            logger.error(f"❌ Sniper service initialization failed: {e}")
            return False
    
    async def _do_initialize(self):
        """Actual initialization logic"""
        # Build the Rust service if needed
        if not await self.ensure_binary_exists():
            logger.error("❌ Failed to build sniper service")
            return False
            
        # Start the service
        if self.auto_start:
            if not await self.start_service():
                logger.error("❌ Failed to start sniper service")
                return False
                
        # Initialize client
        self.client = SniperClient(self.host, self.port)
        await self.client.connect()
        
        # Wait for service to be ready (with shorter timeout)
        if not await self.client.wait_for_service(timeout=10):
            logger.error("❌ Sniper service not ready")
            return False
            
        # Update session data
        await self.sync_session_data()
        
        self.running = True
        logger.info("✅ Sniper service initialized successfully")
        return True
        
    async def shutdown(self):
        """Shutdown the sniper service"""
        if not self.running:
            return
            
        logger.info("🛑 Shutting down sniper service...")
        
        # Close client
        if self.client:
            await self.client.disconnect()
            
        # Stop process
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Sniper service didn't stop gracefully, forcing...")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping sniper service: {e}")
                
        self.running = False
        logger.info("✅ Sniper service stopped")
        
    async def ensure_binary_exists(self) -> bool:
        """Ensure the Rust binary is built and available"""
        if self.binary_path.exists():
            logger.debug("✅ Sniper binary found")
            return True
            
        logger.info("🔨 Building sniper service...")
        
        try:
            # Change to sniper directory
            original_cwd = os.getcwd()
            os.chdir(self.sniper_dir)
            
            # Build in release mode for maximum performance
            result = subprocess.run(
                ["cargo", "build", "--release"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            os.chdir(original_cwd)
            
            if result.returncode != 0:
                logger.error(f"❌ Cargo build failed: {result.stderr}")
                return False
                
            if not self.binary_path.exists():
                logger.error("❌ Binary not found after build")
                return False
                
            logger.info("✅ Sniper service built successfully")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Build timeout")
            return False
        except FileNotFoundError:
            logger.error("❌ Cargo not found - please install Rust")
            return False
        except Exception as e:
            logger.error(f"❌ Build error: {e}")
            return False
            
    async def start_service(self) -> bool:
        """Start the Rust sniper service process"""
        if self.process and self.process.poll() is None:
            logger.debug("Sniper service already running")
            return True
            
        # First, try to kill any existing processes on this port
        await self._kill_existing_service()
        
        try:
            logger.info(f"🚀 Starting sniper service on {self.host}:{self.port}")
            
            # Start the process
            self.process = subprocess.Popen(
                [str(self.binary_path), "--host", self.host, "--port", str(self.port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            # Check if it's still running
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                logger.error(f"❌ Sniper service failed to start:")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                
                # If port is still in use, try a different port
                if "Address already in use" in stderr:
                    logger.info("🔄 Port in use, trying alternative port...")
                    return await self._try_alternative_port()
                
                return False
                
            logger.info("✅ Sniper service process started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start sniper service: {e}")
            return False
            
    async def _kill_existing_service(self):
        """Kill any existing sniper service processes"""
        try:
            # Find processes using our port
            result = subprocess.run(
                ["lsof", "-ti", f":{self.port}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        logger.info(f"🔫 Killing existing process on port {self.port}: PID {pid}")
                        subprocess.run(["kill", "-9", pid], check=True)
                        await asyncio.sleep(0.5)
                    except subprocess.CalledProcessError:
                        pass  # Process might already be gone
                        
        except FileNotFoundError:
            # lsof not available, try alternative approach
            try:
                # Kill by process name (less precise but works)
                subprocess.run(["pkill", "-f", "tribals-sniper"], check=False)
                await asyncio.sleep(1)
            except:
                pass
        except Exception as e:
            logger.debug(f"Could not kill existing processes: {e}")
            
    async def _try_alternative_port(self) -> bool:
        """Try starting on an alternative port"""
        original_port = self.port
        
        # Try ports 9001-9010
        for port in range(9001, 9011):
            if port == original_port:
                continue
                
            try:
                logger.info(f"🔄 Trying port {port}...")
                
                self.process = subprocess.Popen(
                    [str(self.binary_path), "--host", self.host, "--port", str(port)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                await asyncio.sleep(1)
                
                if self.process.poll() is None:
                    self.port = port
                    logger.info(f"✅ Sniper service started on alternative port {port}")
                    
                    # Update client to use new port
                    if self.client:
                        await self.client.disconnect()
                        self.client = SniperClient(self.host, port)
                        await self.client.connect()
                    
                    return True
                else:
                    stdout, stderr = self.process.communicate()
                    if "Address already in use" not in stderr:
                        # Different error, stop trying
                        break
                        
            except Exception as e:
                logger.debug(f"Failed to start on port {port}: {e}")
                continue
                
        logger.error(f"❌ Could not find available port for sniper service")
        self.port = original_port  # Restore original port
        return False
            
    async def sync_session_data(self):
        """Sync session data from browser manager to sniper service"""
        if not self.client or not self.browser_manager:
            return
            
        try:
            # Extract session data from browser
            session_data = await self.extract_session_data()
            
            if session_data:
                success = await self.client.update_session(session_data)
                if success:
                    logger.info("📋 Session data synced to sniper service")
                else:
                    logger.warning("⚠️ Failed to sync session data to sniper service")
            else:
                logger.warning("⚠️ No session data available to sync")
                
        except Exception as e:
            logger.error(f"❌ Error syncing session data: {e}")
            
    async def extract_session_data(self) -> Optional[Dict[str, Any]]:
        """Extract session data from browser manager"""
        if not self.browser_manager or not self.browser_manager.main_context:
            return None
            
        try:
            # Get cookies from browser context
            cookies = await self.browser_manager.main_context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # Extract CSRF token from page if available
            csrf_token = ""
            if self.browser_manager.game_page:
                try:
                    # Try to find CSRF token in common locations
                    csrf_selectors = [
                        'input[name="h"]',
                        'meta[name="csrf-token"]',
                        'input[name="_token"]'
                    ]
                    
                    for selector in csrf_selectors:
                        element = await self.browser_manager.game_page.query_selector(selector)
                        if element:
                            csrf_token = await element.get_attribute('value') or await element.get_attribute('content') or ""
                            if csrf_token:
                                break
                                
                    # If not found in attributes, try JavaScript
                    if not csrf_token:
                        try:
                            csrf_token = await self.browser_manager.game_page.evaluate("""
                                () => {
                                    // Common places for CSRF tokens
                                    const selectors = ['input[name="h"]', 'meta[name="csrf-token"]', '[data-csrf]'];
                                    for (const sel of selectors) {
                                        const el = document.querySelector(sel);
                                        if (el) {
                                            return el.value || el.content || el.dataset.csrf || '';
                                        }
                                    }
                                    
                                    // Look in window variables
                                    if (window.csrf_token) return window.csrf_token;
                                    if (window.game_data && window.game_data.csrf) return window.game_data.csrf;
                                    
                                    return '';
                                }
                            """) or ""
                        except:
                            pass
                            
                except Exception as e:
                    logger.debug(f"Could not extract CSRF token: {e}")
                    
            # Extract game data
            village_id = 0
            player_id = 0
            world_url = ""
            
            if self.browser_manager.game_page:
                try:
                    game_data = await self.browser_manager.game_page.evaluate("""
                        () => {
                            return {
                                village_id: window.game_data?.village?.id || 0,
                                player_id: window.game_data?.player?.id || 0,
                                world_url: window.location.origin || ''
                            };
                        }
                    """)
                    
                    village_id = game_data.get('village_id', 0)
                    player_id = game_data.get('player_id', 0)
                    world_url = game_data.get('world_url', '')
                    
                except Exception as e:
                    logger.debug(f"Could not extract game data: {e}")
                    
            # Use server config as fallback for world URL
            if not world_url:
                world_url = self.config.get('server', {}).get('base_url', '')
                
            return {
                'cookies': cookie_dict,
                'csrf_token': csrf_token,
                'village_id': village_id,
                'player_id': player_id,
                'world_url': world_url
            }
            
        except Exception as e:
            logger.error(f"Error extracting session data: {e}")
            return None
            
    def create_attack_builder(self) -> AttackBuilder:
        """Create an attack builder for easy attack scheduling"""
        if not self.client:
            raise RuntimeError("Sniper service not initialized")
        return AttackBuilder(self.client)
        
    async def schedule_attack(
        self,
        target_village_id: int,
        source_village_id: int,
        attack_type: str,
        units: Dict[str, int],
        execute_at: datetime,
        priority: int = 100
    ) -> Optional[str]:
        """Convenience method to schedule an attack"""
        if not self.client:
            logger.error("Sniper service not initialized")
            return None
            
        return await self.client.schedule_attack(
            target_village_id=target_village_id,
            source_village_id=source_village_id,
            attack_type=attack_type,
            units=units,
            execute_at=execute_at,
            priority=priority
        )
        
    async def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        if not self.client:
            return {"status": "not_initialized"}
            
        try:
            status = await self.client.get_status()
            status["process_running"] = self.process and self.process.poll() is None
            status["client_connected"] = not self.client.session.closed if self.client.session else False
            return status
        except Exception as e:
            return {"status": "error", "error": str(e)}
            
    async def list_scheduled_attacks(self) -> List[Dict[str, Any]]:
        """List all scheduled attacks"""
        if not self.client:
            logger.warning("⚠️ Sniper client not available for listing attacks")
            return []
        
        try:
            attacks = await self.client.list_attacks()
            logger.info(f"📋 Sniper client returned {len(attacks)} attacks")
            return attacks
        except Exception as e:
            logger.error(f"❌ Error getting attacks from client: {e}")
            return []
        
    async def cancel_attack(self, attack_id: str) -> bool:
        """Cancel a scheduled attack"""
        if not self.client:
            return False
        return await self.client.cancel_attack(attack_id)