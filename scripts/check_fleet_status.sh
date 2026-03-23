#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Check fleet host/process status from local machine.

Usage:
  ./scripts/check_fleet_status.sh [options]

Options:
  --config <path>           Fleet config path (default: <repo>/config/fleet.json)
  --connect-timeout <sec>   SSH/TCP connect timeout seconds (default: 3)
  --check-ros               Also verify ROS topic visibility from supervisor host
  --only <targets>          Comma-separated targets: server,robots (default: server,robots)
  -h, --help                Show this help

What it checks:
  1) host reachability (TCP/22 + SSH non-interactive)
  2) process status via remote PID file + pattern fallback
  3) optional ROS topic checks from supervisor machine
USAGE
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="$REPO_ROOT/config/fleet.json"
CONNECT_TIMEOUT=3
CHECK_ROS=0
ONLY="server,robots"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG_PATH="$2"; shift 2 ;;
    --connect-timeout) CONNECT_TIMEOUT="$2"; shift 2 ;;
    --check-ros) CHECK_ROS=1; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH" >&2
  exit 1
fi

check_tcp_22() {
  local host="$1"
  local timeout="$2"
  python3 - "$host" "$timeout" <<'PY'
import socket
import sys

host = sys.argv[1]
timeout = float(sys.argv[2])

try:
    with socket.create_connection((host, 22), timeout=timeout):
        pass
except Exception:
    sys.exit(1)
sys.exit(0)
PY
}

ssh_ok() {
  local target="$1"
  local timeout="$2"
  ssh \
    -o BatchMode=yes \
    -o ConnectTimeout="$timeout" \
    -o StrictHostKeyChecking=accept-new \
    "$target" "echo ok" >/dev/null 2>&1
}

remote_process_check() {
  local target="$1"
  local timeout="$2"
  local pid_file="$3"
  local pattern="$4"

  ssh \
    -o BatchMode=yes \
    -o ConnectTimeout="$timeout" \
    -o StrictHostKeyChecking=accept-new \
    "$target" "PID_FILE='$pid_file' PATTERN='$pattern' bash -s" <<'EOS'
set -euo pipefail

pid_line=""
if [[ -f "$PID_FILE" ]]; then
  pid="$(tr -d '[:space:]' < "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && ps -p "$pid" -o pid=,etime=,command= >/dev/null 2>&1; then
    pid_line="$(ps -p "$pid" -o pid=,etime=,command=)"
    if grep -E -q "$PATTERN" <<<"$pid_line"; then
      echo "RUNNING_PID|$pid_line"
      exit 0
    fi
  fi
fi

if pgrep -af "$PATTERN" >/tmp/hydra_status_matches.$$ 2>/dev/null; then
  count="$(wc -l < /tmp/hydra_status_matches.$$ | tr -d '[:space:]')"
  first="$(head -n 1 /tmp/hydra_status_matches.$$)"
  rm -f /tmp/hydra_status_matches.$$ || true
  if [[ "${count:-0}" -gt 1 ]]; then
    echo "RUNNING_PATTERN_MULTI|count=$count|$first"
  else
    echo "RUNNING_PATTERN|$first"
  fi
  exit 0
fi
rm -f /tmp/hydra_status_matches.$$ || true

if [[ -n "$pid_line" ]]; then
  echo "PID_ALIVE_UNEXPECTED|$pid_line"
else
  echo "NOT_RUNNING"
fi
EOS
}

remote_ros_topic_once() {
  local target="$1"
  local timeout="$2"
  local ros_setup="$3"
  local remote_root="$4"
  local topic="$5"

  ssh \
    -o BatchMode=yes \
    -o ConnectTimeout="$timeout" \
    -o StrictHostKeyChecking=accept-new \
    "$target" "ROS_SETUP='$ros_setup' REMOTE_ROOT='$remote_root' TOPIC='$topic' bash -s" <<'EOS'
set -euo pipefail

if [[ ! -f "$ROS_SETUP" ]]; then
  echo "ROS_SETUP_MISSING"
  exit 2
fi

set +u
source "$ROS_SETUP"
set -u
if [[ -f "$REMOTE_ROOT/ros2_ws/install/setup.bash" ]]; then
  set +u
  source "$REMOTE_ROOT/ros2_ws/install/setup.bash"
  set -u
fi

if ! command -v timeout >/dev/null 2>&1; then
  echo "NO_TIMEOUT_CMD"
  exit 2
fi

timeout 6 ros2 topic echo --once "$TOPIC" >/dev/null 2>&1 && echo "ROS_OK" || echo "ROS_NO_DATA"
EOS
}

