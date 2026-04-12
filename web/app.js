const state = {
  dataDir: localStorage.getItem("coachGarmin.dataDir") || "data",
  workspace: localStorage.getItem("coachGarmin.workspace") || "data",
  provider: localStorage.getItem("coachGarmin.provider") || "ollama",
  model: localStorage.getItem("coachGarmin.model") || "",
  baseUrl: localStorage.getItem("coachGarmin.baseUrl") || "",
  sourcePath: localStorage.getItem("coachGarmin.sourcePath") || "",
  goalText: localStorage.getItem("coachGarmin.goalText") || "",
  currentQuestions: [],
  answers: {},
  installPrompt: null,
};

const $ = (id) => document.getElementById(id);

const transcript = $("chat-transcript");
const questionsBox = $("questions");
const planList = $("plan-list");
const summaryBox = $("coach-summary");
const busyBanner = $("busy-banner");
const busyText = $("busy-text");
const providerChip = $("provider-chip");
const importChip = $("import-chip");
const workspaceChip = $("workspace-chip");
const workspaceLine = $("workspace-status-line");
const importLine = $("import-status-line");
const installButton = $("install-button");

const actionButtons = [];

function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return String(value);
  }
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(numeric);
}

function formatKilometers(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return `${formatNumber(value, 1)} km`;
}

function formatPace(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const totalMinutes = Number(value);
  if (!Number.isFinite(totalMinutes) || totalMinutes <= 0) {
    return "-";
  }
  const minutes = Math.floor(totalMinutes);
  const seconds = Math.round((totalMinutes - minutes) * 60);
  if (seconds === 60) {
    return `${minutes + 1}:00/km`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}/km`;
}

function formatHeartRate(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return `${formatNumber(value, 0)} bpm`;
}

function formatDurationHours(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  const hours = Math.floor(numeric);
  const minutes = Math.round((numeric - hours) * 60);
  if (!hours) {
    return `${minutes} min`;
  }
  return `${hours}h ${String(minutes).padStart(2, "0")}`;
}

function setBusy(active, message = "Analyse en cours...") {
  busyBanner.classList.toggle("hidden", !active);
  busyText.textContent = message;
  document.body.classList.toggle("is-busy", active);
  actionButtons.forEach((button) => {
    button.disabled = active;
  });
}

function addMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  transcript.appendChild(node);
  transcript.scrollTop = transcript.scrollHeight;
}

function setInputs() {
  $("data-dir-input").value = state.dataDir;
  $("workspace-input").value = state.workspace;
  $("provider-select").value = state.provider;
  $("model-input").value = state.model;
  $("base-url-input").value = state.baseUrl;
  $("source-path-input").value = state.sourcePath;
  $("goal-input").value = state.goalText;
}

function persistSettings() {
  state.dataDir = $("data-dir-input").value.trim() || "data";
  state.workspace = $("workspace-input").value.trim() || state.dataDir;
  state.provider = $("provider-select").value;
  state.model = $("model-input").value.trim();
  state.baseUrl = $("base-url-input").value.trim();
  state.sourcePath = $("source-path-input").value.trim();
  state.goalText = $("goal-input").value.trim();

  localStorage.setItem("coachGarmin.dataDir", state.dataDir);
  localStorage.setItem("coachGarmin.workspace", state.workspace);
  localStorage.setItem("coachGarmin.provider", state.provider);
  localStorage.setItem("coachGarmin.model", state.model);
  localStorage.setItem("coachGarmin.baseUrl", state.baseUrl);
  localStorage.setItem("coachGarmin.sourcePath", state.sourcePath);
  localStorage.setItem("coachGarmin.goalText", state.goalText);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  if (!response.ok) {
    throw new Error(payload.error || `Request failed with status ${response.status}`);
  }
  return payload;
}

async function withBusy(message, action) {
  setBusy(true, message);
  try {
    return await action();
  } finally {
    setBusy(false);
  }
}

function renderSparkline(container, series, options = {}) {
  const values = Array.isArray(series) ? series.filter((value) => Number.isFinite(Number(value))) : [];
  if (!values.length) {
    container.innerHTML = "<p class='status-line'>Pas encore de données exploitables.</p>";
    return;
  }

  const width = options.width || 340;
  const height = options.height || 90;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((value, index) => {
    const x = values.length > 1 ? index * step : width / 2;
    const y = height - ((Number(value) - min) / span) * (height - 16) - 8;
    return { x, y };
  });
  const line = points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="sparkline-fill-${options.id || "base"}" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="${options.fill || "rgba(138, 230, 192, 0.38)"}" />
          <stop offset="100%" stop-color="rgba(138, 230, 192, 0.03)" />
        </linearGradient>
      </defs>
      <polygon points="${area}" fill="url(#sparkline-fill-${options.id || "base"})"></polygon>
      <polyline
        points="${line}"
        fill="none"
        stroke="${options.stroke || "#8ae6c0"}"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      ></polyline>
      ${points
        .map(
          (point) => `
            <circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.5" fill="${options.stroke || "#8ae6c0"}"></circle>
          `,
        )
        .join("")}
    </svg>
  `;
}

