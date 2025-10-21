#!/usr/bin/env python3
"""
Virtual Robot Path Simulator with UI
Draw paths and watch a simulated robot follow them using the PathFollower module.
"""

import tkinter as tk
import math
import time
from path_follower import PathFollower


class VirtualRobot:
    """Virtual robot with same constraints as real robot."""
    
    def __init__(self, x=0.0, y=0.0, yaw=0.0, scale=100):
        self.x = x
        self.y = y
        self.yaw = yaw
        self.max_speed = 0.5  # m/s
        self.max_turn_rate = 1.5  # rad/s
        self.size = 20  # pixels
        self.scale = scale  # pixels per meter
        
    def update(self, direction, turn_rate_deg, dt):
        """Update robot based on command."""
        turn_rate_rad = turn_rate_deg * math.pi / 180.0
        turn_rate_rad = max(-self.max_turn_rate, min(self.max_turn_rate, turn_rate_rad))
        
        self.yaw += turn_rate_rad * dt
        
        while self.yaw > math.pi:
            self.yaw -= 2 * math.pi
        while self.yaw < -math.pi:
            self.yaw += 2 * math.pi
        
        if direction == 1:
            # Convert m/s to pixels/s
            speed_pixels = self.max_speed * self.scale
            self.x += speed_pixels * math.cos(self.yaw) * dt
            self.y += speed_pixels * math.sin(self.yaw) * dt
    
    def get_position(self):
        """Get position in pixels."""
        return self.x, self.y, self.yaw


