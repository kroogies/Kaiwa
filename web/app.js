/* Kaiwa — client app */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = {
  get: (u) => fetch(u).then(r => r.json()),
  post: (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }).then(r => r.json()),
  put: (u, b) => fetch(u, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }).then(r => r.json()),
  del: (u) => fetch(u, { method: "DELETE" }).then(r => r.json()),
};

const icon = (n, cls = "") => `<svg class="icon ${cls}"><use href="/static/icons.svg#${n}"/></svg>`;
/* scenario/lesson id → Lucide icon */
const ICON_MAP = {
  ramen: "soup", izakaya: "beer", cafe: "coffee", sushi: "fish", konbini: "store",
  airport: "plane", train: "train-front", hotel: "hotel", directions: "map",
  taxi: "car-taxi-front", ryokan: "waves", clothes: "shirt", electronics: "smartphone",
  souvenir: "gift", intro: "hand", weather: "cloud-sun", weekend: "ferris-wheel",
  hobbies: "guitar", family: "users", barber: "scissors", gym: "dumbbell",
  interview: "briefcase", office: "building-2", classroom: "graduation-cap",
  phone_call: "phone", friends: "handshake", karaoke: "mic-vocal", date: "heart",
  festival: "sparkles", doctor: "stethoscope", pharmacy: "pill", lost: "shield-alert",
  bank: "landmark", post: "mailbox", apartment: "house", phone_contract: "signal",
  greetings: "sunrise", self_intro: "user-round", numbers_shopping: "calculator",
  time_dates: "clock", likes_dislikes: "thumbs-up", daily_routine: "sun",
  past_tense: "calendar", te_form: "link", feelings: "smile", keigo_basics: "award",
};

const state = {
  profile: null,
  settings: {},
  session: null,      // {session_id, scenario, mode, title}
  busy: false,
  audio: null,
  catalog: null,
};

/* ============================================================ navigation */
function show(view) {
  $$(".view").forEach(v => v.classList.add("hidden"));
  $(`#view-${view}`).classList.remove("hidden");
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  if (view === "home") loadHome();
  if (view === "review") loadReview();
  if (view === "vocab") loadVocab();
  if (view === "dict") $("#dict-search").focus();
  if (view === "progress") loadProgress();
  if (view === "settings") loadSettings();
  updateResumePill(view);
}
$$(".nav-btn").forEach(b => b.addEventListener("click", () => show(b.dataset.view)));

/* an active chat isn't lost when you switch tabs — tap the pill to get back */
const sessionView = () =>            // story sessions live in the reader, not chat
  state.session && state.session.mode === "story" ? "reader" : "chat";
const sessionTitle = () =>
  (state.session && state.session.scenario && state.session.scenario.title) ||
  $("#chat-title").textContent;
function updateResumePill(view) {
  const active = state.session && state.session.mode !== "call";
  $("#resume-pill").classList.toggle("hidden", !(active && view !== sessionView()));
  if (active) $("#resume-title").textContent = sessionTitle();
}
$("#resume-pill").addEventListener("click", () => show(sessionView()));

/* starting a new session over an active one asks first (report / discard / stay) */
let pendingStart = null;
function guardActiveSession(startFn) {
  pendingStart = startFn;
  $("#switch-title").textContent = sessionTitle();
  $("#switch-modal").classList.remove("hidden");
}
$("#switch-cancel").addEventListener("click", () => {
  pendingStart = null;
  $("#switch-modal").classList.add("hidden");
  show(sessionView());
});
$("#switch-skip").addEventListener("click", () => {
  $("#switch-modal").classList.add("hidden");
  state.session = null;
  const go = pendingStart; pendingStart = null;
  if (go) go();
});
$("#switch-report").addEventListener("click", () => {
  $("#switch-modal").classList.add("hidden");
  showSessionSummary();       // pendingStart continues after "Done ✓"
});

/* =============================================================== startup */
async function boot() {
  state.profile = await api.get("/api/profile");
  state.settings = state.profile.settings;
  updateHealth();
  setInterval(updateHealth, 20000);
  if (!state.profile.name) startOnboarding();
  loadHome();
  refreshDueBadge();
}

async function updateHealth() {
  try {
    const h = await api.get("/api/health");
    const dot = ok => `<span class="${ok ? "ok" : "bad"}">●</span>`;
    const llmLabel = h.provider === "ollama"
      ? (h.model ? h.model.split(":")[0] : "—")
      : (h.provider_label || h.provider);
    $("#health").innerHTML =
      `${dot(h.llm_ready)} LLM ${llmLabel}<br>` +
      `${dot(h.whisper)} whisper (voice in)<br>` +
      `${dot(h.voicevox || h.aivis || h.os_voice)} ${[h.aivis && "Aivis", h.voicevox && "VOICEVOX"].filter(Boolean).join(" + ") || (h.os_voice ? "system voice" : "no voice")} (voice out)`;
  } catch { $("#health").innerHTML = `<span class="bad">●</span> server offline`; }
}

async function refreshDueBadge() {
  const d = await api.get("/api/srs/due");
  const n = d.due.length;
  const b = $("#due-badge");
  b.classList.toggle("hidden", n === 0);
  b.textContent = n;
}

/* ============================================================ onboarding */
function obShow(step) { // "ai" | "profile" | "voice"
  $("#ob-step-ai").classList.toggle("hidden", step !== "ai");
  $("#ob-step-profile").classList.toggle("hidden", step !== "profile");
  $("#ob-step-voice").classList.toggle("hidden", step !== "voice");
  if (step === "voice") obVoiceInit();
}

async function startOnboarding() {
  $("#onboard-modal").classList.remove("hidden");
  try {
    const h = await api.get("/api/health");
    obShow(h.llm_ready ? "profile" : "ai"); // AI already working → skip straight to profile
  } catch { obShow("profile"); }
}

/* --- step 0: pick + set up the AI --- */
let obPoll = null;
function obPanel(name) { // "choice" | "local" | "cloud"
  $("#ob-ai-choice").classList.toggle("hidden", name !== "choice");
  $("#ob-local").classList.toggle("hidden", name !== "local");
  $("#ob-cloud").classList.toggle("hidden", name !== "cloud");
  $("#ob-ai-back-row").classList.toggle("hidden", name === "choice");
  if (name !== "local" && obPoll) { clearInterval(obPoll); obPoll = null; }
}
$("#ob-opt-local").addEventListener("click", () => { obPanel("local"); obLocalCheck(); });
$("#ob-opt-cloud").addEventListener("click", () => { obPanel("cloud"); obCloudInit(); });
$("#ob-ai-back").addEventListener("click", () => obPanel("choice"));

async function obLocalCheck() {
  const h = await api.get("/api/health");
  if (!h.ollama) {
    $("#ob-ollama-missing").classList.remove("hidden");
    $("#ob-model-dl").classList.add("hidden");
    if (!obPoll) obPoll = setInterval(obLocalCheck, 3000); // watch for Ollama appearing
    return;
  }
  if (obPoll) { clearInterval(obPoll); obPoll = null; }
  $("#ob-ollama-missing").classList.add("hidden");
  if (h.models.length) { // a model is already installed — nothing to download
    await api.post("/api/settings", { provider: "ollama" });
    updateHealth();
    obShow("profile");
    return;
  }
  const hw = await api.get("/api/setup/hardware");
  const r = hw.recommended;
  $("#ob-hw-note").textContent =
    `Your ${hw.system === "Darwin" ? "Mac" : "computer"} (${hw.cores} cores, ${hw.ram_gb ?? "?"} GB RAM) — ` +
    `recommended model: ${r.model} (${r.size} download). ${r.reason}`;
  $("#ob-model-dl").classList.remove("hidden");
  $("#ob-pull-btn").onclick = () => obPull(r.model);
}

async function obPull(model) {
  $("#ob-pull-btn").disabled = true;
  $("#ob-pull-progress").classList.remove("hidden");
  const status = $("#ob-pull-status"), fill = $("#ob-pull-fill");
  try {
    const resp = await fetch("/api/setup/pull", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "", ok = false;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n\n"); buf = lines.pop();
      for (const l of lines) {
        if (!l.startsWith("data: ")) continue;
        const d = JSON.parse(l.slice(6));
        if (d.error) throw new Error(d.error);
        if (d.total && d.completed != null) {
          const pct = Math.round(d.completed / d.total * 100);
          fill.style.width = pct + "%";
          status.textContent = `Downloading — ${pct}%`;
        } else if (d.status) status.textContent = d.status;
        if (d.status === "success") ok = true;
      }
    }
    if (!ok) throw new Error("download did not finish — is Ollama still running?");
    fill.style.width = "100%";
    status.textContent = "Done! Your tutor is ready.";
    await api.post("/api/settings", { provider: "ollama", model });
    updateHealth();
    setTimeout(() => obShow("profile"), 800);
  } catch (e) {
    status.textContent = "Download failed: " + e.message;
    $("#ob-pull-btn").disabled = false;
  }
}

