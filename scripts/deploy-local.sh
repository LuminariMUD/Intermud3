#!/usr/bin/env bash
#===============================================================================
#
#   ██╗███╗   ██╗████████╗███████╗██████╗ ███╗   ███╗██╗   ██╗██████╗ ███████╗
#   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║██║   ██║██╔══██╗╚════██║
#   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝██╔████╔██║██║   ██║██║  ██║    ██╔╝
#   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║   ██║██║  ██║   ██╔╝
#   ██║██║ ╚████║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║╚██████╔╝██████╔╝   ██║
#   ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═════╝    ╚═╝
#
#   ⚔️  GATEWAY OF THE REALMS  ⚔️
#   Bridging the Infinite Planes of MUD
#
#   Local Development Deployment Script
#===============================================================================

set -euo pipefail

#-------------------------------------------------------------------------------
# Configuration
#-------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/venv"
LOGS_DIR="$PROJECT_ROOT/logs"
STATE_DIR="$PROJECT_ROOT/state"
PID_DIR="$PROJECT_ROOT/.pids"

# Default ports (can be overridden by .env)
WS_PORT="${API_WS_PORT:-8080}"
TCP_PORT="${API_TCP_PORT:-8081}"
NGROK_PORT="${NGROK_INSPECTOR_PORT:-4042}"

# Colors for the arcane terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color
BOLD='\033[1m'
DIM='\033[2m'

#-------------------------------------------------------------------------------
# ASCII Art & Banners
#-------------------------------------------------------------------------------
show_banner() {
    echo -e "${PURPLE}"
    cat << 'EOF'

          ___________________________________________________________
         /                                                           \
        |    ░▒▓█ THE ANCIENT GATEWAY AWAKENS █▓▒░                   |
         \___________________________________________________________/
                                  ||
                             ___  ||  ___
                            /   \ || /   \
                           | ⚔️  | || |  ⚔️ |
                            \___/ || \___/
                                  ||
                    ╔═══════════════════════════════╗
                    ║                               ║
                    ║   🏰 INTERMUD-3 GATEWAY 🏰    ║
                    ║   ═══════════════════════     ║
                    ║   Connecting Realms Since     ║
                    ║   The Age of Telnet           ║
                    ║                               ║
                    ╚═══════════════════════════════╝
                           ╱╲      ╱╲      ╱╲
                          ╱  ╲    ╱  ╲    ╱  ╲
                         ╱    ╲  ╱    ╲  ╱    ╲
                        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓

EOF
    echo -e "${NC}"
}

show_quest_complete() {
    echo -e "${GREEN}"
    cat << 'EOF'

    ╔════════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║     ⚔️  QUEST COMPLETE: The Gateway Stands Ready! ⚔️           ║
    ║                                                                ║
    ║     The ancient portals hum with arcane energy.               ║
    ║     Adventurers from distant realms may now traverse          ║
    ║     the ethereal pathways of the Intermud Network.            ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝

EOF
    echo -e "${NC}"
}

show_quest_failed() {
    echo -e "${RED}"
    cat << 'EOF'

    ╔════════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║     💀 QUEST FAILED: The Gateway Could Not Be Summoned 💀     ║
    ║                                                                ║
    ║     Dark forces have disrupted the ritual.                    ║
    ║     Consult the scroll of errors above for guidance.          ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝

EOF
    echo -e "${NC}"
}

