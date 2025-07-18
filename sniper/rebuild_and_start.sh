#!/bin/bash

echo "Building sniper service..."
cargo build --release

echo "Killing existing tribals-sniper processes..."
pkill -f tribals-sniper || true

echo "Starting tribals-sniper service..."
RUST_LOG=info ./target/release/tribals-sniper > /tmp/sniper_output.log 2>&1 &

echo "Waiting for service to start..."
sleep 2

echo "Testing service..."
curl http://127.0.0.1:9001/api/attacks

echo "Service started. Check logs at /tmp/sniper_output.log"