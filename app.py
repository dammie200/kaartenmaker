import io
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import flask
import geopandas as gpd
import matplotlib.pyplot as plt
import osmnx as ox
import pyproj
from flask import Flask, jsonify, render_template, request, send_file
from matplotlib_scalebar.scalebar import ScaleBar
from shapely.geometry import Point, box
from shapely.ops import transform as shapely_transform

# --- Configuratie van OSM-lagen ---
TAGS_PER_LAYER: Dict[str, Dict[str, object]] = {
    "Gebouwen": {"building": True},
    "Hoofdwegen": {
        "highway": [
            "motorway",
            "primary",
            "secondary",
            "tertiary",
            "trunk",
            "residential",
        ]
    },
    "Voetpaden": {"highway": ["footway", "path"]},
    "Water": {"natural": "water"},
    "Bos": {"landuse": "forest"},
}

# --- Stijlinstellingen per laag ---
STYLE_VARS: Dict[str, Dict[str, object]] = {
    name: {"fill": "#888888", "edge": "#000000", "linewidth": 0.5, "alpha": 1.0}
    for name in TAGS_PER_LAYER
}

# Papierformaten (mm)
PAPER_FORMATS: Dict[str, Tuple[int, int]] = {
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189),
}

app = Flask(__name__)


@dataclass
class Selection:
    polygon_utm: object
    polygon_ll: object
    utm_crs: pyproj.CRS


@dataclass
class LayerSelection:
    enabled: bool
    allowed_values: Dict[str, List[str]]


class BadRequest(Exception):
    """Eenvoudige exception voor gebruikersfouten."""


@app.errorhandler(BadRequest)
def handle_bad_request(exc: BadRequest):
    return jsonify({"error": str(exc)}), 400


@app.route("/")
def index():
    return render_template(
        "index.html",
        tags=TAGS_PER_LAYER,
        paper_formats=PAPER_FORMATS,
        styles=STYLE_VARS,
    )


def _utm_crs_for_location(lat: float, lon: float) -> pyproj.CRS:
    zone = int((lon + 180) / 6) + 1
    epsg = 32600 + zone if lat >= 0 else 32700 + zone
    return pyproj.CRS.from_epsg(epsg)


def _build_selection(data: dict) -> Selection:
    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
        scale = float(data.get("scale", 5000))
    except (TypeError, ValueError) as exc:  # pragma: no cover - guarded at runtime
        raise BadRequest("Ongeldige coördinaten of schaal") from exc

    shape = data.get("shape", "circle")
    utm_crs = _utm_crs_for_location(lat, lon)
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True).transform
    to_ll = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True).transform
    center_utm = shapely_transform(to_utm, Point(lon, lat))

    if shape == "circle":
        try:
            radius = float(data.get("radius", 1000))
        except (TypeError, ValueError) as exc:  # pragma: no cover - guarded at runtime
            raise BadRequest("Ongeldige straal") from exc
        poly = center_utm.buffer(radius)
    elif shape == "square":
        try:
            side = float(data.get("side", 1000))
        except (TypeError, ValueError) as exc:  # pragma: no cover - guarded at runtime
            raise BadRequest("Ongeldige zijde") from exc
        half = side / 2
        poly = box(center_utm.x - half, center_utm.y - half, center_utm.x + half, center_utm.y + half)
    elif shape == "rectangle":
        try:
            length = float(data.get("length", 1000))
            width = float(data.get("width", 1000))
        except (TypeError, ValueError) as exc:  # pragma: no cover - guarded at runtime
            raise BadRequest("Ongeldige lengte of breedte") from exc
        poly = box(
            center_utm.x - length / 2,
            center_utm.y - width / 2,
            center_utm.x + length / 2,
            center_utm.y + width / 2,
        )
    elif shape == "paper":
        paper = data.get("paper", "A4")
        orientation = data.get("orientation", "portrait")
        try:
            width_mm, height_mm = PAPER_FORMATS[paper]
        except KeyError as exc:  # pragma: no cover - guarded at runtime
            raise BadRequest("Onbekend papierformaat") from exc
        if orientation == "landscape":
            width_mm, height_mm = height_mm, width_mm
        width_m = (width_mm / 1000) * scale
        height_m = (height_mm / 1000) * scale
        poly = box(
            center_utm.x - width_m / 2,
            center_utm.y - height_m / 2,
            center_utm.x + width_m / 2,
            center_utm.y + height_m / 2,
        )
    else:  # pragma: no cover - guarded at runtime
        raise BadRequest("Onbekende selectievorm")

    return Selection(polygon_utm=poly, polygon_ll=shapely_transform(to_ll, poly), utm_crs=utm_crs)


