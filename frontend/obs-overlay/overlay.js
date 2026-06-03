(function () {
  const params = new URLSearchParams(window.location.search);
  const forwardedKeys = ["tournament_id", "event_id", "token"];
  const refreshMs = Math.min(
    30000,
    Math.max(2000, Number.parseInt(params.get("refresh") || "5000", 10) || 5000)
  );

  function endpointUrl() {
    const configured = params.get("api");
    const base =
      configured ||
      (window.location.protocol === "file:"
        ? "http://localhost:8000/overlay/live-score"
        : "/overlay/live-score");
    const url = new URL(base, window.location.href);
    forwardedKeys.forEach((key) => {
      const value = params.get(key);
      if (value) {
        url.searchParams.set(key, value);
      }
    });
    return url;
  }

  const els = {
    status: document.getElementById("overlay-status"),
    eventName: document.getElementById("event-name"),
    eventMeta: document.getElementById("event-meta"),
    updatedAt: document.getElementById("updated-at"),
    scoreStrip: document.getElementById("score-strip"),
    leaderboard: document.getElementById("leaderboard"),
    bouts: document.getElementById("bouts"),
  };

  function text(value, fallback) {
    return value === null || value === undefined || value === "" ? fallback : String(value);
  }

  function setStatus(label, state) {
    els.status.textContent = label;
    els.status.className = `status-pill ${state}`;
  }

  function renderUpdatedAt(value) {
    if (!value) {
      els.updatedAt.textContent = "--:--";
      return;
    }
    const date = new Date(value);
    els.updatedAt.textContent = Number.isNaN(date.getTime())
      ? "--:--"
      : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function eventMeta(event) {
    const parts = [event.weapon, event.gender, event.category, event.country].filter(Boolean);
    return parts.join(" / ") || "Live event";
  }

  function renderLeaders(leaders) {
    if (!leaders.length) {
      els.leaderboard.innerHTML = "<li>No active leaderboard</li>";
      return;
    }
    els.leaderboard.innerHTML = leaders
      .slice(0, 5)
      .map(
        (row) =>
          `<li><strong>#${text(row.rank, "-")}</strong><span>${text(row.name, "Unknown")}</span><small>${text(
            row.country,
            ""
          )}</small></li>`
      )
      .join("");
  }

  function renderScoreStrip(bouts) {
    if (!bouts.length) {
      els.scoreStrip.className = "score-strip no-active";
      els.scoreStrip.innerHTML = "<span>No active bouts</span>";
      return;
    }
    els.scoreStrip.className = "score-strip";
    els.scoreStrip.innerHTML = bouts
      .slice(0, 3)
      .map((bout) => {
        const left = text(bout.fencer_a && bout.fencer_a.name, "TBD");
        const right = text(bout.fencer_b && bout.fencer_b.name, "TBD");
        const score = `${text(bout.score && bout.score.a, "-")} - ${text(bout.score && bout.score.b, "-")}`;
        return `<span>${left}<br><strong>${score}</strong><br>${right}</span>`;
      })
      .join("");
  }

  function renderBouts(bouts) {
    if (!bouts.length) {
      els.bouts.innerHTML = '<article class="bout-card no-active"><span>No active bouts</span></article>';
      return;
    }
    els.bouts.innerHTML = bouts
      .slice(0, 4)
      .map((bout) => {
        const left = text(bout.fencer_a && bout.fencer_a.name, "TBD");
        const right = text(bout.fencer_b && bout.fencer_b.name, "TBD");
        const score = `${text(bout.score && bout.score.a, "-")} - ${text(bout.score && bout.score.b, "-")}`;
        return `<article class="bout-card">
          <div class="bout-header"><span>${text(bout.round, "Bout")}</span><span>${text(bout.status, "")}</span></div>
          <div class="bout-line"><span>${left}</span><span class="score">${score}</span><span class="right">${right}</span></div>
        </article>`;
      })
      .join("");
  }

  function renderNoActive(payload) {
    setStatus("No active event", "no-active");
    els.eventName.textContent = "FenceSpace Live";
    els.eventMeta.textContent = text(payload.message, "No active event");
    els.scoreStrip.className = "score-strip no-active";
    els.scoreStrip.innerHTML = "<span>No active event</span>";
    renderLeaders([]);
    renderBouts([]);
    renderUpdatedAt(payload.updated_at);
  }

  function renderDisconnected(message) {
    setStatus("Disconnected", "disconnected");
    els.eventName.textContent = "FenceSpace Live";
    els.eventMeta.textContent = message || "Disconnected from live data";
    els.scoreStrip.className = "score-strip disconnected";
    els.scoreStrip.innerHTML = "<span>Disconnected from live data</span>";
    renderLeaders([]);
    els.bouts.innerHTML = '<article class="bout-card disconnected"><span>Disconnected from live data</span></article>';
    renderUpdatedAt(null);
  }

  function renderActive(payload) {
    const event = payload.event || {};
    setStatus("Live", "");
    els.eventName.textContent = text(event.name, "Live Tournament");
    els.eventMeta.textContent = eventMeta(event);
    renderUpdatedAt(payload.updated_at);
    renderScoreStrip(payload.bouts || []);
    renderLeaders(payload.leaders || []);
    renderBouts(payload.bouts || []);
  }

  async function refresh() {
    try {
      const response = await fetch(endpointUrl(), { cache: "no-store" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.status === "error") {
        renderDisconnected(payload.message || "Disconnected from live data");
        return;
      }
      if (!payload.active) {
        renderNoActive(payload);
        return;
      }
      renderActive(payload);
    } catch (error) {
      renderDisconnected("Disconnected from live data");
    }
  }

  refresh();
  window.setInterval(refresh, refreshMs);
})();
