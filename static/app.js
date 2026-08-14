let nextRunTimestamp = null;

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

    // 1. Status
    const statusEl = document.getElementById('system-status');
    if (data.status === 'running') {
      statusEl.className = 'status-pill running';
      statusEl.innerHTML = '<span class="dot"></span> RUNNING PIPELINE...';
      document.getElementById('btn-trigger').disabled = true;
      document.getElementById('btn-trigger').style.opacity = '0.6';
    } else {
      statusEl.className = 'status-pill';
      statusEl.innerHTML = '<span class="dot"></span> READY (STANDBY)';
      document.getElementById('btn-trigger').disabled = false;
      document.getElementById('btn-trigger').style.opacity = '1';
    }

    // 2. Next Run
    if (data.next_run) {
      nextRunTimestamp = new Date(data.next_run).getTime();
    } else {
      nextRunTimestamp = Date.now() + 7200000;
    }

    // 3. Speech Bubbles for each agent
    if (data.agents) {
      for (const [agentName, agentData] of Object.entries(data.agents)) {
        const bubble = document.getElementById(`bubble-${agentName}`);
        if (bubble) {
          if (bubble.textContent !== agentData.speech) {
            bubble.style.opacity = '0';
            bubble.style.transform = 'translateY(4px)';
            setTimeout(() => {
              bubble.textContent = agentData.speech;
              bubble.style.opacity = '1';
              bubble.style.transform = 'translateY(0)';
            }, 150);
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

  container.innerHTML = newsList.map(item => {
    const emoji = categoryEmojis[item.category] || "📰";
    const pointsList = (item.points || []).map(p => `<li>${p}</li>`).join('');

    return `
      <div class="tg-bubble">
        <div class="tg-bubble-header">
          <span>${emoji} [${item.category.toUpperCase()} UPDATE]</span>
          <span>${item.time || 'Baru saja'}</span>
        </div>
        <div class="tg-bubble-title">${item.title}</div>
        <div><strong>📌 Ringkasan Inti:</strong> ${item.tldr || '-'}</div>
        <ul class="tg-bubble-points">${pointsList}</ul>
        <div><strong>💡 Dampak:</strong> <em>${item.impact || '-'}</em></div>
        <div class="tg-bubble-footer">
          <span>⏱️ 1 min read</span>
          <a href="${item.url}" target="_blank" rel="noopener">🔗 Sumber: ${item.source}</a>
        </div>
      </div>
    `;
  }).join('');
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
        <span class="news-card-cat ${catClass}">${item.category.toUpperCase()}</span>
        <div class="news-card-title">${item.title}</div>
        <div class="news-card-tldr">${item.tldr || ''}</div>
        <div class="news-card-meta">
          <span>📰 ${item.source}</span>
          <a href="${item.url}" target="_blank" style="color: #38bdf8; text-decoration: none;">Baca Sumber ↗</a>
        </div>
      </div>
    `;
  }).join('');
}

async function triggerManualRun() {
  const btn = document.getElementById('btn-trigger');
  btn.disabled = true;
  btn.style.opacity = '0.6';
  
  try {
    const res = await fetch('/api/trigger', { method: 'POST' });
    if (res.ok) {
      console.log("News cycle triggered!");
      fetchState();
    }
  } catch (err) {
    console.error("Trigger error:", err);
  }
}

// Initial Fetch & Interval Polling
fetchState();
setInterval(fetchState, 2000);
