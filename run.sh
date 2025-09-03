#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
print_success() { printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"; }
print_warning() { printf "${YELLOW}[WARNING]${NC} %s\n" "$1"; }
print_error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to show help
show_help() {
    printf "${CYAN}Pipecat Client-Server Quickstart Runner${NC}\n\n"
    printf "${GREEN}USAGE:${NC}\n"
    printf "    ./run.sh [OPTIONS]\n\n"
    printf "${GREEN}DESCRIPTION:${NC}\n"
    printf "    This script automates the complete setup and execution of the Pipecat client-server\n"
    printf "    application. It handles dependency installation, environment validation, and service\n"
    printf "    orchestration.\n\n"
    printf "${GREEN}SCENARIO OPTIONS:${NC}\n"
    printf "    --card        Lost Card scenario (Sarah Chen) - Family time pressure, immediate\n"
    printf "                  access to funds needed. ${YELLOW}[Default]${NC}\n\n"
    printf "    --transfer    Failed Transfer scenario (Marcus Williams) - IRS payment stuck,\n"
    printf "                  deadline-driven escalation.\n\n"
    printf "    --account     Account Locked scenario (Janet Rodriguez) - Payroll blocked,\n"
    printf "                  employees awaiting paychecks.\n\n"
    printf "${GREEN}OTHER OPTIONS:${NC}\n"
    printf "    --help, -h    Show this help message and exit\n"
    printf "    --skip-deps   Skip dependency installation (use if already installed)\n"
    printf "    --verbose     Show detailed output from services\n\n"
    printf "${GREEN}WHAT THIS SCRIPT DOES:${NC}\n"
    printf "    1. ${BLUE}Prerequisites Check & Install:${NC}\n"
    printf "       - Installs 'uv' (Python package manager) if missing\n"
    printf "       - Installs 'pnpm' (Node package manager) via nvm if missing\n\n"
    printf "    2. ${BLUE}Environment Setup:${NC}\n"
    printf "       - Validates .env file and all required API keys\n"
    printf "       - Auto-generates Langfuse OTLP auth headers (base64 encoded)\n"
    printf "       - Configures tracing if enabled\n\n"
    printf "    3. ${BLUE}Port Management:${NC}\n"
    printf "       - Cleans up ports 5173 (client) and 7860 (server)\n"
    printf "       - Ensures no conflicting processes are running\n\n"
    printf "    4. ${BLUE}Dependency Installation:${NC}\n"
    printf "       - Python: runs 'uv sync' in server directory\n"
    printf "       - Node.js: runs 'pnpm install' in client directory\n\n"
    printf "    5. ${BLUE}Service Orchestration:${NC}\n"
    printf "       - Starts Python bot server with selected scenario\n"
    printf "       - Starts React client development server\n"
    printf "       - Manages logging to ./logs/ directory\n"
    printf "       - Provides graceful shutdown on Ctrl+C\n\n"
    printf "${GREEN}REQUIRED ENVIRONMENT VARIABLES:${NC}\n"
    printf "    The following must be set in server/.env:\n"
    printf "    - DEEPGRAM_API_KEY     (Speech-to-Text)\n"
    printf "    - OPENAI_API_KEY       (Language Model)\n"
    printf "    - ELEVENLABS_API_KEY   (Text-to-Speech)\n"
    printf "    - ELEVENLABS_VOICE_ID  (Voice selection)\n"
    printf "    - GEMINI_API_KEY       (Coach evaluation)\n\n"
    printf "    Optional for tracing:\n"
    printf "    - LANGFUSE_SECRET_KEY  (Observability)\n"
    printf "    - LANGFUSE_PUBLIC_KEY  (Observability)\n"
    printf "    - ENABLE_TRACING       (true/false)\n\n"
    printf "${GREEN}EXAMPLES:${NC}\n"
    printf "    # Run with default scenario (card)\n"
    printf "    ./run.sh\n\n"
    printf "    # Run with transfer scenario\n"
    printf "    ./run.sh --transfer\n\n"
    printf "    # Run with account locked scenario\n"
    printf "    ./run.sh --account\n\n"
    printf "    # Skip dependency installation (faster startup)\n"
    printf "    ./run.sh --skip-deps --card\n\n"
    printf "${GREEN}ACCESS URLS:${NC}\n"
    printf "    Once running, access the application at:\n"
    printf "    - Client UI: ${CYAN}http://localhost:5173${NC}\n"
    printf "    - Server API: ${CYAN}http://localhost:7860${NC}\n"
    printf "    - Coach Feedback: ${CYAN}http://localhost:8090${NC}\n"
    printf "    - Langfuse: ${CYAN}https://cloud.langfuse.com${NC} (if tracing enabled)\n\n"
    printf "${GREEN}TROUBLESHOOTING:${NC}\n"
    printf "    - Check logs in ./logs/server.log, ./logs/client.log, and ./logs/feedback_viewer.log\n"
    printf "    - Ensure all API keys are valid in server/.env\n"
    printf "    - Try running with --verbose for detailed output\n"
    printf "    - Kill stuck processes: lsof -ti tcp:5173,7860,8090 | xargs kill -9\n\n"
    printf "${YELLOW}Press Ctrl+C at any time to stop all services${NC}\n\n"
    exit 0
}

# Parse arguments
SCENARIO_ARG=""
SKIP_DEPS=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            ;;
        --card)
            SCENARIO_ARG="--card"
            shift
            ;;
        --transfer)
            SCENARIO_ARG="--transfer"
            shift
            ;;
        --account)
            SCENARIO_ARG="--account"
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set default scenario if not specified
if [ -z "$SCENARIO_ARG" ]; then
    SCENARIO_ARG="--card"
    print_status "Using default scenario: Lost Card (use --help to see other options)"
