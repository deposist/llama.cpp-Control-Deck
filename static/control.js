const state = {
  data: window.__INITIAL_STATE__ || {},
  serviceMode: "create",
  serviceOriginalId: "",
  serviceRunning: false,
  pathPicker: {
    targetId: "",
    kind: "file",
    selectedPath: "",
    selectedType: "",
    parent: "",
    lastByKind: {},
  },
};

const serviceFields = {
  id: "svc-id",
  name: "svc-name",
  profile: "svc-profile",
  alias: "svc-alias",
  enabled: "svc-enabled",
  model_path: "svc-model-path",
  mmproj_path: "svc-mmproj-path",
  models_dir: "svc-models-dir",
  models_preset: "svc-models-preset",
  host: "svc-host",
  port: "svc-port",
  api_key: "svc-api-key",
  n_ctx: "svc-n-ctx",
  n_gpu_layers: "svc-gpu-layers",
  main_gpu: "svc-main-gpu",
  n_threads: "svc-threads",
  n_threads_batch: "svc-threads-batch",
  n_batch: "svc-batch",
  n_ubatch: "svc-ubatch",
  flash_attn: "svc-flash-attn",
  split_mode: "svc-split-mode",
  tensor_split: "svc-tensor-split",
  models_max: "svc-models-max",
  extra_args: "svc-extra-args",
  use_mmap: "svc-use-mmap",
  use_mlock: "svc-use-mlock",
  webui: "svc-webui",
  cont_batching: "svc-cont-batching",
  metrics: "svc-metrics",
  slots: "svc-slots",
  models_autoload: "svc-models-autoload",
};

function t(key) {
  return (state.data.i18n && state.data.i18n[key]) || key;
}

function byId(id) {
  return document.getElementById(id);
}

function toast(message) {
  const node = byId("toast");
  node.textContent = message;
  node.classList.add("visible");
  window.setTimeout(() => node.classList.remove("visible"), 2800);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.message || response.statusText);
  }
  return data;
}

function setText() {
  document.documentElement.lang = state.data.config?.ui_language || "ru";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
}

function setChip(node, status) {
  node.classList.remove("good", "bad");
  if (status?.running && status?.healthy) {
    node.textContent = "ready";
    node.classList.add("good");
  } else if (status?.running) {
    node.textContent = "starting";
  } else {
    node.textContent = "stopped";
    node.classList.add("bad");
  }
}

function setFieldValue(id, value) {
  const node = byId(id);
  if (document.activeElement === node) return;
  node.value = value ?? "";
}

function renderProfileOptions(config) {
  const select = byId("active-profile");
  const current = config.active_profile || "chat";
  const names = config.profile_order || Object.keys(config.profiles || {});
  const existing = Array.from(select.options).map((option) => option.value).join("|");
  if (existing !== names.join("|")) {
    select.innerHTML = "";
    names.forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      select.appendChild(option);
    });
  }
  setFieldValue("active-profile", current);
}

function renderServiceProfileOptions(config) {
  const select = byId("svc-profile");
  const names = config.profile_order || Object.keys(config.profiles || {});
  const existing = Array.from(select.options).map((option) => option.value).join("|");
  if (existing === names.join("|")) return;
  select.innerHTML = "";
  names.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
}

function setDownloadChip(download) {
  const node = byId("download-chip");
  node.classList.remove("good", "bad");
  const status = download?.status || "idle";
  node.textContent = status;
  if (status === "succeeded") node.classList.add("good");
  if (status === "failed") node.classList.add("bad");
}

function renderWarnings() {
  const warnings = byId("warnings");
  warnings.innerHTML = "";
  (state.data.validation || []).forEach((item) => {
    const node = document.createElement("div");
    node.className = "warning";
    node.textContent = `${item.message} ${item.next_action || ""}`.trim();
    warnings.appendChild(node);
  });
}

function serviceStatusLabel(item) {
  if (item.running && item.healthy) return "ready";
  if (item.running) return "starting";
  if (item.port_owner) return "port busy";
  return "stopped";
}

function modelBasename(item) {
  const value = item.model_path || item.alias || "";
  return value.split("/").filter(Boolean).pop() || value || "no model";
}

