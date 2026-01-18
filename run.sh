#!/bin/bash

# Configuration
VENV_DIR="venv"
PORT=8501

echo "🚀 Initializing CrossAsset Financial Analysis Tool..."

# 1. Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 2. Activate virtual environment
source "$VENV_DIR/bin/activate"

# 3. Install dependencies
echo "📥 Installing/Updating dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Open browser (macOS)
echo "🌐 Launching browser..."
open "http://localhost:$PORT"

# 5. Run Streamlit app
nohup streamlit run app.py --server.port $PORT --browser.gatherUsageStats false > /dev/null 2>&1 &
echo "✅ Application running in background!"
