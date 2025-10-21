#!/usr/bin/env python3
"""
Barebones CLI Server for Robot Control
Accepts user input and broadcasts commands to connected robot clients.
Commands are sent as JSON: {"direction": 0/1, "angle": degrees_per_sec}
"""

import socket
import threading
import json
import sys

class BarebonesServer:
    def __init__(self, host='0.0.0.0', port=6969):
        self.host = host
        self.port = port
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = True
        
    def handle_client(self, client_socket, address):
        """Handle a connected client."""
        print(f"[SERVER] Client connected from {address}")
        with self.clients_lock:
            self.clients.append(client_socket)
        
        try:
            while self.running:
                # Keep connection alive
                pass
        except Exception as e:
            print(f"[SERVER] Client {address} error: {e}")
        finally:
            with self.clients_lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            client_socket.close()
            print(f"[SERVER] Client {address} disconnected")
    
    def broadcast_command(self, direction, angle):
        """Send command to all connected clients."""
        cmd = {"direction": direction, "angle": angle}
        msg = json.dumps(cmd) + '\n'
        
        with self.clients_lock:
            dead_clients = []
            for client in self.clients:
                try:
                    client.sendall(msg.encode('utf-8'))
                except Exception as e:
                    print(f"[SERVER] Failed to send to client: {e}")
                    dead_clients.append(client)
            
            # Remove dead clients
            for client in dead_clients:
                self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
        
        print(f"[SERVER] Broadcasted: direction={direction}, angle={angle} to {len(self.clients)} client(s)")
    
    def run(self):
        """Start the server and accept connections."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)
            print(f"[SERVER] Listening on {self.host}:{self.port}")
            print("[SERVER] Waiting for robot clients to connect...")
        except OSError as e:
            print(f"[SERVER] ERROR: Cannot bind to port {self.port}: {e}")
            print(f"[SERVER] Port {self.port} may already be in use.")
            print(f"[SERVER] Try running with a different port: python3 {sys.argv[0]} <port>")
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
                        print(f"[SERVER] Accept error: {e}")
        
        accept_thread = threading.Thread(target=accept_connections, daemon=True)
        accept_thread.start()
        
        # Interactive command loop
        print("\n=== Barebones Robot Control Server ===")
        print("Commands:")
        print("  <direction> <angle>  - Send command (direction: 0/1, angle: deg/s)")
        print("  Examples:")
        print("    1 0      - Move forward straight")
        print("    1 60     - Move forward, turn left 60 deg/s")
        print("    1 -45    - Move forward, turn right 45 deg/s")
        print("    0 90     - Stop linear, turn in place 90 deg/s")
        print("    0 0      - Full stop")
        print("  quit       - Exit server")
        print("=" * 40)
        
        try:
            while self.running:
                try:
                    user_input = input("\nCommand: ").strip()
                    
                    if not user_input:
                        continue
                    
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("[SERVER] Shutting down...")
                        break
                    
                    parts = user_input.split()
                    if len(parts) != 2:
                        print("[SERVER] Invalid format. Use: <direction> <angle>")
                        continue
                    
                    try:
                        direction = int(parts[0])
                        angle = float(parts[1])
                        
                        if direction not in [0, 1]:
                            print("[SERVER] Direction must be 0 or 1")
                            continue
                        
                        self.broadcast_command(direction, angle)
                        
                    except ValueError:
                        print("[SERVER] Invalid numbers. Use: <direction(0/1)> <angle(float)>")
                        
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\n[SERVER] Shutting down...")
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
            
            print("[SERVER] Server stopped.")

def main():
    """Main entry point."""
    port = 6969
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)
    
    server = BarebonesServer(host='0.0.0.0', port=port)
    server.run()

if __name__ == '__main__':
    main()