function renderInstances() {
  const body = byId("services");
  body.innerHTML = "";
  (state.data.instances || []).forEach((item) => {
    const card = document.createElement("article");
    card.className = "service-card";
    card.innerHTML = `
      <header>
        <div>
          <h3>${item.name || item.id}</h3>
          <div class="muted">${item.profile || ""} · ${modelBasename(item)}</div>
        </div>
        <span class="chip ${item.running && item.healthy ? "good" : item.running ? "" : "bad"}">${serviceStatusLabel(item)}</span>
      </header>
      <div class="service-meta">
        <div>Port: ${item.port || ""}</div>
        <div>Alias: ${item.alias || ""}</div>
        <label><span>OpenAI URL</span><input id="url-${item.id}" value="${item.openai_url || ""}" readonly /></label>
      </div>
      <div class="actions compact">
        <button data-instance="${item.id}" data-instance-action="start">${t("start")}</button>
        <button data-instance="${item.id}" data-instance-action="stop">${t("stop")}</button>
        <button data-instance="${item.id}" data-instance-action="restart">${t("restart")}</button>
        <button data-service-edit="${item.id}" data-i18n="edit">${t("edit")}</button>
        <button data-service-duplicate="${item.id}" data-i18n="duplicate">${t("duplicate")}</button>
        <button data-service-delete="${item.id}" data-i18n="delete">${t("delete")}</button>
        <button data-copy="url-${item.id}" data-i18n="copy">${t("copy")}</button>
      </div>
    `;
    body.appendChild(card);
  });
}

function render() {
  setText();
  const config = state.data.config || {};
  const profile = config.profile || {};
  const runtime = config.runtime || {};
  const proxy = config.proxy || {};

  setFieldValue("language", config.ui_language || "ru");
  renderProfileOptions(config);
  renderServiceProfileOptions(config);
  byId("friendly-status").textContent = state.data.friendly?.server || "";
  setChip(byId("server-chip"), state.data.server || {});
  setChip(byId("proxy-chip"), state.data.proxy || {});
  setDownloadChip(state.data.download || {});

  setFieldValue("model-path", profile.model_path || "");
  setFieldValue("port", profile.port || 8081);
  setFieldValue("openai-url", state.data.urls?.openai || "");
  setFieldValue("ollama-url", state.data.urls?.ollama || "");
  setFieldValue("proxy-port", proxy.port || 11435);
  setFieldValue("proxy-target", proxy.target_base_url || "");
  setFieldValue("python-path", runtime.python_path || "");
  setFieldValue("binary-path", runtime.llama_server_binary || "");
  setFieldValue("cwd-path", runtime.llama_server_cwd || "");
  setFieldValue("library-path", runtime.llama_server_library_path || "");
  setFieldValue("n-ctx", profile.n_ctx || "");
  setFieldValue("gpu-layers", profile.n_gpu_layers || "");
  setFieldValue("threads", profile.n_threads || "");
  setFieldValue("extra-args", profile.extra_args || "");
  byId("runtime-summary").textContent = `${runtime.llama_server_binary || "llama-server not selected"} · ${runtime.llama_server_cwd || "working dir not selected"}`;
  renderDownload(state.data.download || {});

  renderWarnings();
  renderInstances();
}

function renderServiceValidation(items) {
  const node = byId("service-validation");
  node.innerHTML = "";
  (items || []).forEach((item) => {
    const row = document.createElement("div");
    row.className = "warning";
    row.textContent = `${item.message} ${item.next_action || ""}`.trim();
    node.appendChild(row);
  });
}

function serviceFormData() {
  const data = {};
  Object.entries(serviceFields).forEach(([key, id]) => {
    const node = byId(id);
    if (!node) return;
    data[key] = node.type === "checkbox" ? node.checked : node.value;
  });
  return data;
}

function fillServiceForm(instance, detail = {}) {
  Object.entries(serviceFields).forEach(([key, id]) => {
    const node = byId(id);
    if (!node) return;
    const value = instance[key];
    if (node.type === "checkbox") {
      node.checked = Boolean(value);
    } else {
      node.value = value ?? "";
    }
  });
  const status = detail.status || {};
  state.serviceRunning = Boolean(status.running);
  byId("service-modal-status").textContent = status.running ? "Running: changes may require restart." : "Stopped";
  byId("svc-url-preview").value = `http://${instance.host || "127.0.0.1"}:${instance.port || ""}/v1`;
  renderServiceValidation(detail.validation || []);
  renderCommandPreview(detail.command || [], detail.command_error || "");
}

function renderCommandPreview(command, error) {
  byId("svc-command-preview").textContent = error || (command || []).join(" ");
}

function renderPathWarning(message) {
  const node = byId("path-validation");
  node.innerHTML = "";
  if (!message) return;
  const row = document.createElement("div");
  row.className = "warning";
  row.textContent = message;
  node.appendChild(row);
}

