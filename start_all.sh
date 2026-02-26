#!/bin/bash

# Configuration
LM_STUDIO_URL="http://localhost:1234/v1/models"
BACKEND_CMD="source venv/bin/activate && python Backend/server.py"
FRONTEND_CMD="cd frontend && npm run dev"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Testing connection to LM Studio...${NC}"

# Check if LM Studio API is responding
if curl -s --max-time 3 "$LM_STUDIO_URL" > /dev/null; then
    echo -e "${GREEN}✓ LM Studio is running and responding on port 1234.${NC}"
else
    echo -e "${RED}✗ Error: LM Studio is not responding.${NC}"
    echo -e "Please ensure LM Studio is open and the Local Server (port 1234) is started."
    exit 1
fi

echo -e "\n${YELLOW}Starting FastAPI Backend...${NC}"
# Start the backend in the background
eval "$BACKEND_CMD" &
BACKEND_PID=$!

# Wait a second for backend to initialize
sleep 2

echo -e "\n${YELLOW}Starting Vite Frontend...${NC}"
# Start the frontend in the background
eval "$FRONTEND_CMD" &
FRONTEND_PID=$!

echo -e "\n${GREEN}===========================================${NC}"
echo -e "${GREEN}All systems go!${NC}"
echo -e "Frontend: http://localhost:5173"
echo -e "Backend API: http://localhost:8000"
echo -e "${GREEN}===========================================${NC}"
echo -e "Press Ctrl+C to stop all servers."

# Trap SIGINT (Ctrl+C) and kill background processes
trap "echo -e '\n${YELLOW}Shutting down servers...${NC}'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT

# Keep script running to wait for background jobs
wait