/* --- step 0, cloud path --- */
const OB_KEY_HINTS = {
  gemini: "Free tier available — create a key at aistudio.google.com/apikey",
  openai: "Create a key at platform.openai.com/api-keys",
  anthropic: "Create a key at console.anthropic.com",
};
async function obCloudInit() {
  const cat = await api.get("/api/providers");
  $("#ob-provider").innerHTML = cat.providers.filter(p => p.needs_key)
    .map(p => `<option value="${p.id}">${p.label}</option>`).join("");
  const hint = () => { $("#ob-key-hint").textContent = OB_KEY_HINTS[$("#ob-provider").value] || ""; };
  $("#ob-provider").onchange = hint;
  hint();
}
$("#ob-cloud-save").addEventListener("click", async () => {
  const prov = $("#ob-provider").value;
  const key = $("#ob-apikey").value.trim();
  if (!key) { $("#ob-apikey").focus(); return; }
  const patch = { provider: prov };
  patch[`api_key_${prov}`] = key;
  await api.post("/api/settings", patch);
  updateHealth();
  obShow("profile");
});

/* --- step 1: profile --- */
$("#ob-level").addEventListener("click", e => {
  const btn = e.target.closest("button"); if (!btn) return;
  $$("#ob-level button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
});
$("#ob-start").addEventListener("click", async () => {
  const name = $("#ob-name").value.trim() || "friend";
  const level = $("#ob-level .active")?.dataset.l || "N5";
  const interests = $("#ob-interests").value.trim();
  state.profile = await api.put("/api/profile", { name, jlpt_level: level, interests });
  obShow("voice");
});

/* --- step 2: voice (optional — speech in & nicer voices out) --- */
let obVoicePoll = null;
async function obVoiceInit() {
  try {
    const h = await api.get("/api/health");
    $("#ob-stt-ready").classList.toggle("hidden", !h.whisper);
    $("#ob-stt-btn").classList.toggle("hidden", h.whisper);
    obVoiceDetected(h);
  } catch {}
  if (!obVoicePoll) obVoicePoll = setInterval(async () => {
    try { obVoiceDetected(await api.get("/api/health")); } catch {}
  }, 4000); // notice a voice engine the moment the user launches it
}
function obVoiceDetected(h) {
  const names = [h.aivis && "AivisSpeech", h.voicevox && "VOICEVOX"].filter(Boolean);
  $("#ob-voice-detected").textContent = names.length
    ? `✓ Detected ${names.join(" + ")} — pick its voices in Settings.`
    : "No voice engine running — using your system voice for now.";
}
function obVoiceStop() { if (obVoicePoll) { clearInterval(obVoicePoll); obVoicePoll = null; } }

$("#ob-stt-btn").addEventListener("click", async () => {
  const btn = $("#ob-stt-btn"), status = $("#ob-stt-status"), fill = $("#ob-stt-fill");
  btn.disabled = true;
  $("#ob-stt-progress").classList.remove("hidden");
  status.textContent = "Starting…";
  try {
    const resp = await fetch("/api/setup/download/whisper", { method: "POST" });
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "", ok = false;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n\n"); buf = lines.pop();
      for (const l of lines) {
        if (!l.startsWith("data: ")) continue;
        const d = JSON.parse(l.slice(6));
        if (d.error) throw new Error(d.error);
        if (d.total && d.completed != null) {
          const pct = Math.round(d.completed / d.total * 100);
          fill.style.width = pct + "%";
          status.textContent = `Downloading — ${pct}%`;
        }
        if (d.status === "success") ok = true;
      }
    }
    if (!ok) throw new Error("download did not finish");
    fill.style.width = "100%";
    status.textContent = "Done! Voice input is ready.";
    $("#ob-stt-btn").classList.add("hidden");
    $("#ob-stt-ready").classList.remove("hidden");
    updateHealth();
  } catch (e) {
    status.textContent = "Download failed: " + e.message;
    btn.disabled = false;
  }
});
$("#ob-voice-done").addEventListener("click", () => {
  obVoiceStop();
  $("#onboard-modal").classList.add("hidden");
  loadHome();
});

/* re-run the wizard from Settings (existing installs already have a name set) */
$("#rerun-setup").addEventListener("click", () => {
  const p = state.profile || {};
  $("#ob-name").value = p.name && p.name !== "friend" ? p.name : "";
  $("#ob-interests").value = p.interests || "";
  $$("#ob-level button").forEach(b =>
    b.classList.toggle("active", b.dataset.l === (p.jlpt_level || "N5")));
  startOnboarding();
});

/* ================================================================== home */
async function loadHome() {
  const p = state.profile || await api.get("/api/profile");
  const hour = new Date().getHours();
  const greet = hour < 11 ? "おはよう" : hour < 18 ? "こんにちは" : "こんばんは";
  $("#greeting").textContent = `${greet}、${p.name || ""}さん！`;

  api.get("/api/dashboard").then(d => {
    $("#home-stats").innerHTML =
      `<div class="chip">${icon("flame", "accent")} ${d.streak} day streak</div>` +
      `<div class="chip">${icon("timer")} ${d.total_minutes} min</div>` +
      `<div class="chip">${icon("book-open")} ${d.words_saved} words</div>`;
    const banner = $("#srs-banner");
    if (d.srs_due > 0) {
      banner.classList.remove("hidden");
      banner.innerHTML = `${icon("layers")} <b>${d.srs_due} word${d.srs_due > 1 ? "s" : ""}</b> ready for review — keep them fresh!`;
      banner.onclick = () => show("review");
    } else banner.classList.add("hidden");
  });

  if (!state.catalog) state.catalog = await api.get("/api/scenarios");
  const { scenarios, lessons } = state.catalog;

  $("#lessons-row").innerHTML = lessons.map(scenCard).join("");
  const cats = {};
  scenarios.forEach(s => (cats[s.category] ||= []).push(s));
  $("#scenario-cats").innerHTML = Object.entries(cats).map(([cat, list]) =>
    `<div class="cat-title">${cat}</div><div class="scen-grid">${list.map(scenCard).join("")}</div>`
  ).join("");

  $$("#lessons-row .scen-card, #scenario-cats .scen-card").forEach(c =>
    c.addEventListener("click", () => startSession(
      c.dataset.kind === "lesson" ? "lesson" : "roleplay", { scenario_id: c.dataset.id }))
  );
}

function scenCard(s) {
  return `<div class="scen-card" data-id="${s.id}" data-kind="${s.kind}">
    <span class="scen-icon">${icon(ICON_MAP[s.id] || "message-circle")}</span>
    <h4>${s.title}</h4><span class="ja">${s.title_ja}</span>
    <p>${s.description}</p><span class="lv">${s.levels}</span>
  </div>`;
}

$("#card-free").addEventListener("click", () => startSession("free_chat", {}));
$("#card-custom").addEventListener("click", () => $("#custom-modal").classList.remove("hidden"));
$("#card-story").addEventListener("click", () => $("#story-modal").classList.remove("hidden"));
$("#st-cancel").addEventListener("click", () => $("#story-modal").classList.add("hidden"));
$("#st-script").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  $$("#st-script button").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
});
$("#st-start").addEventListener("click", () => {
  $("#story-modal").classList.add("hidden");
  startSession("story", { story: {
    topic: $("#st-topic").value.trim(),
    script: $("#st-script .active")?.dataset.s || "normal",
  }});
});
$("#cr-cancel").addEventListener("click", () => $("#custom-modal").classList.add("hidden"));
$("#cr-start").addEventListener("click", () => {
  const custom = {
    title: $("#cr-title").value.trim() || "Custom Roleplay",
    ai_role: $("#cr-ai").value.trim(), user_role: $("#cr-user").value.trim(),
    setting: $("#cr-setting").value.trim(), description: $("#cr-desc").value.trim(),
  };
  $("#custom-modal").classList.add("hidden");
  startSession("roleplay", { custom });
});

