#!/bin/bash
# YouTube MP3 Downloader - Startup Script

echo "🎵 YouTube MP3 Downloader"
echo "=========================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate venv
source venv/bin/activate

# Check if dependencies are installed
python -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Get local IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n1)
fi

echo "✅ Starting server..."
echo ""
echo "🖥️  Local:   http://localhost:8000"
if [ -n "$LOCAL_IP" ]; then
    echo "📱 Network: http://$LOCAL_IP:8000"
fi
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the app (module form, since app/main.py uses absolute `app.*` imports)
python -m app.main
