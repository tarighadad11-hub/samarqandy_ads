import json
import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "samarqandy_ads_secret_2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADS_DATA_FILE = os.path.join(BASE_DIR, "ads_data.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "ads_media")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGES = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_VIDEOS = {"mp4", "webm", "mov", "ogg"}

DEFAULT_BRANCHES = [
    "الثمامة 1",
    "الثمامة 3",
    "الملك فهد",
    "طريق الدمام",
    "الصناعية",
    "أبوبكر",
    "الملقاء",
    "النظم",
    "شيخ جابر",
    "عتيقة",
    "النسيم",
    "السويدي",
    "الشفاء",
]


def load_ads_db():
    if not os.path.exists(ADS_DATA_FILE):
        return {"branches": list(DEFAULT_BRANCHES), "ads": []}
    try:
        with open(ADS_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"branches": list(DEFAULT_BRANCHES), "ads": []}
            data.setdefault("branches", list(DEFAULT_BRANCHES))
            data.setdefault("ads", [])
            return data
    except Exception:
        return {"branches": list(DEFAULT_BRANCHES), "ads": []}


def save_ads_db(data):
    with open(ADS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


ADS_DB = load_ads_db()


def save_media_file(file_storage):
    if not file_storage or not getattr(file_storage, "filename", ""):
        return "", ""
    safe_name = secure_filename(file_storage.filename)
    ext = safe_name.rsplit(".", 1)[1].lower() if "." in safe_name else ""
    if ext in ALLOWED_IMAGES:
        media_type = "image"
    elif ext in ALLOWED_VIDEOS:
        media_type = "video"
    else:
        return "", ""

    unique_name = f"ad_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
    full_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file_storage.save(full_path)
    return f"/static/ads_media/{unique_name}", media_type


@app.route("/")
def index():
    return redirect(url_for("ads_admin"))


@app.route("/ads", methods=["GET", "POST"])
def ads_admin():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        duration = int(request.form.get("duration") or 8)
        selected_branches = request.form.getlist("branches")
        if not selected_branches or "ALL" in selected_branches:
            target_branches = ["ALL"]
        else:
            target_branches = selected_branches

        media_file = request.files.get("media_file") or request.files.get("file") or request.files.get("image")
        media_url, media_type = save_media_file(media_file)

        if media_url:
            new_ad = {
                "id": uuid.uuid4().hex[:10],
                "title": title or "إعلان جديد",
                "media_url": media_url,
                "media_type": media_type,
                "duration": max(2, duration),
                "branches": target_branches,
                "active": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            ADS_DB["ads"].insert(0, new_ad)
            save_ads_db(ADS_DB)

        return redirect(url_for("ads_admin"))

    return render_template(
        "ads_admin.html",
        branches=ADS_DB.get("branches", DEFAULT_BRANCHES),
        ads=ADS_DB.get("ads", []),
    )


@app.route("/ads/toggle/<ad_id>", methods=["POST"])
def toggle_ad(ad_id):
    for ad in ADS_DB.get("ads", []):
        if str(ad.get("id")) == str(ad_id):
            ad["active"] = not bool(ad.get("active", True))
            break
    save_ads_db(ADS_DB)
    return redirect(url_for("ads_admin"))


@app.route("/ads/delete/<ad_id>", methods=["POST"])
def delete_ad(ad_id):
    remaining = []
    for ad in ADS_DB.get("ads", []):
        if str(ad.get("id")) == str(ad_id):
            m_url = ad.get("media_url", "")
            if m_url.startswith("/static/ads_media/"):
                fname = os.path.basename(m_url)
                fpath = os.path.join(UPLOAD_FOLDER, fname)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
            continue
        remaining.append(ad)
    ADS_DB["ads"] = remaining
    save_ads_db(ADS_DB)
    return redirect(url_for("ads_admin"))


@app.route("/display")
def display_page():
    branch = (request.args.get("branch") or "ALL").strip()
    return render_template(
        "ads_display.html",
        branches=ADS_DB.get("branches", DEFAULT_BRANCHES),
        selected_branch=branch,
    )


@app.route("/api/ads")
def api_ads():
    branch = (request.args.get("branch") or "ALL").strip()
    active_ads = []
    for ad in ADS_DB.get("ads", []):
        if not ad.get("active", True):
            continue
        ad_branches = ad.get("branches") or ["ALL"]
        if branch == "ALL" or "ALL" in ad_branches or branch in ad_branches:
            active_ads.append(ad)
    return jsonify({"branch": branch, "ads": active_ads, "count": len(active_ads)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