# Output fields:
# kind<TAB>name<TAB>host<TAB>user<TAB>ros_setup<TAB>remote_root<TAB>pid_file<TAB>pattern<TAB>topic<TAB>pose_topic<TAB>alt_pose_topic
TARGET_ROWS=()
while IFS= read -r _row; do
  TARGET_ROWS+=("$_row")
done < <(python3 - "$CONFIG_PATH" "$ONLY" <<'PY'
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
only = {x.strip().lower() for x in sys.argv[2].split(",") if x.strip()}

cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
deploy = cfg.get("DEPLOYMENT_CONFIG", {})
robots_cfg = cfg.get("ROBOT_CONFIG", {})

if "server" in only:
    server = deploy.get("server", {})
    if server.get("enabled", False):
        host = str(server.get("host", "")).strip()
        user = str(server.get("user", "")).strip()
        ros_setup = str(server.get("ros_setup", "/opt/ros/jazzy/setup.bash")).strip()
        remote_root = str(server.get("remote_root", f"/home/{user}/hydra")).strip()
        pid_file = f"{remote_root}/logs/supervisor.pid"
        pattern = r"(ros2 launch hydra_bringup supervisor.launch.py|/hydra_supervisor_bridge/lib/hydra_supervisor_bridge/supervisor_bridge)"
        topic = "/hydra/supervisor_heartbeat"
        if host and user:
            print("\t".join(["server", "server", host, user, ros_setup, remote_root, pid_file, pattern, topic, "", ""]))

if "robots" in only:
    robots_deploy = deploy.get("robots", {})
    defaults = robots_deploy.get("defaults", {})
    devices = robots_deploy.get("devices", {})
    for robot_name, device in devices.items():
        if not isinstance(device, dict) or not device.get("enabled", False):
            continue
        robot_cfg = robots_cfg.get(robot_name, {}) if isinstance(robots_cfg, dict) else {}
        host = str(device.get("host") or robot_cfg.get("ip") or "").strip()
        user = str(device.get("user") or defaults.get("user") or "").strip()
        ros_setup = str(device.get("ros_setup") or defaults.get("ros_setup") or "/opt/ros/jazzy/setup.bash").strip()
        remote_root = str(device.get("remote_root") or defaults.get("remote_root") or f"/home/{user}/hydra").strip()
        namespace = str(robot_cfg.get("namespace") or f"/{robot_name}").strip()
        if not namespace.startswith("/"):
            namespace = "/" + namespace
        topic = f"{namespace}/hydra/status"
        pid_file = f"{remote_root}/logs/robot_{robot_name}.pid"
        pattern = rf"(ros2 launch hydra_bringup robot_agent.launch.py .*robot_name:={robot_name}|/hydra_robot_agent/lib/hydra_robot_agent/robot_agent)"
        pose_topic = str(robot_cfg.get("pose_topic") or "").strip()
        umh_id = str(robot_cfg.get("umh_id") or "").strip()
        if not pose_topic and umh_id:
            pose_topic = f"/natnet_ros/{umh_id}/pose"
        alt_pose_topic = f"/{umh_id}/pose" if umh_id else ""
        if host and user:
            print("\t".join(["robot", robot_name, host, user, ros_setup, remote_root, pid_file, pattern, topic, pose_topic, alt_pose_topic]))
PY
)