/* ================================================================== chat */
async function startSession(mode, opts) {
  if (state.session) return guardActiveSession(() => startSession(mode, opts));
  const res = await api.post("/api/sessions", { mode, ...opts });
  state.session = { ...res, mode };
  if (mode === "story") return openReader(res);   // stories get the book UI
  const scen = res.scenario;
  $("#chat-title").textContent = scen ? `${scen.title}` : "Free Chat 💬";
  $("#chat-sub").textContent = scen ? (scen.setting || scen.description || "") : "Talk about anything!";
  $("#messages").innerHTML = "";
  $("#hints").classList.add("hidden");
  $("#tgl-furigana").checked = state.settings.furigana !== false;
  $("#tgl-romaji").checked = !!state.settings.romaji;
  applyReadingToggles();
  show("chat");
  sendChat("");   // AI opens the conversation
}

$("#chat-back").addEventListener("click", () => show("home"));
$("#tgl-furigana").addEventListener("change", applyReadingToggles);
$("#tgl-romaji").addEventListener("change", applyReadingToggles);
function applyReadingToggles() {
  $("#messages").classList.toggle("no-furigana", !$("#tgl-furigana").checked);
  $("#messages").classList.toggle("show-romaji", $("#tgl-romaji").checked);
}

function msgEl(role) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = `<div class="who">${role === "ai" ? "カイワ Kaiwa" : "You"}</div><div class="bubble"></div>`;
  $("#messages").appendChild(div);
  return div;
}
const scrollDown = () => { const m = $("#messages"); m.scrollTop = m.scrollHeight; };

function renderTokens(tokens) {
  return tokens.map(t => {
    const ruby = t.ruby.map(seg =>
      seg.r ? `<ruby>${esc(seg.t)}<rt>${esc(seg.r)}</rt></ruby>` : esc(seg.t)
    ).join("");
    return t.word ? `<span class="tok" data-w="${esc(t.surface)}">${ruby}</span>` : ruby;
  }).join("");
}
const esc = s => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* shared SSE pump for /api/chat — chat bubbles and the story reader both use it */
async function streamChat(text, h) {
  const resp = await fetch("/api/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.session.session_id, text }),
  });
  if (!resp.ok) throw new Error((await resp.json()).error || resp.statusText);
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "", raw = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 2);
      if (!line.startsWith("data: ")) continue;
      const ev = JSON.parse(line.slice(6));
      if (ev.user_message_id && h.onUser) h.onUser(ev.user_message_id);
      if (ev.error) { h.onError(ev.error); return; }
      if (ev.delta) { raw += ev.delta; h.onDelta(raw); }
      if (ev.done) h.onDone(ev, raw);
    }
  }
}

async function sendChat(text) {
  if (state.busy || !state.session) return;
  state.busy = true;
  $("#hints").classList.add("hidden");

  let userDiv = null;
  if (text) {
    userDiv = msgEl("user");
    $(".bubble", userDiv).textContent = text;
    scrollDown();
  }
  const aiDiv = msgEl("ai");
  const bubble = $(".bubble", aiDiv);
  bubble.innerHTML = `<span class="typing"><span></span><span></span><span></span></span>`;
  scrollDown();

  let started = false;
  try {
    await streamChat(text, {
      onUser: mid => { if (userDiv) queueCorrection(mid, userDiv); },
      onError: msg => { bubble.textContent = "⚠️ " + msg; },
      onDelta: raw => {
        if (!started) { bubble.textContent = ""; started = true; }
        bubble.textContent = raw;
        scrollDown();
      },
      onDone: (ev, raw) => finishAiMessage(aiDiv, ev, raw),
    });
  } catch (e) {
    bubble.textContent = "⚠️ " + e.message;
  }
  state.busy = false;
  scrollDown();
}

function finishAiMessage(aiDiv, ev, raw) {
  const bubble = $(".bubble", aiDiv);
  bubble.innerHTML = renderTokens(ev.tokens) +
    `<div class="romaji-line">${esc(ev.romaji || "")}</div>` +
    `<div class="trans-line hidden"></div>`;
  const actions = document.createElement("div");
  actions.className = "msg-actions";
  actions.innerHTML = `
    <button class="act-play" title="Play">${icon("volume-2")} Play</button>
    <button class="act-slow" title="Play slowly">${icon("turtle")} Slow</button>
    <button class="act-trans" title="Translate">${icon("languages")} Translate</button>`;
  aiDiv.appendChild(actions);

  $(".act-play", actions).addEventListener("click", () => playTTS(raw, 1.0));
  $(".act-slow", actions).addEventListener("click", () => playTTS(raw, 0.7));
  $(".act-trans", actions).addEventListener("click", () => translateMsg(ev.message_id, aiDiv));
  $$(".tok", bubble).forEach(tok =>
    tok.addEventListener("click", e => wordPopup(e, tok.dataset.w, raw)));

  if (state.settings.auto_play !== false) playTTS(raw, 1.0);
  if (state.settings.auto_translate) translateMsg(ev.message_id, aiDiv);
}

async function translateMsg(mid, aiDiv) {
  const line = $(".trans-line", aiDiv);
  if (!line.classList.contains("hidden")) { line.classList.add("hidden"); return; }
  line.classList.remove("hidden");
  if (!line.textContent) {
    line.textContent = "…";
    const r = await api.post("/api/translate", { message_id: mid });
    line.textContent = r.translation || "(translation failed)";
  }
  scrollDown();
}

function playTTS(text, speed) {
  if (state.audio) { state.audio.pause(); state.audio = null; }
  const s = (state.settings.speed || 1.0) * speed;
  const v = encodeURIComponent(state.settings.voice || "");
  state.audio = new Audio(`/api/tts?text=${encodeURIComponent(text)}&speed=${s}&voice=${v}`);
  state.audio.play().catch(() => {});
}

/* corrections (async, after user message) */
async function queueCorrection(mid, userDiv) {
  try {
    const c = await api.post("/api/correct", { message_id: mid });
    const div = document.createElement("div");
    if (!c.has_errors) {
      div.className = "correction good";
      div.innerHTML = icon("check") + " " + esc(c.praise || "Perfect!");
    } else {
      div.className = "correction fix";
      div.innerHTML =
        c.errors.map(e =>
          `<div class="fixline">${icon("pencil")} <span class="wrong">${esc(e.wrong || "")}</span> → ` +
          `<span class="right">${esc(e.right || "")}</span><br><span class="why">${esc(e.explanation || "")}</span></div>`
        ).join("") +
        (c.praise ? `<div class="praise">${icon("trophy")} ${esc(c.praise)}</div>` : "");
    }
    userDiv.appendChild(div);
    scrollDown();
  } catch { /* silent */ }
}

/* hints */
$("#hint-btn").addEventListener("click", async () => {
  if (!state.session) return;
  const h = $("#hints");
  if (!h.classList.contains("hidden")) { h.classList.add("hidden"); return; }  // toggle off
  h.classList.remove("hidden");
  h.innerHTML = `<div class="hint-card">${icon("lightbulb")} thinking…</div>`;
  const r = await api.post("/api/hint", { session_id: state.session.session_id });
  h.innerHTML = ((r.suggestions || []).map(s =>
    `<div class="hint-card" data-t="${esc(s.japanese)}">${esc(s.japanese)}` +
    `<span class="en">${esc(s.romaji || "")} — ${esc(s.english || "")}</span></div>`).join("")
    || `<div class="hint-card">Couldn't think of hints, sorry!</div>`) +
    `<button class="hint-close" title="Close hints">${icon("x")}</button>`;
  $(".hint-close", h).addEventListener("click", () => h.classList.add("hidden"));
  $$(".hint-card", h).forEach(c => c.addEventListener("click", () => {
    if (c.dataset.t) { $("#chat-input").value = c.dataset.t; h.classList.add("hidden"); $("#chat-input").focus(); }
  }));
});

/* composer */
$("#send-btn").addEventListener("click", submitInput);
$("#chat-input").addEventListener("keydown", e => { if (e.key === "Enter") submitInput(); });
function submitInput() {
  const inp = $("#chat-input");
  const t = inp.value.trim();
  if (!t || state.busy) return;
  inp.value = "";
  sendChat(t);
}

