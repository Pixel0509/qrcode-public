import base64
import hashlib
import hmac
import io
import os
import time
import zipfile

from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
import qrcode
import requests

app = Flask(__name__)

IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
_SECRET = os.environ.get("QR_SECRET", "qr-secret-change-me-in-prod")
CD_IMG_S = 120
CD_TEXT_S = 30


def _sign(payload: str) -> str:
    return hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(kind: str) -> str:
    ts = int(time.time())
    sig = _sign(f"{kind}:{ts}")
    return f"{kind}:{ts}:{sig}"


def verify_token(token: str | None, kind: str) -> tuple[bool, int]:
    if not token:
        return False, 0
    try:
        k, ts_str, sig = token.split(":", 2)
    except ValueError:
        return False, 0
    if k != kind:
        return False, 0
    ts = int(ts_str)
    if not hmac.compare_digest(sig, _sign(f"{k}:{ts}")):
        return False, 0
    elapsed = int(time.time()) - ts
    limit = CD_IMG_S if kind == "img" else CD_TEXT_S
    rem = limit - elapsed
    return rem > 0, max(rem, 0)


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
    return render_template("vi/index.html")


@app.route("/upload", methods=["POST"])
def upload():
    token = request.form.get("cd_token", "")
    cooling, rem = verify_token(token, "img")
    if cooling:
        return jsonify({
            "success": False,
            "error": f"Vui lòng chờ {rem} giây",
            "cooldown": rem
        })

    file = request.files.get("image")
    if not file or file.filename == "":
        return jsonify({
            "success": False,
            "error": "Chưa chọn file ảnh"
        })

    api_key = request.form.get("api_key", "").strip() or IMGBB_API_KEY
    if not api_key:
        return jsonify({
            "success": False,
            "error": "Thiếu API key ImgBB"
        })

    try:
        image_bytes = file.read()

        if len(image_bytes) > 3 * 1024 * 1024:
            return jsonify({
                "success": False,
                "error": "Ảnh vượt quá 3 MB"
            })

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": api_key,
                "image": encoded_image
            },
            timeout=20
        )

        result = response.json()

        if result.get("success"):
            image_url = result["data"]["url"]
            img = qrcode.make(image_url)
            buf = io.BytesIO()
            img.save(buf, format="PNG")

            qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            new_token = make_token("img")

            return jsonify({
                "success": True,
                "qr_code": qr_b64,
                "image_url": image_url,
                "cd_token": new_token,
                "cd_rem": CD_IMG_S
            })

        msg = result.get("error", {}).get(
            "message",
            "Không rõ nguyên nhân"
        )

        return jsonify({
            "success": False,
            "error": msg
        })

    except requests.Timeout:
        return jsonify({
            "success": False,
            "error": "ImgBB không phản hồi, thử lại sau"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/qrtext", methods=["POST"])
def qrtext():
    data = request.get_json(force=True)

    token = data.get("cd_token", "")
    cooling, rem = verify_token(token, "text")

    if cooling:
        return jsonify({
            "success": False,
            "error": f"Vui lòng chờ {rem} giây",
            "cooldown": rem
        })

    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({
            "success": False,
            "error": "Nội dung không được để trống"
        })

    if len(text) > 250:
        return jsonify({
            "success": False,
            "error": "Nội dung quá dài (tối đa 250 ký tự)"
        })

    try:
        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        new_token = make_token("text")

        return jsonify({
            "success": True,
            "qr_code": qr_b64,
            "cd_token": new_token,
            "cd_rem": CD_TEXT_S
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/source", methods=["GET"])
def download_source():
    base = os.path.dirname(os.path.abspath(__file__))

    include = [
        "app.py",
        "requirements.txt",
        "vercel.json",
        "README.md",
        "templates/index.html",
        "templates/404.html",
        "static/favicon/favicon.png",
    ]

    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in include:
            fpath = os.path.join(base, rel)

            if os.path.isfile(fpath):
                zf.write(fpath, "src/" + rel)

    buf.seek(0)

    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="src.zip"
    )


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
