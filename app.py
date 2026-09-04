"""
NutriTool backend — a minimal local Flask server.

Serves the frontend (static/index.html + assets) and a tiny JSON REST API
that the frontend uses instead of browser localStorage:

    GET  /api/data    -> returns the full dataset {config, customFoods, log, snapshots}
    POST /api/data    -> accepts a full or partial update to that dataset
                        (any of "config" / "customFoods" / "log" / "snapshots"
                        present in the JSON body replaces that top-level key;
                        anything omitted is left untouched)
    GET  /api/history -> historical per-day (or, for window=180,
                        per-rolling-week) %-of-target points built from
                        "snapshots", for the History tab's chart. See
                        get_history() below for the exact contract.

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
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_DATA_FILE = APP_DIR / "data" / "nutritool_data.json"

# Shape of the dataset file. Missing top-level keys are filled with these
# empty defaults; the frontend fills in its own DEFAULT_CONFIG for any
# fields still missing from "config" (e.g. on a brand new data file).
#
# "snapshots" holds one entry per completed calendar day (ISO date string ->
# { nutrientKey: {pct, raw, target} } for all 29 tracked nutrients), written
# by the frontend's catch-up backfill (see index.html) and read back by
# get_history() below. The frontend computes these client-side (that's where
# the decay/target math already lives); this file only stores and aggregates
# them.
EMPTY_DATASET = {"config": {}, "customFoods": [], "log": [], "snapshots": {}}


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
    for key in ("config", "customFoods", "log", "snapshots"):
        if key in payload:
            dataset[key] = payload[key]
    write_dataset(dataset)
    return jsonify(dataset)


HISTORY_WINDOWS = (7, 30, 180)


def _parse_iso_date(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _snapshot_keys_in_range(snapshots, earliest, latest):
    """ISO date-string keys of `snapshots` falling within [earliest, latest],
    sorted ascending. Silently skips any key that isn't a valid ISO date
    (defensive -- this file never writes one, but the JSON file is hand-editable)."""
    out = []
    for k in snapshots.keys():
        d = _parse_iso_date(k)
        if d is not None and earliest <= d <= latest:
            out.append(k)
    return sorted(out)


def build_history_response(snapshots, window, today):
    """Shared aggregation logic behind GET /api/history. `snapshots` is the
    {isoDate: {nutrientKey: {pct, raw, target}}} dict from the dataset;
    `today` is the caller's local "today" (date object) -- see get_history()
    for why that's taken from the client rather than the server clock."""
    latest_completed = today - timedelta(days=1)  # today itself is never snapshotted
    earliest_allowed = today - timedelta(days=window)
    day_keys = _snapshot_keys_in_range(snapshots, earliest_allowed, latest_completed)

    if window in (7, 30):
        points = [{"date": k, "nutrients": snapshots[k]} for k in day_keys]
        return {"window": window, "granularity": "daily", "points": points}

    # window == 180: aggregate into rolling 7-day buckets counted BACKWARD
    # from `latest_completed` (NOT calendar weeks) -- the most recent bucket
    # is a full 7 days whenever there's enough history for it; the oldest
    # bucket may be partial, clipped at `earliest_allowed`.
    buckets = []  # (start, end) inclusive, built newest-first
    bucket_end = latest_completed
    while bucket_end >= earliest_allowed:
        bucket_start = max(bucket_end - timedelta(days=6), earliest_allowed)
        buckets.append((bucket_start, bucket_end))
        bucket_end = bucket_start - timedelta(days=1)

    points = []
    for bucket_start, bucket_end in reversed(buckets):  # oldest-first, left-to-right on the chart
        keys_in_bucket = [k for k in day_keys if bucket_start <= _parse_iso_date(k) <= bucket_end]
        if not keys_in_bucket:
            continue  # no data at all for this bucket -- omit rather than show a fabricated zero
        nutrient_keys = set()
        for k in keys_in_bucket:
            nutrient_keys.update(snapshots[k].keys())
        nutrients = {}
        for nk in nutrient_keys:
            present = [snapshots[k][nk] for k in keys_in_bucket if nk in snapshots[k]]
            nutrients[nk] = {
                "pct": _mean([p.get("pct") for p in present]),
                "raw": _mean([p.get("raw") for p in present]),
                "target": _mean([p.get("target") for p in present]),
            }
        points.append({
            "date": bucket_start.isoformat(),
            "weekStart": bucket_start.isoformat(),
            "weekEnd": bucket_end.isoformat(),
            "nutrients": nutrients,
        })

    return {"window": window, "granularity": "weekly", "points": points}


@app.route("/api/history", methods=["GET"])
def get_history():
    try:
        window = int(request.args.get("window", 30))
    except (TypeError, ValueError):
        window = 0
    if window not in HISTORY_WINDOWS:
        return jsonify({"error": "window must be one of 7, 30, 180"}), 400

    # "today" comes from the client (its own local calendar date) rather than
    # the server clock -- on this local repo server and browser share a
    # machine so it rarely matters, but the aggregation logic is shared
    # verbatim with nutritool-online, where server and browser CAN be in
    # different timezones and this avoids a boundary mismatch there.
    today = _parse_iso_date(request.args.get("today")) or date.today()

    dataset = read_dataset()
    snapshots = dataset.get("snapshots") or {}
    return jsonify(build_history_response(snapshots, window, today))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Using data file: {DATA_FILE_PATH}")
    print(f"\nNutriTool running at: http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
