(function () {
  const params = new URLSearchParams(window.location.search);
  const forwardedKeys = ["tournament_id", "event_id"];
  const overlayToken = params.get("token");
  const refreshMs = Math.min(
    30000,
    Math.max(2000, Number.parseInt(params.get("refresh") || "5000", 10) || 5000)
  );

  if (overlayToken && window.history && window.history.replaceState) {
    const visibleUrl = new URL(window.location.href);
    visibleUrl.searchParams.delete("token");
    window.history.replaceState({}, "", visibleUrl.toString());
  }

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

  function clear(element) {
    element.replaceChildren();
  }

  function appendText(parent, tagName, value, className) {
    const node = document.createElement(tagName);
    if (className) {
      node.className = className;
    }
    node.textContent = value;
    parent.appendChild(node);
    return node;
  }

  function appendBreak(parent) {
    parent.appendChild(document.createElement("br"));
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
    clear(els.leaderboard);
    if (!leaders.length) {
      appendText(els.leaderboard, "li", "No active leaderboard");
      return;
    }
    leaders.slice(0, 5).forEach((row) => {
      const item = document.createElement("li");
      appendText(item, "strong", `#${text(row.rank, "-")}`);
      appendText(item, "span", text(row.name, "Unknown"));
      appendText(item, "small", text(row.country, ""));
      els.leaderboard.appendChild(item);
    });
  }

  function renderScoreStrip(bouts) {
    clear(els.scoreStrip);
    if (!bouts.length) {
      els.scoreStrip.className = "score-strip no-active";
      appendText(els.scoreStrip, "span", "No active bouts");
      return;
    }
    els.scoreStrip.className = "score-strip";
    bouts.slice(0, 3).forEach((bout) => {
      const left = text(bout.fencer_a && bout.fencer_a.name, "TBD");
      const right = text(bout.fencer_b && bout.fencer_b.name, "TBD");
      const score = `${text(bout.score && bout.score.a, "-")} - ${text(bout.score && bout.score.b, "-")}`;
      const item = document.createElement("span");
      item.appendChild(document.createTextNode(left));
      appendBreak(item);
      appendText(item, "strong", score);
      appendBreak(item);
      item.appendChild(document.createTextNode(right));
      els.scoreStrip.appendChild(item);
    });
  }

  function renderBouts(bouts) {
    clear(els.bouts);
    if (!bouts.length) {
      const card = document.createElement("article");
      card.className = "bout-card no-active";
      appendText(card, "span", "No active bouts");
      els.bouts.appendChild(card);
      return;
    }
    bouts.slice(0, 4).forEach((bout) => {
      const left = text(bout.fencer_a && bout.fencer_a.name, "TBD");
      const right = text(bout.fencer_b && bout.fencer_b.name, "TBD");
      const score = `${text(bout.score && bout.score.a, "-")} - ${text(bout.score && bout.score.b, "-")}`;
      const card = document.createElement("article");
      card.className = "bout-card";
      const header = document.createElement("div");
      header.className = "bout-header";
      appendText(header, "span", text(bout.round, "Bout"));
      appendText(header, "span", text(bout.status, ""));
      const line = document.createElement("div");
      line.className = "bout-line";
      appendText(line, "span", left);
      appendText(line, "span", score, "score");
      appendText(line, "span", right, "right");
      card.appendChild(header);
      card.appendChild(line);
      els.bouts.appendChild(card);
    });
  }

  function renderNoActive(payload) {
    setStatus("No active event", "no-active");
    els.eventName.textContent = "FenceSpace Live";
    els.eventMeta.textContent = text(payload.message, "No active event");
    els.scoreStrip.className = "score-strip no-active";
    clear(els.scoreStrip);
    appendText(els.scoreStrip, "span", "No active event");
    renderLeaders([]);
    renderBouts([]);
    renderUpdatedAt(payload.updated_at);
  }

  function renderDisconnected(message) {
    setStatus("Disconnected", "disconnected");
    els.eventName.textContent = "FenceSpace Live";
    els.eventMeta.textContent = message || "Disconnected from live data";
    els.scoreStrip.className = "score-strip disconnected";
    clear(els.scoreStrip);
    appendText(els.scoreStrip, "span", "Disconnected from live data");
    renderLeaders([]);
    clear(els.bouts);
    const card = document.createElement("article");
    card.className = "bout-card disconnected";
    appendText(card, "span", "Disconnected from live data");
    els.bouts.appendChild(card);
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
      const response = await fetch(endpointUrl(), {
        cache: "no-store",
        headers: overlayToken ? { "X-Overlay-Token": overlayToken } : undefined,
      });
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
