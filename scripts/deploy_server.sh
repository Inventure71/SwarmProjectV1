#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Deploy, build, and run Hydra supervisor stack on one server.

Usage:
  ./scripts/deploy_server.sh --host <ip> --user <username> [options]

Required:
  --host <ip>               Server host/IP
  --user <username>         SSH username on server
  --ros-setup <path>        Remote ROS setup script (required)

Options:
  --repo-root <path>        Local repo root (default: auto-detected)
  --remote-root <path>      Remote install root (default: /home/<user>/hydra)
  --supervisor-ip <ip>      Update HYDRA_CONFIG.supervisor_host before sync
  --use-rosdep              Deprecated no-op (dependencies are always installed)
  --no-clean                Do not remove build/install/log before colcon build
  --no-run                  Build/sync only, do not launch supervisor bridge
  -h, --help                Show this help
EOF
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST=""
USER_NAME=""
REMOTE_ROOT=""
ROS_SETUP=""
SUPERVISOR_IP=""
CLEAN_BUILD=1
RUN_AFTER=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --repo-root) REPO_ROOT="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --ros-setup) ROS_SETUP="$2"; shift 2 ;;
    --supervisor-ip) SUPERVISOR_IP="$2"; shift 2 ;;
    --use-rosdep) echo "[server] --use-rosdep is deprecated; dependencies are always installed."; shift ;;
    --no-clean) CLEAN_BUILD=0; shift ;;
    --no-run) RUN_AFTER=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$ROS_SETUP" ]]; then
  echo "Missing required arguments." >&2
  usage
  exit 1
fi

if [[ -z "$REMOTE_ROOT" ]]; then
  REMOTE_ROOT="/home/$USER_NAME/hydra"
fi

if [[ -n "$SUPERVISOR_IP" ]]; then
  python3 - "$REPO_ROOT/config/fleet.json" "$SUPERVISOR_IP" <<'EOF'
import ipaddress
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1]).resolve()
ip = sys.argv[2]
ipaddress.ip_address(ip)
raw = json.loads(cfg_path.read_text(encoding="utf-8"))
raw.setdefault("HYDRA_CONFIG", {})["supervisor_host"] = ip
cfg_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
print(f"Updated {cfg_path} supervisor_host={ip}")
EOF
fi

TARGET="$USER_NAME@$HOST"
SSH_CONTROL_PATH="/tmp/hydra-ssh-%C"
SSH_OPTS=(
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
  -o ControlMaster=auto
  -o ControlPersist=10m
  -o ControlPath="$SSH_CONTROL_PATH"
)
RSYNC_RSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ControlMaster=auto -o ControlPersist=10m -o ControlPath=$SSH_CONTROL_PATH"

echo "[server] target=$TARGET"
echo "[server] syncing files..."

ssh "${SSH_OPTS[@]}" -MNf "$TARGET"
ssh "${SSH_OPTS[@]}" "$TARGET" "mkdir -p '$REMOTE_ROOT/ros2_ws/src' '$REMOTE_ROOT/config' '$REMOTE_ROOT/logs'"
rsync -az --delete -e "$RSYNC_RSH" "$REPO_ROOT/ros2_ws/src/shared/" "$TARGET:$REMOTE_ROOT/ros2_ws/src/shared/"
rsync -az --delete -e "$RSYNC_RSH" "$REPO_ROOT/ros2_ws/src/server/" "$TARGET:$REMOTE_ROOT/ros2_ws/src/server/"
rsync -az --delete -e "$RSYNC_RSH" "$REPO_ROOT/ros2_ws/src/orchestration/" "$TARGET:$REMOTE_ROOT/ros2_ws/src/orchestration/"
rsync -az --delete -e "$RSYNC_RSH" "$REPO_ROOT/config/" "$TARGET:$REMOTE_ROOT/config/"

echo "[server] building workspace..."
ssh "${SSH_OPTS[@]}" "$TARGET" "REMOTE_ROOT='$REMOTE_ROOT' ROS_SETUP='$ROS_SETUP' CLEAN_BUILD='$CLEAN_BUILD' bash -s" <<'EOF'
set -euo pipefail

