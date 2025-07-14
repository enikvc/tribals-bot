#!/usr/bin/env python3
"""
Cleanup utility for Tribals sniper service
Use this if the sniper service fails to start due to port conflicts
"""

import subprocess
import sys
import time

def kill_sniper_processes():
    """Kill any running sniper processes"""
    print("🔍 Looking for running sniper processes...")
    
    try:
        # Try to kill by process name
        result = subprocess.run(["pkill", "-f", "tribals-sniper"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Killed sniper processes by name")
        else:
            print("ℹ️ No sniper processes found by name")
    except FileNotFoundError:
        print("⚠️ pkill not available")
    
    # Try to kill processes on common ports
    ports = [9001, 9002, 9003, 9004, 9005]
    
    for port in ports:
        try:
            # Find processes using the port
            result = subprocess.run(["lsof", "-ti", f":{port}"], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        print(f"🔫 Killing process {pid} on port {port}")
                        subprocess.run(["kill", "-9", pid], check=True)
                    except subprocess.CalledProcessError:
                        print(f"⚠️ Could not kill process {pid}")
        except FileNotFoundError:
            print("⚠️ lsof not available")
            break
        except Exception as e:
            print(f"⚠️ Error checking port {port}: {e}")

def main():
    print("🎯 Tribals Sniper Cleanup Utility")
    print("=" * 40)
    
    kill_sniper_processes()
    
    print("\n⏳ Waiting 2 seconds for processes to terminate...")
    time.sleep(2)
    
    # Check if any processes are still running
    try:
        result = subprocess.run(["pgrep", "-f", "tribals-sniper"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("⚠️ Some sniper processes may still be running")
            print(f"PIDs: {result.stdout.strip()}")
        else:
            print("✅ All sniper processes cleaned up")
    except FileNotFoundError:
        print("ℹ️ Cannot verify cleanup (pgrep not available)")
    
    print("\n🚀 You can now restart the bot")
    print("=" * 40)

if __name__ == "__main__":
    main()