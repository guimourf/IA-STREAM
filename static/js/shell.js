// Casca da página de exemplo. Os modos ficam em stream/voice.js, response/chat.js e hybrid/listen.js.

const modeHelp = {
  stream: "A voz e o texto chegam aos poucos, direto da OpenAI. O código está na pasta stream/.",
  response: "A mensagem vai ao servidor e a resposta volta inteira, num único JSON. O código está na pasta response/.",
  hybrid: "Você fala. A resposta volta inteira, em texto e em voz. O código está na pasta hybrid/.",
};

const formEl = document.querySelector("#context-form");
const formErrorEl = document.querySelector("#form-error");
const contextCard = document.querySelector("#context-card");

const example = {
  assistant: null,
  mode: "stream",
  readContext() {
    const context = {};
    for (const field of example.assistant?.context_fields || []) {
      const control = formEl.querySelector(`#field-${CSS.escape(field.key)}`);
      context[field.key] = control ? control.value.trim() : "";
    }
    return context;
  },
  applyFieldErrors(errors) {
    formEl.querySelectorAll(".field-error").forEach((node) => {
      node.textContent = "";
    });
    for (const error of errors || []) {
      if (!error.field) continue;
      const node = formEl.querySelector(`[data-error-for="${CSS.escape(error.field)}"]`);
      if (node) node.textContent = error.message;
    }
  },
  showFormError(message) {
    formErrorEl.hidden = !message;
    formErrorEl.textContent = message || "";
  },
  showContext(visible) {
    contextCard.hidden = !visible;
  },
};

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
    control.type = "text";
    control.inputMode = field.type === "number" ? "decimal" : "text";
  }
  control.id = `field-${field.key}`;
  control.autocomplete = "off";
  if (field.placeholder) control.placeholder = field.placeholder;
  if (field.required) control.required = true;
  if (field.max_length) control.maxLength = field.max_length;
  return control;
}

function renderAssistant(assistant) {
  document.querySelector("#assistant-name").textContent = assistant.name || "Assistente";
  document.querySelector("#tagline").textContent = assistant.tagline || "";
  document.querySelector("#privacy").textContent = assistant.privacy_notice || "";
  formEl.replaceChildren();
  for (const field of assistant.context_fields || []) {
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    const label = document.createElement("label");
    label.htmlFor = `field-${field.key}`;
    label.textContent = field.label;
    wrapper.append(label, createControl(field));
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
}

function selectMode(mode) {
  if (mode !== "stream" && window.streamExample) window.streamExample.stop();
  if (mode !== "hybrid" && window.hybridExample) window.hybridExample.stop();
  example.mode = mode;
  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.setAttribute("aria-selected", String(button.dataset.mode === mode));
  });
  document.querySelector("#panel-stream").hidden = mode !== "stream";
  document.querySelector("#panel-response").hidden = mode !== "response";
  document.querySelector("#panel-hybrid").hidden = mode !== "hybrid";
  document.querySelector("#mode-help").textContent = modeHelp[mode] || "";
  if (mode === "response") {
    document.querySelector("#status").dataset.state = "idle";
    document.querySelector("#status").textContent = "Aguardando";
  }
  example.showFormError("");
  example.applyFieldErrors([]);
  example.showContext(true);
}

document.querySelectorAll("[data-mode]").forEach((button) => {
  button.addEventListener("click", () => selectMode(button.dataset.mode));
});

async function boot() {
  try {
    const response = await fetch("/api/assistant");
    if (!response.ok) throw new Error("config");
    example.assistant = await response.json();
    renderAssistant(example.assistant);
    selectMode("stream");
  } catch (_error) {
    example.showFormError("Não foi possível carregar o exemplo.");
  }
}

window.example = example;
void boot();
