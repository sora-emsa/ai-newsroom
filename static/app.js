let nextRunTimestamp = null;
let isPipelineRunning = false;
const speechTimers = {};

// Palet Warna Pixel Human untuk 8 Karakter (3D Voxel Shading)
const humanThemes = {
  chronos: { hair: "#f59e0b", skin: "#ffdfba", shirt: "#1e3a8a", pants: "#0f172a", shoes: "#78350f", acc: "#fbbf24" },
  radar:   { hair: "#78350f", skin: "#ffdfba", shirt: "#15803d", pants: "#1e293b", shoes: "#0f172a", acc: "#ea580c" },
  babel:   { hair: "#172554", skin: "#ffd1a4", shirt: "#881337", pants: "#334155", shoes: "#451a03", acc: "#14b8a6" },
  quill:   { hair: "#713f12", skin: "#ffdfba", shirt: "#a16207", pants: "#334155", shoes: "#713f12", acc: "#f8fafc" },
  sentinel:{ hair: "#1e293b", skin: "#ffd1a4", shirt: "#2563eb", pants: "#0f172a", shoes: "#000000", acc: "#10b981" },
  press:   { hair: "#d97706", skin: "#ffdfba", shirt: "#ea580c", pants: "#1e293b", shoes: "#f8fafc", acc: "#38bdf8" },
  nexus:   { hair: "#0f172a", skin: "#ffdfba", shirt: "#334155", pants: "#090d16", shoes: "#0284c7", acc: "#00f0ff" },
  boss:    { hair: "#334155", skin: "#ffd1a4", shirt: "#0f172a", pants: "#0a0e17", shoes: "#b45309", acc: "#eab308" }
};

function createHumanPixelSVG(theme) {
  return `
    <svg viewBox="0 0 16 24" class="human-svg" shape-rendering="crispEdges">
      <!-- 3D ISOMETRIC HUMAN HEAD & HAIR -->
      <g class="human-head">
        <rect x="5" y="1" width="6" height="2" fill="${theme.hair}" />
        <rect x="4" y="2" width="8" height="2" fill="${theme.hair}" />
        <rect x="5" y="4" width="6" height="5" fill="${theme.skin}" />
        <!-- 3D Shaded Eyes & Glasses -->
        <rect x="6" y="5" width="1" height="1" fill="#0f172a" />
        <rect x="9" y="5" width="1" height="1" fill="#0f172a" />
        <!-- Head Accessory / Headset / Tie -->
        <rect x="5" y="3" width="6" height="1" fill="${theme.acc}" />
      </g>

      <!-- TORSO / 3D VEST -->
      <g class="human-body">
        <rect x="4" y="9" width="8" height="7" fill="${theme.shirt}" />
        <rect x="7" y="10" width="2" height="4" fill="${theme.acc}" />
      </g>

      <!-- LEFT ARM -->
      <g class="human-arm-l">
        <rect x="2" y="9" width="2" height="5" fill="${theme.shirt}" />
        <rect x="2" y="14" width="2" height="2" fill="${theme.skin}" />
      </g>

      <!-- RIGHT ARM -->
      <g class="human-arm-r">
        <rect x="12" y="9" width="2" height="5" fill="${theme.shirt}" />
        <rect x="12" y="14" width="2" height="2" fill="${theme.skin}" />
      </g>

      <!-- LEFT LEG -->
      <g class="human-leg-l">
        <rect x="5" y="16" width="3" height="5" fill="${theme.pants}" />
        <rect x="4" y="21" width="4" height="3" fill="${theme.shoes}" />
      </g>

      <!-- RIGHT LEG -->
      <g class="human-leg-r">
        <rect x="8" y="16" width="3" height="5" fill="${theme.pants}" />
        <rect x="8" y="21" width="4" height="3" fill="${theme.shoes}" />
      </g>
    </svg>
  `;
}