function renderTrendCard(container, series, options = {}) {
  const values = Array.isArray(series) ? series : [];
  if (!values.length) {
    container.innerHTML = "<p class='status-line'>Aucune tendance disponible pour le moment.</p>";
    return;
  }
  renderSparkline(container, values, options);
}

function renderDashboard(payload) {
  const workspace = payload.workspace || {};
  const importStatus = payload.import_status || {};
  const analysis = payload.analysis || {};
  const metrics = analysis.metrics || {};
  const trend = analysis.trend || {};
  const provider = payload.provider || {};
  const latestRun = importStatus.latest_run || payload.health?.latest_sync_run || null;
  const syncState = importStatus.sync_state || payload.health?.sync_state || {};
  const ready = provider.status === "ready";

  const workspaceLabel = workspace.path || state.workspace || state.dataDir;
  const importState = importStatus.state || (importStatus.available ? "indexed" : "empty");
  const providerLabel = ready
    ? `Provider ${provider.provider === "ollama" ? "Ollama" : provider.provider} prêt`
    : `Provider ${provider.provider || state.provider} indisponible`;
  const importLabel = importState === "imported" ? "Données importées" : importState === "indexed" ? "Données indexées" : "Aucune donnée importée";
  const importDetail = latestRun
    ? `Dernier import: ${latestRun.run_label || "sync"} · ${latestRun.total_records || 0} enregistrements · ${syncState.new_artifact_count || 0} nouveaux · ${syncState.reused_artifact_count || 0} réutilisés · ${syncState.pending_count || 0} en attente`
    : "Aucun import Garmin détecté pour ce workspace.";

  providerChip.textContent = providerLabel;
  providerChip.classList.toggle("warn", !ready);
  importChip.textContent = `Données: ${importLabel}`;
  importChip.classList.toggle("warn", importState === "empty");
  workspaceChip.textContent = `Workspace: ${workspaceLabel}`;
  workspaceLine.textContent = `Workspace: ${workspaceLabel}`;
  importLine.textContent = `Import: ${importDetail}`;

  $("weekly-volume-card").textContent = formatKilometers(metrics.weekly_volume_km ?? metrics.total_distance_km_7d ?? metrics.total_distance_km_21d);
  $("weekly-volume-subtitle").textContent = `${formatNumber(metrics.weekly_running_days ?? metrics.recent_running_days ?? 0)} sorties course sur 7 jours`;

  const load7d = metrics.load_7d;
  const load28d = metrics.load_28d;
  const ratio = metrics.load_ratio_7_28;
  $("load-card").textContent = load7d === null || load7d === undefined ? "-" : formatNumber(load7d, 0);
  $("load-subtitle").textContent =
    load28d !== null && load28d !== undefined
      ? `28j ${formatNumber(load28d, 0)} · ratio ${ratio === null || ratio === undefined ? "-" : formatNumber(ratio, 2)}`
      : "Charge non disponible";

  $("resting-hr-card").textContent = formatHeartRate(metrics.resting_hr_7d);
  $("resting-hr-subtitle").textContent = metrics.fatigue_flag ? "Fatigue détectée" : "Signal stable";

  $("sleep-card").textContent = metrics.sleep_hours_7d === null || metrics.sleep_hours_7d === undefined ? "-" : `${formatNumber(metrics.sleep_hours_7d, 1)} h`;
  $("sleep-subtitle").textContent = metrics.overreaching_flag ? "Récupération à surveiller" : "Sommeil récent correct";

  const pace = metrics.average_pace_21d ?? metrics.threshold_pace_min_per_km;
  const latestHr = trend.pace_hr_sessions?.length ? trend.pace_hr_sessions[trend.pace_hr_sessions.length - 1].average_hr : null;
  $("pace-hr-card").textContent = `${formatPace(pace)} · ${formatHeartRate(latestHr)}`;
  $("pace-hr-subtitle").textContent =
    analysis.benchmark?.event && analysis.benchmark?.pace_min_per_km
      ? `${analysis.benchmark.event} repère ${formatPace(analysis.benchmark.pace_min_per_km)}`
      : "Base allure calculée depuis l'historique";

  $("max-hr-card").textContent = formatHeartRate(metrics.max_hr_estimate);
  $("max-hr-subtitle").textContent = metrics.max_hr_estimate ? "Estimée depuis les zones" : "Non disponible";

  $("analysis-card").textContent = analysis.summary || "Aucune lecture coach pour le moment.";
  const signalBits = [];
  if (analysis.training_phase) signalBits.push(`Phase: ${analysis.training_phase}`);
  if (metrics.hrv_7d !== null && metrics.hrv_7d !== undefined) signalBits.push(`HRV 7j: ${formatNumber(metrics.hrv_7d, 1)}`);
  if (metrics.long_run_km !== null && metrics.long_run_km !== undefined) signalBits.push(`Sortie longue: ${formatKilometers(metrics.long_run_km)}`);
  $("analysis-subtitle").textContent = signalBits.join(" · ") || "Analyse locale en attente.";

  $("volume-trend-summary").textContent =
    trend.daily_volume?.length
      ? `${formatKilometers(trend.daily_volume.reduce((sum, row) => sum + (row.distance_km || 0), 0))} sur ${trend.daily_volume.length} jours`
      : "Pas encore de série";
  renderTrendCard(
    $("volume-trend"),
    trend.daily_volume?.map((row) => row.distance_km || 0) || [],
    {
      id: "volume",
      stroke: "#8ae6c0",
      fill: "rgba(138, 230, 192, 0.35)",
      height: 96,
      width: 360,
    },
  );

  const paceSeries = trend.pace_hr_sessions?.map((row) => row.pace_min_per_km || 0) || [];
  const hrSeries = trend.pace_hr_sessions?.map((row) => row.average_hr || 0) || [];
  const paceSummary =
    trend.pace_hr_sessions?.length && trend.pace_hr_sessions[trend.pace_hr_sessions.length - 1]
      ? `${formatPace(trend.pace_hr_sessions[trend.pace_hr_sessions.length - 1].pace_min_per_km)} · ${formatHeartRate(trend.pace_hr_sessions[trend.pace_hr_sessions.length - 1].average_hr)}`
      : "Pas encore de séries";
  $("pace-hr-trend-summary").textContent = paceSummary;
  const paceChart = $("pace-hr-trend");
  if (!paceSeries.length || !hrSeries.length) {
    paceChart.innerHTML = "<p class='status-line'>Aucune série récente pour la courbe allure / FC.</p>";
  } else {
    const paceSvgId = "pace";
    const hrSvgId = "hr";
    const paceWidth = 360;
    const chartHeight = 54;
    const renderSeries = (series, stroke, fill, id) => {
      const values = series.filter((value) => Number.isFinite(Number(value)));
      if (!values.length) {
        return "<p class='status-line'>Pas de données.</p>";
      }
      const min = Math.min(...values);
      const max = Math.max(...values);
      const span = max - min || 1;
      const step = values.length > 1 ? paceWidth / (values.length - 1) : paceWidth;
      const points = values.map((value, index) => {
        const x = values.length > 1 ? index * step : paceWidth / 2;
        const y = chartHeight - ((Number(value) - min) / span) * (chartHeight - 12) - 6;
        return { x, y };
      });
      const line = points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
      return `
        <svg viewBox="0 0 ${paceWidth} ${chartHeight}" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="sparkline-fill-${id}" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stop-color="${fill}" />
              <stop offset="100%" stop-color="rgba(138, 180, 255, 0.02)" />
            </linearGradient>
          </defs>
          <polygon points="0,${chartHeight} ${line} ${paceWidth},${chartHeight}" fill="url(#sparkline-fill-${id})"></polygon>
          <polyline
            points="${line}"
            fill="none"
            stroke="${stroke}"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          ></polyline>
          ${points
            .map(
              (point) => `
                <circle cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.25" fill="${stroke}"></circle>
              `,
            )
            .join("")}
        </svg>
      `;
    };

    paceChart.innerHTML = `
      <div class="stacked-trend">
        <div class="stacked-row">
          <span class="card-label">Allure</span>
          ${renderSeries(paceSeries, "#8ae6c0", "rgba(138, 230, 192, 0.35)", paceSvgId)}
        </div>
        <div class="stacked-row">
          <span class="card-label">FC</span>
          ${renderSeries(hrSeries, "#8ab4ff", "rgba(138, 180, 255, 0.32)", hrSvgId)}
        </div>
      </div>
    `;
  }

  setBusy(false);
}

