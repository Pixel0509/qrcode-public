import base64
import hashlib
import hmac
import io
import os
import time

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect
import qrcode
import requests

app = Flask(__name__)

IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
_SECRET = os.environ.get("QR_SECRET", "dev-secret-change-me").encode()

_LIMITS = {"img": 120, "text": 30}

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


def _check_rate(kind: str, client_token: str) -> tuple[bool, int, str]:
    limit = _LIMITS[kind]
    now = time.time()
    if client_token:
        valid, ts = _verify_token(kind, client_token)
        if valid:
            elapsed = now - ts
            if elapsed < limit:
                return True, int(limit - elapsed) + 1, ""
    new_token = _make_token(kind, now)
    return False, limit, new_token


def _safe_ip(req) -> str:
    forwarded = req.headers.get("X-Forwarded-For", "")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:
            return ip[:45]
    return (req.remote_addr or "unknown")[:45]


def _make_qr(text: str) -> str:
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static", "favicon"),
        "favicon.png",
        mimetype="image/png",
    )


@app.route("/")
def index():
    return redirect("/vi/qrcode", code=302)


@app.route("/vi")
def vi_root():
    return redirect("/vi/qrcode", code=302)


@app.route("/en")
def en_root():
    return redirect("/en/qrcode", code=302)


@app.route("/scan")
def scan():
    return redirect("/vi/qrcode", code=302)


@app.route("/vi/qrcode")
def qrcode_vi():
    return render_template("vi/index.html")


@app.route("/en/qrcode")
def qrcode_en():
    return render_template("en/index.html")


@app.route("/upload", methods=["POST"])
def upload():
    client_token = (request.form.get("cd_token") or "")[:256]
    blocked, rem, new_token = _check_rate("img", client_token)
    if blocked:
        return jsonify({"success": False, "error": f"Vui lòng chờ {rem} giây", "cooldown": rem}), 429

    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"success": False, "error": "Chưa chọn file ảnh"})

    ext = (file.filename.rsplit(".", 1)[-1].lower()) if "." in file.filename else ""
    if ext not in {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"}:
        return jsonify({"success": False, "error": "Định dạng file không được hỗ trợ"})

    if not (file.content_type or "").startswith("image/"):
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

        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": base64.b64encode(image_bytes).decode()},
            timeout=20,
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("success"):
            image_url = result["data"]["url"]
            return jsonify({
                "success": True,
                "qr_code": _make_qr(image_url),
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
    except Exception:
        return jsonify({"success": False, "error": "Lỗi xử lý ảnh"})


@app.route("/qrtext", methods=["POST"])
def qrtext():
    data = request.get_json(force=True, silent=True) or {}
    client_token = str(data.get("cd_token") or "")[:256]
    blocked, rem, new_token = _check_rate("text", client_token)
    if blocked:
        return jsonify({"success": False, "error": f"Vui lòng chờ {rem} giây", "cooldown": rem}), 429

    text = str(data.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "error": "Nội dung không được để trống"})
    if len(text) > _MAX_TEXT_LEN:
        return jsonify({"success": False, "error": f"Nội dung quá dài (tối đa {_MAX_TEXT_LEN} ký tự)"})

    try:
        return jsonify({
            "success": True,
            "qr_code": _make_qr(text),
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
