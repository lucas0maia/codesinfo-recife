const STATUS_LABELS = {
  aberto: "Aberto",
  fluxo_continuo: "Fluxo contínuo",
  verificar_prazo: "Verificar prazo",
  encerrado: "Encerrado",
};

const els = {
  kpiTotal: document.getElementById("kpi-total"),
  kpiOpen: document.getElementById("kpi-open"),
  kpiDirect: document.getElementById("kpi-direct"),
  kpiTransversal: document.getElementById("kpi-transversal"),
  filterQ: document.getElementById("filter-q"),
  filterStatus: document.getElementById("filter-status"),
  filterArea: document.getElementById("filter-area"),
  filterSource: document.getElementById("filter-source"),
  tbody: document.getElementById("editais-tbody"),
  listCount: document.getElementById("list-count"),
  btnCollect: document.getElementById("btn-collect"),
  collectBanner: document.getElementById("collect-banner"),
  modalBackdrop: document.getElementById("modal-backdrop"),
  modalClose: document.getElementById("modal-close"),
  modalBadge: document.getElementById("modal-badge"),
  modalTitle: document.getElementById("modal-title"),
  modalOrganizer: document.getElementById("modal-organizer"),
  modalDeadline: document.getElementById("modal-deadline"),
  modalValue: document.getElementById("modal-value"),
  modalSource: document.getElementById("modal-source"),
  modalType: document.getElementById("modal-type"),
  modalEligibility: document.getElementById("modal-eligibility"),
  modalTips: document.getElementById("modal-tips"),
  modalSummary: document.getElementById("modal-summary"),
  modalSourceLink: document.getElementById("modal-source-link"),
  modalLink: document.getElementById("modal-link"),
};

let currentItems = [];
let staticMode = false;
let staticAllItems = [];

function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function enableStaticMode() {
  if (staticMode) return;
  staticMode = true;
  els.btnCollect.disabled = true;
  els.btnCollect.textContent = "Fac-símile Estático";
  els.btnCollect.title = "Versão online de apresentação com dados da última coleta programática";
}

async function fetchJsonWithFallback(apiUrl, staticUrl) {
  if (!staticMode) {
    try {
      const res = await fetch(apiUrl);
      if (res.ok) return await res.json();
    } catch (_) {
      // Fallback to static snapshot when hosted without Python backend
    }
  }
  enableStaticMode();
  const res = await fetch(staticUrl);
  return await res.json();
}

async function loadStats() {
  const stats = await fetchJsonWithFallback("/api/stats", "./data/stats.json");
  els.kpiTotal.textContent = stats.total;
  els.kpiOpen.textContent = stats.open_or_rolling;
  els.kpiDirect.textContent = stats.journalism_direct_count;
  els.kpiTransversal.textContent = stats.transversal_count;

  const prevArea = els.filterArea.value;
  els.filterArea.innerHTML = '<option value="">Todas as áreas</option>';
  Object.keys(stats.by_area || {}).forEach((area) => {
    const opt = document.createElement("option");
    opt.value = area;
    opt.textContent = `${area} (${stats.by_area[area]})`;
    els.filterArea.appendChild(opt);
  });
  els.filterArea.value = prevArea;
}

function filterStaticItems() {
  const statusVal = els.filterStatus.value;
  const areaVal = els.filterArea.value;
  const sourceVal = els.filterSource.value;
  const qVal = els.filterQ.value.trim().toLowerCase();

  return staticAllItems.filter((item) => {
    if (statusVal && statusVal !== "__all__") {
      if (item.status !== statusVal) return false;
    } else if (statusVal === "" && item.status === "encerrado") {
      return false;
    }
    if (areaVal && item.primary_area !== areaVal && !(item.areas || []).includes(areaVal)) {
      return false;
    }
    if (sourceVal && item.source_id !== sourceVal) {
      return false;
    }
    if (qVal) {
      const hay = `${item.title} ${item.summary} ${item.organizer}`.toLowerCase();
      if (!hay.includes(qVal)) return false;
    }
    return true;
  });
}

async function loadEditais() {
  const params = new URLSearchParams();
  const statusVal = els.filterStatus.value;
  if (statusVal && statusVal !== "__all__") {
    params.set("status", statusVal);
  } else if (statusVal === "") {
    params.set("exclude_closed", "1");
  }
  if (els.filterArea.value) params.set("area", els.filterArea.value);
  if (els.filterSource.value) params.set("source", els.filterSource.value);
  if (els.filterQ.value.trim()) params.set("q", els.filterQ.value.trim());

  if (staticMode && staticAllItems.length > 0) {
    currentItems = filterStaticItems();
  } else {
    const data = await fetchJsonWithFallback(`/api/editais?${params.toString()}`, "./data/editais.json");
    if (staticMode) {
      staticAllItems = data.items || [];
      currentItems = filterStaticItems();
    } else {
      currentItems = data.items || [];
    }
  }
  els.listCount.textContent = currentItems.length;

  // Populate source filter once if empty
  if (els.filterSource.options.length <= 1 && currentItems.length > 0) {
    const seen = new Map();
    currentItems.forEach((it) => seen.set(it.source_id, it.source_name));
    seen.forEach((name, id) => {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = name;
      els.filterSource.appendChild(opt);
    });
  }

  renderTable(currentItems);
}