/* end session */
$("#end-session").addEventListener("click", showSessionSummary);
async function showSessionSummary() {
  if (!state.session) return;
  const inner = $("#summary-inner");
  inner.innerHTML = `<h2>${icon("clipboard-list")} Session Report</h2><p class='sub'>Kaiwa is writing your report…</p>`;
  $("#summary-modal").classList.remove("hidden");
  const s = await api.post(`/api/sessions/${state.session.session_id}/end`);
  inner.innerHTML = `
    <h2>${icon("clipboard-list")} Session Report</h2>
    <div class="summary-stats">
      <div class="chip">${icon("message-circle")} ${s.stats?.turns ?? 0} replies</div>
      <div class="chip">${icon("pencil")} ${s.stats?.corrections ?? 0} corrections</div>
    </div>
    <p>${esc(s.summary || "")}</p>
    ${s.strengths?.length ? `<h3 class="sect">${icon("trophy")} Strengths</h3><ul class="sum-list">${s.strengths.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${s.areas_to_improve?.length ? `<h3 class="sect">${icon("target")} Work on next</h3><ul class="sum-list">${s.areas_to_improve.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    ${s.new_words?.length ? `<h3 class="sect">${icon("sparkles")} Words worth saving</h3>` + s.new_words.map((w, i) =>
      `<div class="new-word-row"><span class="w">${esc(w.word || "")}</span>
       <span class="r">${esc(w.reading || "")}</span><span class="m">${esc(w.meaning || "")}</span>
       <button data-i="${i}">${icon("plus")} Save</button></div>`).join("") : ""}
    <div class="modal-btns"><button class="btn primary" id="sum-close">Done ✓</button></div>`;
  $$(".new-word-row button", inner).forEach(btn => btn.addEventListener("click", async () => {
    const w = s.new_words[+btn.dataset.i];
    await api.post("/api/vocab", w);
    btn.textContent = "✓ Saved"; btn.disabled = true;
    refreshDueBadge();
  }));
  $("#sum-close").addEventListener("click", () => {
    $("#summary-modal").classList.add("hidden");
    state.session = null;
    const go = pendingStart; pendingStart = null;
    if (go) go(); else show("home");
  });
}

/* ========================================================== story reader */
/* Story mode renders as book pages instead of chat bubbles: page 1 is the
   story itself, each quiz turn becomes the next page. Same /api/chat session
   underneath, so resume, reports, and corrections all keep working. */
const reader = { pages: [], cur: 0 };

/* Hiragana-only stories: the local model sometimes slips katakana in anyway.
   Convert it deterministically at render time so beginners never hit kana they
   can't read yet. Text-node only — data-w attributes keep the original surface
   so word lookups still work. */
const storyIsHiragana = () => state.session?.scenario?.script === "hiragana";
const toHiragana = (s) => s.replace(/[ァ-ヶ]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60));
function hiraganizeEl(el) {
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) n.nodeValue = toHiragana(n.nodeValue);
}
const TYPING = `<span class="typing"><span></span><span></span><span></span></span>`;

function openReader(res) {
  const scen = res.scenario || {};
  $("#reader-title").textContent = scen.title || "Story Time";
  $("#reader-sub").textContent =
    ({ hiragana: "ひらがな only", katakana: "カタカナ practice", stretch: "kanji stretch" })[scen.script] || "";
  reader.pages = []; reader.cur = 0;
  $("#reader-pages").innerHTML = "";
  $("#reader-nav").classList.add("hidden");
  $("#rd-furigana").checked = state.settings.furigana !== false;
  $("#rd-romaji").checked = !!state.settings.romaji;
  applyReaderToggles();
  show("reader");
  readerStream("", addReaderPage("story"));   // AI opens by writing the story
}

$("#reader-back").addEventListener("click", () => show("home"));
$("#reader-end").addEventListener("click", showSessionSummary);
$("#rd-prev").addEventListener("click", () => readerGo(reader.cur - 1));
$("#rd-next").addEventListener("click", () => readerGo(reader.cur + 1));
$("#rd-furigana").addEventListener("change", applyReaderToggles);
$("#rd-romaji").addEventListener("change", applyReaderToggles);
function applyReaderToggles() {
  $("#reader-pages").classList.toggle("no-furigana", !$("#rd-furigana").checked);
  $("#reader-pages").classList.toggle("show-romaji", $("#rd-romaji").checked);
}

function addReaderPage(type) {
  const div = document.createElement("div");
  div.className = `reader-page ${type}`;
  if (type === "story") {
    div.innerHTML = `
      <h2 class="story-title"></h2>
      <div class="story-body">${TYPING}</div>
      <div class="romaji-line"></div><div class="trans-line hidden"></div>
      <div class="msg-actions reader-actions"></div>
      <div class="reader-cta hidden"><button class="btn primary">Start the quiz ➤</button></div>`;
  } else {
    // story is page 0; quiz pages 1-3 are the questions, 4 is the wrap-up
    const n = reader.pages.length;
    const label = n <= 3 ? `Question ${n} <span class="of">/ 3</span>`
      : n === 4 ? `${icon("party-popper")} Story complete!`
      : `${icon("message-circle")} Chat`;
    div.innerHTML = `
      <div class="quiz-label">${label}</div>
      <div class="quiz-body">${TYPING}</div>
      <div class="romaji-line"></div><div class="trans-line hidden"></div>
      <div class="msg-actions reader-actions"></div>
      <div class="quiz-after"></div>
      <div class="quiz-answer hidden">
        <input type="text" placeholder="${n <= 3 ? "Answer in Japanese…" : "Reply…"}" autocomplete="off">
        <button class="icon-btn big send" title="Send">${icon("send-horizontal")}</button>
      </div>`;
  }
  $("#reader-pages").appendChild(div);
  reader.pages.push(div);
  readerGo(reader.pages.length - 1);
  return div;
}

function readerGo(i) {
  reader.cur = Math.max(0, Math.min(i, reader.pages.length - 1));
  reader.pages.forEach((p, j) => p.classList.toggle("hidden", j !== reader.cur));
  $("#reader-pages").scrollTop = 0;
  updateReaderNav();
}

function updateReaderNav() {
  const dots = $("#rd-dots");
  dots.innerHTML = reader.pages.map((p, j) =>
    `<button class="rd-dot ${j === reader.cur ? "on" : ""}" data-i="${j}" ` +
    `title="${j === 0 ? "Story" : "Page " + (j + 1)}">${j === 0 ? icon("book-open") : j}</button>`).join("");
  $$(".rd-dot", dots).forEach(b => b.addEventListener("click", () => readerGo(+b.dataset.i)));
  $("#rd-prev").disabled = reader.cur === 0;
  $("#rd-next").disabled = reader.cur >= reader.pages.length - 1;
  $("#reader-nav").classList.toggle("hidden", reader.pages.length < 2);
}

async function readerStream(text, page, correctEl) {
  if (!state.session) return;
  state.busy = true;
  const isStory = page.classList.contains("story");
  const body = $(isStory ? ".story-body" : ".quiz-body", page);
  const title = isStory ? $(".story-title", page) : null;
  let started = false;
  try {
    await streamChat(text, {
      onUser: mid => { if (correctEl) queueCorrection(mid, correctEl); },
      onError: msg => { body.textContent = "⚠️ " + msg; },
      onDelta: raw => {
        if (!started) { body.textContent = ""; started = true; }
        if (storyIsHiragana()) raw = toHiragana(raw);   // strip stray katakana live
        if (title) {                     // first line of the story is its title
          const nl = raw.indexOf("\n");
          title.textContent = nl >= 0 ? raw.slice(0, nl).trim() : raw;
          body.textContent = nl >= 0 ? raw.slice(nl + 1).replace(/^\n+/, "") : "";
        } else body.textContent = raw;
      },
      onDone: (ev, raw) => finishReaderPage(page, ev, raw),
    });
  } catch (e) { body.textContent = "⚠️ " + e.message; }
  state.busy = false;
}

function finishReaderPage(page, ev, raw) {
  const isStory = page.classList.contains("story");
  const body = $(isStory ? ".story-body" : ".quiz-body", page);
  let toks = ev.tokens || [];
  if (isStory) {
    const nl = toks.findIndex(t => t.surface === "\n");
    if (nl > 0) {
      $(".story-title", page).innerHTML = renderTokens(toks.slice(0, nl));
      toks = toks.slice(nl + 1);
      while (toks.length && toks[0].surface === "\n") toks.shift();
    }
  }
  body.innerHTML = renderTokens(toks);
  if (storyIsHiragana()) {               // safety net: convert any katakana the model left in
    if (isStory) hiraganizeEl($(".story-title", page));
    hiraganizeEl(body);
  }
  $(".romaji-line", page).textContent = ev.romaji || "";

  const actions = $(".reader-actions", page);
  actions.innerHTML = `
    <button class="act-play" title="Play">${icon("volume-2")} Play</button>
    <button class="act-slow" title="Play slowly">${icon("turtle")} Slow</button>
    <button class="act-trans" title="Translate">${icon("languages")} Translate</button>`;
  $(".act-play", actions).addEventListener("click", () => playTTS(raw, 1.0));
  $(".act-slow", actions).addEventListener("click", () => playTTS(raw, 0.7));
  $(".act-trans", actions).addEventListener("click", () => translateMsg(ev.message_id, page));
  $$(".tok", page).forEach(tok =>
    tok.addEventListener("click", e => wordPopup(e, tok.dataset.w, raw)));

  if (isStory) {
    const cta = $(".reader-cta", page);
    cta.classList.remove("hidden");
    $("button", cta).addEventListener("click", () => {
      cta.remove();                             // one story, one quiz
      readerStream("はい、クイズをおねがいします！", addReaderPage("quiz"));
    }, { once: true });
  } else {
    if (reader.pages.indexOf(page) === 4) {     // wrap-up page: offer the report
      const after = $(".quiz-after", page);
      after.innerHTML = `<button class="btn primary rd-finish">${icon("clipboard-list")} Finish &amp; get report</button>`;
      $(".rd-finish", after).addEventListener("click", showSessionSummary);
    }
    wireQuizAnswer(page);
    if (state.settings.auto_play !== false) playTTS(raw, 1.0);  // hear the question
  }
  updateReaderNav();
}

