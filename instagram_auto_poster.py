#!/usr/bin/env python3
"""
instagram_auto_poster.py

Erstellt automatisch einen türkischen "interessante Fakten"-Post im Stil
von Karussell-/Fakten-Seiten (Hook-Überschrift + fotorealistisches
KI-Bild) und veröffentlicht ihn über die Instagram Graph API.

Ablauf:
1. Google Gemini API (kostenloser Free-Tier) generiert:
   - ein neues, noch nicht verwendetes Thema
   - eine kurze, knackige türkische Hook-Überschrift
   - eine türkische Instagram-Caption mit Hashtags
   - einen englischen Bild-Prompt für die Bild-KI
2. Pollinations.ai (kostenlos, kein API-Key) erzeugt ein fotorealistisches
   Bild passend zum Thema
3. Die Hook-Überschrift wird mit Pillow über das Bild gelegt
4. Bild wird ins Repo committet & gepusht (öffentliche Raw-URL nötig,
   damit Instagram das Bild laden kann)
5. Über die Instagram Graph API wird der Post veröffentlicht
6. Erst nach Erfolg: Thema als "verwendet" vermerkt (posted_topics.json)

Benötigte Umgebungsvariablen (siehe SETUP.md):
- IG_USER_ID       -> Instagram Business Account ID
- IG_ACCESS_TOKEN  -> Langlebiges Meta/Instagram Access Token
- GEMINI_API_KEY   -> Kostenloser Google AI Studio API-Key
- GITHUB_REPOSITORY_RAW_BASE -> z.B. https://raw.githubusercontent.com/<user>/<repo>/main
"""

import json
import os
import random
import subprocess
import sys
import textwrap
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent
POSTED_TOPICS_FILE = REPO_ROOT / "posted_topics.json"
IMAGES_DIR = REPO_ROOT / "images"

IMAGE_SIZE = (1080, 1080)  # Instagram-Standardformat (quadratisch)
TEXT_COLOR = (255, 255, 255)

FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

MAX_POSTED_TOPICS_IN_PROMPT = 60  # so viele zuletzt genutzte Themen werden Gemini als Kontext mitgegeben


# ---------------------------------------------------------------------------
# Schritt 1: Bereits verwendete Themen laden / speichern
# ---------------------------------------------------------------------------

def load_posted_topics() -> list:
    if not POSTED_TOPICS_FILE.exists():
        return []
    with open(POSTED_TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_posted_topics(topics: list) -> None:
    with open(POSTED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Schritt 2: Gemini API - neues Thema + türkische Texte + Bild-Prompt generieren
# ---------------------------------------------------------------------------

def build_gemini_prompt(recent_topics: list) -> str:
    avoid_list = ", ".join(recent_topics[-MAX_POSTED_TOPICS_IN_PROMPT:]) or "(noch keine)"
    return f"""Sen viral bir Instagram "ilginç bilgiler" sayfası için içerik üretiyorsun.
Konu havuzu: bilim, tarih, psikoloji, uzay, doğa, teknoloji, kültür, ilginç gerçekler.

Daha önce kullanılan konular (bunları TEKRARLAMA, tamamen farklı ve yeni bir konu seç):
{avoid_list}

Görev: SADECE aşağıdaki alanları içeren geçerli bir JSON nesnesi döndür, başka hiçbir şey yazma:

{{
  "topic": "Konunun kısa İngilizce özeti (tekrar kontrolü için, örn. 'octopus three hearts')",
  "hook": "Görselin üzerine yazılacak, MAKSİMUM 8 kelimelik çok kısa, merak uyandırıcı Türkçe başlık",
  "caption": "Instagram gönderisi için 2-3 cümlelik ilginç, akıcı Türkçe açıklama metni, sonuna 5-8 alakalı Türkçe/İngilizce hashtag ekle",
  "image_prompt": "Detailed English prompt for a photorealistic AI image illustrating this fact, cinematic lighting, no text or letters in the image, high quality photography style"
}}

Kurallar:
- "hook" çok kısa ve dikkat çekici olmalı (max 8 kelime, başlık gibi)
- Gerçek, doğrulanabilir ve ilginç bir bilgi seç
- JSON dışında hiçbir açıklama, markdown veya kod bloğu ekleme"""


def call_gemini(prompt: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Umgebungsvariable GEMINI_API_KEY fehlt.")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 1.1,
        },
    }
    response = requests.post(
        f"{GEMINI_API_URL}?key={api_key}",
        json=payload,
        timeout=30,
    )
    if not response.ok:
        print(f"FEHLERDETAILS von Gemini: {response.text}")
    response.raise_for_status()

    data = response.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

    # Defensive: falls das Modell trotz Anweisung Markdown-Codeblöcke liefert
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]

    return json.loads(cleaned)


def generate_content(posted_topics: list) -> dict:
    prompt = build_gemini_prompt(posted_topics)
    content = call_gemini(prompt)

    required_keys = {"topic", "hook", "caption", "image_prompt"}
    if not required_keys.issubset(content.keys()):
        raise ValueError(f"Gemini-Antwort unvollständig: {content}")

    return content


# ---------------------------------------------------------------------------
# Schritt 3: Bild via Pollinations.ai erzeugen
# ---------------------------------------------------------------------------

def fetch_pollinations_image(image_prompt: str) -> bytes:
    encoded_prompt = urllib.parse.quote(image_prompt)
    seed = random.randint(1, 1_000_000)
    url = POLLINATIONS_URL.format(prompt=encoded_prompt)
    params = {
        "width": IMAGE_SIZE[0],
        "height": IMAGE_SIZE[1],
        "model": "flux",
        "seed": seed,
        "nologo": "true",
    }
    response = requests.get(url, params=params, timeout=90)
    response.raise_for_status()
    return response.content


