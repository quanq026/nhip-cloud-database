import http.client
import json
import os
import secrets
import socket
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, g, jsonify, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


def read_secret(name):
    path = os.environ.get(name + "_FILE")
    return Path(path).read_text().strip() if path else os.environ[name]


class DatabaseUnavailable(Exception):
    pass


class D1Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect("/run/d1/d1.sock")


def d1_query(sql, params=()):
    request_body = json.dumps({"sql": sql, "params": list(params)}).encode("utf-8")
    connection = D1Connection("localhost", timeout=12)
    try:
        connection.request("POST", "/query", body=request_body,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise DatabaseUnavailable()
        payload = json.loads(response.read())
        result = payload.get("result") or []
        if not payload.get("success") or len(result) != 1 or not result[0].get("success"):
            raise DatabaseUnavailable()
        return result[0].get("results") or []
    except (http.client.HTTPException, TimeoutError, OSError, ValueError) as exception:
        raise DatabaseUnavailable() from exception
    finally:
        connection.close()


app = Flask(__name__, static_folder="static", static_url_path="/static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
app.config.update(
    SECRET_KEY=read_secret("SECRET_KEY"),
    MAX_CONTENT_LENGTH=8192,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)
PUBLIC_ORIGINS = {origin.strip().rstrip("/") for origin in os.environ["PUBLIC_ORIGIN"].split(",") if origin.strip()}
DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(32))
TASK_COLUMNS = "id, title, done, due_date, created_at"


def error(message, status):
    return jsonify(error=message), status


def task_json(row):
    return {
        **row,
        "done": bool(row["done"]),
    }


def task_input(payload, partial=False):
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Dữ liệu không hợp lệ.")
    if set(payload) - {"title", "done", "due_date"}:
        raise ValueError("Trường dữ liệu không hợp lệ.")
    values = {}
    if "title" in payload or not partial:
        title = payload.get("title")
        if not isinstance(title, str) or "\x00" in title or not 1 <= len(title.strip()) <= 200:
            raise ValueError("Tên công việc cần từ 1 đến 200 ký tự.")
        values["title"] = title.strip()
    if "done" in payload:
        if type(payload["done"]) is not bool:
            raise ValueError("Trạng thái công việc không hợp lệ.")
        values["done"] = payload["done"]
    if "due_date" in payload:
        due = payload["due_date"]
        if due is not None:
            if not isinstance(due, str):
                raise ValueError("Ngày đến hạn cần có định dạng YYYY-MM-DD.")
            try:
                parsed = date.fromisoformat(due)
            except ValueError:
                raise ValueError("Ngày đến hạn cần có định dạng YYYY-MM-DD.") from None
            if parsed.isoformat() != due:
                raise ValueError("Ngày đến hạn cần có định dạng YYYY-MM-DD.")
            due = parsed.isoformat()
        values["due_date"] = due
    return values


@app.before_request
def protect_api():
    if not request.path.startswith("/api/"):
        return None
    if request.method in {"POST", "PATCH", "DELETE"}:
        if request.headers.get("Origin") not in PUBLIC_ORIGINS:
            return error("Nguồn yêu cầu không hợp lệ.", 403)
    if request.path == "/api/login":
        return None
    user_id = session.get("user_id")
    if type(user_id) is not int:
        return error("Vui lòng đăng nhập.", 401)
    users = d1_query("SELECT id, email FROM users WHERE id = ?", (user_id,))
    g.user = users[0] if users else None
    if g.user is None:
        session.clear()
        return error("Vui lòng đăng nhập lại.", 401)
    if request.method in {"POST", "PATCH", "DELETE"}:
        provided = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not provided or not expected or not secrets.compare_digest(provided.encode(), expected.encode()):
            return error("Phiên xác thực không hợp lệ. Vui lòng tải lại trang.", 403)
    return None


@app.after_request
def response_headers(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.errorhandler(DatabaseUnavailable)
def database_error(_exception):
    return error("Database tạm thời chưa sẵn sàng. Vui lòng thử lại.", 503)


@app.errorhandler(HTTPException)
def http_error(exception):
    if request.path.startswith("/api/"):
        return error("Yêu cầu không hợp lệ.", exception.code)
    return exception


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/healthz")
def health():
    return jsonify(status="ok")


@app.get("/version")
def version():
    return jsonify(version=os.environ.get("APP_VERSION", "v1"))


@app.get("/readyz")
def ready():
    d1_query("SELECT 1")
    return jsonify(status="ready")


@app.post("/api/login")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("Email hoặc mật khẩu không hợp lệ.", 400)
    email = payload.get("email")
    password = payload.get("password")
    if (
        not isinstance(email, str)
        or not isinstance(password, str)
        or "\x00" in email
        or not 1 <= len(email) <= 254
        or not 1 <= len(password) <= 1024
    ):
        return error("Email hoặc mật khẩu không hợp lệ.", 400)
    users = d1_query(
        "SELECT id, email, password_hash FROM users WHERE email = ?",
        (email.strip().lower(),),
    )
    user = users[0] if users else None
    valid = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)
    if not user or not valid:
        return error("Email hoặc mật khẩu chưa đúng.", 401)
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(
        user={"id": user["id"], "email": user["email"]},
        csrf_token=session["csrf_token"],
    )


@app.get("/api/me")
def me():
    return jsonify(user=g.user, csrf_token=session["csrf_token"])


@app.post("/api/logout")
def logout():
    session.clear()
    return "", 204


@app.get("/api/tasks")
def list_tasks():
    rows = d1_query(
        f"SELECT {TASK_COLUMNS} FROM tasks WHERE user_id = ? ORDER BY id DESC",
        (g.user["id"],),
    )
    return jsonify(tasks=[task_json(row) for row in rows])


@app.post("/api/tasks")
def create_task():
    try:
        values = task_input(request.get_json(silent=True))
    except ValueError as exception:
        return error(str(exception), 400)
    rows = d1_query(
        f"INSERT INTO tasks (user_id, title, done, due_date) VALUES (?, ?, ?, ?) RETURNING {TASK_COLUMNS}",
        (g.user["id"], values["title"], int(values.get("done", False)), values.get("due_date")),
    )
    row = rows[0]
    return jsonify(task=task_json(row)), 201


@app.patch("/api/tasks/<int:task_id>")
def update_task(task_id):
    try:
        values = task_input(request.get_json(silent=True), partial=True)
    except ValueError as exception:
        return error(str(exception), 400)
    # Column names come only from task_input's fixed allowlist; values stay parameterized.
    assignments = ", ".join(f"{column} = ?" for column in values)
    parameters = [int(value) if type(value) is bool else value for value in values.values()]
    rows = d1_query(
        f"UPDATE tasks SET {assignments} WHERE id = ? AND user_id = ? RETURNING {TASK_COLUMNS}",
        (*parameters, task_id, g.user["id"]),
    )
    if not rows:
        return error("Không tìm thấy công việc.", 404)
    return jsonify(task=task_json(rows[0]))


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    rows = d1_query(
        "DELETE FROM tasks WHERE id = ? AND user_id = ? RETURNING id",
        (task_id, g.user["id"]),
    )
    if not rows:
        return error("Không tìm thấy công việc.", 404)
    return "", 204
