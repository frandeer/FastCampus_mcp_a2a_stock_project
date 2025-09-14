#!/bin/bash

# Universal Platform Demo Application Startup Script

echo "🚀 Starting Universal Platform Demo Application..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo "❌ Please run this script from the demo_app directory"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Set environment variables for demo
export ENVIRONMENT=development
export LOG_LEVEL=INFO
export HOST=0.0.0.0
export PORT=8000

echo "🔧 Configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Log Level: $LOG_LEVEL"

# Start the application
echo "✅ Starting application..."
echo "📍 Access the demo at: http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo "⚙️  Admin Dashboard: http://localhost:8000/admin"
echo "❤️  Health Check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the application"
echo ""

python3 main.py