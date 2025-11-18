# Kaartenmaker (web)

Eenvoudige Flask-webapp die de oorspronkelijke Tkinter-kaartenmaker omzet naar een browserervaring. Kies je selectie (cirkel, vierkant, rechthoek of papierformaat), toggle lagen en download een kaart in PNG, SVG of PDF.

## Project starten
1. Installeer afhankelijkheden (bijvoorbeeld via een virtualenv):
   ```bash
   pip install -r requirements.txt
   ```
2. Start de app:
   ```bash
   flask --app app run
   ```
3. Open de browser op [http://localhost:5000](http://localhost:5000).

## Gebruik
- Zoom/pan de kaart; het midden vormt het startpunt van de selectie.
- Kies de vorm en vul de parameters in (straal, zijde, lengte/breedte of papierformaat + oriëntatie) en voer een schaal in.
- Zet lagen of sublagen aan/uit.
- Klik op **Preview** om een PNG te bekijken of op **Download** voor het gekozen formaat.
