#!/usr/bin/env python3
"""
instagram_auto_poster.py

Erstellt automatisch ein Motivations-Zitat-Bild und veröffentlicht es
über die Instagram Graph API auf einem Instagram Business-Account.

Ablauf:
1. Zufälliges Zitat aus quotes.json auswählen
2. Bild mit Zitat auf farbigem Hintergrund erzeugen (Pillow)
3. Bild ins Repo committen & pushen (damit es über eine öffentliche
   Raw-URL erreichbar ist -> Instagram braucht eine öffentliche Bild-URL)
4. Über die Instagram Graph API einen Media-Container erstellen
5. Media-Container veröffentlichen

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
QUOTES_FILE = REPO_ROOT / "quotes.json"
IMAGES_DIR = REPO_ROOT / "images"

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
# Schritt 1: Zitat auswählen
# ---------------------------------------------------------------------------

def choose_quote() -> dict:
    with open(QUOTES_FILE, "r", encoding="utf-8") as f:
        quotes = json.load(f)
    return random.choice(quotes)


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

def commit_and_push_image(image_path: Path) -> str:
    subprocess.run(["git", "config", "user.name", "instagram-auto-poster-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
    subprocess.run(["git", "add", str(image_path)], check=True)
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
        "#motivation #zitate #mindset #erfolg #selbstliebe "
        "#persönlichkeitsentwicklung #inspiration #ziele"
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

    quote = choose_quote()
    print(f"Ausgewähltes Zitat: {quote['text']} – {quote.get('author')}")

    image_path = generate_quote_image(quote)
    image_url = commit_and_push_image(image_path)
    caption = build_caption(quote)

    creation_id = create_media_container(ig_user_id, access_token, image_url, caption)
    publish_media(ig_user_id, access_token, creation_id)


if __name__ == "__main__":
    main()