function renderTable(items) {
  if (!items.length) {
    els.tbody.innerHTML = '<tr><td colspan="7" class="empty">Nenhum edital encontrado com esses filtros.</td></tr>';
    return;
  }

  els.tbody.innerHTML = items
    .map(
      (item, idx) => `
      <tr data-idx="${idx}">
        <td>
          <div class="edital-title">${escapeHtml(item.title)}</div>
          <div class="edital-org">${escapeHtml(item.organizer)} · ${escapeHtml(item.source_name)}</div>
        </td>
        <td>
          <span class="area-tag">${escapeHtml(item.primary_area)}</span>
          <span class="transversal-note">${item.is_transversal ? "Edital transversal" : "Jornalismo direto"}</span>
        </td>
        <td>
          <span class="status-tag status-${escapeHtml(item.status)}">${escapeHtml(STATUS_LABELS[item.status] || item.status)}</span>
        </td>
        <td>${escapeHtml(item.deadline_raw || "Verificar")}</td>
        <td>${escapeHtml(item.value_raw || "Não informado")}</td>
        <td><span class="score-pill">${item.relevance_score}%</span></td>
        <td><button class="btn-small" type="button">Detalhes</button></td>
      </tr>
    `
    )
    .join("");

  els.tbody.querySelectorAll("tr[data-idx]").forEach((row) => {
    row.addEventListener("click", () => {
      const item = currentItems[Number(row.dataset.idx)];
      if (item) openModal(item);
    });
  });
}

function openModal(item) {
  els.modalBadge.className = `status-tag status-${item.status}`;
  els.modalBadge.textContent = STATUS_LABELS[item.status] || item.status;
  els.modalTitle.textContent = item.title;
  els.modalOrganizer.textContent = `Realizador: ${item.organizer}`;
  els.modalDeadline.textContent = item.deadline_raw || "Verificar no edital";
  els.modalValue.textContent = item.value_raw || "Não informado";
  els.modalSource.textContent = item.source_name;
  els.modalType.textContent = item.is_transversal ? "Transversal (aceita mídia/projetos)" : "Jornalismo Direto";

  els.modalEligibility.innerHTML = (item.eligibility || [])
    .map((e) => `<li>${escapeHtml(e)}</li>`)
    .join("");
  els.modalTips.innerHTML = (item.journalism_fit_tips || [])
    .map((t) => `<li>${escapeHtml(t)}</li>`)
    .join("");
  els.modalSummary.textContent = item.summary || "";
  els.modalLink.href = item.url;
  if (item.source_url && item.source_url !== item.url) {
    els.modalSourceLink.href = item.source_url;
    els.modalSourceLink.classList.remove("hidden");
  } else {
    els.modalSourceLink.classList.add("hidden");
  }

  els.modalBackdrop.classList.remove("hidden");
}

function closeModal() {
  els.modalBackdrop.classList.add("hidden");
}

els.modalClose.addEventListener("click", closeModal);
els.modalBackdrop.addEventListener("click", (e) => {
  if (e.target === els.modalBackdrop) closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

[els.filterStatus, els.filterArea, els.filterSource].forEach((el) =>
  el.addEventListener("change", loadEditais)
);
let searchTimer = null;
els.filterQ.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadEditais, 200);
});

els.btnCollect.addEventListener("click", async () => {
  els.btnCollect.disabled = true;
  els.btnCollect.textContent = "Coletando...";
  els.collectBanner.classList.add("hidden");
  try {
    const res = await fetch("/api/collect", { method: "POST" });
    const data = await res.json();
    const r = data.report;
    els.collectBanner.textContent = `Coleta programática concluída: ${r.stored_unique} editais únicos processados (${r.filtered_noise} ruídos filtrados).`;
    els.collectBanner.classList.remove("hidden");
    await loadStats();
    await loadEditais();
  } catch (err) {
    els.collectBanner.textContent = `Erro ao coletar: ${err.message}`;
    els.collectBanner.classList.remove("hidden");
  } finally {
    els.btnCollect.disabled = false;
    els.btnCollect.textContent = "Atualizar Coleta Agora";
  }
});

(async function init() {
  await loadStats();
  await loadEditais();
})();