function wireQuizAnswer(page) {
  const box = $(".quiz-answer", page);
  box.classList.remove("hidden");
  const inp = $("input", box), send = $("button", box);
  const go = () => {
    const t = inp.value.trim();
    if (!t || state.busy) return;
    box.classList.add("hidden");
    const chip = document.createElement("div");   // the answer stays on its
    chip.className = "your-answer";               // question page for review
    chip.innerHTML = `<span class="ya-label">Your answer</span>${esc(t)}`;
    $(".quiz-after", page).appendChild(chip);
    readerStream(t, addReaderPage("quiz"), chip); // corrections land on the chip
  };
  send.addEventListener("click", go);
  inp.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  inp.focus();
}

/* ============================================================ word popup */
async function wordPopup(e, word, sentence) {
  const pop = $("#word-pop"), inner = $("#word-pop-inner");
  pop.classList.remove("hidden");
  const x = Math.min(e.clientX, window.innerWidth - 310);
  const y = Math.min(e.clientY + 12, window.innerHeight - 260);
  inner.style.left = x + "px"; inner.style.top = y + "px";
  inner.innerHTML = `<span class="w">${esc(word)}</span><div class="loading">looking up…</div>`;
  const info = await api.post("/api/word", { word, sentence });
  inner.innerHTML = `
    <span class="w">${esc(word)}</span><span class="r">${esc(info.reading || "")}</span>
    <div class="rom">${esc(info.romaji || "")}</div>
    <div class="m">${esc(info.meaning || "")}</div>
    ${info.notes ? `<div class="note">${icon("info")} ${esc(info.notes)}</div>` : ""}
    ${info.example ? `<div class="ex">${esc(info.example)}<br><i>${esc(info.example_en || "")}</i></div>` : ""}
    <div class="pop-btns">
      <button class="btn small" id="pop-play">${icon("volume-2")}</button>
      <button class="btn small primary" id="pop-save">${icon("bookmark-plus")} Save word</button>
    </div>`;
  $("#pop-play").addEventListener("click", ev => { ev.stopPropagation(); playTTS(word, 1.0); });
  $("#pop-save").addEventListener("click", async ev => {
    ev.stopPropagation();
    await api.post("/api/vocab", info);
    $("#pop-save").textContent = "✓ Saved"; $("#pop-save").disabled = true;
    refreshDueBadge();
  });
}
$("#word-pop").addEventListener("click", e => {
  if (e.target.id === "word-pop") $("#word-pop").classList.add("hidden");
});

/* ============================================================= recording */
let rec = null;
$("#mic-btn").addEventListener("click", async () => {
  const btn = $("#mic-btn");
  if (rec) {                                  // stop & transcribe
    const { ctx, proc, stream, chunks, rate } = rec;
    rec = null;
    btn.classList.remove("recording");
    proc.disconnect(); stream.getTracks().forEach(t => t.stop()); ctx.close();
    const wav = encodeWav(chunks, rate);
    btn.innerHTML = icon("loader", "spin");
    try {
      const fd = new FormData();
      fd.append("audio", new Blob([wav], { type: "audio/wav" }), "in.wav");
      const r = await fetch("/api/stt", { method: "POST", body: fd }).then(r => r.json());
      btn.innerHTML = icon("mic");
      if (r.text) { $("#chat-input").value = r.text; submitInput(); }
    } catch { btn.innerHTML = icon("mic"); }
    return;
  }
  try {                                       // start
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const chunks = [];
    proc.onaudioprocess = ev => chunks.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
    src.connect(proc); proc.connect(ctx.destination);
    rec = { ctx, proc, stream, chunks, rate: ctx.sampleRate };
    btn.classList.add("recording"); btn.innerHTML = icon("square");
  } catch { alert("Microphone access denied."); }
});

function encodeWav(chunks, inRate) {
  let len = chunks.reduce((a, c) => a + c.length, 0);
  const input = new Float32Array(len);
  let off = 0;
  chunks.forEach(c => { input.set(c, off); off += c.length; });
  // downsample to 16k
  const outRate = 16000, ratio = inRate / outRate;
  const outLen = Math.floor(len / ratio);
  const pcm = new Int16Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const v = input[Math.floor(i * ratio)];
    pcm[i] = Math.max(-1, Math.min(1, v)) * 0x7fff;
  }
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const dv = new DataView(buf);
  const ws = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
  ws(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); ws(8, "WAVE");
  ws(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true);
  dv.setUint16(22, 1, true); dv.setUint32(24, outRate, true);
  dv.setUint32(28, outRate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true);
  ws(36, "data"); dv.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  return buf;
}

/* ============================================================ voice call */
/* Half-duplex "phone call": the tutor's reply is synthesized and spoken
   sentence-by-sentence WHILE it streams; when it finishes, the mic opens
   automatically and simple energy-based VAD detects when you stop talking. */
const call = {
  active: false, muted: false, captions: true,
  queue: [], playing: false, streamDone: true, interrupted: false,
  listening: false, mic: null, vad: null,
  audio: null, timer: null, t0: 0,
};
const SILENT_WAV = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQQAAAAAAA==";

$("#card-call").addEventListener("click", startCall);
$("#call-hangup").addEventListener("click", endCall);
$("#call-avatar").addEventListener("click", interruptAI);
$("#call-mute").addEventListener("click", () => {
  call.muted = !call.muted;
  $("#call-mute").innerHTML = icon(call.muted ? "mic-off" : "mic");
  $("#call-mute").classList.toggle("muted-on", call.muted);
  if (call.listening) {
    call.vad = freshVad();
    callStatus(call.muted ? "muted" : "listening", call.muted ? "Muted" : "Your turn — just speak");
  }
});
$("#call-cc").addEventListener("click", () => {
  call.captions = !call.captions;
  $("#call-cc").classList.toggle("active", call.captions);
  $("#call-overlay").classList.toggle("no-cc", !call.captions);
});

async function startCall() {
  if (state.session) return guardActiveSession(startCall);
  const res = await api.post("/api/sessions", { mode: "call" });
  state.session = { ...res, mode: "call" };
  Object.assign(call, {
    active: true, muted: false, captions: true,
    queue: [], playing: false, streamDone: true, interrupted: false, listening: false,
  });
  $("#call-caption").textContent = "";
  $("#call-mute").innerHTML = icon("mic");
  $("#call-mute").classList.remove("muted-on");
  $("#call-cc").classList.add("active");
  $("#call-overlay").classList.remove("hidden", "no-cc");
  call.t0 = Date.now();
  $("#call-timer").textContent = "0:00";
  call.timer = setInterval(() => {
    const s = Math.floor((Date.now() - call.t0) / 1000);
    $("#call-timer").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 1000);
  if (!call.audio) call.audio = new Audio();
  call.audio.src = SILENT_WAV;                 // unlock audio inside the tap (iOS)
  call.audio.play().catch(() => {});
  await ensureMic();                           // ask permission inside the tap too
  callStatus("thinking", "Calling…");
  callTurn("");                                // Kaiwa opens the call
}

async function endCall() {
  call.active = false;
  clearInterval(call.timer);
  call.queue = []; call.playing = false; call.listening = false;
  if (call.audio) call.audio.pause();
  if (call.mic) {
    try {
      call.mic.proc.disconnect();
      call.mic.stream.getTracks().forEach(t => t.stop());
      call.mic.ctx.close();
    } catch { /* already closed */ }
    call.mic = null;
  }
  $("#call-overlay").classList.add("hidden");
  showSessionSummary();
}

function callStatus(cls, text) {
  $("#call-avatar").className = "call-avatar" + (cls ? " " + cls : "");
  $("#call-status").textContent = text;
}

function showCaption(text, user) {
  const c = $("#call-caption");
  c.innerHTML = (user ? `<span class="you">You</span> ` : "") + esc(text);
  c.classList.toggle("user", !!user);
}

/* --- AI turn: stream, split into sentences, speak each as it completes --- */
async function callTurn(text) {
  if (!call.active) return;
  call.streamDone = false;
  call.interrupted = false;
  callStatus("thinking", "Kaiwa is thinking…");
  let pending = "";
  try {
    const resp = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.session.session_id, text }),
    });
    if (!resp.ok) throw new Error((await resp.json()).error || resp.statusText);
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 2);
        if (!line.startsWith("data: ")) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.user_message_id)  // keep the mistake-memory pipeline fed
          api.post("/api/correct", { message_id: ev.user_message_id }).catch(() => {});
        if (ev.error) throw new Error(ev.error);
        if (ev.delta) {
          pending += ev.delta;
          const [sents, rest] = splitSentences(pending);
          pending = rest;
          sents.forEach(enqueueSpeech);
        }
        if (ev.done && pending.trim()) { enqueueSpeech(pending.trim()); pending = ""; }
      }
    }
  } catch (e) {
    if (!call.active) return;
    call.streamDone = true;
    callStatus("", "Hiccup: " + e.message);
    startListening(true);
    return;
  }
  call.streamDone = true;
  pumpSpeech();   // if everything already played (or was interrupted), move on
}

