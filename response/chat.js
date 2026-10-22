// Exemplo Response. Copie este arquivo para o projeto que espera a resposta inteira.
// Nada aparece em pedaços: o texto só entra na tela quando o JSON final chega.

const messageEl = document.querySelector("#response-message");
const sendButton = document.querySelector("#response-send");
const clearButton = document.querySelector("#response-clear");
const threadEl = document.querySelector("#response-thread");
const responseErrorEl = document.querySelector("#response-error");
const history = [];

function showResponseError(message) {
  responseErrorEl.hidden = !message;
  responseErrorEl.textContent = message || "";
}

function appendTurn(role, text) {
  const empty = threadEl.querySelector(".empty");
  if (empty) empty.remove();
  const bubble = document.createElement("p");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  threadEl.append(bubble);
  threadEl.scrollTop = threadEl.scrollHeight;
}

function showEmptyThread() {
  threadEl.replaceChildren();
  const empty = document.createElement("p");
  empty.className = "empty";
  empty.textContent = "Escreva uma mensagem. A resposta aparece inteira.";
  threadEl.append(empty);
}

async function sendMessage() {
  const message = messageEl.value.trim();
  showResponseError("");
  window.example.showFormError("");
  window.example.applyFieldErrors([]);
  if (!message) {
    showResponseError("Escreva uma mensagem antes de enviar.");
    return;
  }

  sendButton.disabled = true;
  try {
    const response = await fetch("/api/response", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        context: window.example.readContext(),
        message,
        history,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail;
      const text = typeof detail === "string" ? detail : detail?.message || "Não foi possível responder.";
      const fieldErrors = detail && typeof detail === "object" ? detail.errors || [] : [];
      window.example.applyFieldErrors(fieldErrors);
      const fieldOwnsMessage = fieldErrors.some((error) => error.field && error.message === text);
      if (fieldOwnsMessage) window.example.showFormError("");
      else if (fieldErrors.length) window.example.showFormError(text);
      else showResponseError(text);
      return;
    }
    appendTurn("user", message);
    appendTurn("assistant", data.text || "");
    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: data.text || "" });
    messageEl.value = "";
  } catch (_error) {
    showResponseError("Falha de conexão com o servidor. Tente novamente.");
  } finally {
    sendButton.disabled = false;
  }
}

function clearThread() {
  history.splice(0, history.length);
  messageEl.value = "";
  showResponseError("");
  showEmptyThread();
}

sendButton.addEventListener("click", () => {
  void sendMessage();
});
messageEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void sendMessage();
  }
});
clearButton.addEventListener("click", clearThread);
showEmptyThread();