async function loadPathRoots() {
  const result = await api("/api/paths/roots");
  const select = byId("path-roots");
  select.innerHTML = "";
  (result.details || []).forEach((root) => {
    const option = document.createElement("option");
    option.value = root.path;
    option.textContent = `${root.label}: ${root.path}`;
    select.appendChild(option);
  });
  return result.details || [];
}

function renderPathEntries(entries) {
  const list = byId("path-entries");
  list.innerHTML = "";
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "path-empty";
    empty.textContent = "No matching files or folders.";
    list.appendChild(empty);
    return;
  }
  entries.forEach((entry) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "path-entry";
    row.dataset.path = entry.path;
    row.dataset.type = entry.type;
    row.dataset.selectable = entry.selectable ? "true" : "false";
    const name = document.createElement("span");
    name.className = "path-entry-name";
    name.textContent = `${entry.type === "directory" ? "Folder" : "File"} · ${entry.name}`;
    const meta = document.createElement("span");
    meta.className = "muted";
    const parts = [];
    if (entry.size) parts.push(`${entry.size} bytes`);
    if (entry.executable) parts.push("executable");
    if (entry.has_llama_libs) parts.push("llama libs");
    if (!entry.selectable && entry.type === "file") parts.push("not selectable");
    meta.textContent = parts.join(" · ");
    row.append(name, meta);
    list.appendChild(row);
  });
}

async function loadPathList(path, kind) {
  const result = await api(`/api/paths/list?path=${encodeURIComponent(path)}&kind=${encodeURIComponent(kind)}`);
  const details = result.details || {};
  state.pathPicker.parent = details.parent || "";
  state.pathPicker.selectedPath = "";
  state.pathPicker.selectedType = "";
  byId("path-current").value = details.path || path;
  const roots = byId("path-roots");
  if (Array.from(roots.options).some((option) => option.value === details.path)) {
    roots.value = details.path;
  }
  renderPathWarning("");
  renderPathEntries(details.entries || []);
}

async function openPathPicker(targetId, kind) {
  state.pathPicker.targetId = targetId;
  state.pathPicker.kind = kind || "file";
  byId("path-modal-kind").textContent = state.pathPicker.kind;
  byId("path-modal").classList.remove("hidden");
  const roots = await loadPathRoots();
  const currentValue = byId(targetId)?.value || "";
  const startPath = currentValue || state.pathPicker.lastByKind[state.pathPicker.kind] || roots[0]?.path || "/";
  await loadPathList(startPath, state.pathPicker.kind);
}

function closePathPicker() {
  byId("path-modal").classList.add("hidden");
  renderPathWarning("");
}

async function selectPath(path) {
  const result = await api("/api/paths/validate", {
    method: "POST",
    body: JSON.stringify({ path, kind: state.pathPicker.kind }),
  });
  if (!result.ok) {
    renderPathWarning(result.message || "Path is not valid.");
    return;
  }
  const target = byId(state.pathPicker.targetId);
  if (target) {
    target.value = result.details?.path || path;
    target.dispatchEvent(new Event("input", { bubbles: true }));
  }
  state.pathPicker.lastByKind[state.pathPicker.kind] = byId("path-current").value;
  closePathPicker();
  toast(result.message || "Path selected.");
}

function openServiceModal(mode) {
  state.serviceMode = mode;
  byId("service-modal-title").textContent = mode === "create" ? t("add_service") : t("edit");
  document
    .querySelector('[data-action="service-save-start"]')
    .classList.toggle("hidden", mode !== "create");
  byId("service-modal").classList.remove("hidden");
}

function closeServiceModal() {
  byId("service-modal").classList.add("hidden");
  renderServiceValidation([]);
}

function renderDownload(download) {
  const progress = byId("download-progress");
  const status = download.status || "idle";
  progress.className = `progress-bar ${status}`;
  progress.style.width = status === "idle" ? "0%" : "";
  byId("download-message").textContent = download.message || "No download running.";
  byId("download-lines").textContent = (download.lines || []).join("\n");
}

function configPatch() {
  return {
    ui_language: byId("language").value,
    active_profile: byId("active-profile").value,
    runtime: {
      python_path: byId("python-path").value,
      llama_server_binary: byId("binary-path").value,
      llama_server_cwd: byId("cwd-path").value,
      llama_server_library_path: byId("library-path").value,
    },
    profile: {
      model_path: byId("model-path").value,
      port: byId("port").value,
      n_ctx: byId("n-ctx").value,
      n_gpu_layers: byId("gpu-layers").value,
      n_threads: byId("threads").value,
      extra_args: byId("extra-args").value,
    },
    proxy: {
      port: byId("proxy-port").value,
      target_base_url: byId("proxy-target").value,
    },
  };
}

