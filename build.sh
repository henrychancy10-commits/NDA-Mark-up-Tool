#!/usr/bin/env bash
# Build script for Render deployment
# This runs during the build phase

set -e

echo "=== Installing backend dependencies ==="
cd backend
pip install -r requirements.txt

echo "=== Installing frontend dependencies ==="
cd ../frontend
npm install

echo "=== Building frontend ==="
npx vite build

echo "=== Build complete ==="
