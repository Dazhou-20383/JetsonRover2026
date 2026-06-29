const http = require('node:http');
const net = require('node:net');
const fs = require('node:fs');
const path = require('node:path');

const DASHBOARD_PORT = Number(process.env.DASHBOARD_PORT || 3000);
const SOCKET_HOST = process.env.DASHBOARD_SOCKET_HOST || '0.0.0.0';
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

let telemetryServer = null;
const socketBuffers = new WeakMap();

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

function closeSocket() {
  if (telemetryServer) {
    telemetryServer.close();
    telemetryServer = null;
  }
}

function handleTelemetrySocket(socket) {
  socketBuffers.set(socket, '');
  socket.setNoDelay(true);
  setConnectionStatus(true, null);

  console.log(
    `Telemetry client connected from ${socket.remoteAddress || 'unknown'}:${socket.remotePort || 'unknown'}`,
  );

  socket.on('data', (chunk) => {
    const nextBuffer = `${socketBuffers.get(socket) || ''}${chunk.toString('utf8')}`;
    let socketBuffer = nextBuffer;

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

    socketBuffers.set(socket, socketBuffer);
  });

  socket.on('error', (error) => {
    console.warn(`Telemetry socket error: ${error.message}`);
  });

  socket.on('close', () => {
    socketBuffers.delete(socket);
    if (state.connection.socketConnected) {
      setConnectionStatus(false, 'Socket disconnected');
    }
  });
}

function startSocketServer() {
  closeSocket();

  telemetryServer = net.createServer(handleTelemetrySocket);

  telemetryServer.on('error', (error) => {
    setConnectionStatus(false, error.message);
    console.warn(`Telemetry socket server error: ${error.message}`);
  });

  telemetryServer.listen(SOCKET_PORT, SOCKET_HOST, () => {
    console.log(`Listening for telemetry socket on ${SOCKET_HOST}:${SOCKET_PORT}`);
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
  startSocketServer();
});

process.on('SIGINT', () => {
  closeSocket();
  server.close(() => process.exit(0));
});