fi

# Banner
printf "\n"
printf "==================================================\n"
printf "   ${CYAN}Pipecat Client-Server Quickstart${NC}\n"
printf "==================================================\n"
printf "   Scenario: ${YELLOW}%s${NC}\n" "${SCENARIO_ARG#--}"
printf "==================================================\n"
printf "\n"

# Step 1: Check and install uv if needed
if [ "$SKIP_DEPS" = false ]; then
    print_status "Checking for uv (Python package manager)..."
    if ! command_exists uv; then
        print_warning "uv not found. Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Add uv to PATH for current session
        export PATH="$HOME/.cargo/bin:$PATH"
        
        if command_exists uv; then
            print_success "uv installed successfully ($(uv --version))"
        else
            print_error "Failed to install uv. Please install manually from https://docs.astral.sh/uv/"
            exit 1
        fi
    else
        print_success "uv is already installed ($(uv --version))"
    fi

    # Step 2: Check and install pnpm if needed
    print_status "Checking for pnpm (Node package manager)..."
    if ! command_exists pnpm; then
        print_warning "pnpm not found. Installing nvm, Node.js, and pnpm..."
        
        # Check for nvm
        if ! command_exists nvm; then
            print_status "Installing nvm..."
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
            
            # Load nvm for current session
            export NVM_DIR="$HOME/.nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
        fi
        
        # Install latest Node.js
        print_status "Installing latest Node.js..."
        nvm install node
        nvm use node
        
        # Install pnpm globally
        print_status "Installing pnpm globally..."
        npm install -g pnpm
        
        if command_exists pnpm; then
            print_success "pnpm installed successfully ($(pnpm --version))"
        else
            print_error "Failed to install pnpm"
            exit 1
        fi
    else
        print_success "pnpm is already installed ($(pnpm --version))"
    fi
else
    print_status "Skipping dependency checks (--skip-deps flag set)"
fi

# Step 3: Kill any existing processes on required ports
print_status "Checking for processes on ports 5173, 7860, and 8090..."

# Kill processes on port 5173 (client)
if lsof -ti tcp:5173 > /dev/null 2>&1; then
    print_warning "Killing process on port 5173..."
    lsof -ti tcp:5173 | xargs kill -9 2>/dev/null || true
    print_success "Port 5173 cleared"
fi

# Kill processes on port 7860 (server)
if lsof -ti tcp:7860 > /dev/null 2>&1; then
    print_warning "Killing process on port 7860..."
    lsof -ti tcp:7860 | xargs kill -9 2>/dev/null || true
    print_success "Port 7860 cleared"
fi

