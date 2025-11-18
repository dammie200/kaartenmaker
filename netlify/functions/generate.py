import base64
import json

from kaart_generator import BadRequest, generate_map


def handler(event, context):  # pylint: disable=unused-argument
    try:
        data = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": "Ongeldige JSON"}

    try:
        buffer, mimetype, fmt = generate_map(data)
    except BadRequest as exc:
        return {"statusCode": 400, "body": str(exc)}
    except Exception:  # pragma: no cover - runtime guard
        return {"statusCode": 500, "body": "Interne serverfout"}

    encoded = base64.b64encode(buffer.read()).decode("ascii")
    headers = {
        "Content-Type": mimetype,
        "Content-Disposition": f"attachment; filename=kaart.{fmt}",
        "Access-Control-Allow-Origin": "*",
    }
    return {"statusCode": 200, "headers": headers, "body": encoded, "isBase64Encoded": True}
