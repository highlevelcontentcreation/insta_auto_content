#!/usr/bin/env python3
"""
instagram_auto_poster.py

Erstellt automatisch ein Stoiker-Zitat-Bild (Marcus Aurelius, Seneca,
Epiktet, ...) und veröffentlicht es über die Instagram Graph API auf
einem Instagram Business-Account. Jedes Zitat wird nur EINMAL gepostet.

Ablauf:
1. Zufälliges, noch nicht gepostetes Zitat von der stoic-quotes.com API holen
2. Bild mit Zitat auf farbigem Hintergrund erzeugen (Pillow)
3. Zitat als "bereits gepostet" vermerken (posted_quotes.json)
4. Bild + posted_quotes.json ins Repo committen & pushen (damit das Bild
   über eine öffentliche Raw-URL erreichbar ist -> Instagram braucht
   zwingend eine öffentliche Bild-URL)
5. Über die Instagram Graph API einen Media-Container erstellen
6. Media-Container veröffentlichen

Benötigte Umgebungsvariablen (siehe SETUP.md):
- IG_USER_ID       -> Instagram Business Account ID
- IG_ACCESS_TOKEN  -> Langlebiges Meta/Instagram Access Token
- GITHUB_REPOSITORY_RAW_BASE -> z.B. https://raw.githubusercontent.com/<user>/<repo>/main
"""

import json
import os
import random
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent
POSTED_QUOTES_FILE = REPO_ROOT / "posted_quotes.json"
FALLBACK_QUOTES_FILE = REPO_ROOT / "quotes.json"  # falls die API mal nicht erreichbar ist
IMAGES_DIR = REPO_ROOT / "images"

STOIC_API_SINGLE = "https://stoic-quotes.com/api/quote"
STOIC_API_BATCH = "https://stoic-quotes.com/api/quotes?num=100"
MAX_FETCH_ATTEMPTS = 40  # so oft maximal ein neues, unverbrauchtes Zitat versucht wird

IMAGE_SIZE = (1080, 1080)  # Instagram-Standardformat (quadratisch)
BACKGROUND_COLORS = [
    (30, 30, 46),   # dunkelblau
    (24, 48, 43),   # dunkelgrün
    (46, 30, 46),   # dunkellila
    (48, 34, 24),   # dunkelbraun/orange
    (20, 20, 20),   # fast schwarz
]
TEXT_COLOR = (255, 255, 255)
AUTHOR_COLOR = (200, 200, 200)

# Auf GitHub-Actions-Runnern (ubuntu-latest) ist DejaVu Sans standardmäßig
# installiert. Lokal ggf. Pfad anpassen.
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ---------------------------------------------------------------------------
# Schritt 1: Bereits gepostete Zitate laden & neues, unverbrauchtes Zitat holen
# ---------------------------------------------------------------------------

def load_posted_quotes() -> set:
    if not POSTED_QUOTES_FILE.exists():
        return set()
    with open(POSTED_QUOTES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data)


def save_posted_quotes(posted_texts: set) -> None:
    with open(POSTED_QUOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(posted_texts), f, ensure_ascii=False, indent=2)


