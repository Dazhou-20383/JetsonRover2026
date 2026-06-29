const socketStatus = document.getElementById('socketStatus');
const lastMessageAt = document.getElementById('lastMessageAt');
const imageMeta = document.getElementById('imageMeta');
const cameraImage = document.getElementById('cameraImage');
const imagePlaceholder = document.getElementById('imagePlaceholder');
const linearVelocity = document.getElementById('linearVelocity');
const angularVelocity = document.getElementById('angularVelocity');
const poseX = document.getElementById('poseX');
const poseY = document.getElementById('poseY');
const poseTheta = document.getElementById('poseTheta');
const motorCommands = document.getElementById('motorCommands');
const motorCount = document.getElementById('motorCount');
const agentState = document.getElementById('agentState');
const snapshot = document.getElementById('snapshot');

function formatNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(3) : '0.000';
}

function renderMotorCommands(values) {
  motorCommands.innerHTML = '';

  if (!Array.isArray(values) || values.length === 0) {
    motorCount.textContent = '0 values';
    motorCommands.innerHTML = '<div class="command-item"><span>Status</span><strong>No commands</strong></div>';
    return;
  }

  motorCount.textContent = `${values.length} values`;
  values.forEach((value, index) => {
    const row = document.createElement('div');
    row.className = 'command-item';
    row.innerHTML = `<span>Motor ${index + 1}</span><strong>${Number(value).toFixed(3)}</strong>`;
    motorCommands.appendChild(row);
  });
}

function setStatus(connected, errorMessage) {
  socketStatus.textContent = connected ? 'Connected' : 'Disconnected';
  socketStatus.className = connected ? 'status-value ok' : 'status-value warn';
  lastMessageAt.textContent = errorMessage || 'Waiting for first payload';
}

function updateSnapshot(data) {
  const connection = data?.connection || {};
  const payload = data?.data || {};

  setStatus(Boolean(connection.socketConnected), connection.lastSocketError);

  if (connection.lastMessageAt) {
    lastMessageAt.textContent = `Last message ${new Date(connection.lastMessageAt).toLocaleString()}`;
  }

  linearVelocity.textContent = formatNumber(payload.velocity?.linear);
  angularVelocity.textContent = formatNumber(payload.velocity?.angular);
  poseX.textContent = formatNumber(payload.pose?.x);
  poseY.textContent = formatNumber(payload.pose?.y);
  poseTheta.textContent = formatNumber(payload.pose?.theta);

  renderMotorCommands(payload.motor_commands);

  agentState.textContent = JSON.stringify(payload.agent_state ?? {}, null, 2);
  snapshot.textContent = JSON.stringify(data, null, 2);

  if (payload.image?.data) {
    cameraImage.src = `data:image/jpeg;base64,${payload.image.data}`;
    cameraImage.style.display = 'block';
    imagePlaceholder.style.display = 'none';
    imageMeta.textContent = `${payload.image.width || '?'} x ${payload.image.height || '?'} JPEG`;
  } else {
    cameraImage.removeAttribute('src');
    cameraImage.style.display = 'none';
    imagePlaceholder.style.display = 'grid';
    imageMeta.textContent = 'No image yet';
  }
}

const eventSource = new EventSource('/events');

eventSource.addEventListener('status', (event) => {
  const payload = JSON.parse(event.data);
  setStatus(Boolean(payload.connection?.socketConnected), payload.connection?.lastSocketError);
});

eventSource.addEventListener('snapshot', (event) => {
  updateSnapshot(JSON.parse(event.data));
});

eventSource.onerror = () => {
  setStatus(false, 'Browser stream disconnected');
};