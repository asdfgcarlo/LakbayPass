# Mission cards and automatic claims

The existing local database is `lakbaypass` on MySQL/MariaDB. Flask uses
Flask-MySQLdb and the existing `users.id` login session. Database settings can be
overridden with `LAKBAYPASS_MYSQL_HOST`, `LAKBAYPASS_MYSQL_USER`,
`LAKBAYPASS_MYSQL_PASSWORD`, and `LAKBAYPASS_MYSQL_DB`.

From the project root in PowerShell:

```powershell
.\venv\Scripts\python.exe -m flask --app app import-mission-cards
```

This installs `schema.sql` using `CREATE TABLE IF NOT EXISTS`, then imports the
exact 18 assignments in `missions.py`. It inserts only missing cards. Running it
again preserves IDs and saved claims. It never uses REPLACE, deletes claims, or
changes existing card assignments/points. A conflicting QR, destination/mission
slot, point value, or duplicate QR is reported and stops the import before any
card inserts. Resolve conflicts explicitly; do not delete a claimed card to make
an import pass. Schema uniqueness additions also fail rather than remove rows
if an existing database contains duplicate claims.

`mission_cards.qr_code` is case-sensitive and unique. One card occupies each
`(destination_slug, mission_type)` slot. `point_claims` records `user_id`,
`mission_card_id`, `points_awarded`, and `claimed_at` (database timestamp).
The unique `(user_id, mission_card_id)` index is the concurrency guarantee.
Foreign keys preserve referenced cards/users. Point totals are always
`SUM(point_claims.points_awarded)`, with zero for a new player.

## HTTP flow

- The protected destination page reads saved mission progress and total points.
- **Scan a QR** opens an inline scanner and requests video only, preferring the
  rear camera. No camera request is made on page load. jsQR is self-hosted under
  `static/vendor`; camera frames remain in the browser.
- `POST /api/claims` accepts JSON `qr_code` and `destination_slug`, with a
  session CSRF token in `X-CSRF-Token`. The player ID comes only from the signed
  login session. Client-supplied point values, user IDs, and card IDs are ignored.
- The server looks up the exact QR and checks its destination, then inserts the
  claim with the card's stored point value. A duplicate-key error returns
  `already_claimed` and zero new points. A different account may claim it once.
- Successful and already-claimed responses return freshly queried mission
  states and total points. `GET /api/destinations/<slug>/missions` reads the same
  saved progress. Personalized responses use `Cache-Control: no-store`.
- Unknown QR, wrong destination, expired login/CSRF, network errors, and camera
  failures have distinct feedback. Closing, Escape, hiding/leaving the page,
  or finding a QR stops every camera track, including late permission results.

Camera access requires HTTPS, except trusted local development origins such as
`http://localhost:5000` or `http://127.0.0.1:5000`. A phone opening a plain HTTP
LAN address will need an HTTPS development URL. See
[the browser camera requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security).

The old public Flask signing-key placeholder has been replaced with a generated,
persistent `instance/secret_key` (ignored by version control). Set a stable,
private `LAKBAYPASS_SECRET_KEY` for deployment, shared across its app workers.
Existing sessions using the placeholder key need to log in again. Do not commit
or copy the local key into source control.

## Verification

```powershell
$env:LAKBAYPASS_TEST_MYSQL = '1'
.\venv\Scripts\python.exe -m unittest discover -s tests

# npm install playwright, or point to an existing package:
$env:PLAYWRIGHT_MODULE = 'C:\path\to\node_modules\playwright'
node tests/scanner.browser.cjs
node tests/destinations.browser.cjs
node tests/canvas.browser.cjs
```

The MySQL integration and scanner browser suites create a randomly named test
database and two test accounts inside it, then remove that test database. They
require CREATE DATABASE permission and never add claims to the app database.
The other Python tests mock database reads. The gallery browser regressions
read the installed mission table but do not write claims.

The scanner suite passes real QR pixels through canvas MediaStreams, the actual
jsQR decoder, HTTP, Flask, and MySQL. Only physical camera acquisition is
substituted. Camera permission states are simulated; a real phone/camera smoke
test remains a hardware check. The four pixel fixtures in
`tests/fixtures/mission-qr.json` were generated with Python `qrcode==8.2`, default
error correction, `box_size=1`, and `border=4`; no QR generator is needed at app
runtime or to run the committed browser suite.
