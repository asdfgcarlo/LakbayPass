# Database setup, mission cards, and automatic claims

Flask uses Flask-MySQLdb and the existing `users.id` login session. The database
connection settings are configured directly in `app.py`. The configured host is
`sql12.freesqldatabase.com`, database/user `sql12841075`, port `3306`.

Environment variables can override the settings in `app.py`:
`LAKBAYPASS_MYSQL_HOST`, `LAKBAYPASS_MYSQL_USER`,
`LAKBAYPASS_MYSQL_PASSWORD`, `LAKBAYPASS_MYSQL_DB`, and
`LAKBAYPASS_MYSQL_PORT`. The port must be an integer from 1 to 65535.
Connections use `utf8mb4` and a 10-second connection timeout. No additional
local database configuration file is required.

From the project root in PowerShell, install missing tables and mission cards
in the configured database, then start the app:

```powershell
.\venv\Scripts\python.exe -m flask --app app import-mission-cards
.\venv\Scripts\python.exe app.py
```

The hosted database must already exist; the import does not issue
`CREATE DATABASE`. The account needs permissions to create tables, read and
insert rows, and add unique indexes if existing tables lack them. Normal app
startup does not run the import. Changing the connection settings does not
transfer existing local users or claims: export and import that data separately
if it needs to be retained on the hosted database.

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
Foreign keys preserve referenced cards/users. Lifetime earned points are
`SUM(point_claims.points_awarded)`, with zero for a new player. Available points
subtract `SUM(reward_redemptions.points_spent)`. Redemption never changes or
deletes mission claims. Profile tiers and mission progress use lifetime earned
points; dashboard totals, mission API totals, and reward eligibility use the
remaining available balance.

Earned and spent totals are summed separately and cast to signed values before
subtraction. This also supports the hosted MySQL 5.5 server, where combining
unsigned awards with negative spending in a `UNION` can omit the deductions.

## Admin accounts

The `users.role` column is `user` or `admin`, defaulting to `user`. Public
registration always creates a regular user; a submitted role is ignored.
The import command adds this column to existing installations. To create the
designated admin and set its password, run after importing the schema:

```powershell
.\venv\Scripts\python.exe -m flask --app app setup-admin
```

The default email and password are both `admin@lakbay.pass`, as requested.
The password is stored in the same hashed format as existing accounts. The
command is rerunnable: it updates only the designated account's password and
role, preserving existing users, claims, and redemptions. Optional `--email` and
`--password` arguments select different credentials.

Admin login opens `/admin` (`templates/lakbayAdmin.html`). Every request checks
the saved database role; regular users receive 403. The page lists all accounts
(including admins), their available and lifetime earned points, and all reward
requests with their user, reference, cost, status, and server timestamp. It is
read-only and uses `Cache-Control: no-store`.

## Rewards and redemption

The same import command above adds the `reward_redemptions` table to an
existing database. Run it before starting an updated checkout. The three offers
are defined in `rewards.py`: eCert (90), 20% Discount for the New Card Game
(180), and Physical Keychain (270 points).

The protected `/redeem` page uses normal POST forms with a session CSRF token.
Prices and user identity come from the server. A transaction locks the user's
row before checking the current balance and recording the charge. A unique
`(user_id, request_key)` prevents a retried form or double click from charging
again. Separate purchases are allowed when the account has enough points.
Refreshing a page preserves pending request keys until a successful response.

Each record stores the reward name and cost at redemption time, a unique
reference, and `requested` status. The page shows the current user's saved
requests. Certificate delivery, discount activation, and keychain fulfillment
are handled separately; no certificate file, usable discount code, email, or
shipment is automatically issued by this feature.

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

Run the database-independent Python tests first:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```

The responsive browser suite uses synthetic local fixtures and never connects
to MySQL. With Playwright installed (or `PLAYWRIGHT_MODULE` pointing to its
package), run:

```powershell
node tests/responsive.browser.cjs
```

It checks all 12 pages at phone, tablet, landscape, and desktop widths, the
mobile menu, keyboard/touch navigation, current-point refresh, gallery playback,
long identities, zero/error states, and native navigation without JavaScript.
The fixture server and browser stop when the suite finishes. These are Chrome
emulation checks; physical phones and Safari are separate hardware/browser checks.

The hosted account may only have access to its supplied database. Run the MySQL
integration and scanner browser suites against a separate development MySQL
server/account with `CREATE DATABASE` permission, using the environment
overrides above:

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

To check balance deductions and simultaneous redemptions on the configured
hosted server, run the opt-in compatibility test:

```powershell
$env:LAKBAYPASS_TEST_LEGACY_MYSQL = '1'
.\venv\Scripts\python.exe -m unittest discover -s tests -p test_rewards_legacy_mysql.py
Remove-Item Env:\LAKBAYPASS_TEST_LEGACY_MYSQL
```

This test creates uniquely named disposable tables in the configured database
and drops them afterward. It requires `CREATE TABLE` and `DROP TABLE`
permissions; it never writes application users, mission claims, or redemptions.

The scanner suite passes real QR pixels through canvas MediaStreams, the actual
jsQR decoder, HTTP, Flask, and MySQL. Only physical camera acquisition is
substituted. Camera permission states are simulated; a real phone/camera smoke
test remains a hardware check. The four pixel fixtures in
`tests/fixtures/mission-qr.json` were generated with Python `qrcode==8.2`, default
error correction, `box_size=1`, and `border=4`; no QR generator is needed at app
runtime or to run the committed browser suite.
