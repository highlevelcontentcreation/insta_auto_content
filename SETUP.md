# Setup-Anleitung: KI-generierte türkische "Interessante Fakten"-Instagram-Seite

Dieses Projekt postet täglich automatisch:
- ein neues, KI-generiertes interessantes Fakten-Thema (Wissenschaft, Geschichte, Psychologie, Natur, Weltraum, Kultur, Kuriositäten)
- als fotorealistisches KI-Bild mit kurzer türkischer Hook-Überschrift
- inklusive türkischer Caption mit Hashtags

**Komplett kostenlos:** Text via Google Gemini API (Free-Tier), Bild via Pollinations.ai (kein Key nötig).

---

## 1-7: Instagram/Facebook/GitHub Grundeinrichtung

Diese Schritte sind identisch zum vorherigen Projekt (Instagram Business-Account, Facebook-Seite verknüpfen, Meta Developer App, Instagram Graph API Produkt hinzufügen, Access Token generieren, IG_USER_ID finden, GitHub Repo erstellen). Falls du das bereits für einen anderen Account eingerichtet hast, kannst du App/Token wiederverwenden oder ein neues Set für diesen Account anlegen.

**Kurzfassung (Details siehe ggf. vorherige Anleitung):**
1. Instagram-Account → Professionelles Konto → Unternehmen
2. Facebook-Seite erstellen & mit Instagram verknüpfen
3. App auf developers.facebook.com erstellen (Anwendungsfall: Content-Management)
4. Produkt "Instagram Graph API" hinzufügen, mit der Facebook-Seite verbinden
5. Im Graph API Explorer ein User-Token generieren mit: `instagram_business_basic`, `instagram_business_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`
6. Kurzlebiges Token in ein langlebiges (60 Tage) umwandeln:
   ```bash
   curl -X GET "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=<APP_ID>&client_secret=<APP_SECRET>&fb_exchange_token=<KURZLEBIGES_TOKEN>"
   ```
7. IG_USER_ID ermitteln:
   ```
   https://graph.facebook.com/v21.0/me/accounts?access_token=<TOKEN>
   https://graph.facebook.com/v21.0/<SEITEN_ID>?fields=instagram_business_account&access_token=<TOKEN>
   ```

## 8. Kostenlosen Gemini API-Key erstellen

1. Gehe zu [aistudio.google.com](https://aistudio.google.com) und logge dich mit einem Google-Konto ein
2. Klicke auf **"Get API key"** (meist oben links oder im Menü)
3. **"Create API key"** → neues Projekt wählen oder erstellen lassen
4. Der generierte Key beginnt meist mit `AIza...` – kopiere ihn

**Keine Kreditkarte, kein Google Cloud Billing nötig** für den Free-Tier (Flash-Modelle).

## 9. Repository erstellen & Projektdateien hochladen

1. Neues (öffentliches – wichtig, damit `raw.githubusercontent.com` die Bilder ausliefern kann) GitHub-Repository erstellen
2. Alle Dateien dieses Projekts in den **Root-Ordner** hochladen (inkl. `.github/workflows/daily-post.yml` – als eigene Datei mit exakt diesem Pfad anlegen, siehe Hinweis unten)

**Wichtig:** Der Ordner `.github/workflows/daily-post.yml` muss beim Hochladen über GitHub als **Dateiname mit Pfad** angelegt werden (Add file → Create new file → Dateiname: `.github/workflows/daily-post.yml`), da man Ordner nicht direkt hochladen kann.

## 10. GitHub Secrets hinterlegen

**Settings → Secrets and variables → Actions → New repository secret:**

| Name | Wert |
|---|---|
| `IG_USER_ID` | deine Instagram Business Account ID |
| `IG_ACCESS_TOKEN` | dein langlebiges Access Token |
| `GEMINI_API_KEY` | dein Gemini API-Key aus Schritt 8 |

## 11. Testen

**Actions**-Tab → **"Täglicher Instagram-Post"** → **"Run workflow"**. Logs prüfen, bei Erfolg erscheint der Post kurz danach auf Instagram.

---

## Wichtige Hinweise

- **Token-Ablauf:** Access Token alle 60 Tage erneuern (Schritt 6), sonst schlägt der Post fehl.
- **Themen-Wiederholung:** `posted_topics.json` merkt sich alle bereits verwendeten Themen und wird Gemini als Kontext mitgegeben, damit keine Wiederholungen entstehen. Das ist ein KI-basierter Best-Effort-Mechanismus (kein 100%-Garant wie bei exakten Zitaten), funktioniert aber in der Praxis gut.
- **Pollinations.ai Zuverlässigkeit:** Kein SLA, kein Uptime-Versprechen. Schlägt ein Lauf mal fehl (z. B. Bild-API kurzzeitig nicht erreichbar), postet der nächste tägliche Lauf einfach normal weiter – kein manuelles Eingreifen nötig.
- **Gemini Free-Tier Limits:** Bei 1 Post/Tag bist du weit von jedem Limit entfernt (Free-Tier erlaubt i.d.R. mehrere Anfragen pro Minute).
- **Bildstil anpassen:** Der Bild-Prompt wird von Gemini automatisch generiert. Willst du einen bestimmten visuellen Stil erzwingen (z. B. "immer warme Farbtöne"), ergänze das in `build_gemini_prompt()` in `instagram_auto_poster.py`.
- **Hashtags/Caption-Stil anpassen:** Ebenfalls in `build_gemini_prompt()` anpassbar.
- **Kosten:** 0 € – Instagram Graph API, Gemini Free-Tier und Pollinations sind alle kostenlos nutzbar.
