// Exemplo Voz + texto. Copie este arquivo para o projeto que ouve a fala e mostra a resposta inteira.
// A sessão Realtime só transcreve. O texto vem de /api/response. A voz vem de /api/speech.
(() => {
const statusLabels = {
  idle: "Aguardando",
  connecting: "Conectando",
  listening: "Ouvindo",
  transcribing: "Transcrevendo",
  responding: "Respondendo",
  speaking: "Falando",
};

const state = {
  pc: null,
  dc: null,
  localStream: null,
  guardEnabled: false,
  turn: 0,
  pending: false,
  stopping: false,
  active: false,
  history: [],
};

const startButton = document.querySelector("#hybrid-start");
const stopButton = document.querySelector("#hybrid-stop");
const transcriptEl = document.querySelector("#hybrid-transcript");
const statusEl = document.querySelector("#status");
const liveErrorEl = document.querySelector("#hybrid-error");
const conversationEl = document.querySelector("#hybrid-conversation");
const speechAudio = document.querySelector("#hybrid-audio");

function setStatus(next) {
  if (window.example?.mode && window.example.mode !== "hybrid") return;
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
  empty.textContent = "Pode falar. A resposta aparece inteira e é falada.";
  transcriptEl.append(empty);
}

function setMicEnabled(enabled) {
  if (!state.localStream) return;
  for (const track of state.localStream.getTracks()) track.enabled = enabled;
}

function trimHistory() {
  while (state.history.length > 12) state.history.shift();
}

async function speak(text) {
  const response = await fetch("/api/speech", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error("speech");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  speechAudio.src = url;
  setMicEnabled(false);
  setStatus("speaking");
  try {
    await speechAudio.play();
    await new Promise((resolve, reject) => {
      speechAudio.onended = resolve;
      speechAudio.onerror = reject;
    });
  } finally {
    URL.revokeObjectURL(url);
    speechAudio.removeAttribute("src");
    setMicEnabled(true);
  }
}

async function requestCompleteText(message) {
  const response = await fetch("/api/response", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      context: window.example.readContext(),
      message,
      history: state.history,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const text = typeof detail === "string" ? detail : detail?.message || "Não foi possível responder.";
    throw new Error(text);
  }
  return (data.text || "").trim();
}

async function handleUtterance(text) {
  const turn = ++state.turn;
  state.pending = true;
  setStatus("responding");
  showLiveError("");

  let spoken = "";
  try {
    if (state.guardEnabled) {
      let decision = { allowed: true, refusal_text: null };
      try {
        const response = await fetch("/api/guard", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (response.ok) decision = await response.json();
      } catch (_error) {
        decision = { allowed: true, refusal_text: null };
      }
      if (turn !== state.turn || state.stopping) return;
      if (!decision.allowed && decision.refusal_text) {
        spoken = decision.refusal_text;
      }
    }
    if (!spoken) {
      spoken = await requestCompleteText(text);
    }
    if (turn !== state.turn || state.stopping) return;
    if (!spoken) throw new Error("A resposta veio vazia. Tente novamente.");

    appendBubble("assistant", spoken);
    state.history.push({ role: "user", content: text });
    state.history.push({ role: "assistant", content: spoken });
    trimHistory();
    try {
      await speak(spoken);
    } catch (_error) {
      if (turn === state.turn && !state.stopping) {
        showLiveError("A resposta está na tela, mas não foi possível falá-la.");
      }
    }
  } catch (error) {
    if (turn === state.turn && !state.stopping) {
      showLiveError(error.message || "Não foi possível responder. Tente novamente.");
    }
  } finally {
    if (turn === state.turn) {
      state.pending = false;
      if (!state.stopping && state.active) setStatus("listening");
    }
  }
}

function onRealtimeEvent(raw) {
  let event;
  try {
    event = JSON.parse(raw.data);
  } catch (_error) {
    return;
  }
  if (event.type === "input_audio_buffer.speech_started") {
    if (!state.pending && !state.stopping) setStatus("listening");
    return;
  }
  if (event.type === "input_audio_buffer.speech_stopped") {
    if (!state.pending && !state.stopping) setStatus("transcribing");
    return;
  }
  if (event.type === "conversation.item.input_audio_transcription.completed") {
    const text = (event.transcript || "").trim();
    if (!text || state.pending || state.stopping || !state.active) return;
    appendBubble("user", text);
    void handleUtterance(text);
  }
}

async function connect(session) {
  const pc = new RTCPeerConnection();
  state.pc = pc;
  const remote = document.querySelector("#hybrid-remote");
  pc.ontrack = (event) => {
    remote.srcObject = event.streams[0];
  };
  state.localStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });
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
  const remote = document.querySelector("#hybrid-remote");
  if (remote) remote.srcObject = null;
  speechAudio.pause();
  speechAudio.removeAttribute("src");
}

function resetScreen() {
  const wasActive = state.active;
  state.stopping = true;
  state.turn += 1;
  state.pending = false;
  stopMedia();
  state.guardEnabled = false;
  state.active = false;
  state.history = [];
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
  state.history = [];

  let session;
  try {
    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: window.example.readContext(), transcribe_only: true }),
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
window.hybridExample = { stop: resetScreen };
})();
