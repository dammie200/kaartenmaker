# Kaartenmaker (web)

Browserversie van de Tkinter-kaartenmaker. Kies een vorm (cirkel, vierkant, rechthoek of papierformaat), zet lagen/sublagen aan of uit en exporteer als PNG, SVG of PDF.

## Deployen op Netlify
Deze repository bevat een statische front-end (`index.html`, `static/`) en een Netlify Function (`netlify/functions/generate.py`) die de kaart genereert.

1. Installeer afhankelijkheden zodat de functie lokaal kan draaien (bijvoorbeeld in een virtualenv):
   ```bash
   pip install -r requirements.txt
   ```
2. Installeer de Netlify CLI als je lokaal wilt testen:
   ```bash
   npm install -g netlify-cli
   ```
3. Start lokaal met functies:
   ```bash
   netlify dev
   ```
   De front-end staat dan op http://localhost:8888 en proxy't `/generate` naar de functie.
4. Deploy naar Netlify met je eigen site:
   ```bash
   netlify deploy --prod
   ```

## Alternatief: lokaal via Flask
Dezelfde back-end kan ook lokaal via Flask draaien:

```bash
pip install -r requirements.txt
flask --app app run
```

## Gebruik
- Zoom/pan de kaart; het midden vormt het startpunt van de selectie.
- Kies de vorm en vul de parameters in (straal, zijde, lengte/breedte of papierformaat + oriëntatie) en voer een schaal in.
- Zet lagen of sublagen aan/uit.
- Klik op **Preview** om een PNG te bekijken of op **Download** voor het gekozen formaat.