# Kill processes on port 8090 (feedback viewer)
if lsof -ti tcp:8090 > /dev/null 2>&1; then
    print_warning "Killing process on port 8090..."
    lsof -ti tcp:8090 | xargs kill -9 2>/dev/null || true
    print_success "Port 8090 cleared"
fi

# Step 4: Validate .env file
print_status "Checking environment configuration..."

ENV_FILE="server/.env"
ENV_EXAMPLE="server/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        print_warning ".env file not found. Creating from .env.example..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        print_error "Please edit $ENV_FILE and add your API keys before running again."
        exit 1
    else
        print_error "Neither .env nor .env.example found in server directory"
        exit 1
    fi
fi

# Source the .env file
set -a
source "$ENV_FILE"
set +a

# Check required environment variables
REQUIRED_VARS=(
    "DEEPGRAM_API_KEY"
    "OPENAI_API_KEY"
    "ELEVENLABS_API_KEY"
    "ELEVENLABS_VOICE_ID"
    "GEMINI_API_KEY"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ] || [[ "${!var}" == *"your_"*"_here"* ]]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    print_error "Missing or invalid environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    print_warning "Please edit $ENV_FILE and add your API keys"
    exit 1
fi

print_success "All required environment variables are set"

# Step 5: Configure Langfuse tracing if enabled
if [ "$ENABLE_TRACING" = "true" ]; then
    print_status "Configuring Langfuse tracing..."
    
    # Check Langfuse credentials
    if [ -z "$LANGFUSE_PUBLIC_KEY" ] || [ -z "$LANGFUSE_SECRET_KEY" ]; then
        print_warning "Langfuse credentials not found. Disabling tracing..."
        export ENABLE_TRACING=false
    else
        # Generate base64 encoded auth header
        AUTH_STRING="${LANGFUSE_PUBLIC_KEY}:${LANGFUSE_SECRET_KEY}"
        ENCODED_AUTH=$(echo -n "$AUTH_STRING" | base64)
        export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20${ENCODED_AUTH}"
        
        # Write the header back to .env for persistence
        # First, remove any existing OTEL_EXPORTER_OTLP_HEADERS line (including comments)
        sed -i.bak '/^[#]*.*OTEL_EXPORTER_OTLP_HEADERS=/d' "$ENV_FILE"
        rm -f "$ENV_FILE.bak"
        
        # Ensure file ends with newline
        [[ $(tail -c1 "$ENV_FILE" | wc -l) -eq 0 ]] && echo >> "$ENV_FILE"
        
        # Append the new header
        printf "OTEL_EXPORTER_OTLP_HEADERS=\"Authorization=Basic%%20%s\"\n" "${ENCODED_AUTH}" >> "$ENV_FILE"
        
        print_success "Langfuse tracing configured with auth headers"
    fi
else
    print_status "Tracing is disabled (set ENABLE_TRACING=true to enable)"
fi

# Step 6: Install dependencies if not skipped
if [ "$SKIP_DEPS" = false ]; then
    # Install Python dependencies
    print_status "Installing Python dependencies..."
    cd server
    if [ "$VERBOSE" = true ]; then
        uv sync
    else
        uv sync > /dev/null 2>&1
    fi
    cd ..
    print_success "Python dependencies installed"

    # Install Node dependencies
    print_status "Installing Node.js dependencies..."
    cd client
    if [ "$VERBOSE" = true ]; then
        pnpm install
    else
        pnpm install > /dev/null 2>&1
    fi
    cd ..
    print_success "Node.js dependencies installed"
else
    print_status "Skipping dependency installation"
fi

# Step 7: Create log directory
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

