"""Flask API for audio analysis microservice."""

import os
import tempfile
import uuid

from flask import Flask, request, jsonify
from flask_cors import CORS

from analyzer import extract_features, compute_similarity, download_youtube_audio, search_and_download_youtube

app = Flask(__name__)
CORS(app)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}

# In-memory cache keyed by file hash (simple MVP caching)
_feature_cache: dict[str, dict] = {}


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/analyze", methods=["POST"])
def analyze():
    """Extract features from a single audio file."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        file.save(tmp.name)
        if os.path.getsize(tmp.name) > MAX_FILE_SIZE:
            return jsonify({"error": "File too large (max 50 MB)"}), 400

        features = extract_features(tmp.name)
        return jsonify({"features": features})
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500
    finally:
        os.unlink(tmp.name)


@app.route("/compare", methods=["POST"])
def compare():
    """Compare two audio files and return similarity scores."""
    if "file_a" not in request.files or "file_b" not in request.files:
        return jsonify({"error": "Two files required (file_a, file_b)"}), 400

    file_a = request.files["file_a"]
    file_b = request.files["file_b"]

    for f, label in [(file_a, "file_a"), (file_b, "file_b")]:
        if not f.filename or not _allowed_file(f.filename):
            return jsonify({"error": f"Unsupported file type for {label}"}), 400

    tmp_a = None
    tmp_b = None
    try:
        ext_a = os.path.splitext(file_a.filename)[1].lower()
        ext_b = os.path.splitext(file_b.filename)[1].lower()

        tmp_a = tempfile.NamedTemporaryFile(delete=False, suffix=ext_a)
        tmp_b = tempfile.NamedTemporaryFile(delete=False, suffix=ext_b)

        file_a.save(tmp_a.name)
        file_b.save(tmp_b.name)

        for path, label in [(tmp_a.name, "file_a"), (tmp_b.name, "file_b")]:
            if os.path.getsize(path) > MAX_FILE_SIZE:
                return jsonify({"error": f"{label} too large (max 50 MB)"}), 400

        features_a = extract_features(tmp_a.name)
        features_b = extract_features(tmp_b.name)
        result = compute_similarity(features_a, features_b)

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Comparison failed: {str(e)}"}), 500
    finally:
        if tmp_a:
            os.unlink(tmp_a.name)
        if tmp_b:
            os.unlink(tmp_b.name)


@app.route("/compare-urls", methods=["POST"])
def compare_urls():
    """Compare two YouTube URLs and return similarity scores."""
    data = request.get_json(silent=True)
    if not data or not data.get("url_a") or not data.get("url_b"):
        return jsonify({"error": "Two YouTube URLs required (url_a, url_b)"}), 400

    url_a = data["url_a"].strip()
    url_b = data["url_b"].strip()

    path_a = None
    path_b = None
    try:
        path_a = download_youtube_audio(url_a)
        path_b = download_youtube_audio(url_b)

        features_a = extract_features(path_a)
        features_b = extract_features(path_b)
        result = compute_similarity(features_a, features_b)

        return jsonify(result)
    except (ValueError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Comparison failed: {str(e)}"}), 500
    finally:
        import shutil
        for p in [path_a, path_b]:
            if p:
                # Remove parent tmp dir created by download_youtube_audio
                parent = os.path.dirname(p)
                if parent and parent != "/tmp":
                    shutil.rmtree(parent, ignore_errors=True)


@app.route("/compare-search", methods=["POST"])
def compare_search():
    """Search YouTube for two songs by name+artist and compare them."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    song_a = data.get("song_a", {})
    song_b = data.get("song_b", {})

    name_a = (song_a.get("name") or "").strip()
    artist_a = (song_a.get("artist") or "").strip()
    name_b = (song_b.get("name") or "").strip()
    artist_b = (song_b.get("artist") or "").strip()

    if not name_a or not artist_a or not name_b or not artist_b:
        return jsonify({"error": "Both songs require name and artist fields"}), 400

    path_a = None
    path_b = None
    try:
        path_a = search_and_download_youtube(name_a, artist_a)
        path_b = search_and_download_youtube(name_b, artist_b)

        features_a = extract_features(path_a)
        features_b = extract_features(path_b)
        result = compute_similarity(features_a, features_b)

        return jsonify(result)
    except (ValueError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Comparison failed: {str(e)}"}), 500
    finally:
        import shutil
        for p in [path_a, path_b]:
            if p:
                parent = os.path.dirname(p)
                if parent and parent != "/tmp":
                    shutil.rmtree(parent, ignore_errors=True)


def _resolve_song(song: dict) -> str:
    """Download audio for a song entry (search or URL). Returns temp file path."""
    stype = song.get("type", "search")
    if stype == "url":
        url = (song.get("url") or "").strip()
        if not url:
            raise ValueError("URL is required when type is 'url'")
        return download_youtube_audio(url)
    # Default: search
    name = (song.get("name") or "").strip()
    artist = (song.get("artist") or "").strip()
    if not name or not artist:
        raise ValueError("Song name and artist are required for search")
    return search_and_download_youtube(name, artist)


@app.route("/compare-mixed", methods=["POST"])
def compare_mixed():
    """Compare two songs — each can be a search query or a direct YouTube URL.

    Accepts JSON: { "song_a": { "type": "search"|"url", ... }, "song_b": { ... } }
    For search: { "type": "search", "name": "...", "artist": "..." }
    For url:    { "type": "url", "url": "https://youtube.com/..." }
    """
    data = request.get_json(silent=True)
    if not data or "song_a" not in data or "song_b" not in data:
        return jsonify({"error": "song_a and song_b are required"}), 400

    path_a = None
    path_b = None
    try:
        path_a = _resolve_song(data["song_a"])
        path_b = _resolve_song(data["song_b"])

        features_a = extract_features(path_a)
        features_b = extract_features(path_b)
        result = compute_similarity(features_a, features_b)

        return jsonify(result)
    except (ValueError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Comparison failed: {str(e)}"}), 500
    finally:
        import shutil
        for p in [path_a, path_b]:
            if p:
                parent = os.path.dirname(p)
                if parent and parent != "/tmp":
                    shutil.rmtree(parent, ignore_errors=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG", "false").lower() == "true")
