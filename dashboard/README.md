# Jetson Rover Dashboard

This dashboard reads the newline-delimited JSON stream emitted by `dashboard_node` on TCP port `9000`, then renders it in a browser.

## Run

```bash
cd dashboard
npm start
```

Open `http://localhost:3000` in a browser.

## Configuration

Set these environment variables if the socket is running elsewhere:

- `DASHBOARD_SOCKET_HOST` defaults to `127.0.0.1`
- `DASHBOARD_SOCKET_PORT` defaults to `9000`
- `DASHBOARD_PORT` defaults to `3000`
