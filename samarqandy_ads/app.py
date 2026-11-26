import os
import json
import uuid
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    send_from_directory,
)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_VIDEO_EXT = {"mp4", "webm", "ogg", "mov"}
ALLOWED_EXT = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT

DEFAULT_BRANCHES = [
    "فرع 1",
    "فرع 2",
    "فرع 3",
    "طريق المطار",
    "السليمانية",
    "الروضة",
    "العليا",
    "طريق أنس",
    "النسيم",
    "البديعة",
    "الشفا",
    "اليرموك",
]


def resolve_static_folder() -> str:
    candidates = [
        os.path.join(BASE_DIR, "static"),
        os.path.join(BASE_DIR, "samarqandy_ads", "static"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


def resolve_templates_folder() -> str:
    candidates = [
        os.path.join(BASE_DIR, "templates"),
        os.path.join(BASE_DIR, "samarqandy_ads", "templates"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


STATIC_ROOT = resolve_static_folder()
TEMPLATES_ROOT = resolve_templates_folder()

app = Flask(
    __name__,
    static_folder=STATIC_ROOT,
    static_url_path="/static",
    template_folder=TEMPLATES_ROOT,
)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB


def resolve_data_file() -> str:
    candidates = [
        os.path.join(BASE_DIR, "ads_data.json"),
        os.path.join(BASE_DIR, "samarqandy_ads", "ads_data.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def resolve_media_dir() -> str:
    # على Render نظام الملفات يكون للقراءة فقط في مجلد الكود بعد النشر، لذا نستخدم /tmp إذا لزم الأمر
    candidates = [
        os.path.join(STATIC_ROOT, "ads_media"),
        os.path.join(BASE_DIR, "samarqandy_ads", "static", "ads_media"),
        "/tmp/samarqandy_ads_media",
    ]
    for directory in candidates:
        try:
            os.makedirs(directory, exist_ok=True)
            test_file = os.path.join(directory, ".write_test")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test_file)
            return directory
        except OSError:
            continue
    return candidates[0]


DATA_FILE = resolve_data_file()
MEDIA_DIR = resolve_media_dir()


def load_data() -> dict:
    path = resolve_data_file()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    branches = data.get("branches")
                    if not isinstance(branches, list) or not branches:
                        branches = list(DEFAULT_BRANCHES)
                    ads = data.get("ads")
                    if not isinstance(ads, list):
                        ads = []
                    return {"branches": branches, "ads": ads}
        except Exception:
            pass
    return {"branches": list(DEFAULT_BRANCHES), "ads": []}


def save_data(data: dict) -> None:
    path = resolve_data_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        # في حال عدم قابلية الكتابة داخل مجلد المشروع على Render، نحفظ في /tmp
        tmp_path = "/tmp/ads_data.json"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower().strip()
    return ext in ALLOWED_EXT


def detect_media_type(filename: str) -> str:
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[1].lower().strip()
        if ext in ALLOWED_VIDEO_EXT:
            return "video"
    return "image"


@app.route("/")
def index():
    return redirect(url_for("ads_admin"))


@app.route("/ads", methods=["GET", "POST"])
def ads_admin():
    data = load_data()

    if request.method == "POST":
        action = request.form.get("action", "create").strip()

        if action == "add_branch":
            new_branch = (request.form.get("branch_name") or "").strip()
            if new_branch and new_branch not in data["branches"]:
                data["branches"].append(new_branch)
                save_data(data)
            return redirect(url_for("ads_admin"))

        if action == "toggle":
            ad_id = (request.form.get("ad_id") or "").strip()
            for ad in data["ads"]:
                if ad.get("id") == ad_id:
                    ad["active"] = not bool(ad.get("active", True))
                    break
            save_data(data)
            return redirect(url_for("ads_admin"))

        if action == "delete":
            ad_id = (request.form.get("ad_id") or "").strip()
            data["ads"] = [ad for ad in data["ads"] if ad.get("id") != ad_id]
            save_data(data)
            return redirect(url_for("ads_admin"))

        # إنشاء إعلان جديد
        title = (request.form.get("title") or "إعلان جديد").strip()
        selected_branches = request.form.getlist("branches")
        if not selected_branches or "ALL" in selected_branches:
            branches_val = ["ALL"]
        else:
            branches_val = selected_branches

        try:
            duration = int(request.form.get("duration", 8))
            if duration < 2:
                duration = 2
            elif duration > 300:
                duration = 300
        except (TypeError, ValueError):
            duration = 8

        media_url = (request.form.get("media_url") or "").strip()
        media_type = (request.form.get("media_type") or "image").strip().lower()
        uploaded = request.files.get("media_file")

        if uploaded and uploaded.filename:
            if allowed_file(uploaded.filename):
                ext = uploaded.filename.rsplit(".", 1)[1].lower().strip()
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_name = f"ad_{stamp}_{uuid.uuid4().hex[:8]}.{ext}"
                save_path = os.path.join(MEDIA_DIR, secure_filename(unique_name))
                uploaded.save(save_path)
                media_url = f"/static/ads_media/{unique_name}"
                media_type = detect_media_type(unique_name)

        if not media_type:
            media_type = detect_media_type(media_url)

        new_ad = {
            "id": uuid.uuid4().hex[:10],
            "title": title,
            "media_url": media_url,
            "media_type": media_type,
            "duration": duration,
            "branches": branches_val,
            "active": True,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        data["ads"].insert(0, new_ad)
        save_data(data)
        return redirect(url_for("ads_admin"))

    return render_template(
        "ads_admin.html",
        branches=data["branches"],
        ads=data["ads"],
    )


@app.route("/display")
def display_page():
    data = load_data()
    selected_branch = (request.args.get("branch") or "ALL").strip()
    return render_template(
        "ads_display.html",
        branches=data["branches"],
        default_branches=DEFAULT_BRANCHES,
        selected_branch=selected_branch,
        ads_json=json.dumps(data["ads"], ensure_ascii=False),
        back_url=url_for("ads_admin"),
    )


@app.route("/static/ads_media/<path:filename>")
def serve_ads_media(filename):
    search_dirs = [
        MEDIA_DIR,
        os.path.join(STATIC_ROOT, "ads_media"),
        os.path.join(BASE_DIR, "static", "ads_media"),
        os.path.join(BASE_DIR, "samarqandy_ads", "static", "ads_media"),
        "/tmp/samarqandy_ads_media",
    ]
    safe_name = os.path.basename(filename)
    for directory in search_dirs:
        full_path = os.path.join(directory, safe_name)
        if os.path.isfile(full_path):
            return send_from_directory(directory, safe_name)
    return jsonify({"error": "Media file not found", "file": safe_name}), 404


@app.route("/api/ads")
def api_ads():
    data = load_data()
    branch = (request.args.get("branch") or "ALL").strip()
    filtered = []
    for ad in data["ads"]:
        if not ad.get("active", True):
            continue
        ad_branches = ad.get("branches") or ["ALL"]
        if (
            branch.upper() == "ALL"
            or "ALL" in ad_branches
            or branch in ad_branches
        ):
            filtered.append(ad)
    return jsonify({"branch": branch, "ads": filtered})


@app.route("/ads_data.json")
def serve_ads_json():
    data = load_data()
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