def fetch_quote_from_api() -> dict:
    response = requests.get(STOIC_API_SINGLE, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_quote_batch_from_api() -> list:
    response = requests.get(STOIC_API_BATCH, timeout=15)
    response.raise_for_status()
    return response.json()


def choose_unused_quote(posted_texts: set) -> dict:
    """Holt Zitate von der stoic-quotes.com API, bis eins gefunden wird,
    das noch nicht gepostet wurde. Fällt auf die lokale Backup-Liste
    zurück, falls die API nicht erreichbar ist."""

    # Zuerst versuchen, per Batch-Abruf schnell ein unverbrauchtes Zitat zu finden
    try:
        batch = fetch_quote_batch_from_api()
        random.shuffle(batch)
        for quote in batch:
            if quote["text"] not in posted_texts:
                return quote
    except requests.RequestException as e:
        print(f"WARNUNG: Batch-Abruf von stoic-quotes.com fehlgeschlagen: {e}")

    # Falls im Batch alles schon verbraucht war (oder Batch fehlschlug):
    # einzeln weiterprobieren (die API liefert bei jedem Aufruf ein neues Zufalls-Zitat)
    for attempt in range(MAX_FETCH_ATTEMPTS):
        try:
            quote = fetch_quote_from_api()
            if quote["text"] not in posted_texts:
                return quote
        except requests.RequestException as e:
            print(f"WARNUNG: API-Abruf fehlgeschlagen (Versuch {attempt + 1}): {e}")
            time.sleep(2)

    # Alle Zitate der API scheinen verbraucht -> Zyklus neu starten
    print("Alle bekannten Stoiker-Zitate wurden bereits gepostet. Starte neuen Zyklus.")
    posted_texts.clear()
    try:
        return fetch_quote_from_api()
    except requests.RequestException:
        pass

    # Letzter Ausweg: lokale Backup-Zitate verwenden
    print("WARNUNG: stoic-quotes.com nicht erreichbar. Nutze lokale Backup-Zitate.")
    with open(FALLBACK_QUOTES_FILE, "r", encoding="utf-8") as f:
        fallback_quotes = json.load(f)
    unused_fallback = [q for q in fallback_quotes if q["text"] not in posted_texts]
    return random.choice(unused_fallback or fallback_quotes)


# ---------------------------------------------------------------------------
# Schritt 2: Bild erzeugen
# ---------------------------------------------------------------------------

def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        print(f"WARNUNG: Font {path} nicht gefunden, nutze Standardfont.")
        return ImageFont.load_default()


def generate_quote_image(quote: dict) -> Path:
    IMAGES_DIR.mkdir(exist_ok=True)

    bg_color = random.choice(BACKGROUND_COLORS)
    img = Image.new("RGB", IMAGE_SIZE, color=bg_color)
    draw = ImageDraw.Draw(img)

    text = quote["text"]
    author = f"– {quote.get('author', 'Unbekannt')}"

    # Schriftgröße abhängig von der Textlänge wählen, damit lange Zitate passen
    if len(text) < 60:
        font_size = 70
    elif len(text) < 120:
        font_size = 54
    else:
        font_size = 42

    font_quote = load_font(FONT_BOLD_PATH, font_size)
    font_author = load_font(FONT_REGULAR_PATH, 34)

    wrap_width = max(10, int(IMAGE_SIZE[0] / (font_size * 0.55)))
    wrapped_lines = textwrap.wrap(text, width=wrap_width)

    # Textblock vertikal zentrieren
    line_height = font_size + 14
    total_text_height = len(wrapped_lines) * line_height
    y = (IMAGE_SIZE[1] - total_text_height) / 2 - 40

    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        line_width = bbox[2] - bbox[0]
        x = (IMAGE_SIZE[0] - line_width) / 2
        draw.text((x, y), line, font=font_quote, fill=TEXT_COLOR)
        y += line_height

    # Autor unter dem Zitat
    y += 30
    bbox = draw.textbbox((0, 0), author, font=font_author)
    author_width = bbox[2] - bbox[0]
    x = (IMAGE_SIZE[0] - author_width) / 2
    draw.text((x, y), author, font=font_author, fill=AUTHOR_COLOR)

    filename = f"post_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    output_path = IMAGES_DIR / filename
    img.save(output_path)
    print(f"Bild erstellt: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Schritt 3: Bild ins Repo committen & pushen (damit es öffentlich per URL
# erreichbar ist – Instagram benötigt zwingend eine öffentliche Bild-URL)
# ---------------------------------------------------------------------------

def commit_and_push_files(image_path: Path) -> str:
    subprocess.run(["git", "config", "user.name", "instagram-auto-poster-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
    subprocess.run(["git", "add", str(image_path), str(POSTED_QUOTES_FILE)], check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Automatischer Post: {image_path.name}"],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)

    raw_base = os.environ.get("GITHUB_REPOSITORY_RAW_BASE")
    if not raw_base:
        raise RuntimeError(
            "Umgebungsvariable GITHUB_REPOSITORY_RAW_BASE fehlt. "
            "Beispiel: https://raw.githubusercontent.com/<user>/<repo>/main"
        )

    image_url = f"{raw_base}/images/{image_path.name}"
    print(f"Öffentliche Bild-URL: {image_url}")

    # Kurze Pause, damit GitHub die Datei über raw.githubusercontent.com bereitstellt
    time.sleep(15)
    return image_url


# ---------------------------------------------------------------------------
# Schritt 4 & 5: Instagram Graph API - Media Container erstellen & veröffentlichen
# ---------------------------------------------------------------------------

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def build_caption(quote: dict) -> str:
    hashtags = (
        "#stoicism #stoic #marcusaurelius #seneca #epictetus "
        "#philosophy #wisdom #mindset #motivation #innerpeace"
    )
    return f"{quote['text']}\n— {quote.get('author', 'Unbekannt')}\n\n{hashtags}"


def create_media_container(ig_user_id: str, access_token: str, image_url: str, caption: str) -> str:
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload, timeout=30)
    response.raise_for_status()
    creation_id = response.json()["id"]
    print(f"Media-Container erstellt: {creation_id}")
    return creation_id


def publish_media(ig_user_id: str, access_token: str, creation_id: str) -> None:
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": access_token,
    }
    response = requests.post(url, data=payload, timeout=30)
    response.raise_for_status()
    print(f"Post veröffentlicht! Antwort: {response.json()}")


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main() -> None:
    ig_user_id = os.environ.get("IG_USER_ID")
    access_token = os.environ.get("IG_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        print(
            "FEHLER: IG_USER_ID und/oder IG_ACCESS_TOKEN sind nicht gesetzt. "
            "Siehe SETUP.md für die Einrichtung.",
            file=sys.stderr,
        )
        sys.exit(1)

    posted_texts = load_posted_quotes()
    print(f"Bereits geposteter Zitate: {len(posted_texts)}")

    quote = choose_unused_quote(posted_texts)
    print(f"Ausgewähltes Zitat: {quote['text']} – {quote.get('author')}")

    image_path = generate_quote_image(quote)

    # Zitat als "gepostet" vermerken, BEVOR wir committen, damit es
    # dauerhaft im Repo festgehalten wird
    posted_texts.add(quote["text"])
    save_posted_quotes(posted_texts)

    image_url = commit_and_push_files(image_path)
    caption = build_caption(quote)

    creation_id = create_media_container(ig_user_id, access_token, image_url, caption)
    publish_media(ig_user_id, access_token, creation_id)


if __name__ == "__main__":
    main()