function renderSummary(payload) {
  const analysis = payload.analysis || {};
  const lines = [];
  if (payload.coach_summary) lines.push(payload.coach_summary);
  if (analysis.training_phase) lines.push(`Phase: ${analysis.training_phase}`);
  if (analysis.benchmark?.event) {
    const pace = analysis.benchmark.pace_min_per_km ? ` à ${formatPace(analysis.benchmark.pace_min_per_km)}` : "";
    lines.push(`Benchmark retenu: ${analysis.benchmark.event}${pace}`);
  }
  summaryBox.textContent = lines.join("\n\n") || "Aucun plan généré pour le moment.";

  planList.innerHTML = "";
  (payload.weekly_plan || []).forEach((session) => {
    const item = document.createElement("article");
    item.className = "plan-item";
    item.innerHTML = `
      <strong>${session.day} - ${session.session_title}</strong>
      <span>${session.duration_minutes} min | ${session.intensity}</span>
      <p>${session.objective || ""}</p>
      <p>${session.notes || ""}</p>
    `;
    planList.appendChild(item);
  });
}

function renderQuestions(questions) {
  questionsBox.innerHTML = "";
  state.currentQuestions = questions || [];
  state.answers = {};
  if (!state.currentQuestions.length) {
    questionsBox.innerHTML = "<p class='status-line'>Aucune question complémentaire. Tu peux générer le plan directement.</p>";
    return;
  }
  state.currentQuestions.forEach((question) => {
    const template = $("question-template");
    const node = template.content.firstElementChild.cloneNode(true);
    const label = node.querySelector(".question-label");
    const input = node.querySelector("input");
    label.textContent = question.question;
    input.placeholder = question.key;
    input.dataset.key = question.key;
    input.addEventListener("input", () => {
      state.answers[question.key] = input.value.trim();
    });
    questionsBox.appendChild(node);
  });
}

