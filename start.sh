#!/bin/bash
# ============================================
# NDA Markup Tool - One-Click Startup Script
# ============================================
# Usage: ./start.sh
# This script installs all dependencies and
# starts both the backend and frontend servers.
# ============================================

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo ""
echo "========================================="
echo "  NDA Markup Tool - Starting Up..."
echo "========================================="
echo ""

# --- Check for API key ---
ENV_FILE="$BACKEND_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp "$BACKEND_DIR/.env.example" "$ENV_FILE"
fi

# Check if API key is set
if grep -q "your-api-key-here" "$ENV_FILE" 2>/dev/null; then
    echo "!! IMPORTANT: You need to set your Anthropic API key."
    echo ""
    echo "   1. Get an API key from: https://console.anthropic.com/settings/keys"
    echo "   2. Open the file: $ENV_FILE"
    echo "   3. Replace 'your-api-key-here' with your actual key"
    echo ""
    echo "   The app will start, but Claude analysis won't work"
    echo "   until you set the key and restart."
    echo ""
    read -p "   Press Enter to continue anyway, or Ctrl+C to stop... "
    echo ""
fi

# --- Install backend dependencies ---
echo "[1/4] Installing backend dependencies..."
cd "$BACKEND_DIR"
pip install -q -r requirements.txt 2>&1 | tail -1
echo "       Done."

# --- Install frontend dependencies ---
echo "[2/4] Installing frontend dependencies..."
cd "$FRONTEND_DIR"
npm install --silent 2>&1 | tail -1
echo "       Done."

# --- Start backend server ---
echo "[3/4] Starting backend server (port 5000)..."
cd "$BACKEND_DIR"
PYTHONPATH=. python run.py &
BACKEND_PID=$!
echo "       Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "       Waiting for backend..."
for i in $(seq 1 15); do
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo "       Backend is ready."
        break
    fi
    sleep 1
done

# --- Start frontend server ---
echo "[4/4] Starting frontend server (port 5173)..."
cd "$FRONTEND_DIR"
npx vite --host 2>&1 &
FRONTEND_PID=$!
echo "       Frontend PID: $FRONTEND_PID"

# Wait for frontend
sleep 3

echo ""
echo "========================================="
echo "  NDA Markup Tool is running!"
echo "========================================="
echo ""
echo "  Open your browser to:"
echo ""
echo "    http://localhost:5173"
echo ""
echo "  To stop the app, press Ctrl+C"
echo ""
echo "========================================="

# Handle shutdown
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "Stopped."
    exit 0
}

trap cleanup INT TERM

# Keep running
wait
