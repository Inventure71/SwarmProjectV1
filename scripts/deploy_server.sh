#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Deploy, build, and run Mosaic supervisor stack on one server.

Usage:
  ./scripts/deploy_server.sh --host <ip> --user <username> [options]

Required:
  --host <ip>               Server host/IP
  --user <username>         SSH username on server
  --ros-setup <path>        Remote ROS setup script (required)

Options:
  --repo-root <path>        Local repo root (default: auto-detected)
  --remote-root <path>      Remote install root (default: /home/<user>/mosaic)
  --supervisor-ip <ip>      Update MOSAIC_CONFIG.supervisor_host before sync
  --use-rosdep              Deprecated no-op (dependencies are always installed)
  --no-clean                Do not remove build/install/log before colcon build
  --no-run                  Build/sync only; do not start service/process now
  --autostart               Enable systemd autostart management for supervisor service
  --no-autostart            Disable systemd autostart management (default)
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
AUTOSTART=0

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
    --autostart) AUTOSTART=1; shift ;;
    --no-autostart) AUTOSTART=0; shift ;;
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
  REMOTE_ROOT="/home/$USER_NAME/mosaic"
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
raw.setdefault("MOSAIC_CONFIG", {})["supervisor_host"] = ip
cfg_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
print(f"Updated {cfg_path} supervisor_host={ip}")
EOF
fi

TARGET="$USER_NAME@$HOST"
SSH_CONTROL_PATH="/tmp/mosaic-ssh-%C"
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

colcon list | grep -E 'mosaic_(interfaces|common|supervisor_bridge|optitrack_bridge|bringup)' >/dev/null
colcon build --symlink-install --packages-select \
  mosaic_interfaces mosaic_common mosaic_supervisor_bridge mosaic_optitrack_bridge mosaic_bringup
EOF

START_SCRIPT="$REMOTE_ROOT/mosaic_start.sh"
SERVICE_NAME="mosaic-supervisor.service"
UNIT_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "[server] installing manual start script ($START_SCRIPT)..."
ssh "${SSH_OPTS[@]}" "$TARGET" "REMOTE_ROOT='$REMOTE_ROOT' ROS_SETUP='$ROS_SETUP' START_SCRIPT='$START_SCRIPT' bash -s" <<'EOF'
set -euo pipefail

if [[ ! -f "$ROS_SETUP" ]]; then
  echo "ROS setup script not found: $ROS_SETUP" >&2
  exit 1
fi

cat > "$START_SCRIPT" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail
ROS_SETUP="$ROS_SETUP"
REMOTE_ROOT="$REMOTE_ROOT"

if [[ ! -f "\$ROS_SETUP" ]]; then
  echo "ROS setup script not found: \$ROS_SETUP" >&2
  exit 1
fi

set +u
source "\$ROS_SETUP"
set -u
cd "\$REMOTE_ROOT/ros2_ws"
set +u
source "\$REMOTE_ROOT/ros2_ws/install/setup.bash"
set -u

pkill -f "ros2 launch mosaic_bringup supervisor.launch.py" || true
pkill -f "/mosaic_supervisor_bridge/lib/mosaic_supervisor_bridge/supervisor_bridge" || true
rm -f "\$REMOTE_ROOT/logs/supervisor.pid"

nohup ros2 launch mosaic_bringup supervisor.launch.py config_path:=\$REMOTE_ROOT/config/fleet.json \
> "\$REMOTE_ROOT/logs/supervisor.log" 2>&1 < /dev/null &

echo \$! > "\$REMOTE_ROOT/logs/supervisor.pid"
pid="\$(cat "\$REMOTE_ROOT/logs/supervisor.pid")"
echo "supervisor_bridge started (pid=\$pid)"
echo "log: \$REMOTE_ROOT/logs/supervisor.log"
SCRIPT

chmod +x "$START_SCRIPT"
EOF

if [[ "$AUTOSTART" == "1" ]]; then
  echo "[server] installing/updating systemd service ($SERVICE_NAME)..."
  ssh "${SSH_OPTS[@]}" "$TARGET" "REMOTE_ROOT='$REMOTE_ROOT' ROS_SETUP='$ROS_SETUP' USER_NAME='$USER_NAME' SERVICE_NAME='$SERVICE_NAME' UNIT_PATH='$UNIT_PATH' RUN_AFTER='$RUN_AFTER' bash -s" <<'EOF'
set -euo pipefail

run_privileged() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required to manage systemd services on the target." >&2
    exit 1
  fi
  if ! sudo -n true >/dev/null 2>&1; then
    echo "Passwordless sudo is required for systemd service management on the target." >&2
    exit 1
  fi
  sudo -n -H "$@"
}

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl is unavailable on target; cannot manage autostart service." >&2
  exit 1
fi

UNIT_TMP="$(mktemp)"
cat > "$UNIT_TMP" <<UNIT
[Unit]
Description=Mosaic Supervisor Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$REMOTE_ROOT/ros2_ws
ExecStart=/bin/bash -lc 'set +u; source "$ROS_SETUP"; source "$REMOTE_ROOT/ros2_ws/install/setup.bash"; set -u; exec ros2 launch mosaic_bringup supervisor.launch.py config_path:=$REMOTE_ROOT/config/fleet.json'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

run_privileged install -m 0644 "$UNIT_TMP" "$UNIT_PATH"
rm -f "$UNIT_TMP"

run_privileged systemctl daemon-reload
run_privileged systemctl enable "$SERVICE_NAME"
if [[ "$RUN_AFTER" == "1" ]]; then
  run_privileged systemctl restart "$SERVICE_NAME"
  echo "supervisor service started: $SERVICE_NAME"
else
  run_privileged systemctl stop "$SERVICE_NAME" || true
  echo "supervisor service installed+enabled but not started (--no-run)."
fi
EOF
else
  echo "[server] autostart disabled (manual start script mode)."
  ssh "${SSH_OPTS[@]}" "$TARGET" "SERVICE_NAME='$SERVICE_NAME' UNIT_PATH='$UNIT_PATH' RUN_AFTER='$RUN_AFTER' START_SCRIPT='$START_SCRIPT' bash -s" <<'EOF'
set -euo pipefail

run_privileged_if_possible() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return 0
  fi
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n -H "$@"
    return 0
  fi
  return 1
}

if command -v systemctl >/dev/null 2>&1; then
  if run_privileged_if_possible true; then
    run_privileged_if_possible systemctl disable --now "$SERVICE_NAME" || true
    run_privileged_if_possible rm -f "$UNIT_PATH" || true
    run_privileged_if_possible systemctl daemon-reload || true
    run_privileged_if_possible systemctl reset-failed "$SERVICE_NAME" || true
  else
    echo "warning: could not remove existing systemd service (missing passwordless sudo). continuing with manual start script."
  fi
fi

if [[ "$RUN_AFTER" == "1" ]]; then
  "$START_SCRIPT"
else
  echo "manual start script installed. run: $START_SCRIPT"
fi
EOF
fi

ssh "${SSH_OPTS[@]}" -O exit "$TARGET" >/dev/null 2>&1 || true

echo "[server] done."