// 3D Isometric Coordinates on Room Floor (in Pixels)
const agentsInfo = {
  chronos: { el: null, homeX: 55,  homeY: 135, curX: 55,  curY: 135 },
  radar:   { el: null, homeX: 145, homeY: 135, curX: 145, curY: 135 },
  babel:   { el: null, homeX: 235, homeY: 135, curX: 235, curY: 135 },
  quill:   { el: null, homeX: 325, homeY: 135, curX: 325, curY: 135 },
  sentinel:{ el: null, homeX: 415, homeY: 135, curX: 415, curY: 135 },
  press:   { el: null, homeX: 505, homeY: 135, curX: 505, curY: 135 },
  nexus:   { el: null, homeX: 595, homeY: 135, curX: 595, curY: 135 },
  boss:    { el: null, homeX: 595, homeY: 285, curX: 595, curY: 285 }
};

// 3D Inter-agent collaborative dialogues in Isometric Space
const INTER_AGENT_CONVERSATIONS = [
  {
    agentA: "radar", agentB: "babel",
    moveA: { x: 200, y: 135 },
    speechA: "Babel, tolong terjemahkan berita IndiaTimes ini ke Bahasa Indonesia ya!",
    speechB: "Siap Radar! Segera saya konversi ke Bahasa Indonesia jurnalistik."
  },
  {
    agentA: "babel", agentB: "quill",
    moveA: { x: 290, y: 135 },
    speechA: "Quill, draf terjemahan sudah siap diringkas!",
    speechB: "Oke Babel, saya ekstrak 5W+1H dan 3 poin pentingnya sekarang!"
  },
  {
    agentA: "quill", agentB: "sentinel",
    moveA: { x: 380, y: 135 },
    speechA: "Sentinel, draf ringkasan siap diaudit anti-duplikasi & faktanya!",
    speechB: "Sedang dicek... Tata bahasa EYD & fakta 2026 valid! Lolos audit ✅"
  },
  {
    agentA: "sentinel", agentB: "press",
    moveA: { x: 470, y: 135 },
    speechA: "Press, berita sudah lolos verifikasi, siap kirim 1 Digest ke Boss!",
    speechB: "Meluncur ke Telegram @EmsaHermesBot! 🚀"
  },
  {
    agentA: "press", agentB: "nexus",
    moveA: { x: 560, y: 135 },
    speechA: "Nexus, data berita terbaru siap di-deploy ke Vercel!",
    speechB: "Siap Press, saya auto-push ke GitHub & Vercel live! ☁️"
  },
  {
    agentA: "chronos", agentB: "boss",
    moveA: { x: 560, y: 285 },
    speechA: "Lapor Boss, sistem kurasi 2 jam & anti-duplikasi berjalan lancar! 🫡",
    speechB: "Bagus sekali tim! Pastikan berita tetap tajam dan akurat ☕"
  }
];

// Initialize human sprites on load
document.addEventListener("DOMContentLoaded", () => {
  for (const [name, theme] of Object.entries(humanThemes)) {
    const container = document.getElementById(`sprite-container-${name}`);
    if (container) {
      container.innerHTML = createHumanPixelSVG(theme);
    }
    const el = document.getElementById(`agent-${name}`);
    if (el && agentsInfo[name]) {
      agentsInfo[name].el = el;
      el.style.left = `${agentsInfo[name].curX}px`;
      el.style.top = `${agentsInfo[name].curY}px`;
    }
  }
});

// Dynamic Speech Bubble: Pops in, stays for duration, then smoothly fades away
function showSpeechBubble(agentName, text, durationMs = 3800) {
  const bubble = document.getElementById(`bubble-${agentName}`);
  if (!bubble) return;

  if (speechTimers[agentName]) {
    clearTimeout(speechTimers[agentName]);
  }

  bubble.textContent = text;
  bubble.classList.add("active");

  speechTimers[agentName] = setTimeout(() => {
    bubble.classList.remove("active");
  }, durationMs);
}

