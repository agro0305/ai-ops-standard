const state = { reports: [], filtered: [], alerts: [], audit: [], selected: null };

const elements = {
  kpis: document.querySelector("#kpi-grid"),
  reportRoot: document.querySelector("#report-root"),
  reportList: document.querySelector("#report-list"),
  alertList: document.querySelector("#alert-list"),
  auditList: document.querySelector("#audit-list"),
  category: document.querySelector("#category-filter"),
  search: document.querySelector("#search-input"),
  refresh: document.querySelector("#refresh-button"),
  connection: document.querySelector("#connection-state"),
  detailEmpty: document.querySelector("#detail-empty"),
  detailContent: document.querySelector("#detail-content"),
  detailCategory: document.querySelector("#detail-category"),
  detailName: document.querySelector("#detail-name"),
  detailSummary: document.querySelector("#detail-summary"),
  detailJson: document.querySelector("#detail-json"),
  copy: document.querySelector("#copy-button"),
};

function text(value) { return String(value ?? ""); }
function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1024 ** 2).toFixed(1)} MiB`;
}
function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? text(value) : date.toLocaleString();
}
function formatAge(seconds) {
  const value = Number(seconds || 0);
  if (value < 60) return `${value}s`;
  if (value < 3600) return `${Math.floor(value / 60)}min`;
  return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}min`;
}

function statusFor(report) {
  const summary = report.summary || {};
  if (report.error) return ["Greška", "bad"];
  if (report.stale) return ["STALE", "warn"];
  if (report.category === "refresh") {
    return summary.success === false ? ["FAIL", "bad"] : ["FRESH", "good"];
  }
  if (report.category === "compliance") {
    return Number(summary.failed || 0) === 0 ? ["PASS", "good"] : ["FAIL", "bad"];
  }
  if (["execution", "rollback"].includes(report.category)) {
    return summary.success === false ? ["FAIL", "bad"] : ["OK", "good"];
  }
  if (report.category === "verification") {
    return summary.passed === false ? ["FAIL", "bad"] : ["PASS", "good"];
  }
  if (report.category === "plan") {
    const risk = summary.risk || "unknown";
    return [risk.toUpperCase(), ["high", "critical"].includes(risk) ? "warn" : "neutral"];
  }
  if (report.category === "backup") {
    return summary.complete === false ? ["NEPOTPUN", "bad"] : ["COMPLETE", "good"];
  }
  return [report.category.toUpperCase(), "neutral"];
}

function kpi(label, value) {
  const card = document.createElement("article");
  card.className = "kpi";
  const number = document.createElement("span");
  number.className = "kpi-value";
  number.textContent = text(value);
  const title = document.createElement("span");
  title.className = "kpi-label";
  title.textContent = label;
  card.append(number, title);
  return card;
}

function renderSummary(summary) {
  elements.kpis.replaceChildren(
    kpi("Izveštaji", summary.report_count),
    kpi("Stale", summary.stale_reports || 0),
    kpi("Upozorenja", summary.alerts?.total || 0),
    kpi("Compliance PASS", summary.compliance?.passed || 0),
    kpi("Compliance FAIL", summary.compliance?.failed || 0),
  );
  elements.reportRoot.textContent = summary.root || "";
}

function renderAlerts(alerts) {
  elements.alertList.replaceChildren();
  if (!alerts.length) {
    const empty = document.createElement("div");
    empty.className = "alert-empty";
    empty.textContent = "Nema aktivnih upozorenja.";
    elements.alertList.append(empty);
    return;
  }
  for (const alert of alerts) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `alert-row ${alert.severity}`;
    row.addEventListener("click", () => openReport(alert.report));
    const badge = document.createElement("span");
    badge.className = `badge ${alert.severity === "critical" ? "bad" : "warn"}`;
    badge.textContent = alert.severity.toUpperCase();
    const content = document.createElement("div");
    const message = document.createElement("strong");
    message.textContent = alert.message;
    const report = document.createElement("span");
    report.textContent = alert.report;
    content.append(message, report);
    row.append(badge, content);
    elements.alertList.append(row);
  }
}

function renderAudit(events) {
  elements.auditList.replaceChildren();
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "audit-empty";
    empty.textContent = "Nema audit događaja.";
    elements.auditList.append(empty);
    return;
  }
  for (const event of events.slice(0, 10)) {
    const row = document.createElement("div");
    row.className = "audit-row";
    const status = document.createElement("span");
    status.className = `badge ${event.success === false ? "bad" : "good"}`;
    status.textContent = event.success === false ? "FAIL" : "OK";
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = event.event_type || "audit-event";
    const meta = document.createElement("span");
    const duration = event.duration_seconds == null ? "" : ` · ${event.duration_seconds}s`;
    meta.textContent = `${formatDate(event.occurred_at)}${duration}`;
    content.append(title, meta);
    row.append(status, content);
    elements.auditList.append(row);
  }
}

function populateCategories() {
  const current = elements.category.value;
  const categories = [...new Set(state.reports.map((item) => item.category))].sort();
  elements.category.replaceChildren(new Option("Svi", "all"));
  for (const category of categories) elements.category.append(new Option(category, category));
  if ([...elements.category.options].some((option) => option.value === current)) {
    elements.category.value = current;
  }
}

function searchableText(report) {
  return JSON.stringify({ name: report.name, category: report.category, summary: report.summary, stale: report.stale }).toLowerCase();
}

function applyFilters() {
  const category = elements.category.value;
  const query = elements.search.value.trim().toLowerCase();
  state.filtered = state.reports.filter((report) => {
    const categoryMatch = category === "all" || report.category === category;
    return categoryMatch && (!query || searchableText(report).includes(query));
  });
  renderReportList();
}

