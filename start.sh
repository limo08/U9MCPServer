#!/usr/bin/env bash
# =============================================================================
# u9-mcp 一键启动脚本
#
#   ./start.sh                 # 后台启动（默认 streamable-http，0.0.0.0:8000）
#   ./start.sh run             # 前台启动（systemd / supervisor / docker 用这个）
#   ./start.sh stop            # 停止
#   ./start.sh restart         # 重启
#   ./start.sh status          # 查看状态
#   ./start.sh logs            # 查看最近日志（持续跟踪：tail -f logs/u9-mcp.log）
#   ./start.sh check           # 检查 U9 / SQL Server 配置，不启动服务
#   ./start.sh install         # 创建 .venv 并安装依赖
#
# 常用参数（也可写在 .env 里）：
#   --transport stdio|sse|streamable-http   （默认 streamable-http）
#   --host 0.0.0.0                          （默认 0.0.0.0）
#   --port 8000                             （默认 8000）
#   --no-install                             缺少依赖时不自动安装
#
# 用友接口变量：U9_API_SERVER_URL / U9_API_CLIENT_ID / U9_API_CLIENT_SECRET /
#               U9_API_ENT_CODE / U9_API_ORG_CODE / U9_API_USERNAME
#               （或直接提供 U9_API_TOKEN）
# 运行变量：U9_MCP_TRANSPORT / U9_MCP_HOST / U9_MCP_PORT /
#           U9_MCP_LOG_FILE / U9_MCP_PID_FILE / U9_MCP_STATE_FILE /
#           U9_MCP_AUTO_INSTALL / MCP_USAGE_LOG
# =============================================================================

set -Eeuo pipefail

APP_NAME="u9-mcp"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# ── 读取 .env（已存在的环境变量优先，不会被 .env 覆盖）──────────────────────
if [[ -f "$BASE_DIR/.env" ]]; then
    # 记录当前已设置的环境变量，source 之后恢复，保证命令行/系统环境优先
    _saved_env="$(export -p)"
    set -a
    # 兼容 Windows 换行（CRLF）
    # shellcheck disable=SC1091
    source <(sed -e 's/\r$//' "$BASE_DIR/.env")
    set +a
    eval "$_saved_env"
    unset _saved_env
fi

TRANSPORT="${U9_MCP_TRANSPORT:-streamable-http}"
HOST="${U9_MCP_HOST:-0.0.0.0}"
PORT="${U9_MCP_PORT:-8000}"
PID_FILE="${U9_MCP_PID_FILE:-$BASE_DIR/.u9-mcp.pid}"
STATE_FILE="${U9_MCP_STATE_FILE:-$BASE_DIR/.u9-mcp.state}"
LOG_FILE="${U9_MCP_LOG_FILE:-$BASE_DIR/logs/u9-mcp.log}"
AUTO_INSTALL="${U9_MCP_AUTO_INSTALL:-1}"

COMMAND="start"
PYTHON_BIN=""

# ── 输出工具 ────────────────────────────────────────────────────────────────
# 注意：信息统一输出到 stderr。stdio 模式下 stdout 必须只跑 MCP 协议，
# 否则启动提示会破坏客户端与服务的 JSON-RPC 握手。
info() { printf '\033[32m[INFO]\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[33m[WARN]\033[0m %s\n' "$*" >&2; }
error() { printf '\033[31m[ERROR]\033[0m %s\n' "$*" >&2; }
die() { error "$*"; exit 1; }

usage() {
    cat <<'USAGE'
用法：./start.sh [命令] [参数]

命令：
  start              后台启动（默认，适合服务器）
  run                前台启动（适合 systemd / supervisor / docker）
  stop               停止服务
  restart            重启服务
  status             查看运行状态
  logs               查看最近 200 行日志
  check              检查 U9 / SQL Server 配置，不启动服务
  install            创建 .venv 并安装依赖

参数：
  --transport NAME   stdio | sse | streamable-http（默认 streamable-http）
  --host HOST        监听地址（默认 0.0.0.0）
  -p, --port PORT    监听端口（默认 8000）
  --no-install       缺少依赖时不自动安装
  -f, --foreground   等同于 run

示例：
  ./start.sh
  ./start.sh --port 9000
  ./start.sh run --transport sse --host 0.0.0.0 --port 8000

端点：
  streamable-http -> http://<host>:<port>/mcp
  sse             -> http://<host>:<port>/sse
USAGE
    exit 0
}

# ── 参数解析 ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --transport)      TRANSPORT="${2:?--transport 需要参数}"; shift 2 ;;
        --transport=*)    TRANSPORT="${1#*=}"; shift ;;
        --host)           HOST="${2:?--host 需要参数}"; shift 2 ;;
        --host=*)         HOST="${1#*=}"; shift ;;
        -p|--port)        PORT="${2:?--port 需要参数}"; shift 2 ;;
        --port=*)         PORT="${1#*=}"; shift ;;
        --foreground|-f)  COMMAND="run"; shift ;;
        --no-install)     AUTO_INSTALL=0; shift ;;
        -h|--help)        usage ;;
        start|run|stop|restart|status|logs|check|install)
                          COMMAND="$1"; shift ;;
        *)
            error "未知参数：$1"
            echo "使用 --help 查看用法"
            exit 2 ;;
    esac