if [[ ! -f "$ROS_SETUP" ]]; then
  echo "ROS setup script not found: $ROS_SETUP" >&2
  exit 1
fi

run_privileged() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi

  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required to install missing dependencies on the target." >&2
    exit 1
  fi

  if ! sudo -n true >/dev/null 2>&1; then
    echo "Passwordless sudo is required for dependency installation on the target." >&2
    exit 1
  fi

  sudo -n -H "$@"
}

APT_UPDATED=0
apt_install_if_missing() {
  local pkg
  for pkg in "$@"; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
      continue
    fi

    if ! command -v apt-get >/dev/null 2>&1; then
      echo "Missing package '$pkg', and apt-get is unavailable on target." >&2
      exit 1
    fi

    if [[ "$APT_UPDATED" -eq 0 ]]; then
      echo "[server] apt-get update (dependency bootstrap)..."
      run_privileged env DEBIAN_FRONTEND=noninteractive apt-get update
      APT_UPDATED=1
    fi

    echo "[server] installing missing package: $pkg"
    run_privileged env DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg"
  done
}

ensure_dependency_tooling() {
  if ! command -v colcon >/dev/null 2>&1; then
    apt_install_if_missing python3-colcon-common-extensions
  fi
  if ! command -v rosdep >/dev/null 2>&1; then
    apt_install_if_missing python3-rosdep
  fi
}

set +u
source "$ROS_SETUP"
set -u
cd "$REMOTE_ROOT/ros2_ws"

ensure_dependency_tooling

if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  echo "[server] initializing rosdep..."
  run_privileged rosdep init
fi

echo "[server] updating rosdep index..."
rosdep update
echo "[server] installing workspace dependencies via rosdep..."
rosdep install --from-paths src --ignore-src -r -y --rosdistro "${ROS_DISTRO:?ROS_DISTRO not set after sourcing ROS setup}"

if [[ "$CLEAN_BUILD" == "1" ]]; then
  rm -rf build install log
fi

colcon list | grep -E 'hydra_(interfaces|common|supervisor_bridge|optitrack_bridge|bringup)' >/dev/null
colcon build --symlink-install --packages-select \
  hydra_interfaces hydra_common hydra_supervisor_bridge hydra_optitrack_bridge hydra_bringup
EOF

if [[ "$RUN_AFTER" == "1" ]]; then
  echo "[server] launching supervisor bridge in background..."
  ssh "${SSH_OPTS[@]}" "$TARGET" "REMOTE_ROOT='$REMOTE_ROOT' ROS_SETUP='$ROS_SETUP' bash -s" <<'EOF'
set -euo pipefail

if [[ ! -f "$ROS_SETUP" ]]; then
  echo "ROS setup script not found: $ROS_SETUP" >&2
  exit 1
fi

set +u
source "$ROS_SETUP"
set -u
cd "$REMOTE_ROOT/ros2_ws"
set +u
source install/setup.bash
set -u

  pkill -f "ros2 launch hydra_bringup supervisor.launch.py" || true
  pkill -f "/hydra_supervisor_bridge/lib/hydra_supervisor_bridge/supervisor_bridge" || true
  rm -f "$REMOTE_ROOT/logs/supervisor.pid"

  nohup bash -c "set +u; source '$ROS_SETUP'; source '$REMOTE_ROOT/ros2_ws/install/setup.bash'; set -u; cd '$REMOTE_ROOT/ros2_ws'; exec ros2 launch hydra_bringup supervisor.launch.py config_path:=$REMOTE_ROOT/config/fleet.json" \
  > "$REMOTE_ROOT/logs/supervisor.log" 2>&1 < /dev/null &

  echo $! > "$REMOTE_ROOT/logs/supervisor.pid"
echo "supervisor_bridge started (pid=$(cat "$REMOTE_ROOT/logs/supervisor.pid"))"
echo "log: $REMOTE_ROOT/logs/supervisor.log"
EOF
fi

ssh "${SSH_OPTS[@]}" -O exit "$TARGET" >/dev/null 2>&1 || true

echo "[server] done."
