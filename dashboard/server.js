const http = require('node:http');
const net = require('node:net');
const fs = require('node:fs');
const path = require('node:path');

const DASHBOARD_PORT = Number(process.env.DASHBOARD_PORT || 3000);
const SOCKET_HOST = process.env.DASHBOARD_SOCKET_HOST || '127.0.0.1';
const SOCKET_PORT = Number(process.env.DASHBOARD_SOCKET_PORT || 9000);

const publicDir = path.join(__dirname, 'public');
const clients = new Set();

const state = {
  connection: {
    socketConnected: false,
    lastSocketError: null,
    lastMessageAt: null,
  },
  data: {
    agent_state: {},
    velocity: { linear: 0, angular: 0 },
    motor_commands: [],
    pose: { x: 0, y: 0, theta: 0 },
    image: null,
    stamp_ns: null,
  },
};

let socketClient = null;
let reconnectTimer = null;
let socketBuffer = '';

function sendSse(res, eventName, payload) {
  res.write(`event: ${eventName}\n`);
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
}

function broadcast(eventName, payload) {
  const message = `event: ${eventName}\ndata: ${JSON.stringify(payload)}\n\n`;
  for (const res of clients) {
    res.write(message);
  }
}

function updateState(nextData) {
  state.data = {
    agent_state: nextData.agent_state ?? {},
    velocity: nextData.velocity ?? { linear: 0, angular: 0 },
    motor_commands: Array.isArray(nextData.motor_commands) ? nextData.motor_commands : [],
    pose: nextData.pose ?? { x: 0, y: 0, theta: 0 },
    image: nextData.image ?? null,
    stamp_ns: nextData.stamp_ns ?? null,
  };
  state.connection.lastMessageAt = new Date().toISOString();
  broadcast('snapshot', { ...state });
}

function setConnectionStatus(connected, errorMessage = null) {
  state.connection.socketConnected = connected;
  state.connection.lastSocketError = errorMessage;
  broadcast('status', { connection: state.connection });
}

function scheduleReconnect() {
  if (reconnectTimer) {
    return;
  }

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectSocket();
  }, 1500);
}

function closeSocket() {
  if (socketClient) {
    socketClient.destroy();
    socketClient = null;
  }
}

function connectSocket() {
  closeSocket();

  socketBuffer = '';
  socketClient = net.createConnection({ host: SOCKET_HOST, port: SOCKET_PORT });

  socketClient.setNoDelay(true);

  socketClient.on('connect', () => {
    setConnectionStatus(true, null);
    console.log(`Connected to telemetry socket at ${SOCKET_HOST}:${SOCKET_PORT}`);
  });

  socketClient.on('data', (chunk) => {
    socketBuffer += chunk.toString('utf8');

    let newlineIndex = socketBuffer.indexOf('\n');
    while (newlineIndex !== -1) {
      const rawLine = socketBuffer.slice(0, newlineIndex).trim();
      socketBuffer = socketBuffer.slice(newlineIndex + 1);
      newlineIndex = socketBuffer.indexOf('\n');

      if (!rawLine) {
        continue;
      }

      try {
        const parsed = JSON.parse(rawLine);
        updateState(parsed);
      } catch (error) {
        console.warn('Failed to parse telemetry payload:', error.message);
      }
    }
  });

  socketClient.on('error', (error) => {
    setConnectionStatus(false, error.message);
    console.warn(`Telemetry socket error: ${error.message}`);
  });

  socketClient.on('close', () => {
    if (state.connection.socketConnected) {
      setConnectionStatus(false, 'Socket disconnected');
    }
    scheduleReconnect();
  });
}

function contentTypeFor(filePath) {
  if (filePath.endsWith('.html')) return 'text/html; charset=utf-8';
  if (filePath.endsWith('.css')) return 'text/css; charset=utf-8';
  if (filePath.endsWith('.js')) return 'application/javascript; charset=utf-8';
  if (filePath.endsWith('.svg')) return 'image/svg+xml';
  return 'application/octet-stream';
}

function serveStatic(res, fileName) {
  const filePath = path.join(publicDir, fileName);
  fs.readFile(filePath, (error, content) => {
    if (error) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not found');
      return;
    }

    res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) });
    res.end(content);
  });
}

const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/index.html') {
    serveStatic(res, 'index.html');
    return;
  }

  if (req.url === '/styles.css') {
    serveStatic(res, 'styles.css');
    return;
  }

  if (req.url === '/app.js') {
    serveStatic(res, 'app.js');
    return;
  }

  if (req.url === '/events') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    });

    res.write(': connected\n\n');
    clients.add(res);

    sendSse(res, 'status', { connection: state.connection });
    sendSse(res, 'snapshot', { ...state });

    req.on('close', () => {
      clients.delete(res);
    });
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end('Not found');
});

server.listen(DASHBOARD_PORT, () => {
  console.log(`Dashboard available at http://localhost:${DASHBOARD_PORT}`);
  console.log(`Listening for telemetry socket on ${SOCKET_HOST}:${SOCKET_PORT}`);
  connectSocket();
});

process.on('SIGINT', () => {
  closeSocket();
  server.close(() => process.exit(0));
});
