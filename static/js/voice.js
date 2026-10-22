const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";

const statusLabels = {
  idle: "Aguardando",
  connecting: "Conectando",
  listening: "Ouvindo",
  transcribing: "Transcrevendo",
  speaking: "Falando",
};

const state = {
  assistant: null,
  pc: null,
  dc: null,
  localStream: null,
  guardEnabled: false,
  turn: 0,
  assistantNode: null,
  stopping: false,
};

const setupEl = document.querySelector("#setup");
const conversationEl = document.querySelector("#conversation");
const formEl = document.querySelector("#context-form");
const startButton = document.querySelector("#start");
const stopButton = document.querySelector("#stop");
const transcriptEl = document.querySelector("#transcript");
const statusEl = document.querySelector("#status");
const formErrorEl = document.querySelector("#form-error");
const liveErrorEl = document.querySelector("#live-error");

function setStatus(next) {
  statusEl.dataset.state = next;
  statusEl.textContent = statusLabels[next] || statusLabels.idle;
}

function showError(element, message) {
  if (!message) {
    element.hidden = true;
    element.textContent = "";
    return;
  }
  element.hidden = false;
  element.textContent = message;
}

function fieldErrorElement(key) {
  return formEl.querySelector(`[data-error-for="${CSS.escape(key)}"]`);
}

function clearFieldErrors() {
  formEl.querySelectorAll(".field-error").forEach((node) => {
    node.textContent = "";
  });
}

function renderAssistant(assistant) {
  document.querySelector("#assistant-name").textContent = assistant.name || "Assistente";
  document.querySelector("#tagline").textContent = assistant.tagline || "";
  document.querySelector("#privacy").textContent = assistant.privacy_notice || "";
  document.title = assistant.name ? `${assistant.name} · IA-STREAM` : "IA-STREAM";
  formEl.replaceChildren();

  for (const field of assistant.context_fields || []) {
    const wrapper = document.createElement("div");
    wrapper.className = "field";

    const label = document.createElement("label");
    label.htmlFor = `field-${field.key}`;
    label.textContent = field.label;

    const control = createControl(field);
    wrapper.append(label, control);

    if (field.help) {
      const help = document.createElement("p");
      help.className = "help";
      help.textContent = field.help;
      wrapper.append(help);
    }

    const error = document.createElement("p");
    error.className = "field-error";
    error.dataset.errorFor = field.key;
    wrapper.append(error);
    formEl.append(wrapper);
  }

  if (!(assistant.context_fields || []).length) {
    const note = document.createElement("p");
    note.className = "help";
    note.textContent = "Nenhum dado é pedido antes da conversa.";
    formEl.append(note);
  }
}

function createControl(field) {
  let control;
  if (field.type === "textarea") {
    control = document.createElement("textarea");
  } else if (field.type === "select") {
    control = document.createElement("select");
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = field.required ? "Selecione" : "Não informar";
    control.append(empty);
    for (const option of field.options || []) {
      const node = document.createElement("option");
      node.value = option.value;
      node.textContent = option.label;
      control.append(node);
    }
  } else {
    control = document.createElement("input");
    control.type = field.type === "number" ? "text" : "text";
    control.inputMode = field.type === "number" ? "decimal" : "text";
  }
  control.id = `field-${field.key}`;
  control.name = field.key;
  control.autocomplete = "off";
  if (field.placeholder && control.placeholder !== undefined) {
    control.placeholder = field.placeholder;
  }
  if (field.required) control.required = true;
  if (field.max_length) control.maxLength = field.max_length;
  return control;
}

function readContext() {
  const context = {};
  for (const field of state.assistant.context_fields || []) {
    const control = formEl.querySelector(`#field-${CSS.escape(field.key)}`);
    context[field.key] = control ? control.value.trim() : "";
  }
  return context;
}

function applyServerErrors(errors) {
  clearFieldErrors();
  for (const error of errors || []) {
    if (!error.field) continue;
    const node = fieldErrorElement(error.field);
    if (node) node.textContent = error.message;
  }
}

function appendBubble(role, text) {
  const empty = transcriptEl.querySelector(".empty");
  if (empty) empty.remove();
  const bubble = document.createElement("p");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  transcriptEl.append(bubble);
  transcriptEl.scrollTop = transcriptEl.scrollHeight;
  return bubble;
}

function showEmptyTranscript() {
  transcriptEl.replaceChildren();
  const empty = document.createElement("p");
  empty.className = "empty";
  empty.textContent = "Pode falar. Estou ouvindo.";
  transcriptEl.append(empty);
}

function sendEvent(event) {
  if (!state.dc || state.dc.readyState !== "open") return;
  state.dc.send(JSON.stringify(event));
}

