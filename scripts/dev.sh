#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
TASK_ROOT="$PWD"
TASK_ENV="$TASK_ROOT/.conda/ai-brain"
export PATH="$TASK_ENV/bin:$PATH"
# Some PDF/ONNX libraries otherwise load an older system C++ runtime first.
export LD_LIBRARY_PATH="$TASK_ENV/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$TASK_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
export NO_PROXY=localhost,127.0.0.1,::1
export no_proxy="$NO_PROXY"
TASK_FRONTEND_HOST=127.0.0.1
TASK_MODE="${1:-all}"
if [[ "$TASK_MODE" == lan ]]; then
  CORTEX_LAN_IP="$("$TASK_ENV/bin/python" "$TASK_ROOT/scripts/configure_lan.py")"
  export CORTEX_LAN_IP
  export AUTH_PUBLIC_ORIGIN=
  export AUTH_ALLOWED_HOSTS="[\"localhost\",\"127.0.0.1\",\"::1\",\"$CORTEX_LAN_IP\"]"
  export CORS_ORIGINS="[\"http://localhost:3000\",\"http://127.0.0.1:3000\",\"http://$CORTEX_LAN_IP:3000\"]"
  TASK_FRONTEND_HOST=0.0.0.0
  TASK_MODE=all
  echo "局域网地址：http://$CORTEX_LAN_IP:3000 · 仅用于可信局域网；请停止旧的 cloudflared 隧道"
fi
backend() { exec "$TASK_ENV/bin/python" -m uvicorn app.main:app --app-dir "$TASK_ROOT/backend" --host 127.0.0.1 --port 8000 --no-proxy-headers; }
frontend() { cd "$TASK_ROOT/frontend"; exec "$TASK_ENV/bin/node" node_modules/next/dist/bin/next dev --hostname "$TASK_FRONTEND_HOST" --port 3000; }
case "$TASK_MODE" in
  backend) backend ;;
  frontend) frontend ;;
  all)
    owned_pids=()
    cleanup() { for pid in "${owned_pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
    trap cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    backend & owned_pids+=("$!")
    frontend & owned_pids+=("$!")
    echo 'Cortex: http://localhost:3000 · 首次登录凭据：storage/initial-login.txt（仅本机可读，首次登录须修改密码）'
    wait -n "${owned_pids[@]}"
    ;;
  *) echo '用法：bash scripts/dev.sh [all|backend|frontend|lan]' >&2; exit 1 ;;
esac