async function refreshDashboard() {
  persistSettings();
  return withBusy("Lecture du workspace local...", async () => {
    const payload = await requestJson(
      `/api/status?data_dir=${encodeURIComponent(state.dataDir)}&provider=${encodeURIComponent(state.provider)}&model=${encodeURIComponent(state.model)}&base_url=${encodeURIComponent(state.baseUrl)}`,
    );
    renderDashboard(payload);
  });
}

async function prepareCoach() {
  persistSettings();
  const goalText = $("goal-input").value.trim();
  if (!goalText) {
    addMessage("assistant", "J'ai besoin d'un objectif running pour démarrer.");
    return;
  }
  addMessage("user", goalText);
  const payload = await withBusy("Le coach analyse tes données locales...", async () =>
    requestJson("/api/coach/prepare", {
      method: "POST",
      body: JSON.stringify({
        goal_text: goalText,
        data_dir: state.workspace || state.dataDir,
        provider: state.provider,
        model: state.model || null,
        base_url: state.baseUrl || null,
      }),
    }),
  );
  if (payload.questions?.length) {
    addMessage("assistant", "Je veux préciser quelques points avant de proposer un plan.");
    renderQuestions(payload.questions);
  } else {
    renderQuestions([]);
  }
  renderDashboard(payload.dashboard || {});
  if (payload.analysis?.analysis_summary) {
    addMessage("assistant", payload.analysis.analysis_summary);
  }
}