# Step 8: Function to cleanup on exit
cleanup() {
    echo ""
    print_status "Shutting down services..."
    
    # Kill server if running
    if [ ! -z "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        print_success "Server stopped"
    fi
    
    # Kill client if running
    if [ ! -z "$CLIENT_PID" ] && kill -0 "$CLIENT_PID" 2>/dev/null; then
        kill "$CLIENT_PID" 2>/dev/null || true
        print_success "Client stopped"
    fi
    
    # Kill feedback viewer if running
    if [ ! -z "$VIEWER_PID" ] && kill -0 "$VIEWER_PID" 2>/dev/null; then
        kill "$VIEWER_PID" 2>/dev/null || true
        print_success "Feedback viewer stopped"
    fi
    
    # Clean up any remaining processes
    lsof -ti tcp:7860 | xargs kill -9 2>/dev/null || true
    lsof -ti tcp:5173 | xargs kill -9 2>/dev/null || true
    lsof -ti tcp:8090 | xargs kill -9 2>/dev/null || true
    
    print_success "All services stopped"
    echo ""
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

# Step 9: Start the server with scenario argument
print_status "Starting Python server with ${SCENARIO_ARG#--} scenario..."
cd server
if [ "$VERBOSE" = true ]; then
    uv run bot.py $SCENARIO_ARG 2>&1 | tee "../$LOG_DIR/server.log" &
    SERVER_PID=$!
else
    uv run bot.py $SCENARIO_ARG > "../$LOG_DIR/server.log" 2>&1 &
    SERVER_PID=$!
fi
cd ..

# Wait for server to start
sleep 3
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    print_error "Server failed to start. Check $LOG_DIR/server.log for errors"
    echo ""
    echo "Last 20 lines of server log:"
    tail -20 "$LOG_DIR/server.log"
    exit 1
fi
print_success "Server started (PID: $SERVER_PID)"

# Step 10: Start the client
print_status "Starting React client..."
cd client
if [ "$VERBOSE" = true ]; then
    pnpm run dev 2>&1 | tee "../$LOG_DIR/client.log" &
    CLIENT_PID=$!
else
    pnpm run dev > "../$LOG_DIR/client.log" 2>&1 &
    CLIENT_PID=$!
fi
cd ..

# Wait for client to start
sleep 3
if ! kill -0 "$CLIENT_PID" 2>/dev/null; then
    print_error "Client failed to start. Check $LOG_DIR/client.log for errors"
    echo ""
    echo "Last 20 lines of client log:"
    tail -20 "$LOG_DIR/client.log"
    exit 1
fi
print_success "Client started (PID: $CLIENT_PID)"

# Step 11: Start the feedback viewer
print_status "Starting Coach Feedback Viewer..."
cd server
if [ "$VERBOSE" = true ]; then
    uv run feedback_viewer.py --port 8090 2>&1 | tee "../$LOG_DIR/feedback_viewer.log" &
    VIEWER_PID=$!
else
    uv run feedback_viewer.py --port 8090 > "../$LOG_DIR/feedback_viewer.log" 2>&1 &
    VIEWER_PID=$!
fi
cd ..

# Wait for viewer to start
sleep 2
if ! kill -0 "$VIEWER_PID" 2>/dev/null; then
    print_warning "Feedback viewer failed to start (non-critical). Check $LOG_DIR/feedback_viewer.log for details"
else
    print_success "Feedback viewer started (PID: $VIEWER_PID)"
fi

# Step 12: Display success message
printf "\n"
printf "==================================================\n"
printf "${GREEN}   Services Successfully Started!${NC}\n"
printf "==================================================\n"
printf "\n"
printf "${BLUE}Scenario:${NC}       ${YELLOW}%s${NC}\n" "${SCENARIO_ARG#--}"
printf "${BLUE}Client UI:${NC}      ${CYAN}http://localhost:5173${NC}\n"
printf "${BLUE}Server:${NC}         ${CYAN}http://localhost:7860${NC}\n"
printf "${BLUE}Coach Feedback:${NC} ${CYAN}http://localhost:8090${NC}\n"
printf "\n"
if [ "$ENABLE_TRACING" = "true" ] && [ ! -z "$LANGFUSE_HOST" ]; then
    printf "${BLUE}Langfuse:${NC}  ${CYAN}%s${NC}\n" "$LANGFUSE_HOST"
    printf "\n"
fi
printf "${YELLOW}Logs:${NC}\n"
printf "  - Server:  %s/server.log\n" "$LOG_DIR"
printf "  - Client:  %s/client.log\n" "$LOG_DIR"
printf "  - Viewer:  %s/feedback_viewer.log\n" "$LOG_DIR"
printf "\n"
if [ "$VERBOSE" = true ]; then
    printf "${CYAN}Running in verbose mode - showing service output${NC}\n"
    printf "\n"
fi
printf "${YELLOW}Press Ctrl+C to stop all services${NC}\n"
printf "\n"

# Keep script running
wait