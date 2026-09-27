import base64
import hashlib
import hmac
import io
import os
import threading
import time
from flask import Flask, render_template, request, jsonify, send_from_directory
import qrcode
import requests

app = Flask(__name__)

IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
_SECRET = os.environ.get("QR_SECRET", "dev-secret-change-me").encode()

_LIMITS = {"img": 120, "text": 30}
_rate_lock = threading.Lock()
_rate_store: dict[str, dict[str, float]] = {"img": {}, "text": {}}

_MAX_IMG_BYTES = 3 * 1024 * 1024
_MAX_TEXT_LEN  = 4096
_MAX_KEY_LEN   = 128


def _make_token(kind: str, ts: float) -> str:
    msg = f"{kind}:{ts:.0f}".encode()
    sig = hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()
    return f"{kind}:{ts:.0f}:{sig}"


def _verify_token(kind: str, token: str) -> tuple[bool, float]:
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False, 0.0
        k, ts_str, sig = parts
        if k != kind:
            return False, 0.0
        ts = float(ts_str)
        msg = f"{kind}:{ts:.0f}".encode()
        expected = hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return False, 0.0
        return True, ts
    except Exception:
        return False, 0.0


def _check_rate(ip: str, kind: str, client_token: str) -> tuple[bool, int, str]:
    limit = _LIMITS[kind]
    now = time.time()

    if client_token:
        valid, ts = _verify_token(kind, client_token)
        if valid:
            elapsed = now - ts
            if elapsed < limit:
                rem = int(limit - elapsed) + 1
                return True, rem, ""

    with _rate_lock:
        last = _rate_store[kind].get(ip, 0.0)
        elapsed = now - last
        if elapsed < limit:
            rem = int(limit - elapsed) + 1
            return True, rem, ""
        _rate_store[kind][ip] = now

    new_token = _make_token(kind, now)
    cd_rem = limit
    return False, cd_rem, new_token


def _safe_ip(req) -> str:
    forwarded = req.headers.get("X-Forwarded-For", "")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip[:45]
    return (req.remote_addr or "unknown")[:45]


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static", "favicon"),
        "favicon.png",
        mimetype="image/png",
    )


@app.route("/", methods=["GET"])
def index():
    from flask import redirect
    return redirect("/vi/qrcode", code=302)


@app.route("/vi", methods=["GET"])
def vi_root():
    from flask import redirect
    return redirect("/vi/qrcode", code=302)


@app.route("/en", methods=["GET"])
def en_root():
    from flask import redirect
    return redirect("/en/qrcode", code=302)


@app.route("/vi/qrcode", methods=["GET"])
def qrcode_vi():
    return render_template("vi/index.html")


@app.route("/en/qrcode", methods=["GET"])
def qrcode_en():
    return render_template("en/index.html")


@app.route("/scan", methods=["GET"])
def scan():
    from flask import redirect
    return redirect("/vi/qrcode", code=302)


@app.route("/upload", methods=["POST"])
def upload():
    ip = _safe_ip(request)
    client_token = (request.form.get("cd_token") or "")[:256]
    blocked, rem, new_token = _check_rate(ip, "img", client_token)
    if blocked:
        return jsonify({
            "success": False,
            "error": f"Vui lòng chờ {rem} giây",
            "cooldown": rem,
        }), 429

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "Chưa chọn file ảnh"})

    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_ext = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"}
    if ext not in allowed_ext:
        return jsonify({"success": False, "error": "Định dạng file không được hỗ trợ"})

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        return jsonify({"success": False, "error": "File không phải ảnh"})

    api_key = (request.form.get("api_key") or "").strip()
    if not api_key:
        api_key = IMGBB_API_KEY
    if not api_key:
        return jsonify({"success": False, "error": "Thiếu API key ImgBB"})
    if len(api_key) > _MAX_KEY_LEN:
        return jsonify({"success": False, "error": "API key không hợp lệ"})

    try:
        image_bytes = file.read(_MAX_IMG_BYTES + 1)
        if len(image_bytes) > _MAX_IMG_BYTES:
            return jsonify({"success": False, "error": "Ảnh vượt quá 3 MB"})

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": encoded_image},
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            image_url = result["data"]["url"]
            img = qrcode.make(image_url)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return jsonify({
                "success": True,
                "qr_code": qr_b64,
                "image_url": image_url,
                "cd_token": new_token,
                "cd_rem": _LIMITS["img"],
            })

        msg = (result.get("error") or {}).get("message", "Không rõ nguyên nhân")
        return jsonify({"success": False, "error": msg})

    except requests.Timeout:
        return jsonify({"success": False, "error": "ImgBB không phản hồi, thử lại sau"})
    except requests.HTTPError as e:
        return jsonify({"success": False, "error": f"ImgBB lỗi HTTP {e.response.status_code}"})
    except Exception as e:
        return jsonify({"success": False, "error": "Lỗi xử lý ảnh"})


@app.route("/qrtext", methods=["POST"])
def qrtext():
    ip = _safe_ip(request)
    data = request.get_json(force=True, silent=True) or {}
    client_token = str(data.get("cd_token") or "")[:256]
    blocked, rem, new_token = _check_rate(ip, "text", client_token)
    if blocked:
        return jsonify({
            "success": False,
            "error": f"Vui lòng chờ {rem} giây",
            "cooldown": rem,
        }), 429

    text = str(data.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "error": "Nội dung không được để trống"})
    if len(text) > _MAX_TEXT_LEN:
        return jsonify({"success": False, "error": f"Nội dung quá dài (tối đa {_MAX_TEXT_LEN} ký tự)"})

    try:
        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return jsonify({
            "success": True,
            "qr_code": qr_b64,
            "cd_token": new_token,
            "cd_rem": _LIMITS["text"],
        })
    except Exception:
        return jsonify({"success": False, "error": "Lỗi tạo mã QR"})



@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=False)