function splitSentences(text) {
  const out = [];
  let cur = "";
  for (const ch of text) {
    cur += ch;
    if ("。！？!?\n".includes(ch)) {
      const t = cur.trim();
      if (t && /[^。！？!?\s]/.test(t)) out.push(t);
      cur = "";
    }
  }
  return [out, cur];
}

function enqueueSpeech(text) {
  if (!call.active || call.interrupted) return;
  const speed = state.settings.speed || 1.0;
  const voice = encodeURIComponent(state.settings.voice || "");
  const url = `/api/tts?text=${encodeURIComponent(text)}&speed=${speed}&voice=${voice}`;
  // start fetching immediately — next sentence synthesizes while this one plays
  call.queue.push({ text, blob: fetch(url).then(r => r.ok ? r.blob() : null).catch(() => null) });
  pumpSpeech();
}

async function pumpSpeech() {
  if (!call.active || call.playing) return;
  const item = call.queue.shift();
  if (!item) {
    if (call.streamDone && !call.listening) startListening();
    return;
  }
  call.playing = true;
  callStatus("speaking", "Kaiwa is speaking — tap the circle to interrupt");
  showCaption(item.text, false);
  const blob = await item.blob;
  if (!call.active || call.interrupted) { call.playing = false; return; }
  if (!blob) { call.playing = false; pumpSpeech(); return; }
  const src = URL.createObjectURL(blob);
  call.audio.src = src;
  call.audio.onended = () => { URL.revokeObjectURL(src); call.playing = false; pumpSpeech(); };
  call.audio.onerror = () => { URL.revokeObjectURL(src); call.playing = false; pumpSpeech(); };
  call.audio.play().catch(() => { call.playing = false; pumpSpeech(); });
}

function interruptAI() {
  if (!call.active || (!call.playing && call.queue.length === 0)) return;
  call.interrupted = true;      // stream keeps finishing silently so the reply is saved
  call.queue = [];
  call.audio.pause();
  call.playing = false;
  startListening();
}

/* --- listening: energy-based VAD, auto-stop on ~1.2s of silence --- */
async function ensureMic() {
  if (call.mic) return true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    proc.onaudioprocess = ev => vadProcess(new Float32Array(ev.inputBuffer.getChannelData(0)));
    src.connect(proc); proc.connect(ctx.destination);
    call.mic = { stream, ctx, proc, rate: ctx.sampleRate };
    return true;
  } catch { return false; }
}

const freshVad = () => ({ started: false, chunks: [], preroll: [], voiced: 0, silence: 0, floor: 0.006 });

async function startListening(afterError) {
  if (!call.active || call.listening) return;
  if (!(await ensureMic())) { callStatus("", "Mic blocked — check browser permissions"); return; }
  if (call.mic.ctx.state === "suspended") call.mic.ctx.resume();
  call.vad = freshVad();
  call.listening = true;
  if (call.muted) callStatus("muted", "Muted");
  else if (!afterError) callStatus("listening", "Your turn — just speak");
}

function vadProcess(buf) {
  if (!call.active || !call.listening || call.muted) return;
  const v = call.vad, ms = (buf.length / call.mic.rate) * 1000;
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  const rms = Math.sqrt(sum / buf.length);
  if (!v.started) {
    v.floor = Math.min(0.02, v.floor * 0.95 + rms * 0.05);   // adapt to room noise
    v.preroll.push(buf);
    if (v.preroll.length > 8) v.preroll.shift();              // keep ~0.7s pre-roll
    v.voiced = rms > Math.max(v.floor * 3, 0.012) ? v.voiced + ms : 0;
    if (v.voiced >= 180) {
      v.started = true;
      v.chunks = v.preroll.splice(0);
      callStatus("listening live", "Listening…");
    }
  } else {
    v.chunks.push(buf);
    v.silence = rms < Math.max(v.floor * 2.5, 0.01) ? v.silence + ms : 0;
    if (v.silence >= 1200 || v.chunks.length * ms > 30000) finishUtterance();
  }
}

async function finishUtterance() {
  const v = call.vad;
  call.listening = false;
  if (v.chunks.length * (4096 / call.mic.rate) * 1000 < 400) { startListening(); return; }
  callStatus("thinking", "Got it…");
  const wav = encodeWav(v.chunks, call.mic.rate);
  let text = "";
  try {
    const fd = new FormData();
    fd.append("audio", new Blob([wav], { type: "audio/wav" }), "in.wav");
    const r = await fetch("/api/stt", { method: "POST", body: fd }).then(r => r.json());
    text = (r.text || "").trim();
  } catch { /* fall through to retry */ }
  if (!call.active) return;
  if (!text) {
    startListening(true);
    callStatus("listening", "Didn't catch that — try again");
    return;
  }
  showCaption(text, true);
  while (!call.streamDone && call.active)   // barge-in: let the previous reply finish saving
    await new Promise(r => setTimeout(r, 150));
  callTurn(text);
}

/* ================================================================ review */
let reviewQueue = [], reviewIdx = 0;
async function loadReview() {
  const d = await api.get("/api/srs/due");
  reviewQueue = d.due; reviewIdx = 0;
  renderReviewCard();
}
// Mirrors db.srs_review() so each grade button can show when the word would
// come back (like Anki's "10m / 1d / 3d" labels).
function srsPreview(w) {
  const fmt = d => d < 30 ? `${Math.round(d)}d` : d < 365 ? `${Math.round(d / 30)}mo` : `${(d / 365).toFixed(1)}y`;
  const next = g => {
    if (g === 0) return "10 min";
    const q = { 1: 3, 2: 4, 3: 5 }[g];
    const ease = Math.max(1.3, (w.ease || 2.5) + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)));
    const reps = (w.reps || 0) + 1;
    let interval;
    if (reps === 1) interval = 1;
    else if (reps === 2) interval = g >= 2 ? 3 : 2;
    else {
      const mult = { 1: 1.2, 2: ease, 3: ease * 1.3 }[g];
      interval = Math.max(w.interval_days * mult, w.interval_days + 1);
    }
    return fmt(interval);
  };
  return [next(0), next(1), next(2), next(3)];
}
function renderReviewCard() {
  const area = $("#review-area");
  refreshDueBadge();
  if (reviewIdx >= reviewQueue.length) {
    area.innerHTML = `<div class="review-done">${icon("party-popper", "big-icon")}<br>All caught up!<br>
      <small>Save words during chats and they'll appear here for review.</small></div>`;
    return;
  }
  const w = reviewQueue[reviewIdx];
  const iv = srsPreview(w);
  area.innerHTML = `
    <p class="review-count">${reviewIdx + 1} / ${reviewQueue.length}</p>
    <div class="flashcard" id="fc">
      <div class="big-word">${esc(w.word)}</div>
      <div class="reading hidden">${esc(w.reading || "")} <i style="font-size:.8em">${esc(w.romaji || "")}</i></div>
      <div class="meaning hidden">${esc(w.meaning || "")}</div>
      ${w.example ? `<div class="example hidden">${esc(w.example)}<br><i>${esc(w.example_en || "")}</i></div>` : ""}
      <p class="sub" id="fc-hint" style="margin-top:16px">tap to reveal</p>
    </div>
    <div class="hidden" id="grades">
      <p class="sub grade-hint">How well did you remember?</p>
      <div class="grade-row">
        <button class="g-again" title="Forgot it — the word starts over and comes right back">Again<span>${iv[0]}</span></button>
        <button class="g-hard" title="Got it, but it was a struggle — small step forward">Hard<span>${iv[1]}</span></button>
        <button class="g-good" title="Remembered it after a moment — normal step forward">Good<span>${iv[2]}</span></button>
        <button class="g-easy" title="Knew it instantly — big step forward">Easy<span>${iv[3]}</span></button>
      </div>
      <p class="sub grade-hint">the time under each button is when you'll see the word again</p>
    </div>
    <div style="text-align:center;margin-top:12px"><button class="btn small" id="fc-play">${icon("volume-2")} Listen</button></div>`;
  $("#fc-play").addEventListener("click", () => playTTS(w.word, 1.0));
  $("#fc").addEventListener("click", () => {
    $$("#fc .hidden").forEach(el => el.classList.remove("hidden"));
    $("#fc-hint").remove();
    $("#grades").classList.remove("hidden");
  }, { once: true });
  const grade = g => async () => {
    await api.post("/api/srs/review", { vocab_id: w.id, grade: g });
    reviewIdx++; renderReviewCard();
  };
  $(".g-again").addEventListener("click", grade(0));
  $(".g-hard").addEventListener("click", grade(1));
  $(".g-good").addEventListener("click", grade(2));
  $(".g-easy").addEventListener("click", grade(3));
}

