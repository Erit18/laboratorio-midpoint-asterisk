(() => {
  const tbody = document.getElementById("cdr-tbody");
  const statTotal = document.getElementById("stat-total");
  const statAnswered = document.getElementById("stat-answered");
  const statNoAnswer = document.getElementById("stat-noanswer");
  const statFailed = document.getElementById("stat-failed");
  const statDuration = document.getElementById("stat-duration");

  const filterSrc = document.getElementById("filter-src");
  const filterDate = document.getElementById("filter-date");
  const filterDisposition = document.getElementById("filter-disposition");
  const btnRefresh = document.getElementById("btn-refresh");

  const playerBar = document.getElementById("player-bar");
  const playerFile = document.getElementById("player-file");
  const audioPlayer = document.getElementById("audio-player");
  const playerClose = document.getElementById("player-close");

  const DISPOSITION_LABELS = {
    "ANSWERED": { text: "Contestada", cls: "badge-answered" },
    "NO ANSWER": { text: "Sin respuesta", cls: "badge-noanswer" },
    "FAILED": { text: "Fallida", cls: "badge-failed" },
    "BUSY": { text: "Ocupado", cls: "badge-busy" },
  };

  function formatDuration(seconds) {
    const s = parseInt(seconds, 10) || 0;
    const h = Math.floor(s / 3600).toString().padStart(2, "0");
    const m = Math.floor((s % 3600) / 60).toString().padStart(2, "0");
    const sec = (s % 60).toString().padStart(2, "0");
    return `${h}:${m}:${sec}`;
  }

  function escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderTable(calls) {
    if (!calls.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="6">Sin llamadas registradas todavía.</td></tr>`;
      return;
    }

    tbody.innerHTML = calls.map((call) => {
      const disp = DISPOSITION_LABELS[call.disposition] || { text: call.disposition || "—", cls: "" };
      const recordingCell = call.recording_file
        ? `<button class="play-btn" data-file="${escapeHtml(call.recording_file)}" title="Reproducir grabación">▶</button>`
        : `<span class="no-recording">sin audio</span>`;

      return `
        <tr>
          <td class="col-time">${escapeHtml(call.start || "—")}</td>
          <td class="col-src">${escapeHtml(call.src || "—")}</td>
          <td class="col-dst">${escapeHtml(call.dst || "—")}</td>
          <td class="col-duration">${formatDuration(call.billsec)}</td>
          <td><span class="badge ${disp.cls}">${escapeHtml(disp.text)}</span></td>
          <td>${recordingCell}</td>
        </tr>
      `;
    }).join("");

    tbody.querySelectorAll(".play-btn").forEach((btn) => {
      btn.addEventListener("click", () => playRecording(btn.dataset.file));
    });
  }

  function renderStats(stats) {
    statTotal.textContent = stats.total;
    statAnswered.textContent = stats.answered;
    statNoAnswer.textContent = stats.no_answer;
    statFailed.textContent = stats.failed;
    statDuration.textContent = formatDuration(stats.total_billsec);
  }

  function playRecording(filename) {
    audioPlayer.src = `/recordings/${encodeURIComponent(filename)}`;
    playerFile.textContent = filename;
    playerBar.classList.add("active");
    audioPlayer.play().catch(() => {});
  }

  playerClose.addEventListener("click", () => {
    audioPlayer.pause();
    audioPlayer.src = "";
    playerBar.classList.remove("active");
  });

  async function loadData() {
    const params = new URLSearchParams();
    if (filterSrc.value.trim()) params.set("src", filterSrc.value.trim());
    if (filterDate.value) params.set("date", filterDate.value);
    if (filterDisposition.value) params.set("disposition", filterDisposition.value);

    try {
      const res = await fetch(`/api/cdr?${params.toString()}`);
      const data = await res.json();
      renderStats(data.stats);
      renderTable(data.calls);
    } catch (err) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="6">No se pudo conectar con el backend del panel.</td></tr>`;
    }
  }

  btnRefresh.addEventListener("click", loadData);
  filterSrc.addEventListener("input", debounce(loadData, 350));
  filterDate.addEventListener("change", loadData);
  filterDisposition.addEventListener("change", loadData);

  function debounce(fn, wait) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  function tickClock() {
    const now = new Date();
    document.getElementById("clock").textContent = now.toLocaleTimeString("es-PE");
  }
  setInterval(tickClock, 1000);
  tickClock();

  loadData();
  setInterval(loadData, 15000);
})();
