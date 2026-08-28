# Setup-Anleitung: Automatisierter Instagram Motivations-Poster

Diese Anleitung führt dich einmalig durch die komplette Einrichtung.
Danach postet das System jeden Tag automatisch ohne dein Zutun.

---

## 1. Instagram Business-Account einrichten

1. Öffne die Instagram-App → **Profil** → **Menü (☰)** → **Einstellungen und Privatsphäre**
2. **Konto** → **Zu professionellem Konto wechseln**
3. Wähle **Unternehmen** (nicht "Creator")
4. Folge dem Dialog bis zum Ende

## 2. Facebook-Seite verknüpfen

1. Falls du noch keine Facebook-Seite hast: [facebook.com/pages/create](https://facebook.com/pages/create) → neue Seite anlegen (kostenlos, Name ist frei wählbar)
2. In Instagram: **Einstellungen** → **Konto** → **Verlinkte Konten** → **Facebook** → deine Seite verknüpfen

## 3. Meta Developer Account & App erstellen

1. Gehe zu [developers.facebook.com](https://developers.facebook.com) und logge dich mit deinem Facebook-Account ein
2. **Meine Apps** → **App erstellen**
3. App-Typ: **Andere** → **Unternehmen**
4. Namen vergeben (z. B. "Mein Insta Auto Poster") → App erstellen

## 4. Instagram Graph API Produkt hinzufügen

1. In deiner neuen App: im linken Menü **Produkt hinzufügen** suchen
2. **Instagram Graph API** hinzufügen (bzw. je nach Dashboard-Version "Instagram" → "Graph API einrichten")
3. Verbinde im Dialog deine Facebook-Seite (aus Schritt 2) mit der App

## 5. Access Token generieren

1. Gehe zum **Graph API Explorer**: [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer)
2. Oben rechts: wähle deine App aus
3. **Berechtigungen hinzufügen**: mindestens
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
4. Klicke **Access Token generieren** und logge dich ein, falls gefragt
5. Du erhältst ein **kurzlebiges Token** (gültig ca. 1 Stunde) – das reicht noch nicht

### Kurzlebiges Token in ein langlebiges umwandeln (60 Tage gültig)

Führe folgenden Befehl aus (z. B. im Terminal, `curl` muss installiert sein), ersetze die Platzhalter:

```bash
curl -X GET "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=<APP_ID>&client_secret=<APP_SECRET>&fb_exchange_token=<KURZLEBIGES_TOKEN>"
```

- `APP_ID` und `APP_SECRET` findest du unter **App-Einstellungen** → **Grundlegendes**
- Das Ergebnis enthält dein **langlebiges Access Token** (60 Tage gültig)

> ⚠️ Nach 60 Tagen läuft das Token ab und muss erneuert werden (manuell mit demselben Befehl, oder du automatisierst das später zusätzlich).

## 6. Deine Instagram Business Account ID (IG_USER_ID) finden

Rufe im Browser folgende URL auf (mit deinem langlebigen Token):

```
https://graph.facebook.com/v21.0/me/accounts?access_token=<DEIN_TOKEN>
```

Das liefert deine verknüpfte Facebook-Seiten-ID. Rufe damit dann auf:

```
https://graph.facebook.com/v21.0/<SEITEN_ID>?fields=instagram_business_account&access_token=<DEIN_TOKEN>
```

Die zurückgegebene `id` ist deine **IG_USER_ID**.

## 7. Projekt auf GitHub hochladen

1. Erstelle einen kostenlosen Account auf [github.com](https://github.com), falls noch nicht vorhanden
2. Erstelle ein neues **privates** Repository (z. B. `instagram-auto-poster`)
3. Lade alle Dateien aus diesem Projekt hoch (per Weboberfläche "Upload files" oder per `git push`)

## 8. Secrets in GitHub hinterlegen

1. Im Repository: **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret** und folgende zwei Secrets anlegen:
   - `IG_USER_ID` → deine Instagram Business Account ID aus Schritt 6
   - `IG_ACCESS_TOKEN` → dein langlebiges Access Token aus Schritt 5

> Der `GITHUB_TOKEN` wird automatisch von GitHub Actions bereitgestellt, den musst du nicht selbst anlegen.

## 9. Testen

1. Im Repository: Tab **Actions** → Workflow **"Täglicher Instagram-Post"** auswählen
2. **Run workflow** klicken, um einen manuellen Testlauf zu starten
3. Prüfe die Logs – bei Erfolg erscheint der Post kurz darauf auf deinem Instagram-Profil

## 10. Fertig – läuft jetzt automatisch

Der Workflow läuft ab jetzt jeden Tag automatisch um 09:00 UTC (Zeile `cron: "0 9 * * *"`
in `.github/workflows/daily-post.yml` – kannst du beliebig anpassen).

---

## Wichtige Hinweise

- **Token-Ablauf:** Alle 60 Tage muss das Access Token erneuert werden (Schritt 5 wiederholen und Secret aktualisieren), sonst schlägt der Post fehl.
- **Rate Limits:** Meta erlaubt begrenzt viele Posts pro Tag – ein Post täglich ist unproblematisch.
- **Zitate erweitern:** Öffne `quotes.json` und füge beliebig viele weitere Zitate hinzu.
- **Design anpassen:** Farben, Schriftgrößen etc. lassen sich in `instagram_auto_poster.py` im Abschnitt "Konfiguration" anpassen.
- **Kosten:** Die Instagram Graph API selbst ist kostenlos. GitHub Actions ist für private Repos mit diesem geringen Nutzungsumfang ebenfalls im kostenlosen Kontingent.