/* ================================================================= vocab */
const VOCAB_PAGE = 8;
async function loadVocab() {
  const d = await api.get("/api/vocab");
  state.vocab = d.vocab;
  state.vocabShown = VOCAB_PAGE;
  renderVocab();
}

function renderVocab() {
  const list = state.vocab || [];
  if (!list.length) {
    $("#vocab-list").innerHTML = `<p class="sub">No words yet — tap any word in a chat to save it!</p>`;
    return;
  }
  const slice = list.slice(0, state.vocabShown);
  const more = list.length - slice.length;
  $("#vocab-list").innerHTML = slice.map(v => `
    <div class="vocab-item" data-id="${v.id}">
      <div><div class="w">${esc(v.word)}</div><div class="r">${esc(v.reading || "")}</div></div>
      <div class="m">${esc(v.meaning || "")}${v.example ? `<div class="ex">${esc(v.example)}</div>` : ""}</div>
      <button class="v-play" title="Listen">${icon("volume-2")}</button>
      <button class="v-del" title="Delete">${icon("trash-2")}</button>
    </div>`).join("") +
    (more ? `<button class="btn small show-more" id="vocab-more">Show more (${more})</button>` : "");
  $$(".vocab-item").forEach(item => {
    const id = item.dataset.id;
    const word = $(".w", item).textContent;
    $(".v-play", item).addEventListener("click", () => playTTS(word, 1.0));
    $(".v-del", item).addEventListener("click", async () => {
      await api.del(`/api/vocab/${id}`);
      state.vocab = state.vocab.filter(x => String(x.id) !== String(id));
      renderVocab(); refreshDueBadge();
    });
  });
  const moreBtn = $("#vocab-more");
  if (moreBtn) moreBtn.addEventListener("click", () => { state.vocabShown += VOCAB_PAGE; renderVocab(); });
}

/* ============================================================== progress */
async function loadProgress() {
  const d = await api.get("/api/dashboard");
  const stat = (n, l) => `<div class="stat-card"><div class="num">${n}</div><div class="lbl">${l}</div></div>`;
  $("#progress-stats").innerHTML =
    stat(`${d.streak}${icon("flame", "accent")}`, "day streak") + stat(d.total_minutes, "minutes practiced") +
    stat(d.sessions_count, "sessions") + stat(d.messages_spoken, "things you said") +
    stat(d.words_saved, "words saved") + stat(d.mistakes_logged, "mistakes caught");
  state.recentSessions = d.recent_sessions;
  state.sessShown = SESS_PAGE;
  renderRecentSessions();
  const max = Math.max(1, ...d.mistake_categories.map(c => c.n));
  $("#mistake-cats").innerHTML = d.mistake_categories.length ? d.mistake_categories.map(c => `
    <div class="mcat"><span class="lbl">${esc(c.category || "other")}</span>
    <div class="bar" style="width:${(c.n / max) * 260}px"></div><span class="n">${c.n}</span></div>`).join("")
    : `<p class="sub">No mistakes logged yet. (That's either very good or very quiet.)</p>`;
}

const SESS_PAGE = 8;
function renderRecentSessions() {
  const list = state.recentSessions || [];
  if (!list.length) {
    $("#recent-sessions").innerHTML = `<p class="sub">No sessions yet — start one from Home!</p>`;
    return;
  }
  const slice = list.slice(0, state.sessShown);   // slice index == index into state.recentSessions
  const more = list.length - slice.length;
  $("#recent-sessions").innerHTML = slice.map((s, i) => `
    <div class="session-item expandable" data-i="${i}">
      <div class="head"><span>${esc(s.title)} <small>(${s.mode.replace("_", " ")})</small></span>
      <span class="when">${new Date(s.started_at * 1000).toLocaleDateString()} · ${s.minutes} min <span class="chev">▾</span></span></div>
      ${s.summary?.summary ? `<div class="summ">${esc(s.summary.summary)}</div>` : ""}
      <div class="sess-detail hidden">${sessionDetailHTML(s)}
        <button class="btn small sess-pdf" data-i="${i}">${icon("clipboard-list")} Save as PDF</button>
      </div>
    </div>`).join("") +
    (more ? `<button class="btn small show-more" id="sess-more">Show more (${more})</button>` : "");
}

