# Debugging OptiTrack Tracking

## Quick Start

Run the advanced server to see if UDP packets are being received:

```bash
python3 src/server/server_tracking_advanced.py
```

Or the barebones version:

```bash
python3 src/server/server_tracking_barebones.py
```

## What to Look For

### 1. Startup Messages

You should see:
```
🚀 STARTING SERVER
✓ Created X Robot instances
🎯 Starting UDP listeners for OptiTrack data...
[Tracker: umh_2] 🎯 Starting listener on 0.0.0.0:9876
[Tracker: umh_2] ✓ Successfully bound to port 9876
[Tracker: umh_3] 🎯 Starting listener on 0.0.0.0:9877
...
```

**If you see "❌ ERROR: Could not bind to port":**
- Port is already in use
- Another instance is running
- Check firewall settings

### 2. UDP Packet Reception

When OptiTrack sends data, you'll see:
```
[Tracker: umh_2] 📦 First packet from ('192.168.x.x', 12345): '[x,y,z,yaw]'
[Tracker: umh_2] 📍 Packets: 120, Current pos: x=5.234, y=3.897, yaw=90.00°
```

**If you DON'T see packet messages:**
- OptiTrack is not sending data
- Wrong port numbers in config.json
- Firewall blocking UDP
- OptiTrack not configured to send to this machine

### 3. Position Display

**Advanced UI:**
- Map shows robots with direction arrows
- Text box below map shows positions as numbers
- Updates 10 times per second

**Barebones:**
- Type `p` or `positions` to see current positions
- Should show actual coordinates, not (0, 0, 0)

## Common Issues

### Positions stay at (0, 0, 0)
**Cause:** Not receiving UDP packets from OptiTrack

**Fix:**
1. Check OptiTrack is running
2. Verify ports in config.json match OptiTrack settings
3. Make sure OptiTrack is sending to this computer's IP
4. Check firewall: `sudo ufw allow 9876/udp` (if using ufw)

### "Port already in use"
**Cause:** Another instance is running or port not released

**Fix:**
1. Kill other instances: `pkill -f server_tracking`
2. Wait a few seconds
3. Try again
4. Or use different port: `python3 src/server/server_tracking_advanced.py 7000`

### No "First packet" message
**Cause:** OptiTrack not sending or wrong configuration

**Fix:**
1. Check OptiTrack streaming settings
2. Verify this computer's IP in OptiTrack
3. Test with netcat: `nc -u -l 9876` (should show incoming data)
4. Check config.json ports match OptiTrack rigid body settings

## Debugging Tips

### Test UDP Reception Manually

Terminal 1 - Listen on port:
```bash
nc -u -l 9876
```

Terminal 2 - Send test data:
```bash
echo "[100,200,50,45]" | nc -u localhost 9876
```

If Terminal 1 shows the data, UDP is working.

### Check What's Using Ports

```bash
# macOS
lsof -i :9876

# Linux
sudo netstat -tulpn | grep 9876
```

### Monitor All Network Traffic

```bash
# macOS/Linux
sudo tcpdump -i any udp port 9876
```

Should show packets if OptiTrack is sending.

## config.json Structure

```json
{
  "ROBOT_CONFIG": {
    "umh_2": {
      "ip": "192.168.1.2",    // Robot's IP for TCP commands
      "port": 9876            // UDP port for OptiTrack data
    }
  }
}
```

- `ip`: Where to send robot movement commands (TCP)
- `port`: Where to listen for OptiTrack position data (UDP)

## Debug Checklist

- [ ] Server starts without errors
- [ ] All UDP listeners bind successfully
- [ ] See "First packet" messages for each robot
- [ ] Packet count increases over time
- [ ] Positions update from (0,0,0) to actual values
- [ ] Map shows robots moving (Advanced UI)
- [ ] Position text shows changing coordinates

## Still Not Working?

1. **Verify OptiTrack is sending:**
   - Open OptiTrack Motive
   - Check streaming settings
   - Verify rigid body is being tracked
   - Check "Broadcast Frame Data" is enabled

2. **Check network:**
   ```bash
   ping <optitrack-computer-ip>
   ```

3. **Try simple UDP test:**
   ```bash
   # Listen for any UDP on port
   nc -u -l 9876
   ```

4. **Check firewall:**
   ```bash
   # macOS - allow incoming UDP
   # No built-in command, check System Preferences > Security
   
   # Linux
   sudo ufw status
   sudo ufw allow 9876/udp
   ```