async function refresh() {
  state.data = await api("/api/state");
  render();
}

async function saveConfig(showToast = true) {
  const result = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(configPatch()),
  });
  state.data = result.details;
  render();
  if (showToast) toast(result.message);
}

async function action(name) {
  const endpoints = {
    autodetect: ["/api/runtime/autodetect", "POST"],
    "server-start": ["/api/server/start", "POST"],
    "server-stop": ["/api/server/stop", "POST"],
    "server-restart": ["/api/server/restart", "POST"],
    "proxy-start": ["/api/proxy/start", "POST"],
    "proxy-stop": ["/api/proxy/stop", "POST"],
    devices: ["/api/devices", "GET"],
    "release-status": ["/api/release/status", "GET"],
    "release-download": ["/api/release/download", "POST"],
    "download-status": ["/api/release/download/status", "GET"],
  };
  if (name === "save") return saveConfig();
  if (name === "refresh") return refresh();
  if (name === "service-add") return serviceAdd();
  if (name === "service-close") return closeServiceModal();
  if (name === "service-save") return serviceSave(false);
  if (name === "service-save-start") return serviceSave(true);
  if (name === "service-validate") return serviceValidate();
  if (name === "path-close") return closePathPicker();
  if (name.startsWith("logs-")) return loadLogs(name.replace("logs-", ""));

  if (name.startsWith("server-") || name.startsWith("proxy-")) {
    await saveConfig(false);
  }

  const [path, method] = endpoints[name];
  const result = await api(path, { method });
  byId("output").textContent = JSON.stringify(result.details || result, null, 2);
  if (name === "release-download" || name === "download-status") {
    renderDownload(result.details || {});
  }
  toast(result.message || "OK");
  await refresh();
}

async function loadLogs(kind) {
  const result = await api(`/api/logs?kind=${encodeURIComponent(kind)}&lines=240`);
  byId("output").textContent = result.text || "No logs";
}

async function instanceAction(id, verb) {
  const result = await api(`/api/instances/${encodeURIComponent(id)}/${verb}`, { method: "POST" });
  toast(result.message);
  await refresh();
}

async function serviceAdd() {
  const result = await api(`/api/instances/defaults?profile=${encodeURIComponent(byId("active-profile").value || "chat")}`);
  state.serviceOriginalId = "";
  openServiceModal("create");
  fillServiceForm(result.details.instance, result.details);
}

async function serviceEdit(id) {
  const result = await api(`/api/instances/${encodeURIComponent(id)}`);
  state.serviceOriginalId = id;
  openServiceModal("edit");
  fillServiceForm(result.details.instance, result.details);
}

async function serviceDuplicate(id) {
  const result = await api(`/api/instances/${encodeURIComponent(id)}/duplicate`, { method: "POST" });
  toast(result.message);
  await refresh();
}

async function serviceDelete(id) {
  const service = (state.data.instances || []).find((item) => item.id === id);
  const stop = service?.running ? "&stop=true" : "";
  const message = service?.running ? "Stop and delete this running service?" : "Delete this service?";
  if (!window.confirm(message)) return;
  const result = await api(`/api/instances/${encodeURIComponent(id)}?${stop.replace("&", "")}`, { method: "DELETE" });
  toast(result.message);
  await refresh();
}

async function serviceValidate() {
  const result = await api("/api/instances/validate", {
    method: "POST",
    body: JSON.stringify({
      instance: { ...serviceFormData(), _original_id: state.serviceOriginalId },
    }),
  });
  renderServiceValidation(result.details.validation || []);
  renderCommandPreview(result.details.command || [], result.details.command_error || "");
  toast(result.message);
  return result;
}

async function serviceSave(start) {
  const instance = serviceFormData();
  const method = state.serviceMode === "create" ? "POST" : "PATCH";
  const path =
    state.serviceMode === "create"
      ? "/api/instances"
      : `/api/instances/${encodeURIComponent(state.serviceOriginalId)}`;
  const result = await api(path, {
    method,
    body: JSON.stringify({ instance, start }),
  });
  if (!result.ok) {
    renderServiceValidation(result.details?.validation || []);
    toast(result.message);
    return;
  }
  toast(result.message);
  closeServiceModal();
  await refresh();
}

