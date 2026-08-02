"""
NutriTool backend — a minimal local Flask server.

Serves the frontend (static/index.html + assets) and a tiny JSON REST API
that the frontend uses instead of browser localStorage:

    GET  /api/data   -> returns the full dataset {config, customFoods, log}
    POST /api/data   -> accepts a full or partial update to that dataset
                        (any of "config" / "customFoods" / "log" present in
                        the JSON body replaces that top-level key; anything
                        omitted is left untouched)

The dataset lives in a single JSON file on disk. Its path is read from
config.json (created next to this script on first run if missing). Point
"data_file_path" at a folder synced by Dropbox/Google Drive/OneDrive/iCloud
to make the same data reachable from any browser, on any device that runs
its own local copy of this server pointed at that same path — the sync
itself is handled entirely by your existing cloud-sync client, not by this
app. See README.md for the full "one server per device, same file, last
write wins" model and its limitations.

No code in this file makes any network call — everything here is local
filesystem I/O plus serving HTTP on 127.0.0.1 (localhost only).
"""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_DATA_FILE = APP_DIR / "data" / "nutritool_data.json"

# Shape of the dataset file. Missing top-level keys are filled with these
# empty defaults; the frontend fills in its own DEFAULT_CONFIG for any
# fields still missing from "config" (e.g. on a brand new data file).
EMPTY_DATASET = {"config": {}, "customFoods": [], "log": []}


def load_server_config():
    """Read config.json, creating a default one on first run if missing."""
    if not CONFIG_PATH.exists():
        default_config = {"data_file_path": str(DEFAULT_DATA_FILE)}
        CONFIG_PATH.write_text(json.dumps(default_config, indent=2) + "\n", encoding="utf-8")
        print(f"No config.json found -- created one at: {CONFIG_PATH}")
        print(f"Data will be stored at: {DEFAULT_DATA_FILE}")
        print()
        print("To access the same data from multiple devices, edit config.json on each")
        print("device and point \"data_file_path\" at a folder synced by Dropbox / Google")
        print("Drive / OneDrive / iCloud, e.g.:")
        print('  { "data_file_path": "~/Dropbox/nutritool/data.json" }')
        print("Each device still runs its own local copy of this server -- syncing the")
        print("file itself is handled by your existing cloud-sync client, not by this app.")
        print()
        return default_config
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Warning: could not read {CONFIG_PATH} ({exc}); falling back to default data path.")
        return {"data_file_path": str(DEFAULT_DATA_FILE)}


SERVER_CONFIG = load_server_config()
DATA_FILE_PATH = Path(
    os.path.expanduser(SERVER_CONFIG.get("data_file_path") or str(DEFAULT_DATA_FILE))
).resolve()
DATA_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)


def read_dataset():
    if not DATA_FILE_PATH.exists():
        return dict(EMPTY_DATASET)
    try:
        with DATA_FILE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(EMPTY_DATASET)
    if not isinstance(data, dict):
        return dict(EMPTY_DATASET)
    merged = dict(EMPTY_DATASET)
    merged.update(data)
    return merged


def write_dataset(dataset):
    # Write-to-temp-then-replace avoids leaving a truncated/corrupt file
    # behind if the process is killed mid-write. This is NOT concurrency
    # control -- see README's "last write wins" note.
    tmp_path = DATA_FILE_PATH.with_suffix(DATA_FILE_PATH.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
    tmp_path.replace(DATA_FILE_PATH)


app = Flask(__name__, static_folder="static", static_url_path="")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(read_dataset())


@app.route("/api/data", methods=["POST"])
def post_data():
    payload = request.get_json(force=True, silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    dataset = read_dataset()
    for key in ("config", "customFoods", "log"):
        if key in payload:
            dataset[key] = payload[key]
    write_dataset(dataset)
    return jsonify(dataset)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Using data file: {DATA_FILE_PATH}")
    print(f"\nNutriTool running at: http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