function sessionDetailHTML(s) {
  const sum = s.summary || {};
  let h = "";
  if (sum.stats) h += `<p class="sub">${sum.stats.turns ?? "?"} turns · ${sum.stats.corrections ?? 0} corrections</p>`;
  if (sum.strengths?.length) h += `<h4>Strengths</h4><ul>${sum.strengths.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
  if (sum.areas_to_improve?.length) h += `<h4>To improve</h4><ul>${sum.areas_to_improve.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
  if (sum.new_words?.length) h += `<h4>New words</h4><ul>${sum.new_words.map(w =>
    `<li><b>${esc(w.word || "")}</b>${w.reading && w.reading !== w.word ? `（${esc(w.reading)}）` : ""} — ${esc(w.meaning || "")}</li>`).join("")}</ul>`;
  return h || `<p class="sub">No detailed report was saved for this session.</p>`;
}

$("#recent-sessions").addEventListener("click", e => {
  if (e.target.closest("#sess-more")) {
    state.sessShown += SESS_PAGE; renderRecentSessions(); return;
  }
  const pdfBtn = e.target.closest(".sess-pdf");
  if (pdfBtn) {
    printSessionReport(state.recentSessions[+pdfBtn.dataset.i]);
    return;
  }
  const item = e.target.closest(".session-item");
  if (item) {
    item.querySelector(".sess-detail")?.classList.toggle("hidden");
    item.classList.toggle("open");
  }
});

function printSessionReport(s) {
  const sum = s.summary || {};
  $("#print-report").innerHTML = `
    <h1>Kaiwa 会話 — Session Report</h1>
    <p class="meta">${esc(s.title)} (${s.mode.replace("_", " ")}) ·
      ${new Date(s.started_at * 1000).toLocaleString()} · ${s.minutes} min</p>
    ${sum.summary ? `<p>${esc(sum.summary)}</p>` : ""}
    ${sessionDetailHTML(s)}`;
  window.print(); // user picks "Save as PDF" in the dialog
}

/* ============================================================== settings */
async function loadSettings() {
  const p = await api.get("/api/profile");
  state.profile = p; state.settings = p.settings;
  $("#set-name").value = p.name || "";
  $("#set-interests").value = p.interests || "";
  $("#set-goals").value = p.goals || "";
  $$("#set-level button").forEach(b => b.classList.toggle("active", b.dataset.l === p.jlpt_level));

  providerCatalog = await api.get("/api/providers");
  $("#set-provider").innerHTML = providerCatalog.providers.map(x =>
    `<option value="${x.id}" ${x.id === providerCatalog.active ? "selected" : ""}>${x.label}</option>`).join("");
  renderProviderUI();

  const v = await api.get("/api/voices");
  const cur = p.settings.voice || v.default;
  $("#set-voice").innerHTML = v.voices.map(x =>
    `<option value="${x.id}" ${x.id === cur ? "selected" : ""}>${x.label} (${x.engine})</option>`).join("");
  $("#aivis-hint").classList.toggle("hidden", v.voices.some(x => x.engine === "AivisSpeech"));

  $("#set-speed").value = p.settings.speed || 1.0;
  $("#speed-val").textContent = `${$("#set-speed").value}×`;
  $("#set-intonation").value = p.settings.intonation ?? 1.0;
  $("#intonation-val").textContent = `${$("#set-intonation").value}×`;
  $("#set-autoplay").checked = p.settings.auto_play !== false;
  $("#set-autotranslate").checked = !!p.settings.auto_translate;

  renderPhoneSetup(); // async, fills its own card
  renderBackupStatus();
}

async function renderBackupStatus() {
  const b = await api.get("/api/backup/status").catch(() => null);
  if (!b) return;
  $("#set-backup-freq").value = b.freq;
  $("#backup-status").textContent =
    `Backups go to ${b.dir}` +
    (b.last ? ` — last backup: ${new Date(b.last * 1000).toLocaleString()}` : " — no backup yet");
}
$("#backup-now").addEventListener("click", async () => {
  const r = await api.post("/api/backup/now", {});
  if (r.error) { $("#backup-status").textContent = r.error; return; }
  renderBackupStatus();
});
$("#import-btn").addEventListener("click", () => $("#import-file").click());
$("#import-file").addEventListener("change", async () => {
  const f = $("#import-file").files[0];
  if (!f) return;
  if (!confirm("Importing replaces ALL current data (a safety copy is kept). Continue?")) return;
  const fd = new FormData();
  fd.append("file", f);
  const resp = await fetch("/api/backup/import", { method: "POST", body: fd });
  const r = await resp.json();
  if (r.error) { $("#backup-status").textContent = r.error; return; }
  location.reload(); // everything (profile, words, streak) just changed
});
$("#reset-data").addEventListener("click", async () => {
  if (!confirm("Delete ALL data — profile, saved words, streak, and history?")) return;
  if (!confirm("Really sure? This wipes everything back to a fresh install.\n(A safety copy is kept next to the database.)")) return;
  const r = await api.post("/api/reset", {});
  if (r.error) { $("#backup-status").textContent = r.error; return; }
  location.reload(); // fresh db → onboarding starts over
});

async function renderPhoneSetup() {
  const box = $("#phone-setup");
  const t = await api.get("/api/setup/phone").catch(() => null);
  if (!t) { box.innerHTML = `<p class="sub">Couldn't check phone status.</p>`; return; }
  if (t.url) {
    const qr = qrcode(0, "M");
    qr.addData(t.url);
    qr.make();
    box.innerHTML = `
      <p class="sub">Install <b>Tailscale</b> on your phone, sign in with the <b>same account</b> as this computer, then scan:</p>
      <div class="qr-wrap">${qr.createSvgTag({ cellSize: 4, margin: 2 })}</div>
      <p class="sub"><a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(t.url)}</a></p>
      <p class="sub">Add it to your home screen for an app-like experience.</p>`;
  } else if (t.installed) {
    box.innerHTML = `
      <p class="sub">Tailscale is installed but not connected.</p>
      <p class="sub">1. Open the Tailscale app on this computer and sign in.<br>
      2. Restart Kaiwa (run.sh) so the secure phone link starts.<br>
      3. Come back here for your QR code.</p>`;
  } else {
    box.innerHTML = `
      <p class="sub">Kaiwa runs on this computer — your phone connects to it as a remote screen.
      The free <b>Tailscale</b> app makes that connection secure from anywhere:</p>
      <p class="sub">1. <a href="https://tailscale.com/download" target="_blank" rel="noopener">Install Tailscale ↗</a> on this computer and sign in.<br>
      2. Install it on your phone and sign in with the same account.<br>
      3. Restart Kaiwa (run.sh), then come back here for your QR code.</p>`;
  }
}
/* AI provider selection */
let providerCatalog = null;
function renderProviderUI() {
  const info = providerCatalog.providers.find(x => x.id === $("#set-provider").value);
  if (!info) return;
  $("#apikey-row").classList.toggle("hidden", !info.needs_key);
  $("#set-apikey").value = "";
  $("#set-apikey").placeholder = info.has_key ? "•••••• saved — paste to replace" : "Paste your API key";
  const cur = info.model || info.models[0];
  $("#set-model").innerHTML = info.models.map(m =>
    `<option ${m === cur ? "selected" : ""}>${m}</option>`).join("") || "<option>none found</option>";
}
$("#set-provider").addEventListener("change", renderProviderUI);

$("#set-speed").addEventListener("input", () => $("#speed-val").textContent = `${$("#set-speed").value}×`);
$("#set-intonation").addEventListener("input", () => $("#intonation-val").textContent = `${$("#set-intonation").value}×`);
/* voice preview: speak a sample with the currently selected (unsaved) voice + sliders */
let previewAudio = null;
$("#voice-preview").addEventListener("click", () => {
  const btn = $("#voice-preview");
  if (previewAudio) { previewAudio.pause(); previewAudio = null; }
  const v = $("#set-voice").value;
  const s = parseFloat($("#set-speed").value) || 1.0;
  const i = parseFloat($("#set-intonation").value) || 1.0;
  btn.innerHTML = icon("loader", "spin");
  const reset = () => { btn.innerHTML = icon("volume-2"); };
  previewAudio = new Audio(`/api/tts?text=${encodeURIComponent("こんにちは、カイワです。よろしくお願いします！")}&speed=${s}&intonation=${i}&voice=${encodeURIComponent(v)}`);
  previewAudio.addEventListener("playing", reset);
  previewAudio.addEventListener("error", reset);
  previewAudio.play().catch(reset);
});
$("#set-level").addEventListener("click", e => {
  const btn = e.target.closest("button"); if (!btn) return;
  $$("#set-level button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
});
$("#save-settings").addEventListener("click", async () => {
  await api.put("/api/profile", {
    name: $("#set-name").value.trim(),
    jlpt_level: $("#set-level .active")?.dataset.l || "N5",
    interests: $("#set-interests").value.trim(),
    goals: $("#set-goals").value.trim(),
  });
  const prov = $("#set-provider").value;
  const patch = {
    provider: prov,
    voice: $("#set-voice").value,
    speed: parseFloat($("#set-speed").value),
    intonation: parseFloat($("#set-intonation").value),
    auto_play: $("#set-autoplay").checked,
    auto_translate: $("#set-autotranslate").checked,
    furigana: $("#tgl-furigana").checked,
    romaji: $("#tgl-romaji").checked,
  };
  patch.backup_freq = $("#set-backup-freq").value;
  patch[prov === "ollama" ? "model" : `model_${prov}`] = $("#set-model").value;
  const keyVal = $("#set-apikey").value.trim();
  if (keyVal) patch[`api_key_${prov}`] = keyVal;  // only send a key when the user typed one
  state.settings = await api.post("/api/settings", patch);
  state.profile = await api.get("/api/profile");
  providerCatalog = await api.get("/api/providers");  // refresh has_key state
  renderProviderUI();
  updateHealth();
  $("#settings-saved").classList.remove("hidden");
  setTimeout(() => $("#settings-saved").classList.add("hidden"), 1800);
});

/* ============================================================ dictionary */
let dictTimer = null;
$("#dict-search").addEventListener("input", () => {
  clearTimeout(dictTimer);
  dictTimer = setTimeout(dictSearch, 250);
});
async function dictSearch() {
  const q = $("#dict-search").value.trim();
  const box = $("#dict-results");
  if (!q) { box.innerHTML = ""; return; }
  const d = await api.get(`/api/dictionary?q=${encodeURIComponent(q)}`);
  if (q !== $("#dict-search").value.trim()) return; // stale response
  if (!d.results.length) {
    box.innerHTML = `<p class="sub">No matches for “${esc(q)}”.</p>`;
    return;
  }
  box.innerHTML = d.results.map(r => `
    <div class="dict-entry">
      <div class="dict-jp">
        <span class="dict-form">${esc(r.form)}</span>
        ${r.reading && r.reading !== r.form ? `<span class="dict-reading">${esc(r.reading)}</span>` : ""}
      </div>
      <div class="dict-def">${esc(r.meaning)}${r.common ? ' <span class="dict-common">common</span>' : ""}</div>
      <button class="icon-btn dict-save" data-word="${esc(r.form)}" data-reading="${esc(r.reading || "")}"
        data-meaning="${esc(r.meaning)}" title="Save to My Words">${icon("bookmark-plus")}</button>
    </div>`).join("");
}
$("#dict-results").addEventListener("click", async e => {
  const btn = e.target.closest(".dict-save");
  if (!btn || btn.disabled) return;
  await api.post("/api/vocab", {
    word: btn.dataset.word, reading: btn.dataset.reading, meaning: btn.dataset.meaning,
  });
  btn.innerHTML = icon("check");
  btn.disabled = true;
});

boot();
