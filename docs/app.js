// Cricket Rules Search — frontend logic.
// Talks to the FastAPI backend on the Hugging Face Space (window.BACKEND_URL).

const BACKEND = (window.BACKEND_URL || "").replace(/\/$/, "");

const form = document.getElementById("searchForm");
const input = document.getElementById("question");
const askBtn = document.getElementById("askBtn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const answerEl = document.getElementById("answer");
const sourcesEl = document.getElementById("sources");
const healthEl = document.getElementById("health");

const SRC_CLASS = { BCMCL: "b", ICC: "i", MCC: "m" };

// --- pre-warm the Space (free Spaces sleep when idle) ------------------------
function preWarm() {
  healthEl.innerHTML = '<span class="dot"></span> waking backend…';
  fetch(`${BACKEND}/health`)
    .then((r) => r.json())
    .then((d) => {
      healthEl.innerHTML =
        `<span class="dot ok"></span> backend ready · ${d.chunks ?? "?"} rules indexed`;
    })
    .catch(() => {
      healthEl.innerHTML = '<span class="dot bad"></span> backend unreachable';
    });
}

function showStatus(html, warn = false) {
  statusEl.className = "status" + (warn ? " warn" : "");
  statusEl.innerHTML = html;
  statusEl.classList.remove("hidden");
}

function renderResult(data) {
  statusEl.classList.add("hidden");
  answerEl.textContent = data.answer || "(no answer)";

  sourcesEl.innerHTML = "";
  const sources = (data.sources || []).filter((s) => s.source);
  if (sources.length) {
    const seen = new Set();
    const h = document.createElement("h3");
    h.textContent = "Based on";
    sourcesEl.appendChild(h);
    sources.forEach((s) => {
      const key = `${s.source}-${s.rule_id}-${s.section}`;
      if (seen.has(key)) return;
      seen.add(key);
      const card = document.createElement("div");
      card.className = "source-card";
      const cls = SRC_CLASS[s.source] || "b";
      const rid = s.rule_id ? ` · rule ${s.rule_id}` : "";
      const sec = s.section ? ` — ${s.section}` : "";
      card.innerHTML = `<span class="src ${cls}">${s.source}</span>` +
                       `<span class="meta">${rid}${sec}</span>`;
      sourcesEl.appendChild(card);
    });
  }
  resultEl.classList.remove("hidden");
}

async function ask(question) {
  if (!question || question.trim().length < 3) return;
  askBtn.disabled = true;
  resultEl.classList.add("hidden");
  showStatus('<span class="spinner"></span>Searching the rules… ' +
             '(first request after idle can take ~30s while the backend wakes up)');

  try {
    const resp = await fetch(`${BACKEND}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await resp.json();
    if (!resp.ok && !data.answer) {
      showStatus("Something went wrong (HTTP " + resp.status + "). Please try again.", true);
    } else {
      renderResult(data);
    }
  } catch (err) {
    showStatus("Couldn't reach the backend. It may be starting up — wait a few " +
               "seconds and try again.", true);
  } finally {
    askBtn.disabled = false;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  ask(input.value);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.textContent;
    ask(chip.textContent);
  });
});

preWarm();