class PathSimulator:
    """UI for drawing and following paths."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 Virtual Robot Path Simulator")
        self.root.configure(bg='#1e1e1e')
        
        self.canvas_width = 600
        self.canvas_height = 600
        self.scale = 100  # pixels per meter
        
        self.path_points = []
        
        self.robot = VirtualRobot(
            x=self.canvas_width / 2,
            y=self.canvas_height / 2,
            yaw=0.0,
            scale=self.scale
        )
        
        self.follower = None
        self.is_animating = False
        self.last_update_time = None
        self.robot_visual = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup UI."""
        title = tk.Label(
            self.root, text="🤖 Virtual Robot Path Simulator",
            font=('Arial', 18, 'bold'), bg='#1e1e1e', fg='#fff'
        )
        title.pack(pady=8)
        
        instructions = tk.Label(
            self.root, text="Click to draw path → Start to simulate",
            font=('Arial', 11), bg='#1e1e1e', fg='#888'
        )
        instructions.pack(pady=2)
        
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(padx=20, pady=8)
        
        self.canvas = tk.Canvas(
            main_frame, width=self.canvas_width, height=self.canvas_height,
            bg='#2b2b2b', highlightthickness=2, highlightbackground='#555'
        )
        self.canvas.pack()
        
        self._draw_grid()
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        
        control_frame = tk.Frame(self.root, bg='#1e1e1e')
        control_frame.pack(pady=8)
        
        self.status_label = tk.Label(
            control_frame, text="Ready - Click to add waypoints",
            font=('Arial', 11, 'bold'), bg='#1e1e1e', fg='#FFA500'
        )
        self.status_label.pack(pady=5)
        
        button_frame = tk.Frame(control_frame, bg='#1e1e1e')
        button_frame.pack(pady=5)
        
        self.start_btn = tk.Button(
            button_frame, text="▶ Start", font=('Arial', 10, 'bold'),
            bg='#4CAF50', fg='#fff', command=self._start,
            padx=15, pady=8, state=tk.DISABLED
        )
        self.start_btn.pack(side=tk.LEFT, padx=3)
        
        self.stop_btn = tk.Button(
            button_frame, text="⏸ Stop", font=('Arial', 10, 'bold'),
            bg='#FFA500', fg='#fff', command=self._stop,
            padx=15, pady=8, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        
        self.reset_btn = tk.Button(
            button_frame, text="🔄 Reset", font=('Arial', 10),
            bg='#2196F3', fg='#fff', command=self._reset,
            padx=15, pady=8
        )
        self.reset_btn.pack(side=tk.LEFT, padx=3)
        
        self.clear_btn = tk.Button(
            button_frame, text="🗑 Clear", font=('Arial', 10),
            bg='#f44336', fg='#fff', command=self._clear,
            padx=15, pady=8
        )
        self.clear_btn.pack(side=tk.LEFT, padx=3)
        
        info_frame = tk.Frame(self.root, bg='#1e1e1e')
        info_frame.pack(pady=5)
        
        self.info_label = tk.Label(
            info_frame, text=self._get_info(),
            font=('Arial', 9), bg='#1e1e1e', fg='#888'
        )
        self.info_label.pack()
        
        # Debug panel
        debug_frame = tk.Frame(self.root, bg='#1e1e1e')
        debug_frame.pack(pady=5)
        
        tk.Label(debug_frame, text="Debug Info:", font=('Arial', 9, 'bold'),
                bg='#1e1e1e', fg='#FFA500').pack()
        
        self.debug_label = tk.Label(
            debug_frame, text=self._get_debug_info(),
            font=('Courier', 8), bg='#1e1e1e', fg='#888',
            justify=tk.LEFT
        )
        self.debug_label.pack()
        
        self._draw_robot()
        
    def _draw_grid(self):
        """Draw grid."""
        for i in range(0, self.canvas_width + 1, self.scale):
            self.canvas.create_line(i, 0, i, self.canvas_height, fill='#333', width=1)
            if i % self.scale == 0:
                self.canvas.create_text(i, self.canvas_height - 10, 
                                      text=f"{i//self.scale}m", fill='#666', font=('Arial', 8))
        
        for i in range(0, self.canvas_height + 1, self.scale):
            self.canvas.create_line(0, i, self.canvas_width, i, fill='#333', width=1)
            if i % self.scale == 0:
                self.canvas.create_text(10, i, text=f"{i//self.scale}m", fill='#666', font=('Arial', 8))
        
        self.canvas.create_oval(
            self.canvas_width//2 - 5, self.canvas_height//2 - 5,
            self.canvas_width//2 + 5, self.canvas_height//2 + 5,
            fill='#FF5722', outline='#fff'
        )
    
    def _canvas_to_meters(self, canvas_x, canvas_y):
        """Convert canvas pixels to meters."""
        x = (canvas_x - self.canvas_width / 2) / self.scale
        y = (canvas_y - self.canvas_height / 2) / self.scale
        return x, y
    
    def _meters_to_canvas(self, x, y):
        """Convert meters to canvas pixels."""
        canvas_x = x * self.scale + self.canvas_width / 2
        canvas_y = y * self.scale + self.canvas_height / 2
        return canvas_x, canvas_y
    
    def _on_canvas_click(self, event):
        """Add waypoint on click."""
        if self.is_animating:
            return
        
        x, y = event.x, event.y
        self.path_points.append((x, y))
        
        self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, 
                               fill='#4CAF50', outline='#fff', tags='waypoint')
        self.canvas.create_text(x, y - 15, text=str(len(self.path_points)),
                               fill='#4CAF50', font=('Arial', 10, 'bold'), tags='waypoint')
        
        if len(self.path_points) > 1:
            prev_x, prev_y = self.path_points[-2]
            self.canvas.create_line(prev_x, prev_y, x, y, fill='#4CAF50', width=2, tags='path_line')
        
        self.status_label.config(text=f"Waypoints: {len(self.path_points)}")
        self.start_btn.config(state=tk.NORMAL if len(self.path_points) > 0 else tk.DISABLED)
    
    def _draw_robot(self):
        """Draw robot."""
        if self.robot_visual:
            self.canvas.delete(self.robot_visual)
            self.canvas.delete('robot_arrow')
            self.canvas.delete('predicted_pos')
        
        x, y = self.robot.x, self.robot.y
        size = self.robot.size
        
        self.robot_visual = self.canvas.create_oval(
            x - size, y - size, x + size, y + size,
            fill='#2196F3', outline='#fff', width=2
        )
        
        arrow_len = size * 1.5
        arrow_x = x + arrow_len * math.cos(self.robot.yaw)
        arrow_y = y + arrow_len * math.sin(self.robot.yaw)
        self.canvas.create_line(x, y, arrow_x, arrow_y, 
                               fill='#fff', width=3, arrow=tk.LAST, tags='robot_arrow')
        
        # Draw predicted position if follower exists
        if self.follower and hasattr(self.follower, 'predictor'):
            x_m, y_m = self._canvas_to_meters(x, y)
            pred_x_m, pred_y_m, pred_yaw = self.follower.predictor.predict(
                x_m, y_m, self.robot.yaw, 0.1
            )
            pred_x, pred_y = self._meters_to_canvas(pred_x_m, pred_y_m)
            
            # Draw predicted position
            pred_size = size * 0.7
            self.canvas.create_oval(
                pred_x - pred_size, pred_y - pred_size,
                pred_x + pred_size, pred_y + pred_size,
                fill='', outline='#FFA500', width=2, dash=(4, 4),
                tags='predicted_pos'
            )
            
            # Draw predicted arrow
            pred_arrow_x = pred_x + arrow_len * 0.7 * math.cos(pred_yaw)
            pred_arrow_y = pred_y + arrow_len * 0.7 * math.sin(pred_yaw)
            self.canvas.create_line(
                pred_x, pred_y, pred_arrow_x, pred_arrow_y,
                fill='#FFA500', width=2, arrow=tk.LAST, tags='predicted_pos'
            )
    
    def _start(self):
        """Start simulation."""
        if len(self.path_points) == 0:
            return
        
        # Convert waypoints to meters
        waypoints_meters = [self._canvas_to_meters(x, y) for x, y in self.path_points]
        
        # Create follower
        self.follower = PathFollower(
            waypoints=waypoints_meters,
            waypoint_tolerance=0.10,
            use_prediction=True,
            estimated_delay_ms=50
        )
        
        self.is_animating = True
        self.last_update_time = time.time()
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Moving...")
        
        self._animate()
    
    def _animate(self):
        """Animation loop."""
        if not self.is_animating:
            return
        
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time
        
        if self.follower.is_complete():
            self._stop()
            self.status_label.config(text="✓ Path completed!")
            return
        
        # Get robot position in meters
        x_pixels, y_pixels, yaw = self.robot.get_position()
        x_meters, y_meters = self._canvas_to_meters(x_pixels, y_pixels)
        
        # Update follower and get command
        self.follower.update_position(x_meters, y_meters, yaw)
        direction, turn_rate = self.follower.compute_command()
        
        # Update robot
        self.robot.update(direction, turn_rate, dt)
        
        # Update visuals
        self._draw_robot()
        self._update_info()
        
        # Show progress
        state = self.follower.get_state()
        self.status_label.config(
            text=f"Waypoint {state['waypoint_index']+1}/{state['total_waypoints']}"
        )
        
        self.root.after(16, self._animate)  # 60 FPS
    
    def _stop(self):
        """Stop simulation."""
        self.is_animating = False
        # Reset follower predictor to avoid stale velocity data
        if self.follower:
            self.follower.reset()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.NORMAL)
    
    def _reset(self):
        """Reset robot."""
        self.is_animating = False
        self.robot.x = self.canvas_width / 2
        self.robot.y = self.canvas_height / 2
        self.robot.yaw = 0.0
        self.follower = None
        
        self.start_btn.config(state=tk.NORMAL if len(self.path_points) > 0 else tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Reset")
        
        self._draw_robot()
        self._update_info()
    
    def _clear(self):
        """Clear path."""
        self.path_points = []
        self.is_animating = False
        self.follower = None
        
        self.canvas.delete('waypoint')
        self.canvas.delete('path_line')
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Path cleared")
        
        self._reset()
    
    def _get_info(self):
        """Get info string."""
        x_m, y_m = self._canvas_to_meters(self.robot.x, self.robot.y)
        yaw_deg = math.degrees(self.robot.yaw)
        return f"Position: ({x_m:.2f}m, {y_m:.2f}m) | Heading: {yaw_deg:.1f}° | Speed: 0.5 m/s"
    
    def _get_debug_info(self):
        """Get debug information."""
        x_m, y_m = self._canvas_to_meters(self.robot.x, self.robot.y)
        yaw_deg = math.degrees(self.robot.yaw)
        
        lines = [
            f"Current Location:  ({x_m:6.3f}m, {y_m:6.3f}m)",
            f"Current Rotation:  {yaw_deg:7.2f}°"
        ]
        
        if self.follower and hasattr(self.follower, 'predictor'):
            pred_x, pred_y, pred_yaw = self.follower.predictor.predict(
                x_m, y_m, self.robot.yaw, 0.1
            )
            pred_yaw_deg = math.degrees(pred_yaw)
            lines.append(f"Predicted Location: ({pred_x:6.3f}m, {pred_y:6.3f}m)")
            lines.append(f"Predicted Rotation: {pred_yaw_deg:7.2f}°")
            
            # Show calculated orientation from follower
            state = self.follower.get_state()
            if state['angle_to_target'] is not None:
                target_angle_deg = math.degrees(state['angle_to_target'])
                lines.append(f"Target Angle Error: {target_angle_deg:7.2f}°")
        else:
            lines.append("Predicted Location: N/A")
            lines.append("Predicted Rotation: N/A")
            lines.append("Target Angle Error: N/A")
        
        return "\n".join(lines)
    
    def _update_info(self):
        """Update info label."""
        self.info_label.config(text=self._get_info())
        self.debug_label.config(text=self._get_debug_info())
    
    def run(self):
        """Run application."""
        self.root.mainloop()


def main():
    app = PathSimulator()
    app.run()


if __name__ == '__main__':
    main()