// Move Human Agent across 3D Room Floor
function moveAgentTo(name, targetX, targetY, onArrival = null) {
  const agent = agentsInfo[name];
  if (!agent || !agent.el) return;

  if (targetX < agent.curX) {
    agent.el.classList.add("flip-left");
    agent.el.classList.remove("flip-right");
  } else if (targetX > agent.curX) {
    agent.el.classList.add("flip-right");
    agent.el.classList.remove("flip-left");
  }

  agent.el.classList.add("walking");
  agent.el.style.left = `${targetX}px`;
  agent.el.style.top = `${targetY}px`;
  agent.curX = targetX;
  agent.curY = targetY;

  setTimeout(() => {
    if (agent.el) agent.el.classList.remove("walking");
    if (onArrival) onArrival();
  }, 2200);
}

// Autonomous Inter-Agent Conversation Trigger
function runInterAgentConversation() {
  if (isPipelineRunning) return;

  const conv = INTER_AGENT_CONVERSATIONS[Math.floor(Math.random() * INTER_AGENT_CONVERSATIONS.length)];
  const agentA = conv.agentA;
  const agentB = conv.agentB;

  // 1. Agent A walks towards Agent B in 3D
  moveAgentTo(agentA, conv.moveA.x, conv.moveA.y, () => {
    // 2. Agent A speaks
    showSpeechBubble(agentA, conv.speechA, 3600);

    // 3. Agent B replies 1.8s later
    setTimeout(() => {
      showSpeechBubble(agentB, conv.speechB, 3600);

      // 4. Return to home desk after conversation
      setTimeout(() => {
        const home = agentsInfo[agentA];
        if (home) moveAgentTo(agentA, home.homeX, home.homeY);
      }, 3500);
    }, 1800);
  });
}
setInterval(runInterAgentConversation, 9000);

// Clock Updater
function updateClock() {
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];
  const clockEl = document.getElementById('office-clock');
  if (clockEl) clockEl.textContent = timeStr + " WIB";

  if (nextRunTimestamp) {
    const diff = Math.max(0, Math.floor((nextRunTimestamp - now.getTime()) / 1000));
    const h = String(Math.floor(diff / 3600)).padStart(2, '0');
    const m = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
    const s = String(diff % 60).padStart(2, '0');
    const cdEl = document.getElementById('countdown-timer');
    if (cdEl) cdEl.textContent = `${h}:${m}:${s}`;
  }
}
setInterval(updateClock, 1000);

// Fetch State from Backend
async function fetchState() {
  try {
    const res = await fetch('/api/state');
    if (!res.ok) return;
    const data = await res.json();

    isPipelineRunning = (data.status === 'running');

    // 1. Status Pill
    const statusEl = document.getElementById('system-status');
    const btn = document.getElementById('btn-trigger');
    if (isPipelineRunning) {
      statusEl.className = 'status-pill running';
      statusEl.innerHTML = '<span class="dot"></span> PROSES PIPELINE...';
      if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.6';
      }
    } else {
      statusEl.className = 'status-pill';
      statusEl.innerHTML = '<span class="dot"></span> READY (STANDBY)';
      if (btn) {
        btn.disabled = false;
        btn.style.opacity = '1';
      }
    }

    // 2. Next Run Countdown
    if (data.next_run) {
      nextRunTimestamp = new Date(data.next_run).getTime();
    } else {
      nextRunTimestamp = Date.now() + 7200000;
    }

    // 3. Speech Bubbles during pipeline
    if (data.agents && isPipelineRunning) {
      for (const [agentName, agentData] of Object.entries(data.agents)) {
        if (agentData.status === "active" || agentData.status === "done") {
          showSpeechBubble(agentName, agentData.speech, 4000);
        }

        if (agentData.action && agentsInfo[agentName]) {
          if (agentData.action.startsWith("walking_to_")) {
            const targetName = agentData.action.replace("walking_to_", "");
            if (agentsInfo[targetName]) {
              moveAgentTo(agentName, agentsInfo[targetName].homeX - 25, agentsInfo[targetName].homeY + 20);
            }
          }
        }
      }
    }

    // 4. Render News & Telegram messages
    if (data.latest_news && data.latest_news.length > 0) {
      renderTelegramFeed(data.latest_news);
      renderNewsList(data.latest_news);
    }
  } catch (err) {
    console.error("State fetch error:", err);
  }
}

