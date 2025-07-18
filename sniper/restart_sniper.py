#!/usr/bin/env python3

import subprocess
import time
import os
import sys

def run_command(cmd, description):
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    # Change to sniper directory
    os.chdir('/Users/maringlen.kovaci/tribals/tribals-bot-python/sniper')
    print(f"Working directory: {os.getcwd()}")
    
    # 1. Build the project
    print("\n1. Building the sniper service...")
    if not run_command("cargo build --release", "Building Rust project"):
        print("Build failed! Continuing anyway...")
    
    # 2. Kill any existing processes
    print("\n2. Killing existing tribals-sniper processes...")
    run_command("pkill -f tribals-sniper", "Killing existing processes")
    time.sleep(1)
    
    # 3. Start the service
    print("\n3. Starting the tribals-sniper service...")
    log_file = "/tmp/sniper_output.log"
    cmd = f"RUST_LOG=info ./target/release/tribals-sniper > {log_file} 2>&1 &"
    if run_command(cmd, "Starting service"):
        print(f"Service started! Logs are being written to {log_file}")
    else:
        print("Failed to start service!")
        return
    
    # 4. Wait for service to initialize
    print("\n4. Waiting for service to start...")
    time.sleep(3)
    
    # 5. Test the service
    print("\n5. Testing the service...")
    if run_command("curl -s http://127.0.0.1:9001/api/attacks", "Testing /api/attacks endpoint"):
        print("Service is responding!")
    else:
        print("Service is not responding!")
    
    # 6. Check if process is running
    print("\n6. Checking if process is running...")
    run_command("ps aux | grep tribals-sniper | grep -v grep", "Checking process")
    
    # 7. Show recent logs
    print(f"\n7. Recent logs from {log_file}:")
    run_command(f"tail -20 {log_file}", "Showing recent logs")

if __name__ == "__main__":
    main()