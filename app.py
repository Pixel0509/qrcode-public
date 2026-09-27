import base64
import hashlib
import hmac
import io
import os
import time

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect
from PIL import Image
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


@app.route("/delete-metadata")
def delete_metadata():
    return render_template("delete-metadata/index.html")


_IMG_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp",
             "TIFF": "image/tiff", "BMP": "image/bmp"}
_IMG_MAX  = 10 * 1024 * 1024
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"}


def _read_image_file(file):
    if not file or not file.filename:
        return None, None, "Chưa chọn file ảnh"
    if (file.content_type or "") not in _ALLOWED_MIME:
        return None, None, "Định dạng không hỗ trợ"
    data = file.read(_IMG_MAX + 1)
    if len(data) > _IMG_MAX:
        return None, None, "File vượt quá 10 MB"
    from PIL import Image
    img = Image.open(io.BytesIO(data))
    img.load()
    return img, data, None


def _img_response(img, fmt):
    buf = io.BytesIO()
    kw = {"format": fmt}
    if fmt == "JPEG":
        kw["quality"] = 95
        kw["subsampling"] = 0
    img.save(buf, **kw)
    buf.seek(0)
    from flask import Response
    return Response(buf.read(), mimetype=_IMG_MIME.get(fmt, "image/jpeg"),
                    headers={"Content-Disposition": "attachment"})


@app.route("/strip-metadata", methods=["POST"])
def strip_metadata():
    try:
        img, _, err = _read_image_file(request.files.get("image"))
        if err:
            return jsonify({"error": err}), 400
        fmt   = img.format or "JPEG"
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))
        return _img_response(clean, fmt)
    except Exception:
        return jsonify({"error": "Lỗi xử lý ảnh"}), 500


@app.route("/sign-image", methods=["POST"])
def sign_image():
    try:
        img, _, err = _read_image_file(request.files.get("image"))
        if err:
            return jsonify({"error": err}), 400
        artist = (request.form.get("artist") or "").strip()[:200]
        desc   = (request.form.get("desc")   or "").strip()[:500]
        fmt    = img.format or "JPEG"
        buf    = io.BytesIO()
        if fmt == "JPEG":
            try:
                import piexif
                raw = img.info.get("exif", b"")
                try:
                    exif_dict = piexif.load(raw)
                except Exception:
                    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
                exif_dict.setdefault("0th", {})
                if artist:
                    exif_dict["0th"][piexif.ImageIFD.Artist] = artist.encode("utf-8")
                if desc:
                    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = desc.encode("utf-8")
                img.save(buf, format="JPEG", quality=95, subsampling=0,
                         exif=piexif.dump(exif_dict))
            except ImportError:
                img.save(buf, format="JPEG", quality=95, subsampling=0)
        else:
            from PIL import PngImagePlugin
            pnginfo = PngImagePlugin.PngInfo()
            if artist: pnginfo.add_text("Artist", artist)
            if desc:   pnginfo.add_text("Description", desc)
            img.save(buf, format=fmt, pnginfo=pnginfo if fmt == "PNG" else None)
        buf.seek(0)
        from flask import Response
        return Response(buf.read(), mimetype=_IMG_MIME.get(fmt, "image/jpeg"),
                        headers={"Content-Disposition": "attachment"})
    except Exception:
        return jsonify({"error": "Lỗi ghi metadata"}), 500


@app.route("/read-metadata", methods=["POST"])
def read_metadata():
    try:
        img, _, err = _read_image_file(request.files.get("image"))
        if err:
            return jsonify({"success": False, "error": err}), 400
        rows = []
        fmt  = img.format or "?"
        if fmt == "JPEG":
            raw = img.info.get("exif", b"")
            if raw:
                try:
                    import piexif
                    exif_dict = piexif.load(raw)
                    tag_map = {
                        piexif.ImageIFD.Artist:           "Artist",
                        piexif.ImageIFD.ImageDescription: "ImageDescription",
                        piexif.ImageIFD.Make:             "Make",
                        piexif.ImageIFD.Model:            "Model",
                        piexif.ImageIFD.Software:         "Software",
                        piexif.ImageIFD.DateTime:         "DateTime",
                        piexif.ImageIFD.Copyright:        "Copyright",
                    }
                    gps_map = {
                        piexif.GPSIFD.GPSLatitude:     "GPS Latitude",
                        piexif.GPSIFD.GPSLongitude:    "GPS Longitude",
                        piexif.GPSIFD.GPSAltitude:     "GPS Altitude",
                        piexif.GPSIFD.GPSDateStamp:    "GPS Date",
                    }
                    for ifd in ("0th", "1st", "Exif"):
                        for tag, label in tag_map.items():
                            val = exif_dict.get(ifd, {}).get(tag)
                            if val is not None:
                                if isinstance(val, bytes):
                                    val = val.decode("utf-8", errors="replace").strip("\x00")
                                rows.append([label, str(val)])
                    for tag, label in gps_map.items():
                        val = exif_dict.get("GPS", {}).get(tag)
                        if val is not None:
                            rows.append([label, str(val)])
                except ImportError:
                    rows.append(["EXIF raw bytes", str(len(raw))])
                except Exception:
                    rows.append(["EXIF raw bytes", str(len(raw))])
            else:
                rows.append(["EXIF", "(Không có)"])
        else:
            info = img.info or {}
            for k, v in info.items():
                rows.append([str(k), str(v)[:300]])
            if not info:
                rows.append(["Metadata", "(Không có)"])
        rows.append(["Format", fmt])
        rows.append(["Mode",   img.mode])
        rows.append(["Kích thước", f"{img.width} x {img.height} px"])
        return jsonify({"success": True, "rows": rows})
    except Exception:
        return jsonify({"success": False, "error": "Lỗi đọc metadata"}), 500


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=False)
