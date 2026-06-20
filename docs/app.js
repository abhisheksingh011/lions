// Cricket Rules Chat — chatbot frontend.
// Each question is sent to the backend /search; answers render as chat bubbles.
// The backend is stateless (rule lookups don't need conversation memory).

const BACKEND = (window.BACKEND_URL || "").replace(/\/$/, "");
const SRC_CLASS = { BCMCL: "b", ICC: "i", MCC: "m" };
const EXAMPLES = [
  "How many overs can one bowler bowl in a 50 over match?",
  "What happens if a team is late for the toss?",
  "If the keeper breaks the stumps while the batter is out of the crease, is it run out or stumped?",
  "What does Law 41 cover?",
];

const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const input = document.getElementById("question");
const sendBtn = document.getElementById("send");
const healthEl = document.getElementById("health");

let busy = false;

function scrollDown() {
  thread.scrollTop = thread.scrollHeight;
}

function addRow(role) {
  const row = document.createElement("div");
  row.className = "row " + role;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  row.appendChild(bubble);
  thread.appendChild(row);
  scrollDown();
  return bubble;
}

function addUser(text) {
  addRow("user").textContent = text;
}

function addBotText(text, isError = false) {
  const b = addRow("bot");
  if (isError) b.classList.add("error");
  b.textContent = text;
  return b;
}

function addSources(bubble, sources) {
  const clean = (sources || []).filter((s) => s.source);
  if (!clean.length) return;
  const wrap = document.createElement("div");
  wrap.className = "srcs";
  const seen = new Set();
  clean.forEach((s) => {
    const key = `${s.source}|${s.rule_id}|${s.section}`;
    if (seen.has(key)) return;
    seen.add(key);
    const tag = document.createElement("span");
    tag.className = "tag " + (SRC_CLASS[s.source] || "b");
    const rid = s.rule_id ? ` ${s.rule_id}` : "";
    tag.innerHTML = `<span class="s">${s.source}</span>${rid}`;
    if (s.section) tag.title = s.section;
    wrap.appendChild(tag);
  });
  bubble.appendChild(wrap);
  scrollDown();
}

function addTyping() {
  const b = addRow("bot");
  b.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  return b.parentElement; // the row, so we can remove it
}

function greet() {
  const b = addRow("bot");
  b.innerHTML =
    '<div class="welcome">Hi! Ask me anything about cricket rules — ' +
    'I answer from <b>BCMCL</b>, <b>ICC</b> and <b>MCC</b> sources and cite them. ' +
    'Try one of these:</div>';
  const chips = document.createElement("div");
  chips.className = "chips";
  EXAMPLES.forEach((q) => {
    const c = document.createElement("button");
    c.type = "button";
    c.className = "chip";
    c.textContent = q;
    c.addEventListener("click", () => { if (!busy) send(q); });
    chips.appendChild(c);
  });
  b.appendChild(chips);
  scrollDown();
}

function setBusy(state) {
  busy = state;
  sendBtn.disabled = state;
}

async function send(text) {
  const q = (text ?? input.value).trim();
  if (!q || q.length < 3 || busy) return;
  input.value = "";
  addUser(q);
  setBusy(true);
  const typingRow = addTyping();

  try {
    const resp = await fetch(`${BACKEND}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await resp.json().catch(() => ({}));
    typingRow.remove();
    if (data.answer) {
      const bubble = addBotText(data.answer, data.error && data.error !== "rate_limit");
      addSources(bubble, data.sources);
    } else {
      addBotText("Something went wrong (HTTP " + resp.status + "). Please try again.", true);
    }
  } catch (err) {
    typingRow.remove();
    addBotText(
      "Couldn't reach the backend. It may be waking up (free tier sleeps when idle) " +
      "— wait ~30s and try again.", true
    );
  } finally {
    setBusy(false);
    input.focus();
  }
}

function preWarm() {
  healthEl.innerHTML = '<span class="dot"></span>waking…';
  fetch(`${BACKEND}/health`)
    .then((r) => r.json())
    .then((d) => {
      healthEl.innerHTML = `<span class="dot ok"></span>online · ${d.chunks ?? "?"} rules`;
    })
    .catch(() => {
      healthEl.innerHTML = '<span class="dot bad"></span>offline — tap send to retry';
    });
}

form.addEventListener("submit", (e) => { e.preventDefault(); send(); });

greet();
preWarm();
