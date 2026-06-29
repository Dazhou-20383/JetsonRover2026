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

function formatMessageContent(content) {
  if (Array.isArray(content)) {
    const fragments = content
      .map((entry) => {
        if (entry && typeof entry === 'object' && entry.type === 'text') {
          return entry.text ?? '';
        }

        if (typeof entry === 'string') {
          return entry;
        }

        if (entry == null) {
          return '';
        }

        return JSON.stringify(entry, null, 2);
      })
      .filter(Boolean);

    return fragments.length > 0 ? fragments.join('\n') : 'No text content';
  }

  if (typeof content === 'string') {
    return content;
  }

  if (content == null) {
    return 'No content';
  }

  return JSON.stringify(content, null, 2);
}

function renderAgentState(value) {
  agentState.innerHTML = '';

  if (Array.isArray(value)) {
    if (value.length === 0) {
      agentState.innerHTML = '<div class="conversation-empty">No agent messages yet.</div>';
      return;
    }

    value.forEach((message, index) => {
      const role = String(message?.role || 'unknown').toLowerCase();
      const card = document.createElement('article');
      card.className = `message-card role-${role}`;

      const header = document.createElement('div');
      header.className = 'message-header';

      const roleLabel = document.createElement('span');
      roleLabel.className = 'message-role';
      roleLabel.textContent = message?.role || `message ${index + 1}`;

      const meta = document.createElement('span');
      meta.className = 'message-meta';
      meta.textContent = message?.tool_calls?.length ? `${message.tool_calls.length} tool call${message.tool_calls.length === 1 ? '' : 's'}` : 'chat turn';

      header.appendChild(roleLabel);
      header.appendChild(meta);

      const body = document.createElement('pre');
      body.className = 'message-content';
      body.textContent = formatMessageContent(message?.content);

      card.appendChild(header);
      card.appendChild(body);

      if (Array.isArray(message?.tool_calls) && message.tool_calls.length > 0) {
        const tools = document.createElement('div');
        tools.className = 'message-tools';

        message.tool_calls.forEach((toolCall) => {
          const tool = document.createElement('span');
          tool.className = 'tool-pill';
          const toolName = toolCall?.function?.name || 'tool';
          tool.textContent = `${toolName}`;
          tools.appendChild(tool);
        });

        card.appendChild(tools);
      }

      agentState.appendChild(card);
    });

    return;
  }

  if (value && typeof value === 'object') {
    const fallback = document.createElement('pre');
    fallback.className = 'message-content conversation-fallback';
    fallback.textContent = JSON.stringify(value, null, 2);
    agentState.appendChild(fallback);
    return;
  }

  agentState.innerHTML = '<div class="conversation-empty">No agent state yet.</div>';
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

  renderAgentState(payload.agent_state ?? {});
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