#-------------------------------------------------------------------------------
# Logging Functions
#-------------------------------------------------------------------------------
log_phase() {
    echo -e "\n${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${PURPLE}⚔️  ${WHITE}${BOLD}$1${NC}"
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

log_step() {
    echo -e "${CYAN}   ▸${NC} $1"
}

log_success() {
    echo -e "${GREEN}   ✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}   ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}   ✗${NC} $1"
}

log_info() {
    echo -e "${BLUE}   ℹ${NC} $1"
}

log_magic() {
    echo -e "${PURPLE}   ✨${NC} $1"
}

#-------------------------------------------------------------------------------
# Utility Functions
#-------------------------------------------------------------------------------
command_exists() {
    command -v "$1" &> /dev/null
}

get_port_process() {
    local port=$1
    lsof -i ":$port" -t 2>/dev/null || true
}

kill_port() {
    local port=$1
    local pids
    pids=$(get_port_process "$port")
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

is_port_available() {
    local port=$1
    ! lsof -i ":$port" &>/dev/null
}

wait_for_port() {
    local port=$1
    local max_attempts=${2:-30}
    local attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if lsof -i ":$port" &>/dev/null; then
            return 0
        fi
        sleep 1
        ((attempt++))
    done
    return 1
}

wait_for_health() {
    local url=$1
    local max_attempts=${2:-30}
    local attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if curl -sf "$url" &>/dev/null; then
            return 0
        fi
        sleep 1
        ((attempt++))
    done
    return 1
}

load_env() {
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        set -a
        source "$PROJECT_ROOT/.env"
        set +a
        WS_PORT="${API_WS_PORT:-8080}"
        TCP_PORT="${API_TCP_PORT:-8081}"
        NGROK_PORT="${NGROK_INSPECTOR_PORT:-4042}"
    fi
}

save_pid() {
    local name=$1
    local pid=$2
    mkdir -p "$PID_DIR"
    echo "$pid" > "$PID_DIR/${name}.pid"
}

get_saved_pid() {
    local name=$1
    local pidfile="$PID_DIR/${name}.pid"
    if [[ -f "$pidfile" ]]; then
        cat "$pidfile"
    fi
}

cleanup_pid() {
    local name=$1
    rm -f "$PID_DIR/${name}.pid" 2>/dev/null || true
}

#-------------------------------------------------------------------------------
# Pre-flight Checks
#-------------------------------------------------------------------------------
check_prerequisites() {
    log_phase "CHAPTER I: Gathering the Sacred Components"

    local missing=()

    log_step "Checking for Python 3.9+..."
    if command_exists python3; then
        local py_version
        py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        local py_major py_minor
        py_major=$(echo "$py_version" | cut -d. -f1)
        py_minor=$(echo "$py_version" | cut -d. -f2)
        if [[ $py_major -ge 3 && $py_minor -ge 9 ]]; then
            log_success "Python $py_version found - A worthy interpreter!"
        else
            log_error "Python $py_version found but 3.9+ required"
            missing+=("python3.9+")
        fi
    else
        log_error "Python3 not found"
        missing+=("python3")
    fi

    log_step "Checking for pip..."
    if command_exists pip3 || command_exists pip; then
        log_success "pip found - Package magic available!"
    else
        log_error "pip not found"
        missing+=("pip")
    fi

    log_step "Checking for ngrok..."
    if command_exists ngrok; then
        local ngrok_version
        ngrok_version=$(ngrok version 2>/dev/null | head -1)
        log_success "ngrok found - Tunnel enchantments ready! ($ngrok_version)"

        # Check ngrok auth
        if ngrok config check &>/dev/null; then
            log_success "ngrok configuration valid"
        else
            log_warning "ngrok config check failed - tunnels may not work"
        fi
    else
        log_warning "ngrok not found - tunnels will be unavailable"
    fi

    log_step "Checking for lsof (port inspection)..."
    if command_exists lsof; then
        log_success "lsof found - Port scrying enabled!"
    else
        log_warning "lsof not found - port checks will be limited"
    fi

    log_step "Checking for curl (health checks)..."
    if command_exists curl; then
        log_success "curl found - Health divination ready!"
    else
        log_warning "curl not found - health checks will be skipped"
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required components: ${missing[*]}"
        log_info "Install them and try again, brave adventurer."
        return 1
    fi

    log_magic "All sacred components gathered!"
    return 0
}

check_environment() {
    log_phase "CHAPTER II: Examining the Tome of Configuration"

    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        if [[ -f "$PROJECT_ROOT/.env.example" ]]; then
            log_warning ".env not found, but .env.example exists"
            log_info "Creating .env from .env.example..."
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
            log_warning "Please edit .env with your configuration before production use!"
        else
            log_error "No .env or .env.example found!"
            log_info "The gateway requires mystical configuration to function."
            return 1
        fi
    else
        log_success ".env configuration tome found!"
    fi

    # Load environment
    load_env

    # Validate critical variables
    local warnings=0

    if [[ -z "${MUD_NAME:-}" ]] || [[ "${MUD_NAME:-}" == "YourMUD" ]]; then
        log_warning "MUD_NAME not configured (using default)"
        ((warnings++))
    else
        log_success "MUD_NAME: ${MUD_NAME}"
    fi

    if [[ -z "${I3_GATEWAY_SECRET:-}" ]] || [[ "${I3_GATEWAY_SECRET:-}" == "your-secret-key-here" ]]; then
        log_warning "I3_GATEWAY_SECRET not configured - using default (INSECURE!)"
        ((warnings++))
    else
        log_success "I3_GATEWAY_SECRET: configured (hidden)"
    fi

    log_info "WebSocket Port: $WS_PORT"
    log_info "TCP Port: $TCP_PORT"
    log_info "ngrok Inspector Port: $NGROK_PORT"

    if [[ $warnings -gt 0 ]]; then
        log_warning "$warnings configuration warnings - review .env for production"
    fi

    # Check ngrok.yml
    if [[ -f "$PROJECT_ROOT/ngrok.yml" ]]; then
        log_success "ngrok.yml tunnel configuration found"
    else
        log_warning "ngrok.yml not found - tunnels will not be available"
    fi

    return 0
}

#-------------------------------------------------------------------------------
# Port Management
#-------------------------------------------------------------------------------
clear_ports() {
    log_phase "CHAPTER III: Banishing Port Demons"

    local ports=("$WS_PORT" "$TCP_PORT" "$NGROK_PORT")
    local cleared=0

    for port in "${ports[@]}"; do
        log_step "Checking port $port..."
        local pids
        pids=$(get_port_process "$port")

        if [[ -n "$pids" ]]; then
            log_warning "Port $port occupied by PID(s): $pids"
            read -t 10 -p "         Banish these processes? [Y/n] " -n 1 -r REPLY || REPLY="y"
            echo
            if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
                kill_port "$port"
                if is_port_available "$port"; then
                    log_success "Port $port has been liberated!"
                    ((cleared++))
                else
                    log_error "Failed to free port $port"
                    return 1
                fi
            else
                log_error "Port $port still occupied - cannot proceed"
                return 1
            fi
        else
            log_success "Port $port is free and clear"
        fi
    done

    if [[ $cleared -gt 0 ]]; then
        log_magic "$cleared port demon(s) banished!"
    else
        log_magic "All ports were already clear - the path is open!"
    fi

    return 0
}

#-------------------------------------------------------------------------------
# Virtual Environment
#-------------------------------------------------------------------------------
setup_virtualenv() {
    log_phase "CHAPTER IV: Conjuring the Python Realm"

    if [[ ! -d "$VENV_DIR" ]]; then
        log_step "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        log_success "Virtual realm manifested at $VENV_DIR"
    else
        log_success "Virtual realm already exists"
    fi

    log_step "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    log_success "Entered the virtual realm (Python: $(python --version 2>&1))"

    return 0
}

update_dependencies() {
    log_phase "CHAPTER V: Upgrading the Arsenal"

    log_step "Upgrading pip to latest..."
    pip install --upgrade pip --quiet
    log_success "pip upgraded to $(pip --version | cut -d' ' -f2)"

    log_step "Checking for outdated packages..."
    local outdated
    outdated=$(pip list --outdated --format=freeze 2>/dev/null | wc -l)

    if [[ $outdated -gt 0 ]]; then
        log_info "$outdated package(s) have newer versions available"
    fi

    log_step "Installing/updating requirements..."
    if pip install -r "$PROJECT_ROOT/requirements.txt" --quiet; then
        log_success "All dependencies installed!"
    else
        log_error "Failed to install dependencies"
        return 1
    fi

    # Check if requirements-dev.txt exists for dev dependencies
    if [[ -f "$PROJECT_ROOT/requirements-dev.txt" ]]; then
        log_step "Installing development dependencies..."
        if pip install -r "$PROJECT_ROOT/requirements-dev.txt" --quiet 2>/dev/null; then
            log_success "Development dependencies installed!"
        else
            log_warning "Some dev dependencies failed (non-critical)"
        fi
    fi

    log_magic "Arsenal fully upgraded and battle-ready!"
    return 0
}

#-------------------------------------------------------------------------------
# Directory Setup
#-------------------------------------------------------------------------------
setup_directories() {
    log_phase "CHAPTER VI: Preparing the Sanctum"

    local dirs=("$LOGS_DIR" "$STATE_DIR" "$PID_DIR")

    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_step "Creating $(basename "$dir")/ directory..."
            mkdir -p "$dir"
            log_success "$(basename "$dir")/ created"
        else
            log_success "$(basename "$dir")/ exists"
        fi
    done

    # Clean old log files if they're too large (> 100MB total)
    local log_size
    log_size=$(du -sm "$LOGS_DIR" 2>/dev/null | cut -f1 || echo "0")
    if [[ $log_size -gt 100 ]]; then
        log_warning "Log directory is ${log_size}MB - consider cleanup"
    fi

    log_magic "The sanctum is prepared!"
    return 0
}

#-------------------------------------------------------------------------------
# Service Management
#-------------------------------------------------------------------------------
start_gateway() {
    log_phase "CHAPTER VII: Awakening the Gateway"

    cd "$PROJECT_ROOT"
    source "$VENV_DIR/bin/activate"

    # Check if already running
    local existing_pid
    existing_pid=$(get_saved_pid "gateway")
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
        log_warning "Gateway already running (PID: $existing_pid)"
        read -t 10 -p "         Restart it? [Y/n] " -n 1 -r REPLY || REPLY="y"
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            kill "$existing_pid" 2>/dev/null || true
            sleep 2
        else
            log_info "Keeping existing gateway running"
            return 0
        fi
    fi

    log_step "Starting I3 Gateway daemon..."

    # Start in background with nohup
    nohup python -m src --debug > "$LOGS_DIR/gateway.log" 2>&1 &
    local gateway_pid=$!
    save_pid "gateway" "$gateway_pid"

    log_info "Gateway starting with PID: $gateway_pid"

    # Wait for startup
    log_step "Waiting for gateway to initialize..."
    local attempts=0
    local max_attempts=30

    while [[ $attempts -lt $max_attempts ]]; do
        if ! kill -0 "$gateway_pid" 2>/dev/null; then
            log_error "Gateway process died unexpectedly!"
            log_info "Check logs: tail -f $LOGS_DIR/gateway.log"
            return 1
        fi

        if command_exists curl && curl -sf "http://localhost:$WS_PORT/health" &>/dev/null; then
            break
        fi

        sleep 1
        ((attempts++))
        printf "\r${CYAN}   ▸${NC} Waiting for gateway... ${DIM}[${attempts}/${max_attempts}]${NC}"
    done
    echo

    if [[ $attempts -ge $max_attempts ]]; then
        log_warning "Gateway may not be fully ready - check logs"
    else
        log_success "Gateway is alive and responding!"
    fi

    # Show health status
    if command_exists curl; then
        local health
        health=$(curl -sf "http://localhost:$WS_PORT/health" 2>/dev/null || echo '{"status":"unknown"}')
        log_info "Health: $health"
    fi

    log_magic "The Gateway stirs with ancient power!"
    return 0
}

start_ngrok() {
    log_phase "CHAPTER VIII: Opening the Dimensional Tunnels"

    if ! command_exists ngrok; then
        log_warning "ngrok not installed - skipping tunnel creation"
        return 0
    fi

    if [[ ! -f "$PROJECT_ROOT/ngrok.yml" ]]; then
        log_warning "ngrok.yml not found - skipping tunnel creation"
        return 0
    fi

    # Check if already running
    local existing_pid
    existing_pid=$(get_saved_pid "ngrok")
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
        log_warning "ngrok already running (PID: $existing_pid)"
        read -t 10 -p "         Restart it? [Y/n] " -n 1 -r REPLY || REPLY="y"
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
            kill "$existing_pid" 2>/dev/null || true
            sleep 2
        else
            log_info "Keeping existing ngrok running"
            return 0
        fi
    fi

    log_step "Starting ngrok tunnels..."

    cd "$PROJECT_ROOT"
    nohup ngrok start --all --config ngrok.yml > "$LOGS_DIR/ngrok.log" 2>&1 &
    local ngrok_pid=$!
    save_pid "ngrok" "$ngrok_pid"

    log_info "ngrok starting with PID: $ngrok_pid"

    # Wait for ngrok API
    log_step "Waiting for tunnels to establish..."
    sleep 3

    if wait_for_port "$NGROK_PORT" 10; then
        log_success "ngrok API is responding!"

        # Show tunnel info
        if command_exists curl; then
            log_step "Fetching tunnel information..."
            sleep 2
            local tunnels
            tunnels=$(curl -sf "http://localhost:$NGROK_PORT/api/tunnels" 2>/dev/null || echo '{}')

            # Parse and display tunnel URLs
            if command_exists python3; then
                echo "$tunnels" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for t in tunnels:
        name = t.get('name', 'unknown')
        url = t.get('public_url', 'N/A')
        proto = t.get('proto', '?')
        print(f'   🌐 {name}: {url}')
except:
    print('   Unable to parse tunnel info')
" 2>/dev/null || log_info "Tunnel info: check http://localhost:$NGROK_PORT"
            fi
        fi
    else
        log_warning "ngrok may not be fully ready - check logs"
    fi

    log_magic "Dimensional rifts have been torn open!"
    return 0
}

#-------------------------------------------------------------------------------
# Final Summary
#-------------------------------------------------------------------------------
show_summary() {
    log_phase "CHAPTER IX: The Chronicle of Deployment"

    echo
    echo -e "${WHITE}${BOLD}Service Status:${NC}"

    # Gateway status
    local gateway_pid
    gateway_pid=$(get_saved_pid "gateway")
    if [[ -n "$gateway_pid" ]] && kill -0 "$gateway_pid" 2>/dev/null; then
        echo -e "   ${GREEN}●${NC} Gateway: Running (PID: $gateway_pid)"
    else
        echo -e "   ${RED}●${NC} Gateway: Not running"
    fi

    # ngrok status
    local ngrok_pid
    ngrok_pid=$(get_saved_pid "ngrok")
    if [[ -n "$ngrok_pid" ]] && kill -0 "$ngrok_pid" 2>/dev/null; then
        echo -e "   ${GREEN}●${NC} ngrok: Running (PID: $ngrok_pid)"
    else
        echo -e "   ${YELLOW}●${NC} ngrok: Not running"
    fi

    echo
    echo -e "${WHITE}${BOLD}Endpoints:${NC}"
    echo -e "   ${CYAN}Local WebSocket:${NC}  http://localhost:$WS_PORT"
    echo -e "   ${CYAN}Local TCP:${NC}        localhost:$TCP_PORT"
    echo -e "   ${CYAN}Health Check:${NC}     http://localhost:$WS_PORT/health"
    echo -e "   ${CYAN}ngrok Inspector:${NC}  http://localhost:$NGROK_PORT"

    echo
    echo -e "${WHITE}${BOLD}Useful Commands:${NC}"
    echo -e "   ${DIM}View gateway logs:${NC}  tail -f $LOGS_DIR/gateway.log"
    echo -e "   ${DIM}View ngrok logs:${NC}    tail -f $LOGS_DIR/ngrok.log"
    echo -e "   ${DIM}Stop services:${NC}      $SCRIPT_DIR/deploy-local.sh --stop"
    echo -e "   ${DIM}Check health:${NC}       curl http://localhost:$WS_PORT/health"

    echo
}

#-------------------------------------------------------------------------------
# Stop Services
#-------------------------------------------------------------------------------
stop_services() {
    log_phase "Closing the Gateway"

    # Stop gateway
    local gateway_pid
    gateway_pid=$(get_saved_pid "gateway")
    if [[ -n "$gateway_pid" ]]; then
        log_step "Stopping gateway (PID: $gateway_pid)..."
        kill "$gateway_pid" 2>/dev/null || true
        cleanup_pid "gateway"
        log_success "Gateway stopped"
    else
        log_info "Gateway was not running"
    fi

    # Stop ngrok
    local ngrok_pid
    ngrok_pid=$(get_saved_pid "ngrok")
    if [[ -n "$ngrok_pid" ]]; then
        log_step "Stopping ngrok (PID: $ngrok_pid)..."
        kill "$ngrok_pid" 2>/dev/null || true
        cleanup_pid "ngrok"
        log_success "ngrok stopped"
    else
        log_info "ngrok was not running"
    fi

    log_magic "The Gateway slumbers once more..."
    echo
    exit 0
}

#-------------------------------------------------------------------------------
# Status Check
#-------------------------------------------------------------------------------
check_status() {
    echo -e "\n${PURPLE}⚔️  I3 Gateway Status${NC}\n"

    # Gateway
    local gateway_pid
    gateway_pid=$(get_saved_pid "gateway")
    if [[ -n "$gateway_pid" ]] && kill -0 "$gateway_pid" 2>/dev/null; then
        echo -e "${GREEN}●${NC} Gateway: Running (PID: $gateway_pid)"
        if command_exists curl; then
            local health
            health=$(curl -sf "http://localhost:$WS_PORT/health" 2>/dev/null || echo "unreachable")
            echo -e "  Health: $health"
        fi
    else
        echo -e "${RED}●${NC} Gateway: Stopped"
    fi

    # ngrok
    local ngrok_pid
    ngrok_pid=$(get_saved_pid "ngrok")
    if [[ -n "$ngrok_pid" ]] && kill -0 "$ngrok_pid" 2>/dev/null; then
        echo -e "${GREEN}●${NC} ngrok: Running (PID: $ngrok_pid)"
    else
        echo -e "${YELLOW}●${NC} ngrok: Stopped"
    fi

    echo
    exit 0
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------
main() {
    cd "$PROJECT_ROOT"

    # Parse arguments
    case "${1:-}" in
        --stop|-s)
            load_env
            stop_services
            ;;
        --status|-t)
            load_env
            check_status
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo
            echo "Options:"
            echo "  --stop, -s     Stop all services"
            echo "  --status, -t   Check service status"
            echo "  --help, -h     Show this help"
            echo
            echo "Without options: Start the gateway and ngrok tunnels"
            exit 0
            ;;
    esac

    # Show banner
    show_banner

    # Run deployment steps
    if check_prerequisites && \
       check_environment && \
       clear_ports && \
       setup_virtualenv && \
       update_dependencies && \
       setup_directories && \
       start_gateway && \
       start_ngrok; then

        show_summary
        show_quest_complete

        echo -e "${DIM}May your packets flow swift and true, brave adventurer!${NC}"
        echo
    else
        show_quest_failed
        exit 1
    fi
}

# Run main
main "$@"
