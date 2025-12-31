#!/bin/bash

# BeatVegas Platform - Quick Start Script
# This script sets up and runs the entire BeatVegas & Omni Edge AI platform

set -e  # Exit on error

echo "🚀 BeatVegas & Omni Edge AI Platform - Quick Start"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if MongoDB is running
echo -e "${BLUE}Checking MongoDB...${NC}"
if ! pgrep -x "mongod" > /dev/null; then
    echo -e "${RED}✗ MongoDB is not running${NC}"
    echo "Please start MongoDB first:"
    echo "  macOS: brew services start mongodb-community"
    echo "  Linux: sudo systemctl start mongod"
    echo "  Docker: docker run -d -p 27017:27017 --name mongodb mongo:latest"
    exit 1
else
    echo -e "${GREEN}✓ MongoDB is running${NC}"
fi

# Check if virtual environment exists
echo -e "${BLUE}Checking Python virtual environment...${NC}"
if [ ! -d "backend/.venv" ]; then
    echo "Creating virtual environment..."
    cd backend
    python3 -m venv .venv
    cd ..
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate virtual environment and install dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
cd backend
source .venv/bin/activate

# Check if requirements have changed
if [ ! -f ".venv/.installed" ] || [ "requirements.txt" -nt ".venv/.installed" ]; then
    pip install -r requirements.txt --quiet
    touch .venv/.installed
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies up to date${NC}"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ .env file not found${NC}"
    echo "Please create a .env file with required configuration"
    echo "See .env for reference"
    exit 1
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi

# Start the backend server
echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}Starting BeatVegas Backend Server...${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo "Features enabled:"
echo "  ✓ A/B Testing (5 variants, 90-day tracking)"
echo "  ✓ Affiliate Viral Loop (zero-ad spend growth)"
echo "  ✓ Module 7: Reflection Loop (self-improving AI)"
echo "  ✓ Community Data Pipeline (NLP + Reputation)"
echo "  ✓ Hybrid AI (odds + weighted sentiment)"
echo "  ✓ Auto Odds Polling - ALL SPORTS (15m intervals)"
echo ""
echo "API Documentation: http://localhost:8000/docs"
echo "Health Check: http://localhost:8000/health"
echo ""
echo -e "${BLUE}Press Ctrl+C to stop the server${NC}"
echo ""

# Run the FastAPI server with PYTHONPATH set
PYTHONPATH=$(pwd) uvicorn main:app --reload --port 8000 --host 0.0.0.0
