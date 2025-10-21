#!/usr/bin/env python3
"""
Barebones Robot Control Server with OptiTrack Tracking

Features:
- Loads robot configuration from config.json
- OptiTrack tracking in background (displays positions in terminal)
- Simple terminal commands for robot control
- TCP server for broadcasting commands to robots

Commands:
- <direction> <angle>  : Send movement command
- positions / p        : Display robot positions
- help / h             : Show help
- quit / q             : Exit
"""

import socket
import threading
import json
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.config_loader import load_config
from optitrack.tracker import RobotTracker


class BarebonesTrackingServer:
    """Barebones server with terminal interface and position tracking."""
    
    def __init__(self, host='0.0.0.0', command_port=6969):
        """Initialize the barebones tracking server."""
        self.host = host
        self.command_port = command_port
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = True
        
        # Load configuration and initialize tracker
        print("\n" + "="*70)
        print("[Server] 🚀 STARTING BAREBONES TRACKING SERVER")
        print("="*70)
        print("[Server] Loading configuration from config.json...")
        self.config = load_config()
        robot_config = self.config.get_robot_config()
        
        print(f"\n[Server] 📋 Found {len(robot_config)} robots in config:")
        for name, cfg in robot_config.items():
            print(f"  - {name}: Robot IP={cfg['ip']}, OptiTrack UDP Port={cfg['port']}")
        
        # Initialize robot tracker
        print(f"\n[Server] 🔧 Initializing OptiTrack tracker...")
        self.tracker = RobotTracker(robot_config)
        self.robots = self.tracker.robots
        print(f"[Server] ✓ Created {len(self.robots)} Robot instances")
        
    def start_tracking(self):
        """Start the OptiTrack tracking system."""
        print(f"\n[Server] 🎯 Starting UDP listeners for OptiTrack data...")
        self.tracker.start()
        print("[Server] ✓ All tracking threads started")
        print("\n[Server] 💡 TIP: Watch for UDP packet reception messages above")
        print("="*70 + "\n")
        
    def stop_tracking(self):
        """Stop the OptiTrack tracking system."""
        self.tracker.stop()
        
    def handle_client(self, client_socket, address):
        """Handle a connected robot client."""
        print(f"[Server] Robot connected: {address}")
        with self.clients_lock:
            self.clients.append(client_socket)
        
        try:
            while self.running:
                pass  # Keep connection alive
        except Exception as e:
            print(f"[Server] Client {address} error: {e}")
        finally:
            with self.clients_lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            client_socket.close()
            print(f"[Server] Robot disconnected: {address}")
    
    def broadcast_command(self, direction, angle):
        """Broadcast movement command to all connected robots."""
        cmd = {"direction": direction, "angle": angle}
        msg = json.dumps(cmd) + '\n'
        
        with self.clients_lock:
            dead_clients = []
            for client in self.clients:
                try:
                    client.sendall(msg.encode('utf-8'))
                except Exception as e:
                    dead_clients.append(client)
            
            # Remove dead clients
            for client in dead_clients:
                self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
        
        active_count = len(self.clients)
        status = "✓" if active_count > 0 else "⚠"
        print(f"[Command] {status} direction={direction}, angle={angle}°/s → {active_count} robot(s)")
    
    def display_positions(self):
        """Display current robot positions in terminal."""
        print("\n" + "=" * 70)
        print(f"{'Robot':<12} {'X (m)':>12} {'Y (m)':>12} {'Yaw (rad)':>12} {'Yaw (°)':>12}")
        print("=" * 70)
        
        for name, robot in self.robots.items():
            pos = robot.get_position()
            yaw_deg = pos[2] * 180 / 3.14159
            print(f"{name:<12} {pos[0]:>12.4f} {pos[1]:>12.4f} {pos[2]:>12.4f} {yaw_deg:>12.2f}")
        
        print("=" * 70 + "\n")
    
    def run(self):
        """Start the command server and run interactive loop."""
        # Start tracking
        self.start_tracking()
        
        # Create command server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.command_port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)
            print(f"\n[Server] ✓ Command server: {self.host}:{self.command_port}")
            print("[Server] Waiting for robots to connect...")
        except OSError as e:
            print(f"[Server] ERROR: Cannot bind to port {self.command_port}: {e}")
            self.stop_tracking()
            return
        
        # Accept connections in background
        def accept_connections():
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[Server] Accept error: {e}")
        
        accept_thread = threading.Thread(target=accept_connections, daemon=True)
        accept_thread.start()
        
        # Print help
        self._print_help()
        
        # Interactive command loop
        try:
            while self.running:
                try:
                    user_input = input("\n> ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Parse commands
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("[Server] Shutting down...")
                        break
                    
                    elif user_input.lower() in ['positions', 'pos', 'p']:
                        self.display_positions()
                    
                    elif user_input.lower() in ['help', 'h', '?']:
                        self._print_help()
                    
                    elif user_input.lower() in ['stop', 's']:
                        print("[Command] EMERGENCY STOP")
                        self.broadcast_command(0, 0.0)
                    
                    elif user_input.lower() in ['clients', 'c']:
                        with self.clients_lock:
                            count = len(self.clients)
                        print(f"[Server] Connected clients: {count}")
                    
                    else:
                        # Parse movement command: <direction> <angle>
                        parts = user_input.split()
                        if len(parts) != 2:
                            print("[Error] Invalid format. Use: <direction> <angle>")
                            print("        Or type 'help' for more commands")
                            continue
                        
                        try:
                            direction = int(parts[0])
                            angle = float(parts[1])
                            
                            if direction not in [0, 1]:
                                print("[Error] Direction must be 0 or 1")
                                continue
                            
                            # Invert angle sign so positive = right turn
                            self.broadcast_command(direction, -angle)
                            
                        except ValueError:
                            print("[Error] Invalid numbers. Use: <direction(0/1)> <angle(float)>")
                            
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\n[Server] Shutting down...")
                    break
                    
        finally:
            self.running = False
            server_socket.close()
            
            # Close all client connections
            with self.clients_lock:
                for client in self.clients:
                    try:
                        client.close()
                    except:
                        pass
            
            # Stop tracking
            self.stop_tracking()
            
            print("[Server] Stopped.")
    
    def _print_help(self):
        """Print help message."""
        print("\n" + "=" * 70)
        print("  BAREBONES ROBOT CONTROL SERVER (with OptiTrack Tracking)")
        print("=" * 70)
        print("\nMovement Commands:")
        print("  <direction> <angle>  - Send movement command")
        print("                         direction: 0=stop, 1=forward")
        print("                         angle: rotation speed (deg/s)")
        print("\n  Examples:")
        print("    1 0      - Move forward straight")
        print("    1 60     - Move forward, turn left 60°/s")
        print("    1 -45    - Move forward, turn right 45°/s")
        print("    0 90     - Stop linear, rotate 90°/s")
        print("    0 0      - Full stop")
        print("\nOther Commands:")
        print("  positions (p)  - Display current robot positions from OptiTrack")
        print("  stop (s)       - Emergency stop (send 0 0)")
        print("  clients (c)    - Show connected clients")
        print("  help (h)       - Show this help")
        print("  quit (q)       - Exit server")
        print("=" * 70)


def main():
    """Main entry point."""
    command_port = 6969
    if len(sys.argv) > 1:
        try:
            command_port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)
    
    server = BarebonesTrackingServer(host='0.0.0.0', command_port=command_port)
    server.run()


if __name__ == '__main__':
    main()

