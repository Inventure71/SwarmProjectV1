# Delay Compensation Techniques

## The Problem

When controlling a robot using external position tracking (like OptiTrack), there's an inherent delay between:
1. Robot's actual position
2. When that position is measured
3. When it's transmitted over network
4. When your control algorithm receives it

Typical delays: 30-200ms. At 0.5 m/s, 100ms delay means you're working with position data from 5cm ago.

## What is Dead Reckoning?

**Dead reckoning** is a navigation technique where you estimate your current position based on:
- Your last known position
- The commands you sent to the robot
- How much time has passed

It's called "dead reckoning" because you're calculating position without external references (historically, "ded" was short for "deduced").

### Example:
```
Last known position: (0, 0) at t=0
Command sent: Move forward at 0.5 m/s
Time elapsed: 0.2 seconds
Estimated position: (0.1, 0) at t=0.2
```

The estimate assumes perfect execution of commands, which isn't true in reality (wheel slip, motor lag, etc.), so error accumulates over time.

## Implemented Solutions

### 1. Position Prediction (Velocity-Based)

**How it works:**
- Track velocity by comparing consecutive position measurements
- Use exponential smoothing to filter noise: `v_new = α * v_measured + (1-α) * v_old`
- Predict future position: `pos_future = pos_current + velocity * delay_time`

**Implementation:**
```python
class PositionPredictor:
    def update(self, x, y, yaw, timestamp):
        # Calculate instantaneous velocity
        vx = (x - last_x) / dt
        # Smooth it
        self.velocity_x = 0.3 * vx + 0.7 * self.velocity_x
    
    def predict(self, x, y, yaw, dt_ahead):
        # Extrapolate forward
        return x + self.velocity_x * dt_ahead
```

**Pros:** Works with any movement, doesn't need to know commands
**Cons:** Can overshoot during turns, accumulates prediction error

### 2. Dead Reckoning (Command-Based)

**How it works:**
- Remember what commands you sent to robot
- Estimate where robot should be based on those commands
- Use kinematic model: `x_new = x + v*cos(θ)*dt`, `y_new = y + v*sin(θ)*dt`

**Implementation:**
```python
class DeadReckoning:
    def update_command(self, direction, angle_deg):
        if direction == 1:
            self.linear_vel = 0.5  # max speed
        self.angular_vel = angle_to_rad(angle_deg)
    
    def estimate(self, x, y, yaw, dt):
        est_x = x + self.linear_vel * cos(yaw) * dt
        est_yaw = yaw + self.angular_vel * dt
        return est_x, est_y, est_yaw
```

**Pros:** Accurate for short durations, no delay in command knowledge
**Cons:** Assumes perfect execution, breaks if robot can't execute command (obstacle, slip, etc.)

### 3. Increased Waypoint Tolerance

Changed from 10cm to 15cm radius for waypoint detection. Accounts for uncertainty in position estimates.

### 4. Reduced Control Frequency

Lowered from 20Hz to 10Hz. Reduces control oscillations when working with delayed/noisy data.

## Usage

### Virtual Simulator (Testing):
```bash
python3 path_simulator_delayed.py
```
- Adjust delay slider (0-300ms) to simulate tracking delay
- Toggle prediction on/off to see impact
- Blue circle = true position
- Orange dashed = predicted position

### Real Robot Controller:
```bash
python3 path_controller.py umh_5
```
- Estimate your system's delay (typically 50-150ms for OptiTrack over WiFi)
- Enable prediction checkbox
- System uses velocity-based prediction automatically
- Orange overlay shows where system thinks robot will be

## When to Use Each Technique

**Position Prediction:** Best for smooth, continuous motion. Good general-purpose solution.

**Dead Reckoning:** Best for short bursts between position updates. Combine with position updates to reset accumulated error.

**Combined Approach:** Use position prediction as primary, reset with actual measurements periodically.

## Key Parameters

- `estimated_delay_ms = 100`: Your system's tracking delay
- `waypoint_tolerance = 0.15`: How close to get to waypoints (meters)
- `control_frequency = 10`: Commands per second
- `alpha = 0.3`: Velocity smoothing factor (lower = smoother, higher = more responsive)