function renderTelegramFeed(newsList) {
  const container = document.getElementById('tg-messages-container');
  if (!container) return;

  const categoryEmojis = {
    "Ekonomi": "📈",
    "Kesehatan": "🏥",
    "Geopolitik": "🌐"
  };

  const sections = newsList.slice(0, 3).map(item => {
    const emoji = categoryEmojis[item.category] || "📰";
    const pointsList = (item.points || []).map(p => `<li>${p}</li>`).join('');

    return `
      <div style="margin-bottom: 12px; border-bottom: 1px dashed #334155; padding-bottom: 8px;">
        <div style="font-weight: bold; color: #38bdf8; font-size: 13.5px;">${emoji} [${item.category.toUpperCase()}] ${item.title}</div>
        <div style="font-size: 11px; color: #facc15;">📅 ${item.pub_date || item.time || '-'} | 🔗 <a href="${item.url}" target="_blank" style="color: #53bdeb;">Sumber: ${item.source}</a></div>
        <div style="margin: 4px 0;"><strong>📌 Intisari:</strong> ${item.tldr || '-'}</div>
        <ul style="padding-left: 14px; margin: 4px 0;">${pointsList}</ul>
        <div><strong>💡 Dampak:</strong> <em>${item.impact || '-'}</em></div>
      </div>
    `;
  }).join('');

  container.innerHTML = `
    <div class="tg-bubble">
      <div class="tg-bubble-header">
        <span>📰 [EXECUTIVE DIGEST 2 JAM]</span>
        <span>${newsList[0]?.time || 'Terkini'}</span>
      </div>
      ${sections}
      <div class="tg-bubble-footer">
        <span>⏱️ 2 min digest</span>
        <span>Zero-Duplicate Verified ✅</span>
      </div>
    </div>
  `;
}

function renderNewsList(newsList) {
  const container = document.getElementById('curated-news-list');
  if (!container) return;

  const catClasses = {
    "Ekonomi": "cat-ekonomi",
    "Kesehatan": "cat-kesehatan",
    "Geopolitik": "cat-geopolitik"
  };

  container.innerHTML = newsList.map(item => {
    const catClass = catClasses[item.category] || "cat-ekonomi";
    return `
      <div class="news-card">
        <div class="news-card-header">
          <span class="news-card-cat ${catClass}">${item.category.toUpperCase()}</span>
          <span class="news-card-pub">📅 ${item.pub_date || item.time || '-'}</span>
        </div>
        <div class="news-card-title">${item.title}</div>
        <div class="news-card-tldr">${item.tldr || ''}</div>
        <div class="news-card-meta">
          <span>📰 Sumber: <strong>${item.source}</strong></span>
          <a href="${item.url}" target="_blank" style="color: #38bdf8; text-decoration: none;">Baca Berita Asli ↗</a>
        </div>
      </div>
    `;
  }).join('');
}

async function triggerManualRun() {
  const btn = document.getElementById('btn-trigger');
  if (btn) {
    btn.disabled = true;
    btn.style.opacity = '0.6';
  }
  
  try {
    const res = await fetch('/api/trigger', { method: 'POST' });
    if (res.ok) {
      fetchState();
    }
  } catch (err) {
    console.error("Trigger error:", err);
  }
}

// Initial Fetch & Polling
fetchState();
setInterval(fetchState, 2000);
