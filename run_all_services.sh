#!/bin/bash

# Run all services concurrently using tmux
# This script creates a tmux session with 3 panes for all services

SESSION_NAME="monitoring-system"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux is not installed. Install it with: sudo apt install tmux"
    exit 1
fi

# Kill existing session if it exists
tmux kill-session -t $SESSION_NAME 2>/dev/null || true

echo "🚀 Starting all services in tmux session '$SESSION_NAME'..."

# Create new session with first window (FastAPI)
tmux new-session -d -s $SESSION_NAME -n "monitoring"

# Pane 0: FastAPI Server
tmux send-keys -t $SESSION_NAME:0.0 "cd /home/run/Documents/langgraph/monitoring-agent" C-m
tmux send-keys -t $SESSION_NAME:0.0 "source .venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME:0.0 "echo '🌐 Starting FastAPI Server...'" C-m
tmux send-keys -t $SESSION_NAME:0.0 "python3 -m uvicorn app.main:app --reload --port 8000" C-m

# Split horizontally for Celery Worker
tmux split-window -h -t $SESSION_NAME:0
tmux send-keys -t $SESSION_NAME:0.1 "cd /home/run/Documents/langgraph/monitoring-agent" C-m
tmux send-keys -t $SESSION_NAME:0.1 "source .venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME:0.1 "sleep 3" C-m
tmux send-keys -t $SESSION_NAME:0.1 "echo '👷 Starting Celery Worker...'" C-m
tmux send-keys -t $SESSION_NAME:0.1 "celery -A app.agents.schedule:celery_app worker --loglevel=info" C-m

# Split the right pane vertically for Celery Beat
tmux split-window -v -t $SESSION_NAME:0.1
tmux send-keys -t $SESSION_NAME:0.2 "cd /home/run/Documents/langgraph/monitoring-agent" C-m
tmux send-keys -t $SESSION_NAME:0.2 "source .venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME:0.2 "sleep 5" C-m
tmux send-keys -t $SESSION_NAME:0.2 "echo '⏰ Starting Celery Beat Scheduler...'" C-m
tmux send-keys -t $SESSION_NAME:0.2 "celery -A app.agents.schedule:celery_app beat --loglevel=info" C-m

# Adjust pane sizes
tmux select-layout -t $SESSION_NAME:0 main-vertical

echo ""
echo "✅ All services started in tmux session!"
echo ""
echo "📋 Useful commands:"
echo "  Attach to session:     tmux attach -t $SESSION_NAME"
echo "  Detach from session:   Ctrl+B then D"
echo "  Switch panes:          Ctrl+B then arrow keys"
echo "  Kill session:          tmux kill-session -t $SESSION_NAME"
echo ""
echo "🌐 API will be available at: http://localhost:8000"
echo "📖 API docs: http://localhost:8000/docs"
echo ""
echo "Attaching to session in 2 seconds..."
sleep 2

# Attach to the session
tmux attach -t $SESSION_NAME
