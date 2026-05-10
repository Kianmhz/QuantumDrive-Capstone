"""
HTTP device agent for the Capstone dashboard.

Endpoints:
  GET  /status
  POST /start
  POST /stop
  GET  /video_feed
"""

import logging

from flask import Flask, Response, jsonify, request
from flask_cors import CORS

import config
from stream_runner import PipelineStreamRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

runner = PipelineStreamRunner()


@app.get("/status")
def status():
    payload = {
        "online": True,
        "running": runner.is_running(),
        "name": config.DEVICE_NAME,
    }
    if runner.last_error:
        payload["error"] = runner.last_error
    return jsonify(payload)


@app.post("/start")
def start():
    body = request.get_json(silent=True) or {}
    video_source = body.get("video_source") or None
    rows = int(body["rows"]) if body.get("rows") is not None else None
    cols = int(body["cols"]) if body.get("cols") is not None else None
    direction_split = body["direction_split"] if "direction_split" in body else "UNSET"
    precision_qubits = int(body["precision_qubits"]) if body.get("precision_qubits") is not None else None
    success, message = runner.start(video_source=video_source, rows=rows, cols=cols, direction_split=direction_split, precision_qubits=precision_qubits)
    code = 200 if success else 409
    return jsonify({"success": success, "message": message}), code


@app.post("/stop")
def stop():
    success, message = runner.stop()
    code = 200 if success else 409
    return jsonify({"success": success, "message": message}), code


@app.get("/video_feed")
def video_feed():
    return Response(
        runner.mjpeg_chunks(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    if config.START_ON_BOOT:
        ok, msg = runner.start()
        if ok:
            log.info("Auto-started stream")
        else:
            log.warning("Auto-start failed: %s", msg)

    log.info("Starting agent '%s' on port %d", config.DEVICE_NAME, config.PORT)
    app.run(host="0.0.0.0", port=config.PORT, threaded=True)