function renderReportList() {
  elements.reportList.replaceChildren();
  if (!state.filtered.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Nema izveštaja za izabrani filter.";
    elements.reportList.append(empty);
    return;
  }
  for (const report of state.filtered) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "report-row";
    if (state.selected === report.name) button.classList.add("active");
    button.addEventListener("click", () => openReport(report.name));
    const left = document.createElement("div");
    const name = document.createElement("div");
    name.className = "report-name";
    name.textContent = report.name;
    const meta = document.createElement("div");
    meta.className = "report-meta";
    meta.textContent = `${formatBytes(report.size)} · ${formatDate(report.modified_at)} · starost ${formatAge(report.age_seconds)}`;
    left.append(name, meta);
    const right = document.createElement("div");
    right.className = "report-status";
    const [label, style] = statusFor(report);
    const badge = document.createElement("span");
    badge.className = `badge ${style}`;
    badge.textContent = label;
    right.append(badge);
    button.append(left, right);
    elements.reportList.append(button);
  }
}

function renderDetail(report) {
  elements.detailEmpty.hidden = true;
  elements.detailContent.hidden = false;
  elements.detailCategory.textContent = report.category;
  elements.detailName.textContent = report.name;
  elements.detailSummary.replaceChildren();
  const values = { ...(report.summary || {}), stale: report.stale, age: formatAge(report.age_seconds), size: formatBytes(report.size), modified_at: formatDate(report.modified_at) };
  for (const [key, value] of Object.entries(values)) {
    const item = document.createElement("div");
    item.className = "summary-item";
    const label = document.createElement("span");
    label.className = "summary-key";
    label.textContent = key.replaceAll("_", " ");
    const content = document.createElement("span");
    content.className = "summary-value";
    content.textContent = typeof value === "boolean" ? (value ? "da" : "ne") : text(value ?? "—");
    item.append(label, content);
    elements.detailSummary.append(item);
  }
  elements.detailJson.textContent = JSON.stringify(report.data ?? { error: report.error }, null, 2);
}

async function openReport(name) {
  state.selected = name;
  renderReportList();
  elements.detailEmpty.hidden = false;
  elements.detailContent.hidden = true;
  elements.detailEmpty.replaceChildren();
  const loadingTitle = document.createElement("h2");
  loadingTitle.textContent = "Učitavanje";
  const loadingText = document.createElement("p");
  loadingText.textContent = "Čitanje izveštaja…";
  elements.detailEmpty.append(loadingTitle, loadingText);
  try {
    const response = await fetch(`/api/reports/${encodeURIComponent(name)}`, { headers: { Accept: "application/json" }, cache: "no-store" });
    const payload = await response.json();
    if (!response.ok && !payload.data) throw new Error(payload.error || `HTTP ${response.status}`);
    renderDetail(payload);
  } catch (error) {
    elements.detailEmpty.hidden = false;
    elements.detailEmpty.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = "Greška";
    const message = document.createElement("p");
    message.textContent = error.message;
    elements.detailEmpty.append(title, message);
  }
}

async function refresh() {
  elements.connection.textContent = "Učitavanje";
  elements.connection.className = "status-pill neutral";
  elements.reportList.replaceChildren();
  const loading = document.createElement("div");
  loading.className = "loading";
  loading.textContent = "Učitavanje izveštaja…";
  elements.reportList.append(loading);
  try {
    const [summaryResponse, reportsResponse, alertsResponse, auditResponse] = await Promise.all([
      fetch("/api/summary", { cache: "no-store" }),
      fetch("/api/reports", { cache: "no-store" }),
      fetch("/api/alerts", { cache: "no-store" }),
      fetch("/api/audit?limit=20", { cache: "no-store" }),
    ]);
    if (![summaryResponse, reportsResponse, alertsResponse, auditResponse].every((response) => response.ok)) {
      throw new Error(`HTTP ${summaryResponse.status}/${reportsResponse.status}/${alertsResponse.status}/${auditResponse.status}`);
    }
    const [summary, reports, alerts, audit] = await Promise.all([
      summaryResponse.json(), reportsResponse.json(), alertsResponse.json(), auditResponse.json(),
    ]);
    state.reports = reports;
    state.alerts = alerts;
    state.audit = audit.events || [];
    renderSummary(summary);
    renderAlerts(alerts);
    renderAudit(state.audit);
    populateCategories();
    applyFilters();
    const critical = alerts.filter((item) => item.severity === "critical").length;
    if (critical) {
      elements.connection.textContent = `${critical} kritično`;
      elements.connection.className = "status-pill bad";
    } else if (alerts.length) {
      elements.connection.textContent = `${alerts.length} upozorenja`;
      elements.connection.className = "status-pill warn";
    } else {
      elements.connection.textContent = "Povezano";
      elements.connection.className = "status-pill good";
    }
  } catch (error) {
    elements.connection.textContent = "Greška";
    elements.connection.className = "status-pill bad";
    elements.reportList.replaceChildren();
    const message = document.createElement("div");
    message.className = "error-state";
    message.textContent = `Dashboard API nije dostupan: ${error.message}`;
    elements.reportList.append(message);
  }
}

elements.category.addEventListener("change", applyFilters);
elements.search.addEventListener("input", applyFilters);
elements.refresh.addEventListener("click", refresh);
elements.copy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(elements.detailJson.textContent);
    elements.copy.textContent = "Kopirano";
    setTimeout(() => { elements.copy.textContent = "Kopiraj JSON"; }, 1200);
  } catch {
    elements.copy.textContent = "Kopiranje nije uspelo";
  }
});

refresh();
setInterval(refresh, 60_000);
