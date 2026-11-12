"use strict";

const $ = (id) => document.getElementById(id);
const state = { user: null, csrf: "", tasks: [], filter: "all", selected: null, loading: false };
const iconPaths = {
  edit: ["M15 4l5 5M4 20l4-1 12-12a2.1 2.1 0 0 0-3-3L5 16l-1 4Z"],
  delete: ["M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5m4-5v5"]
};

async function api(path, options = {}) {
  const headers = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.method && options.method !== "GET" && state.csrf) headers["X-CSRF-Token"] = state.csrf;
  const response = await fetch(path, { credentials: "same-origin", ...options, headers: { ...headers, ...options.headers }, body: options.body === undefined ? undefined : JSON.stringify(options.body) });
  let data = null;
  if (response.status !== 204) data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = typeof data?.error === "string" ? data.error : data?.message || data?.error?.message || "Không thể thực hiện thao tác. Vui lòng thử lại.";
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

function showError(id, error) {
  const target = $(id);
  target.textContent = error instanceof TypeError ? "Không thể kết nối. Kiểm tra mạng rồi thử lại." : error.message || String(error);
  target.hidden = false;
}

function clearError(id) { $(id).hidden = true; $(id).textContent = ""; }
function announce(message) { $("announcement").textContent = message; }

async function updateBackendVersion() {
  if (!$("login-view").hidden && !document.hidden) {
    try {
      const response = await fetch(`/version?t=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Version unavailable");
      const data = await response.json();
      const version = /^v[0-9]+$/.test(data.version) ? data.version : null;
      $("backend-version").textContent = version ? `Backend · ${version}` : "Backend · Không xác định";
    } catch {
      $("backend-version").textContent = "Backend · Không kết nối";
    }
  }
  setTimeout(updateBackendVersion, 5000);
}

function showLogin() {
  state.user = null;
  state.csrf = "";
  state.tasks = [];
  state.selected = null;
  for (const dialog of document.querySelectorAll("dialog[open]")) dialog.close();
  $("app-view").hidden = true;
  $("login-view").hidden = false;
  $("password").value = "";
  $("create-form").reset();
  $("edit-form").reset();
  $("delete-description").textContent = "";
  render();
  document.title = "Nhịp · Đăng nhập";
}

function handleError(id, error) {
  if (error.status === 401) {
    showLogin();
    showError("login-error", new Error("Phiên đăng nhập đã kết thúc. Vui lòng đăng nhập lại."));
    $("email").focus();
  } else showError(id, error);
}

function localDateKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function overdue(task) { return !task.done && !!task.due_date && task.due_date < localDateKey(); }

function formatDue(value) {
  if (!value) return "Không có hạn";
  if (value === localDateKey()) return "Hôm nay";
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", ...(year !== new Date().getFullYear() ? { year: "numeric" } : {}) }).format(new Date(year, month - 1, day));
}

function makeIcon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  for (const d of iconPaths[name]) {
    const path = document.createElementNS(svg.namespaceURI, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

function makeTaskRow(task) {
  const row = document.createElement("li");
  row.className = `task-row${task.done ? " done" : ""}`;
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.id = `task-check-${task.id}`;
  checkbox.className = "task-checkbox";
  checkbox.checked = task.done;
  checkbox.setAttribute("aria-label", `${task.done ? "Đánh dấu chưa hoàn thành" : "Hoàn thành"}: ${task.title}`);
  checkbox.addEventListener("change", async () => {
    clearError("app-error");
    row.classList.add("busy");
    checkbox.disabled = true;
    try {
      const data = await api(`/api/tasks/${task.id}`, { method: "PATCH", body: { done: checkbox.checked } });
      state.tasks = state.tasks.map((item) => item.id === task.id ? data.task : item);
      render();
      ($(`task-check-${task.id}`) || $("focus-create")).focus();
      announce(data.task.done ? "Đã hoàn thành công việc." : "Đã đánh dấu công việc chưa hoàn thành.");
    } catch (error) {
      checkbox.checked = task.done;
      handleError("app-error", error);
    } finally {
      checkbox.disabled = false;
      row.classList.remove("busy");
    }
  });

  const copy = document.createElement("div");
  copy.className = "task-copy";
  const title = document.createElement("div");
  title.className = "task-title";
  title.textContent = task.title;
  const meta = document.createElement("div");
  meta.className = "task-meta";
  meta.textContent = task.done ? "Đã hoàn thành" : overdue(task) ? "Đang chờ bạn hoàn thành" : "Công việc cá nhân";
  copy.append(title, meta);
  const date = document.createElement("span");
  date.className = `task-due${overdue(task) ? " overdue" : ""}`;
  date.textContent = formatDue(task.due_date);
  if (task.due_date) date.title = `${overdue(task) ? "Quá hạn: " : "Hạn hoàn thành: "}${task.due_date}`;

  const actions = document.createElement("div");
  actions.className = "task-actions";
  for (const [name, label] of [["edit", "Sửa"], ["delete", "Xóa"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-button";
    button.setAttribute("aria-label", `${label} công việc: ${task.title}`);
    button.title = `${label} công việc`;
    button.append(makeIcon(name));
    button.addEventListener("click", () => {
      state.selected = task;
      clearError(`${name}-error`);
      if (name === "edit") {
        $("edit-title").value = task.title;
        $("edit-date").value = task.due_date || "";
        $("edit-dialog").showModal();
        $("edit-title").focus();
      } else {
        $("delete-description").textContent = `“${task.title}”`;
        $("delete-dialog").showModal();
      }
    });
    actions.append(button);
  }
  row.append(checkbox, copy, date, actions);
  return row;
}

function render() {
  const total = state.tasks.length;
  const done = state.tasks.filter((task) => task.done).length;
  const late = state.tasks.filter(overdue).length;
  const percent = total ? Math.round(done / total * 100) : 0;
  $("count-all").textContent = total;
  $("count-open").textContent = total - done;
  $("count-done").textContent = done;
  $("count-overdue").textContent = late;
  $("nav-count").textContent = total - done;
  $("progress-title").textContent = total ? `${done} trên ${total} công việc đã hoàn thành` : "Chưa có công việc";
  $("progress-description").textContent = !total ? "Thêm công việc đầu tiên để bắt đầu." : done === total ? "Danh sách đã hoàn tất. Bạn đã làm rất tốt." : `${total - done} công việc đang chờ bạn.${late ? ` ${late} việc đã quá hạn.` : ""}`;
  $("progress-label").textContent = `${percent}%`;
  $("progress-fill").style.width = `${percent}%`;
  $("progress-bar").setAttribute("aria-valuenow", percent);
  const visible = state.tasks.filter((task) => state.filter === "open" ? !task.done : state.filter === "done" ? task.done : state.filter === "overdue" ? overdue(task) : true);
  $("task-list").replaceChildren(...visible.map(makeTaskRow));
  $("list-total").textContent = `${visible.length} công việc${state.filter !== "all" ? ` / ${total}` : ""}`;
  $("empty-state").hidden = state.loading || visible.length > 0;
  $("empty-title").textContent = !total ? "Một khởi đầu mới" : state.filter === "done" ? "Chưa có công việc hoàn thành" : state.filter === "overdue" ? "Không có công việc quá hạn" : "Danh sách đã hoàn tất";
  $("empty-description").textContent = !total ? "Thêm công việc đầu tiên vào danh sách của bạn." : state.filter === "done" ? "Đánh dấu công việc khi bạn đã làm xong." : state.filter === "overdue" ? "Bạn đang theo kịp những việc cần làm." : "Chọn bộ lọc khác để xem công việc của bạn.";
  for (const button of document.querySelectorAll("[data-filter]")) {
    const active = button.dataset.filter === state.filter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active);
  }
}

async function loadTasks() {
  state.loading = true;
  $("list-loading").hidden = false;
  $("task-list").hidden = true;
  $("empty-state").hidden = true;
  $("refresh").disabled = true;
  clearError("app-error");
  try {
    const data = await api("/api/tasks");
    state.tasks = data.tasks;
  } catch (error) { handleError("app-error", error); }
  finally {
    state.loading = false;
    $("list-loading").hidden = true;
    $("task-list").hidden = false;
    $("refresh").disabled = false;
    render();
  }
}

async function enterWorkspace(data) {
  state.user = data.user;
  state.csrf = data.csrf_token;
  state.filter = "all";
  $("account-email").textContent = data.user.email;
  $("avatar").textContent = data.user.email.slice(0, 1).toUpperCase();
  $("login-view").hidden = true;
  $("app-view").hidden = false;
  $("password").value = "";
  document.title = "Nhịp · Công việc của tôi";
  $("today").textContent = new Intl.DateTimeFormat("vi-VN", { weekday: "long", day: "2-digit", month: "long", year: "numeric" }).format(new Date());
  await loadTasks();
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError("login-error");
  $("login-submit").disabled = true;
  try {
    const identifier = $("email").value.trim();
    // shortcut: tên đăng nhập dùng email demo, thêm cột username khi cần tài khoản thực.
    const email = identifier.includes("@") ? identifier : `${identifier}@example.test`;
    const data = await api("/api/login", { method: "POST", body: { email, password: $("password").value } });
    await enterWorkspace(data);
  } catch (error) {
    showError("login-error", error.status === 401 ? new Error("Tên đăng nhập hoặc mật khẩu chưa đúng.") : error);
  } finally { $("login-submit").disabled = false; }
});

$("logout").addEventListener("click", async () => {
  $("logout").disabled = true;
  try {
    await api("/api/logout", { method: "POST" });
    clearError("login-error");
    showLogin();
    $("email").focus();
  } catch (error) { handleError("app-error", error); }
  finally { $("logout").disabled = false; }
});

for (const button of document.querySelectorAll("[data-filter]")) button.addEventListener("click", () => { state.filter = button.dataset.filter; render(); });
$("focus-create").addEventListener("click", () => $("new-title").focus());
$("refresh").addEventListener("click", loadTasks);

$("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = $("new-title").value.trim();
  if (!title) { $("new-title").setCustomValidity("Hãy nhập tên công việc."); $("new-title").reportValidity(); return; }
  clearError("app-error");
  $("create-submit").disabled = true;
  try {
    const data = await api("/api/tasks", { method: "POST", body: { title, due_date: $("new-date").value || null } });
    state.tasks.unshift(data.task);
    state.filter = "all";
    $("create-form").reset();
    render();
    $("new-title").focus();
    announce("Đã thêm công việc.");
  } catch (error) { handleError("app-error", error); }
  finally { $("create-submit").disabled = false; }
});
$("new-title").addEventListener("input", () => $("new-title").setCustomValidity(""));
$("edit-title").addEventListener("input", () => $("edit-title").setCustomValidity(""));

$("edit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = $("edit-title").value.trim();
  if (!title) { $("edit-title").setCustomValidity("Hãy nhập tên công việc."); $("edit-title").reportValidity(); return; }
  clearError("edit-error");
  $("edit-submit").disabled = true;
  try {
    const data = await api(`/api/tasks/${state.selected.id}`, { method: "PATCH", body: { title, due_date: $("edit-date").value || null } });
    state.tasks = state.tasks.map((task) => task.id === data.task.id ? data.task : task);
    $("edit-dialog").close();
    render();
    ($(`task-check-${data.task.id}`) || $("focus-create")).focus();
    announce("Đã lưu thay đổi.");
  } catch (error) { handleError("edit-error", error); }
  finally { $("edit-submit").disabled = false; }
});

$("delete-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError("delete-error");
  $("delete-submit").disabled = true;
  try {
    const id = state.selected.id;
    await api(`/api/tasks/${id}`, { method: "DELETE" });
    state.tasks = state.tasks.filter((task) => task.id !== id);
    $("delete-dialog").close();
    render();
    $("focus-create").focus();
    announce("Đã xóa công việc.");
  } catch (error) { handleError("delete-error", error); }
  finally { $("delete-submit").disabled = false; }
});

for (const button of document.querySelectorAll("[data-close]")) button.addEventListener("click", () => $(button.dataset.close).close());

(async function boot() {
  try { await enterWorkspace(await api("/api/me")); }
  catch (error) {
    showLogin();
    if (error.status !== 401) showError("login-error", error);
  } finally { $("boot").hidden = true; updateBackendVersion(); }
})();