# ---------------------------------------------------------------------------
# Schritt 4: Hook-Text über das Bild legen
# ---------------------------------------------------------------------------

def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        print(f"WARNUNG: Font {path} nicht gefunden, nutze Standardfont.")
        return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int):
    for font_size in range(90, 27, -2):
        font = load_font(FONT_BOLD_PATH, font_size)
        avg_char_width = font.getlength("Abcdefghij") / 10 or 1
        wrap_width = max(4, int(max_width / avg_char_width))
        lines = textwrap.wrap(text, width=wrap_width)

        too_wide = any(
            (draw.textbbox((0, 0), line, font=font)[2]) > max_width for line in lines
        )
        if too_wide:
            continue

        line_height = font_size + 14
        if len(lines) * line_height <= max_height:
            return font, lines, line_height

    font = load_font(FONT_BOLD_PATH, 28)
    avg_char_width = font.getlength("Abcdefghij") / 10 or 1
    wrap_width = max(4, int(max_width / avg_char_width))
    lines = textwrap.wrap(text, width=wrap_width)
    return font, lines, 28 + 14


def create_post_image(image_bytes: bytes, hook_text: str) -> Path:
    IMAGES_DIR.mkdir(exist_ok=True)

    img = Image.open(__import__("io").BytesIO(image_bytes)).convert("RGB")
    img = img.resize(IMAGE_SIZE)

    # Dunkler Verlauf am unteren Bildrand für bessere Lesbarkeit des Textes
    overlay = Image.new("RGBA", IMAGE_SIZE, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    threshold_y = int(IMAGE_SIZE[1] * 0.5)
    for y in range(threshold_y, IMAGE_SIZE[1]):
        t = (y - threshold_y) / (IMAGE_SIZE[1] - threshold_y)
        alpha = int(210 * t)
        overlay_draw.line([(0, y), (IMAGE_SIZE[0], y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    max_width = int(IMAGE_SIZE[0] * 0.86)
    max_height = int(IMAGE_SIZE[1] * 0.32)
    font, lines, line_height = _fit_text(draw, hook_text, max_width, max_height)

    total_text_height = len(lines) * line_height
    y = IMAGE_SIZE[1] - total_text_height - 90

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (IMAGE_SIZE[0] - line_width) / 2
        # Leichter Schlagschatten für Lesbarkeit
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=TEXT_COLOR)
        y += line_height

    filename = f"post_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
    output_path = IMAGES_DIR / filename
    img.save(output_path, quality=90)
    print(f"Bild erstellt: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Schritt 5: Bild ins Repo committen & pushen
# ---------------------------------------------------------------------------

def git_commit_and_push(paths: list, message: str) -> None:
    subprocess.run(["git", "config", "user.name", "instagram-auto-poster-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)
    subprocess.run(["git", "add", *[str(p) for p in paths]], check=True)
    result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Hinweis: git commit übersprungen (evtl. keine Änderungen): {result.stdout}{result.stderr}")
        return
    subprocess.run(["git", "push"], check=True)


def commit_and_push_image(image_path: Path) -> str:
    git_commit_and_push([image_path], f"Automatischer Post: {image_path.name}")

    raw_base = os.environ.get("GITHUB_REPOSITORY_RAW_BASE")
    if not raw_base:
        raise RuntimeError(
            "Umgebungsvariable GITHUB_REPOSITORY_RAW_BASE fehlt. "
            "Beispiel: https://raw.githubusercontent.com/<user>/<repo>/main"
        )

    image_url = f"{raw_base}/images/{image_path.name}"
    print(f"Öffentliche Bild-URL: {image_url}")

    time.sleep(15)
    return image_url


# ---------------------------------------------------------------------------
# Schritt 6: Instagram Graph API - Media Container erstellen & veröffentlichen
# ---------------------------------------------------------------------------

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def create_media_container(ig_user_id: str, access_token: str, image_url: str, caption: str) -> str:
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media"
    payload = {"image_url": image_url, "caption": caption, "access_token": access_token}
    response = requests.post(url, data=payload, timeout=30)
    if not response.ok:
        print(f"FEHLERDETAILS von Instagram: {response.text}")
    response.raise_for_status()
    creation_id = response.json()["id"]
    print(f"Media-Container erstellt: {creation_id}")
    return creation_id


def publish_media(ig_user_id: str, access_token: str, creation_id: str) -> None:
    url = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
    payload = {"creation_id": creation_id, "access_token": access_token}
    response = requests.post(url, data=payload, timeout=30)
    if not response.ok:
        print(f"FEHLERDETAILS von Instagram: {response.text}")
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

    posted_topics = load_posted_topics()
    print(f"Bereits verwendete Themen: {len(posted_topics)}")

    content = generate_content(posted_topics)
    print(f"Neues Thema: {content['topic']}")
    print(f"Hook: {content['hook']}")

    image_bytes = fetch_pollinations_image(content["image_prompt"])
    image_path = create_post_image(image_bytes, content["hook"])
    image_url = commit_and_push_image(image_path)

    creation_id = create_media_container(ig_user_id, access_token, image_url, content["caption"])
    publish_media(ig_user_id, access_token, creation_id)

    # Erst NACH erfolgreichem Post das Thema dauerhaft als "verwendet" vermerken
    posted_topics.append(content["topic"])
    save_posted_topics(posted_topics)
    git_commit_and_push([POSTED_TOPICS_FILE], f"Thema als gepostet markiert: {content['topic']}")


if __name__ == "__main__":
    main()
