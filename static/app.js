const map = L.map('map').setView([51.9244, 4.4777], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap-bijdragers'
}).addTo(map);

const paperFormats = JSON.parse(document.getElementById('paper-formats').textContent);
let selectionLayer = null;

const shapeParamsRoot = document.getElementById('shape-params');
const statusEl = document.getElementById('status');
const previewEl = document.getElementById('preview');

function setStatus(message, type = 'info') {
  statusEl.textContent = message || '';
  statusEl.className = type;
}

function readNumber(id, fallback) {
  const value = parseFloat(document.getElementById(id)?.value);
  return Number.isFinite(value) ? value : fallback;
}

function renderShapeParams(shape) {
  shapeParamsRoot.innerHTML = '';
  if (shape === 'circle') {
    shapeParamsRoot.innerHTML = `
      <label for="radius">Straal (m)</label>
      <input id="radius" type="number" value="1000" min="1" step="10">
    `;
  } else if (shape === 'square') {
    shapeParamsRoot.innerHTML = `
      <label for="side">Zijde (m)</label>
      <input id="side" type="number" value="1000" min="1" step="10">
    `;
  } else if (shape === 'rectangle') {
    shapeParamsRoot.innerHTML = `
      <label for="length">Lengte (m)</label>
      <input id="length" type="number" value="1000" min="1" step="10">
      <label for="width">Breedte (m)</label>
      <input id="width" type="number" value="1000" min="1" step="10">
    `;
  } else {
    shapeParamsRoot.innerHTML = `
      <label for="paper">Formaat</label>
      <select id="paper">
        ${Object.keys(paperFormats).map(key => `<option value="${key}">${key}</option>`).join('')}
      </select>
      <label for="orientation">Oriëntatie</label>
      <select id="orientation">
        <option value="portrait">Portrait</option>
        <option value="landscape">Landscape</option>
      </select>
    `;
  }
}

function buildRectangleFromCenter(width, height) {
  const center = map.getCenter();
  const projected = map.options.crs.project(center);
  const halfW = width / 2;
  const halfH = height / 2;
  const points = [
    L.point(projected.x - halfW, projected.y - halfH),
    L.point(projected.x + halfW, projected.y - halfH),
    L.point(projected.x + halfW, projected.y + halfH),
    L.point(projected.x - halfW, projected.y + halfH),
  ].map(pt => map.options.crs.unproject(pt));
  return L.polygon(points, { color: 'red', weight: 2, fillOpacity: 0.05 });
}

function updateSelection() {
  if (selectionLayer) {
    selectionLayer.remove();
  }
  const shape = document.querySelector('input[name="shape"]:checked').value;
  const scale = readNumber('scale', 5000);
  if (shape === 'circle') {
    const radius = readNumber('radius', 1000);
    selectionLayer = L.circle(map.getCenter(), { radius, color: 'red', weight: 2, fillOpacity: 0.05 });
  } else if (shape === 'square') {
    const side = readNumber('side', 1000);
    selectionLayer = buildRectangleFromCenter(side, side);
  } else if (shape === 'rectangle') {
    const length = readNumber('length', 1000);
    const width = readNumber('width', 1000);
    selectionLayer = buildRectangleFromCenter(length, width);
  } else {
    const paper = document.getElementById('paper').value;
    const orientation = document.getElementById('orientation').value;
    const [wMm, hMm] = paperFormats[paper];
    const isLandscape = orientation === 'landscape';
    const widthMeters = ((isLandscape ? hMm : wMm) / 1000) * scale;
    const heightMeters = ((isLandscape ? wMm : hMm) / 1000) * scale;
    selectionLayer = buildRectangleFromCenter(widthMeters, heightMeters);
  }
  selectionLayer.addTo(map);
}

function collectLayerState() {
  const state = {};
  document.querySelectorAll('.layer-toggle').forEach(box => {
    state[box.dataset.layer] = { enabled: box.checked, values: {} };
  });
  document.querySelectorAll('.sublayer-toggle').forEach(box => {
    const layer = box.dataset.layer;
    const key = box.dataset.key;
    if (!state[layer]) return;
    if (!state[layer].values[key]) state[layer].values[key] = [];
    if (box.checked) state[layer].values[key].push(box.value);
  });
  return state;
}

async function generate(format, showPreview) {
  setStatus('Bezig met genereren...');
  const center = map.getCenter();
  const payload = {
    lat: center.lat,
    lon: center.lng,
    scale: readNumber('scale', 5000),
    shape: document.querySelector('input[name="shape"]:checked').value,
    format,
    layers: collectLayerState(),
  };

  if (payload.shape === 'circle') {
    payload.radius = readNumber('radius', 1000);
  } else if (payload.shape === 'square') {
    payload.side = readNumber('side', 1000);
  } else if (payload.shape === 'rectangle') {
    payload.length = readNumber('length', 1000);
    payload.width = readNumber('width', 1000);
  } else {
    payload.paper = document.getElementById('paper').value;
    payload.orientation = document.getElementById('orientation').value;
  }

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Onbekende fout');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    if (showPreview && ['image/png', 'image/svg+xml'].includes(blob.type)) {
      if (blob.type === 'image/png') {
        const img = document.createElement('img');
        img.src = url;
        img.alt = 'Kaartpreview';
        previewEl.innerHTML = '';
        previewEl.appendChild(img);
      } else {
        fetch(url).then(r => r.text()).then(svg => {
          previewEl.innerHTML = svg;
        });
      }
    }

    const link = document.createElement('a');
    link.href = url;
    link.download = `kaart.${format}`;
    link.click();
    setStatus('Kaart klaar.');
  } catch (err) {
    console.error(err);
    setStatus(err.message || 'Fout bij genereren', 'error');
  }
}

function initSearch() {
  const form = document.getElementById('search-form');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const query = document.getElementById('address').value.trim();
    if (!query) return;
    setStatus('Zoeken...');
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`);
      const results = await res.json();
      if (results.length) {
        const { lat, lon } = results[0];
        map.setView([parseFloat(lat), parseFloat(lon)], 15);
        setStatus('Gevonden.');
      } else {
        setStatus('Geen resultaten gevonden', 'error');
      }
    } catch (err) {
      setStatus('Zoekopdracht mislukt', 'error');
    }
  });
}

function initListeners() {
  document.querySelectorAll('input[name="shape"]').forEach(radio => {
    radio.addEventListener('change', () => {
      renderShapeParams(radio.value);
      updateSelection();
    });
  });

  shapeParamsRoot.addEventListener('input', updateSelection);
  shapeParamsRoot.addEventListener('change', updateSelection);
  document.getElementById('scale').addEventListener('input', updateSelection);
  map.on('moveend', updateSelection);

  document.getElementById('preview-btn').addEventListener('click', () => {
    const fmt = document.getElementById('format').value;
    generate(fmt, true);
  });
  document.getElementById('download-btn').addEventListener('click', () => {
    const fmt = document.getElementById('format').value;
    generate(fmt, false);
  });
}

renderShapeParams('circle');
initListeners();
updateSelection();
initSearch();