async function generatePlan() {
  persistSettings();
  const goalText = $("goal-input").value.trim();
  if (!goalText) {
    addMessage("assistant", "Entre d'abord un objectif running.");
    return;
  }
  const payload = await withBusy("Le modèle prépare le plan...", async () =>
    requestJson("/api/coach/plan", {
      method: "POST",
      body: JSON.stringify({
        goal_text: goalText,
        data_dir: state.workspace || state.dataDir,
        provider: state.provider,
        model: state.model || null,
        base_url: state.baseUrl || null,
        answers: state.answers,
      }),
    }),
  );
  if (payload.needs_clarification) {
    renderQuestions(payload.questions);
    addMessage("assistant", "Il me manque encore quelques réponses pour construire le plan.");
    renderDashboard(payload.dashboard || {});
    return;
  }
  addMessage("assistant", payload.coach_summary || "Plan généré.");
  if (payload.signals_used?.length) {
    addMessage("assistant", `Signaux utilisés: ${payload.signals_used.join(", ")}`);
  }
  renderSummary(payload);
  renderDashboard(payload.dashboard || {});
}

async function importGarmin() {
  persistSettings();
  const sourcePath = $("source-path-input").value.trim();
  if (!sourcePath) {
    addMessage("assistant", "Indique le chemin local de l'export Garmin à importer.");
    return;
  }
  const payload = await withBusy("Import Garmin en cours...", async () =>
    requestJson("/api/import", {
      method: "POST",
      body: JSON.stringify({
        source_path: sourcePath,
        data_dir: state.workspace || state.dataDir,
        run_label: "pwa-import",
      }),
    }),
  );
  addMessage(
    "assistant",
    `Import terminé: ${payload.artifacts_imported} artefacts, ${payload.total_records} enregistrements.`,
  );
  await refreshDashboard();
}

function wireEvents() {
  const saveSettingsButton = $("save-settings-button");
  const refreshButton = $("refresh-button");
  const prepareButton = $("prepare-button");
  const planButton = $("plan-button");
  const importButton = $("import-button");

  actionButtons.push(saveSettingsButton, refreshButton, prepareButton, planButton, importButton);

  saveSettingsButton.addEventListener("click", async () => {
    persistSettings();
    addMessage("assistant", "Réglages sauvegardés localement.");
    await refreshDashboard();
  });
  refreshButton.addEventListener("click", refreshDashboard);
  prepareButton.addEventListener("click", prepareCoach);
  planButton.addEventListener("click", generatePlan);
  importButton.addEventListener("click", importGarmin);

  installButton.addEventListener("click", async () => {
    if (!state.installPrompt) return;
    state.installPrompt.prompt();
    await state.installPrompt.userChoice;
    state.installPrompt = null;
    installButton.classList.add("hidden");
  });
}

async function bootstrap() {
  setInputs();
  wireEvents();
  addMessage("assistant", "Commence par décrire ton objectif. Je peux ensuite poser les questions manquantes puis générer un plan.");
  try {
    await refreshDashboard();
  } catch (error) {
    setBusy(false);
    addMessage("assistant", `Dashboard indisponible: ${error.message}`);
    providerChip.textContent = "Provider indisponible";
    providerChip.classList.add("warn");
    importChip.textContent = "Données: indisponible";
    workspaceChip.textContent = "Workspace: indisponible";
  }
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  state.installPrompt = event;
  installButton.classList.remove("hidden");
});

window.addEventListener("load", () => {
  bootstrap().catch((error) => {
    addMessage("assistant", error.message);
    setBusy(false);
    providerChip.textContent = "Erreur au démarrage";
    providerChip.classList.add("warn");
  });
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js?v=20260412").catch(() => {
      // Best effort only.
    });
  });
}