document.addEventListener("click", async (event) => {
  const actionName = event.target.dataset.action;
  const copyId = event.target.dataset.copy;
  const instanceId = event.target.dataset.instance;
  const instanceVerb = event.target.dataset.instanceAction;
  const serviceEditId = event.target.dataset.serviceEdit;
  const serviceDuplicateId = event.target.dataset.serviceDuplicate;
  const serviceDeleteId = event.target.dataset.serviceDelete;
  const browseTarget = event.target.dataset.browseTarget;
  const browseKind = event.target.dataset.browseKind;
  const tab = event.target.dataset.tab;

  try {
    if (browseTarget) await openPathPicker(browseTarget, browseKind);
    if (actionName) await action(actionName);
    if (copyId) {
      await navigator.clipboard.writeText(byId(copyId).value);
      toast("Copied");
    }
    if (instanceId && instanceVerb) await instanceAction(instanceId, instanceVerb);
    if (serviceEditId) await serviceEdit(serviceEditId);
    if (serviceDuplicateId) await serviceDuplicate(serviceDuplicateId);
    if (serviceDeleteId) await serviceDelete(serviceDeleteId);
    if (tab) switchServiceTab(tab);
  } catch (error) {
    toast(error.message);
  }
});

byId("path-roots").addEventListener("change", async () => {
  try {
    await loadPathList(byId("path-roots").value, state.pathPicker.kind);
  } catch (error) {
    renderPathWarning(error.message);
  }
});

byId("path-open").addEventListener("click", async () => {
  try {
    await loadPathList(byId("path-current").value, state.pathPicker.kind);
  } catch (error) {
    renderPathWarning(error.message);
  }
});

byId("path-up").addEventListener("click", async () => {
  if (!state.pathPicker.parent) return;
  try {
    await loadPathList(state.pathPicker.parent, state.pathPicker.kind);
  } catch (error) {
    renderPathWarning(error.message);
  }
});

byId("path-select-current").addEventListener("click", async () => {
  try {
    await selectPath(byId("path-current").value);
  } catch (error) {
    renderPathWarning(error.message);
  }
});

byId("path-select").addEventListener("click", async () => {
  try {
    await selectPath(state.pathPicker.selectedPath || byId("path-current").value);
  } catch (error) {
    renderPathWarning(error.message);
  }
});

byId("path-entries").addEventListener("click", (event) => {
  const row = event.target.closest(".path-entry");
  if (!row) return;
  byId("path-entries").querySelectorAll(".path-entry").forEach((node) => node.classList.remove("selected"));
  row.classList.add("selected");
  state.pathPicker.selectedPath = row.dataset.path || "";
  state.pathPicker.selectedType = row.dataset.type || "";
  if (state.pathPicker.selectedType === "file") {
    byId("path-current").value = state.pathPicker.selectedPath;
  }
});

byId("path-entries").addEventListener("dblclick", async (event) => {
  const row = event.target.closest(".path-entry");
  if (!row) return;
  try {
    if (row.dataset.type === "directory") {
      await loadPathList(row.dataset.path, state.pathPicker.kind);
    } else if (row.dataset.selectable === "true") {
      await selectPath(row.dataset.path);
    } else {
      renderPathWarning("This file does not match the selected path type.");
    }
  } catch (error) {
    renderPathWarning(error.message);
  }
});

function switchServiceTab(tab) {
  document.querySelectorAll(".tab").forEach((node) => node.classList.toggle("active", node.dataset.tab === tab));
  document
    .querySelectorAll(".tab-panel")
    .forEach((node) => node.classList.toggle("hidden", node.dataset.panel !== tab));
}

byId("svc-profile").addEventListener("change", async () => {
  if (state.serviceMode !== "create") return;
  try {
    const result = await api(`/api/instances/defaults?profile=${encodeURIComponent(byId("svc-profile").value)}`);
    fillServiceForm(result.details.instance, result.details);
  } catch (error) {
    toast(error.message);
  }
});

byId("service-form").addEventListener("input", () => {
  const data = serviceFormData();
  byId("svc-url-preview").value = `http://${data.host || "127.0.0.1"}:${data.port || ""}/v1`;
});

byId("language").addEventListener("change", async () => {
  try {
    await saveConfig(false);
    toast("OK");
  } catch (error) {
    toast(error.message);
  }
});

byId("active-profile").addEventListener("change", async () => {
  try {
    await api("/api/config", {
      method: "POST",
      body: JSON.stringify({ active_profile: byId("active-profile").value }),
    });
    await refresh();
    toast("OK");
  } catch (error) {
    toast(error.message);
  }
});

render();
window.setInterval(refresh, 2500);