def _layer_selection(data: dict) -> Dict[str, LayerSelection]:
    selected_layers: Dict[str, LayerSelection] = {}
    layers = data.get("layers") or {}
    for name, tags in TAGS_PER_LAYER.items():
        layer_info = layers.get(name, {})
        enabled = bool(layer_info.get("enabled", True))
        allowed_values: Dict[str, List[str]] = {}
        for key, values in tags.items():
            if isinstance(values, list):
                chosen = layer_info.get("values", {}).get(key)
                allowed = values if chosen is None else [v for v in values if v in chosen]
                if not allowed:
                    enabled = False
                allowed_values[key] = allowed
        selected_layers[name] = LayerSelection(enabled=enabled, allowed_values=allowed_values)
    return selected_layers


def _fetch_geometries(aoi_ll, query):
    fetch = getattr(ox, "geometries_from_polygon", None) or getattr(ox, "features_from_polygon")
    return fetch(aoi_ll, query)


def _plot_layers(ax, selection: Selection, layers: Dict[str, LayerSelection]):
    minx, miny, maxx, maxy = selection.polygon_utm.bounds
    for name, tagdict in TAGS_PER_LAYER.items():
        layer_state = layers[name]
        if not layer_state.enabled:
            continue
        if any(isinstance(v, list) for v in tagdict.values()):
            query = {}
            skip = False
            for key, values in tagdict.items():
                if isinstance(values, list):
                    filtered = layer_state.allowed_values.get(key, values)
                    if not filtered:
                        skip = True
                        break
                    query[key] = filtered
                else:
                    query[key] = values
            if skip:
                continue
        else:
            query = tagdict

        try:
            gdf = _fetch_geometries(selection.polygon_ll, query)
        except Exception:
            continue
        if gdf.empty:
            continue
        gdf_utm = gdf.to_crs(selection.utm_crs)
        clipped = gpd.clip(gdf_utm, selection.polygon_utm)
        style = STYLE_VARS[name]
        clipped.plot(
            ax=ax,
            color=style["fill"],
            edgecolor=style["edge"],
            linewidth=style["linewidth"],
            alpha=style["alpha"],
        )
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    if not data:  # pragma: no cover - runtime guard
        raise BadRequest("Geen data ontvangen")

    selection = _build_selection(data)
    layers = _layer_selection(data)
    fmt = data.get("format", "png").lower()
    if fmt not in {"png", "pdf", "svg"}:
        raise BadRequest("Ondersteund formaat: png, pdf of svg")

    minx, miny, maxx, maxy = selection.polygon_utm.bounds
    scale = float(data.get("scale", 5000))
    fig_w = ((maxx - minx) / scale) / 0.01 / 2.54
    fig_h = ((maxy - miny) / scale) / 0.01 / 2.54
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    _plot_layers(ax, selection, layers)

    scalebar = ScaleBar(1, 'm', length_fraction=0.25, location='lower right', box_alpha=0.0)
    ax.add_artist(scalebar)
    plt.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format=fmt, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)

    filename = f"kaart.{fmt}"
    mimetypes = {'png': 'image/png', 'svg': 'image/svg+xml', 'pdf': 'application/pdf'}
    return send_file(buffer, mimetype=mimetypes.get(fmt, 'application/octet-stream'), as_attachment=True, download_name=filename)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