if [[ ${#TARGET_ROWS[@]} -eq 0 ]]; then
  echo "No enabled targets found for --only=$ONLY"
  exit 0
fi

SUPERVISOR_TARGET=""
SUPERVISOR_ROS_SETUP=""
SUPERVISOR_REMOTE_ROOT=""

echo "Fleet Status"
echo "config: $CONFIG_PATH"
echo ""

for row in "${TARGET_ROWS[@]}"; do
  IFS=$'\t' read -r kind name host user ros_setup remote_root pid_file pattern topic pose_topic alt_pose_topic <<<"$row"
  target="$user@$host"
  label="$kind:$name"

  if [[ "$kind" == "server" ]]; then
    SUPERVISOR_TARGET="$target"
    SUPERVISOR_ROS_SETUP="$ros_setup"
    SUPERVISOR_REMOTE_ROOT="$remote_root"
  fi

  tcp_status="DOWN"
  if check_tcp_22 "$host" "$CONNECT_TIMEOUT"; then
    tcp_status="UP"
  fi

  ssh_status="UNREACHABLE"
  process_status="SKIPPED"

  if ssh_ok "$target" "$CONNECT_TIMEOUT"; then
    ssh_status="OK"
    process_raw="$(remote_process_check "$target" "$CONNECT_TIMEOUT" "$pid_file" "$pattern" || true)"
    case "$process_raw" in
      RUNNING_PID\|*)
        process_status="RUNNING (pid)"
        process_detail="${process_raw#RUNNING_PID|}"
        ;;
      RUNNING_PATTERN\|*)
        process_status="RUNNING (pattern)"
        process_detail="${process_raw#RUNNING_PATTERN|}"
        ;;
      RUNNING_PATTERN_MULTI\|*)
        process_status="RUNNING (multiple)"
        process_detail="${process_raw#RUNNING_PATTERN_MULTI|}"
        ;;
      PID_ALIVE_UNEXPECTED\|*)
        process_status="PID alive but unexpected cmd"
        process_detail="${process_raw#PID_ALIVE_UNEXPECTED|}"
        ;;
      NOT_RUNNING)
        process_status="NOT RUNNING"
        process_detail=""
        ;;
      *)
        process_status="UNKNOWN"
        process_detail="$process_raw"
        ;;
    esac
  else
    process_detail=""
  fi

  echo "$label"
  echo "  host: $host"
  echo "  tcp22: $tcp_status"
  echo "  ssh: $ssh_status"
  echo "  process: $process_status"
  if [[ -n "${process_detail:-}" ]]; then
    echo "  detail: $process_detail"
  fi
  echo "  pid_file: $pid_file"
  echo ""
done

if [[ "$CHECK_ROS" == "1" ]]; then
  echo "ROS Topic Checks"
  if [[ -z "$SUPERVISOR_TARGET" ]]; then
    echo "  skipped: no enabled server target in config"
    exit 0
  fi

  if ! ssh_ok "$SUPERVISOR_TARGET" "$CONNECT_TIMEOUT"; then
    echo "  skipped: supervisor SSH unreachable ($SUPERVISOR_TARGET)"
    exit 0
  fi

  for row in "${TARGET_ROWS[@]}"; do
    IFS=$'\t' read -r kind name _host _user _ros_setup _remote_root _pid_file _pattern topic pose_topic alt_pose_topic <<<"$row"
    ros_result="$(remote_ros_topic_once "$SUPERVISOR_TARGET" "$CONNECT_TIMEOUT" "$SUPERVISOR_ROS_SETUP" "$SUPERVISOR_REMOTE_ROOT" "$topic" || true)"
    case "$ros_result" in
      ROS_OK)
        echo "  $topic -> OK"
        ;;
      ROS_NO_DATA)
        echo "  $topic -> NO DATA"
        ;;
      ROS_SETUP_MISSING)
        echo "  $topic -> FAILED (supervisor ros_setup missing: $SUPERVISOR_ROS_SETUP)"
        ;;
      NO_TIMEOUT_CMD)
        echo "  $topic -> FAILED (timeout command missing on supervisor)"
        ;;
      *)
        echo "  $topic -> FAILED ($ros_result)"
        ;;
    esac
    if [[ "$kind" == "robot" && -n "${pose_topic:-}" ]]; then
      pose_result="$(remote_ros_topic_once "$SUPERVISOR_TARGET" "$CONNECT_TIMEOUT" "$SUPERVISOR_ROS_SETUP" "$SUPERVISOR_REMOTE_ROOT" "$pose_topic" || true)"
      case "$pose_result" in
        ROS_OK)
          echo "  $pose_topic -> OK"
          ;;
        ROS_NO_DATA)
          echo "  $pose_topic -> NO DATA"
          if [[ -n "${alt_pose_topic:-}" ]]; then
            alt_pose_result="$(remote_ros_topic_once "$SUPERVISOR_TARGET" "$CONNECT_TIMEOUT" "$SUPERVISOR_ROS_SETUP" "$SUPERVISOR_REMOTE_ROOT" "$alt_pose_topic" || true)"
            case "$alt_pose_result" in
              ROS_OK)
                echo "  $alt_pose_topic -> OK (possible pose_topic mismatch)"
                ;;
              ROS_NO_DATA)
                echo "  $alt_pose_topic -> NO DATA"
                ;;
              *)
                echo "  $alt_pose_topic -> FAILED ($alt_pose_result)"
                ;;
            esac
          fi
          ;;
        *)
          echo "  $pose_topic -> FAILED ($pose_result)"
          ;;
      esac
    fi
  done
fi
