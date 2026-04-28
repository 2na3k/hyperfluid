const WS_URL = `ws://${location.host}/ws/matrix`;
let state = null;
let selected = new Set();

function connect() {
  const ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    document.getElementById("connection-badge").textContent = "connected";
    document.getElementById("connection-badge").className = "connected";
  };
  ws.onclose = () => {
    document.getElementById("connection-badge").textContent = "disconnected";
    document.getElementById("connection-badge").className = "disconnected";
    setTimeout(connect, 2000);
  };
  ws.onmessage = (e) => {
    state = JSON.parse(e.data);
    if (selected.size === 0 && state.streams.length) {
      state.streams.forEach((s) => selected.add(s));
    }
    render();
  };
}

function renderSelectors() {
  if (!state) return;
  const allStreams = state.streams.length ? state.streams : Object.keys(state.status);
  if (!allStreams.length) return;
  const source = allStreams[0].split(":")[0];
  const tickers = allStreams.map((s) => ({
    id: s,
    symbol: s.split(":").slice(1).join(":"),
  }));

  document.getElementById("stream-selectors").innerHTML =
    `<span class="source-label">${source}</span>` +
    `<div class="ticker-pills">` +
    tickers
      .map(
        (t) =>
          `<span class="pill${selected.has(t.id) ? " active" : ""}" data-id="${t.id}">${t.symbol}</span>`
      )
      .join("") +
    `</div>`;
}

function getFiltered() {
  if (!state || selected.size < 2) return null;
  const idx = state.streams.map((s, i) => (selected.has(s) ? i : -1)).filter((i) => i >= 0);
  const streams = idx.map((i) => state.streams[i]);
  const covariance = idx.map((i) => idx.map((j) => state.covariance[i][j]));
  const correlation = idx.map((i) => idx.map((j) => state.correlation[i][j]));
  return { streams, covariance, correlation };
}

function render() {
  if (!state) return;
  document.getElementById("last-update").textContent = new Date(state.timestamp).toLocaleTimeString();
  renderSelectors();
  const data = getFiltered();
  if (data) {
    renderCorrelation(data.streams, data.correlation);
    renderCovariance(data.streams, data.covariance);
  } else {
    document.getElementById("correlation-table").innerHTML =
      '<p class="muted">select at least 2 streams</p>';
    document.getElementById("covariance-table").innerHTML = "";
  }
  renderStreams(state.status);
}

function renderCorrelation(streams, matrix) {
  renderMatrix("correlation-table", streams, matrix, (v) => {
    if (v <= 0) {
      const t = v + 1;
      const r = Math.round(180 + 65 * t);
      const gb = Math.round(75 + 170 * t);
      return `rgb(${r},${gb},${gb})`;
    } else {
      const t = 1 - v;
      const r = Math.round(245 - 170 * t);
      const g = Math.round(245 - 115 * t);
      const b = Math.round(243 - 68 * t);
      return `rgb(${r},${g},${b})`;
    }
  });
}

function renderCovariance(streams, matrix) {
  renderMatrix("covariance-table", streams, matrix, () => "#f9f9f7", true);
}

function renderMatrix(id, streams, matrix, colorFn, isCov) {
  const el = document.getElementById(id);
  const n = streams.length;
  if (!n) {
    el.innerHTML = '<p class="muted">waiting for data...</p>';
    return;
  }
  let h = '<table><thead><tr><th></th>';
  for (const s of streams) h += `<th>${s.split(":")[1] || s}</th>`;
  h += "</tr></thead><tbody>";
  for (let i = 0; i < n; i++) {
    h += `<tr><th>${streams[i].split(":")[1] || streams[i]}</th>`;
    for (let j = 0; j < n; j++) {
      const v = matrix[i][j];
      h += `<td style="background:${colorFn(v)}">${isCov ? v.toExponential(4) : v.toFixed(4)}</td>`;
    }
    h += "</tr>";
  }
  h += "</tbody></table>";
  el.innerHTML = h;
}

function renderStreams(status) {
  const el = document.getElementById("streams-status");
  let h =
    '<table><thead><tr><th>stream</th><th>status</th><th>price</th><th>samples</th></tr></thead><tbody>';
  for (const [sid, info] of Object.entries(status)) {
    const hasData = info.samples > 0;
    h += `<tr><td>${sid.split(":")[1] || sid}</td>
          <td class="${hasData ? "ok" : "nodata"}">${hasData ? "ok" : "no data"}</td>
          <td>${info.lastPrice?.toFixed(2) ?? "-"}</td>
          <td>${info.samples}</td></tr>`;
  }
  h += "</tbody></table>";
  el.innerHTML = h;
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("stream-selectors").addEventListener("click", (e) => {
    const pill = e.target.closest(".pill");
    if (!pill) return;
    const id = pill.dataset.id;
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    render();
  });
  connect();
});
