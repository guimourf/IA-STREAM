// Exemplo Stream. Copie este arquivo para o projeto que conversa por voz.
// O servidor só devolve um token. O áudio entra e sai por WebRTC, direto com a OpenAI.

const statusLabels = {
  idle: "Aguardando",
  connecting: "Conectando",
  listening: "Ouvindo",
  transcribing: "Transcrevendo",
  speaking: "Falando",
};

const state = {
  pc: null,
  dc: null,
  localStream: null,
  guardEnabled: false,
  turn: 0,
  assistantNode: null,
  stopping: false,
  active: false,
};

const startButton = document.querySelector("#start");
const stopButton = document.querySelector("#stop");
const transcriptEl = document.querySelector("#transcript");
const statusEl = document.querySelector("#status");
const liveErrorEl = document.querySelector("#live-error");
const conversationEl = document.querySelector("#conversation");

function setStatus(next) {
  statusEl.dataset.state = next;
  statusEl.textContent = statusLabels[next] || statusLabels.idle;
}

function showLiveError(message) {
  liveErrorEl.hidden = !message;
  liveErrorEl.textContent = message || "";
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
  empty.textContent = "Pode falar. A resposta chega enquanto a voz é gerada.";
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
    response: { instructions: decision.refusal_instructions, max_output_tokens: 80 },
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
    if (state.guardEnabled) void guardAndRespond(text);
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
  if (event.type === "response.output_audio_transcript.done" && state.assistantNode && event.transcript) {
    state.assistantNode.textContent = event.transcript;
    return;
  }
  if (event.type === "response.done" || event.type === "output_audio_buffer.stopped") {
    state.assistantNode = null;
    if (!state.stopping) setStatus("listening");
  }
}

async function connect(session) {
  const pc = new RTCPeerConnection();
  state.pc = pc;
  const audio = document.querySelector("#remote-audio");
  pc.ontrack = (event) => {
    audio.srcObject = event.streams[0];
  };
  state.localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  for (const track of state.localStream.getTracks()) pc.addTrack(track, state.localStream);

  const dc = pc.createDataChannel(session.webrtc.data_channel);
  state.dc = dc;
  dc.addEventListener("message", onRealtimeEvent);
  dc.addEventListener("open", () => {
    if (!state.stopping) setStatus("listening");
  });

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  const sdpResponse = await fetch(session.webrtc.url, {
    method: "POST",
    body: offer.sdp,
    headers: {
      Authorization: `Bearer ${session.client_secret}`,
      "Content-Type": session.webrtc.content_type,
    },
  });
  if (!sdpResponse.ok) throw new Error("sdp");
  await pc.setRemoteDescription({ type: "answer", sdp: await sdpResponse.text() });
}

function stopMedia() {
  if (state.dc) state.dc.close();
  if (state.pc) state.pc.close();
  state.dc = null;
  state.pc = null;
  if (state.localStream) {
    for (const track of state.localStream.getTracks()) track.stop();
    state.localStream = null;
  }
  const audio = document.querySelector("#remote-audio");
  if (audio) audio.srcObject = null;
}

function resetScreen() {
  const wasActive = state.active;
  state.stopping = true;
  state.turn += 1;
  stopMedia();
  state.assistantNode = null;
  state.guardEnabled = false;
  state.active = false;
  transcriptEl.replaceChildren();
  showLiveError("");
  conversationEl.hidden = true;
  startButton.disabled = false;
  setStatus("idle");
  if (wasActive) window.example.showContext(true);
  state.stopping = false;
}

function failStart(message, errors) {
  window.example.applyFieldErrors(errors);
  const fieldOwnsMessage = (errors || []).some((error) => error.field && error.message === message);
  window.example.showFormError(fieldOwnsMessage ? "" : message);
  startButton.disabled = false;
  setStatus("idle");
}

async function startConversation() {
  window.example.showFormError("");
  window.example.applyFieldErrors([]);
  showLiveError("");
  startButton.disabled = true;
  setStatus("connecting");
  state.stopping = false;

  let session;
  try {
    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: window.example.readContext() }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const message = typeof detail === "string" ? detail : detail?.message || "Não foi possível iniciar.";
      const fieldErrors = detail && typeof detail === "object" ? detail.errors || [] : [];
      failStart(message, fieldErrors);
      return;
    }
    session = data;
  } catch (_error) {
    failStart("Falha de conexão com o servidor. Tente novamente.");
    return;
  }

  state.guardEnabled = Boolean(session.guard_enabled);
  try {
    await connect(session);
  } catch (error) {
    stopMedia();
    const denied = error && error.name === "NotAllowedError";
    failStart(
      denied
        ? "O microfone precisa estar liberado para a conversa."
        : "Não foi possível conectar a conversa. Tente novamente.",
    );
    return;
  }

  state.active = true;
  showEmptyTranscript();
  window.example.showContext(false);
  conversationEl.hidden = false;
}

startButton.addEventListener("click", () => {
  void startConversation();
});
stopButton.addEventListener("click", resetScreen);
setStatus("idle");
window.streamExample = { stop: resetScreen };
