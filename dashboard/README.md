# Jetson Rover Dashboard

This dashboard listens for the newline-delimited JSON stream emitted by `dashboard_node` on TCP port `9000`, then renders it in a browser.

## Run

```bash
cd dashboard
npm start
```

Open `http://localhost:3000` in a browser.

## Configuration

Set these environment variables if you need to change the dashboard bind address or port:

- `DASHBOARD_SOCKET_HOST` defaults to `0.0.0.0`
- `DASHBOARD_SOCKET_PORT` defaults to `9000`
- `DASHBOARD_PORT` defaults to `3000`

When the dashboard runs on your laptop and `dashboard_node` runs on the Jetson, set `DASHBOARD_SOCKET_HOST` on the Jetson to the laptop's Wi-Fi IP so it can connect back to the laptop on port `9000`. You can also pass the same value as the ROS `socket_host` parameter.
