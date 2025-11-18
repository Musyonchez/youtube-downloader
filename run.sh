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
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo "✅ Starting server..."
echo ""
echo "🖥️  Local:   http://localhost:8000"
echo "📱 Network: http://$LOCAL_IP:8000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the app
python app.py