async function guardAndRespond(text) {
  const turn = ++state.turn;
  let decision = { allowed: true, refusal_instructions: null };
  try {
    const response = await fetch("/api/guard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (response.ok) decision = await response.json();
  } catch (_error) {
    decision = { allowed: true, refusal_instructions: null };
  }
  if (turn !== state.turn || state.stopping) return;
  if (decision.allowed || !decision.refusal_instructions) {
    sendEvent({ type: "response.create" });
    return;
  }
  sendEvent({
    type: "response.create",
    response: {
      instructions: decision.refusal_instructions,
      max_output_tokens: 80,
    },
  });
}

function onRealtimeEvent(raw) {
  let event;
  try {
    event = JSON.parse(raw.data);
  } catch (_error) {
    return;
  }

  if (event.type === "input_audio_buffer.speech_started") {
    setStatus("listening");
    return;
  }
  if (event.type === "input_audio_buffer.speech_stopped") {
    setStatus("transcribing");
    return;
  }
  if (event.type === "conversation.item.input_audio_transcription.completed") {
    const text = (event.transcript || "").trim();
    if (!text) return;
    appendBubble("user", text);
    if (state.guardEnabled) {
      void guardAndRespond(text);
    }
    return;
  }
  if (event.type === "response.created") {
    state.assistantNode = appendBubble("assistant", "");
    setStatus("speaking");
    return;
  }
  if (event.type === "response.output_audio_transcript.delta") {
    if (!state.assistantNode) state.assistantNode = appendBubble("assistant", "");
    state.assistantNode.textContent += event.delta || "";
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
    return;
  }
  if (event.type === "response.output_audio_transcript.done") {
    if (state.assistantNode && event.transcript) {
      state.assistantNode.textContent = event.transcript;
    }
    return;
  }
  if (event.type === "response.done" || event.type === "output_audio_buffer.stopped") {
    state.assistantNode = null;
    if (!state.stopping) setStatus("listening");
  }
}

async function connect(ephemeralKey) {
  const pc = new RTCPeerConnection();
  state.pc = pc;
  const audio = document.querySelector("#remote-audio");
  pc.ontrack = (event) => {
    audio.srcObject = event.streams[0];
  };

  state.localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  for (const track of state.localStream.getTracks()) {
    pc.addTrack(track, state.localStream);
  }

  const dc = pc.createDataChannel("oai-events");
  state.dc = dc;
  dc.addEventListener("message", onRealtimeEvent);
  dc.addEventListener("open", () => {
    if (!state.stopping) setStatus("listening");
  });

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  const sdpResponse = await fetch(REALTIME_CALLS_URL, {
    method: "POST",
    body: offer.sdp,
    headers: {
      Authorization: `Bearer ${ephemeralKey}`,
      "Content-Type": "application/sdp",
    },
  });
  if (!sdpResponse.ok) {
    throw new Error("sdp");
  }
  const answer = await sdpResponse.text();
  await pc.setRemoteDescription({ type: "answer", sdp: answer });
}

function stopMedia() {
  if (state.dc) {
    state.dc.close();
    state.dc = null;
  }
  if (state.pc) {
    state.pc.close();
    state.pc = null;
  }
  if (state.localStream) {
    for (const track of state.localStream.getTracks()) track.stop();
    state.localStream = null;
  }
  const audio = document.querySelector("#remote-audio");
  audio.srcObject = null;
}

function resetScreen() {
  state.stopping = true;
  state.turn += 1;
  stopMedia();
  state.assistantNode = null;
  state.guardEnabled = false;
  transcriptEl.replaceChildren();
  formEl.reset();
  clearFieldErrors();
  showError(formErrorEl, "");
  showError(liveErrorEl, "");
  conversationEl.hidden = true;
  setupEl.hidden = false;
  startButton.disabled = false;
  setStatus("idle");
  state.stopping = false;
}

async function startConversation() {
  showError(formErrorEl, "");
  clearFieldErrors();
  startButton.disabled = true;
  setStatus("connecting");
  state.stopping = false;

  let token;
  try {
    const response = await fetch("/api/realtime/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: readContext() }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string" ? detail : detail?.message || "Não foi possível iniciar.";
      applyServerErrors(detail?.errors);
      showError(formErrorEl, message);
      startButton.disabled = false;
      setStatus("idle");
      return;
    }
    token = data;
  } catch (_error) {
    showError(formErrorEl, "Falha de conexão com o servidor. Tente novamente.");
    startButton.disabled = false;
    setStatus("idle");
    return;
  }

  state.guardEnabled = Boolean(token.guard_enabled);
  try {
    await connect(token.client_secret);
  } catch (error) {
    stopMedia();
    const denied = error && error.name === "NotAllowedError";
    showError(
      formErrorEl,
      denied
        ? "O microfone precisa estar liberado para a conversa."
        : "Não foi possível conectar a conversa. Tente novamente.",
    );
    startButton.disabled = false;
    setStatus("idle");
    return;
  }

  showEmptyTranscript();
  setupEl.hidden = true;
  conversationEl.hidden = false;
  showError(liveErrorEl, "");
}

async function boot() {
  setStatus("idle");
  try {
    const response = await fetch("/api/assistant");
    if (!response.ok) throw new Error("config");
    state.assistant = await response.json();
    renderAssistant(state.assistant);
  } catch (_error) {
    showError(formErrorEl, "Não foi possível carregar a configuração do assistente.");
    startButton.disabled = true;
  }
}

startButton.addEventListener("click", () => {
  void startConversation();
});
stopButton.addEventListener("click", resetScreen);
formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  void startConversation();
});

void boot();