done

case "$TRANSPORT" in
    stdio|sse|streamable-http) ;;
    *) die "无效的 transport：$TRANSPORT（可选：stdio / sse / streamable-http）" ;;
esac

# ── 选择 Python 解释器 ──────────────────────────────────────────────────────
pick_python() {
    if [[ -x "$BASE_DIR/.venv/bin/python" ]]; then
        PYTHON_BIN="$BASE_DIR/.venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    else
        die "未找到 python3，请先安装 Python 3.10+"
    fi
}

deps_ok() {
    "$PYTHON_BIN" -c "import mcp, httpx, pydantic" >/dev/null 2>&1
}

install_deps() {
    info "创建虚拟环境 .venv ..."
    local py="$PYTHON_BIN"
    [[ -x "$BASE_DIR/.venv/bin/python" ]] || "$py" -m venv "$BASE_DIR/.venv"
    PYTHON_BIN="$BASE_DIR/.venv/bin/python"
    info "安装依赖（pip install -e .）..."
    "$PYTHON_BIN" -m pip install --upgrade pip >/dev/null
    "$PYTHON_BIN" -m pip install -e "$BASE_DIR"
    info "依赖安装完成：$("$PYTHON_BIN" -V 2>&1)"
}

ensure_runtime() {
    pick_python
    if deps_ok; then
        return 0
    fi
    if [[ "$AUTO_INSTALL" == "1" ]]; then
        warn "检测到运行依赖缺失，自动执行安装（可用 --no-install 关闭）"
        install_deps
        deps_ok || die "依赖安装后仍无法导入 mcp/httpx/pydantic"
    else
        die "缺少运行依赖，请先执行：./start.sh install"
    fi
}

export_pythonpath() {
    export PYTHONPATH="$BASE_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
}

# ── 进程工具 ────────────────────────────────────────────────────────────────
pid_is_ours() {
    local pid="$1"
    # Linux 下校验命令行，避免 PID 复用导致误判/误杀
    if [[ -r "/proc/$pid/cmdline" ]]; then
        tr '\0' ' ' < "/proc/$pid/cmdline" | grep -Eq 'u9_mcp\.server|/u9-mcp( |$)'
        return
    fi
    return 0
}

get_pid() {
    [[ -f "$PID_FILE" ]] || return 1
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    pid_is_ours "$pid" || return 1
    echo "$pid"
}

write_state() {
    umask 077
    {
        printf 'TRANSPORT=%q\n' "$TRANSPORT"
        printf 'HOST=%q\n' "$HOST"
        printf 'PORT=%q\n' "$PORT"
    } > "$STATE_FILE"
}

load_state() {
    [[ -f "$STATE_FILE" ]] || return 0
    # shellcheck disable=SC1090
    source "$STATE_FILE"
}

port_in_use() {
    local check_host="$HOST"
    if [[ "$check_host" == "0.0.0.0" || "$check_host" == "::" ]]; then
        check_host="127.0.0.1"
    fi
    if command -v ss >/dev/null 2>&1; then
        ss -ltn "sport = :$PORT" 2>/dev/null | tail -n +2 | grep -q .
    else
        (exec 3<>"/dev/tcp/$check_host/$PORT") >/dev/null 2>&1
    fi
}

port_conflict_message() {
    error "端口 $PORT 已被占用，$APP_NAME 无法监听。"
    if command -v ss >/dev/null 2>&1; then
        ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print "       " $0}' >&2 || true
    fi
    error "请换一个端口，例如：./start.sh --port 8800"
    error "或修改 .env 中的 U9_MCP_PORT=8800，然后同步修改 MCP 客户端地址。"
    exit 1
}

endpoint_host() {
    if [[ "$HOST" == "0.0.0.0" || "$HOST" == "::" ]]; then
        echo "<服务器IP>"
    else
        echo "$HOST"
    fi
}

endpoint_hint() {
    case "$TRANSPORT" in
        sse)             echo "http://$(endpoint_host):$PORT/sse" ;;
        streamable-http) echo "http://$(endpoint_host):$PORT/mcp" ;;
        *)               echo "stdio（由 MCP 客户端作为子进程调用）" ;;
    esac
}

upstream_hint() {
    local url="${U9_API_SERVER_URL:-}"
    if [[ -n "$url" ]]; then
        echo "$url"
    elif [[ -n "${MCP_SQLSERVER_HOST:-}" ]]; then
        echo "未配置 U9_API_SERVER_URL（当前仅使用 SQL Server 直连）"
    else
        echo "未配置，请检查 .env 中的 U9_API_SERVER_URL"
    fi
}

