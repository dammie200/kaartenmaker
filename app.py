import os

from flask import Flask, jsonify, request, send_file

from kaart_generator import BadRequest, generate_map

app = Flask(__name__, static_folder="static", static_url_path="/static")


@app.errorhandler(BadRequest)
def handle_bad_request(exc: BadRequest):
    return jsonify({"error": str(exc)}), 400


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    if not data:  # pragma: no cover - runtime guard
        raise BadRequest("Geen data ontvangen")
    buffer, mimetype, fmt = generate_map(data)
    filename = f"kaart.{fmt}"
    return send_file(buffer, mimetype=mimetype, as_attachment=True, download_name=filename)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