print_endpoints() {
    if [[ "$TRANSPORT" == "stdio" ]]; then
        info "MCP 传输：stdio（由 MCP 客户端作为子进程调用）"
    else
        info "MCP 服务监听：$HOST:$PORT"
        info "MCP 客户端端点：$(endpoint_hint)"
    fi
    info "用友业务接口：$(upstream_hint)"
    if [[ "$TRANSPORT" != "stdio" ]]; then
        info "说明：客户端连「MCP 客户端端点」，MCP 服务再访问「用友业务接口」，两者地址不同"
    fi
}

wait_for_listen() {
    local pid="$1" i
    for i in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || return 1
        port_in_use && return 0
        sleep 0.25
    done
    return 1
}

start_foreground() {
    if [[ "$TRANSPORT" != "stdio" ]] && port_in_use; then
        port_conflict_message
    fi
    export_pythonpath
    info "前台启动 $APP_NAME（transport=$TRANSPORT, host=$HOST, port=$PORT）"
    print_endpoints
    exec "$PYTHON_BIN" -m u9_mcp.server --transport "$TRANSPORT" --host "$HOST" --port "$PORT"
}

start_background() {
    ensure_runtime

    local pid
    if pid="$(get_pid)"; then
        load_state
        warn "$APP_NAME 已在运行（PID $pid），无需重复启动"
        print_endpoints
        return 0
    fi
    rm -f "$PID_FILE" "$STATE_FILE"

    if [[ "$TRANSPORT" != "stdio" ]] && port_in_use; then
        port_conflict_message
    fi

    local log_dir pid_dir state_dir
    log_dir="$(dirname "$LOG_FILE")"
    pid_dir="$(dirname "$PID_FILE")"
    state_dir="$(dirname "$STATE_FILE")"
    local d
    for d in "$log_dir" "$pid_dir" "$state_dir"; do
        mkdir -p "$d" 2>/dev/null || die "无法创建目录：$d"
    done
    [[ -w "$log_dir" ]] || die "日志目录不可写：$log_dir（请检查 U9_MCP_LOG_FILE）"
    [[ -w "$pid_dir" ]] || die "PID 目录不可写：$pid_dir（请检查 U9_MCP_PID_FILE）"
    [[ -w "$state_dir" ]] || die "状态目录不可写：$state_dir（请检查 U9_MCP_STATE_FILE）"
    export_pythonpath

    info "启动 $APP_NAME（transport=$TRANSPORT, host=$HOST, port=$PORT）"
    nohup "$PYTHON_BIN" -m u9_mcp.server \
        --transport "$TRANSPORT" --host "$HOST" --port "$PORT" \
        >>"$LOG_FILE" 2>&1 &
    pid=$!
    echo "$pid" > "$PID_FILE"

    if [[ "$TRANSPORT" == "stdio" ]]; then
        sleep 1
        started=1
        kill -0 "$pid" 2>/dev/null || started=0
    else
        started=0
        wait_for_listen "$pid" && started=1
    fi
    if [[ "$started" != "1" ]]; then
        rm -f "$PID_FILE" "$STATE_FILE"
        error "启动失败：进程未存活或端口 $PORT 未监听。最近日志："
        tail -n 30 "$LOG_FILE" >&2 || true
        exit 1
    fi

    write_state
    info "启动成功（PID $pid）"
    print_endpoints
    info "日志：$LOG_FILE"
    info "停止：./start.sh stop    状态：./start.sh status"
}

stop_server() {
    local pid
    if ! pid="$(get_pid)"; then
        rm -f "$PID_FILE"
        info "$APP_NAME 未在运行"
        return 0
    fi
    info "停止 $APP_NAME（PID $pid）..."
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        warn "进程未在 10 秒内退出，强制结束"
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE" "$STATE_FILE"
    info "已停止"
}

status_server() {
    local pid
    if pid="$(get_pid)"; then
        load_state
        info "$APP_NAME 运行中（PID $pid）"
        print_endpoints
        info "日志：$LOG_FILE"
    else
        rm -f "$PID_FILE" "$STATE_FILE"
        info "$APP_NAME 未运行"
        return 1
    fi
}

show_logs() {
    [[ -f "$LOG_FILE" ]] || die "日志文件不存在：$LOG_FILE（服务可能还没启动过）"
    tail -n 200 "$LOG_FILE"
}

run_check() {
    ensure_runtime
    export_pythonpath
    info "检查配置（U9 接口 或 SQL Server 直连，至少一种可用）..."
    exec "$PYTHON_BIN" -m u9_mcp.server --check
}

# ── 主流程 ──────────────────────────────────────────────────────────────────
case "$COMMAND" in
    install)
        pick_python
        install_deps
        ;;
    run)
        ensure_runtime
        start_foreground
        ;;
    start)
        start_background
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        start_background
        ;;
    status)
        status_server
        ;;
    logs)
        show_logs
        ;;
    check)
        run_check
        ;;
    *)
        die "未知命令：$COMMAND"
        ;;
esac
