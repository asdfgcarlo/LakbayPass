# LakbayPass

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

This project currently lets users create an account, log in, explore a destination gallery, read destination details, scan mission QR cards to save points, and log out. Its broader product purpose and audience are not documented.

## Capabilities and Constraints

- Flask and Jinja templates, with MySQL persistence through Flask-MySQLdb.
- Login accepts email and password at `/` and `/login`.
- Registration accepts username, email, and password at `/register`.
- Successful registration returns to login; successful login opens `/dashboard`.
- The signed-in home at `/dashboard` is an infinite destination gallery with six places: Palawan (Mitra’s Ranch), Vigan (Calle Crisologo), Cebu (Binalayan Hidden Falls), Siquijor (Paliton Beach), Siargao (Sugba Lagoon), and Camiguin (Mantigue Island).
- All six destination JPGs are supplied in `static/destinations`. The shared `app.py` photo resolver retains an individual placeholder fallback for missing assets.
- Each whole tile is a real, same-tab destination link; recycled copies retain the same href. A click or tap opens the place, while pointer movement beyond 6px becomes a drag and suppresses navigation.
- The gallery supports drag/swipe, arrow keys and direction controls, plus Play/Pause. All tiles share a slow diagonal drift; dragging pauses movement and release restores the prior playback state. Reduced motion starts paused; without JavaScript, all six places remain available in a static gallery.
- `/destinations/<slug>` uses the dashboard login check: logged-out requests redirect to `/login`. Only `palawan`, `vigan`, `cebu`, `siquijor`, `siargao`, and `camiguin` render their matching `destinations/<slug>.html`; authenticated unknown slugs return 404.
- The six detail templates share a base with the destination photo, destination and attraction descriptions, a Back to gallery link, and mission values: Itinerary 10 pts, Local Foods 15 pts, Activities 20 pts. The list shows saved Claimed states and the account's total points.
- Scan a QR opens an inline live-camera scanner only on tap, prefers the rear camera, and automatically submits decoded mission QR text. Closing, Escape, hiding/leaving the page, or detecting a QR stops the camera, including permission requests that resolve late. JavaScript and a secure camera context are required.
- The 18 exact QR assignments are stored in MySQL. Each mission can be claimed once per account; repeated scans add zero points, and another account can claim the same mission once. The server verifies the signed-in user, CSRF token, destination, and stored mission value. Claimed states and totals come from saved claims, with distinct feedback for repeat, unknown, and wrong-destination scans.
- See [database setup and scanner verification](database/README.md) for the safe, rerunnable mission import, deployment requirements, and test commands. The import preserves existing card IDs and claims and stops on conflicting assignments.
- Email addresses must be unique. Username and email columns allow 100 characters.
- No password recovery flow currently exists.
- Preserve existing authentication storage and session behavior during this UI redesign.

## Brand Commitments

Use the user-supplied `static/lakbayLogo.png` for branding on the login and registration screens and as a centered decorative backdrop behind destination tiles on the dashboard.

The user requested minimalist authentication screens with subtle claymorphism, a warm off-white background, dark readable text, and white accents (confirmed in the design clarification). The dashboard shares this warm off-white palette and dark readable text.

## Accessibility & Inclusion

Both forms must work on small phones and wider screens, use persistent labels, visible keyboard focus, easy-to-tap controls, adjacent validation messages, and submission feedback.
The destination gallery must retain visible focus, controls at least 44px high, a stable accessible list of the six places, and user control over automatic motion. Exactly one tile per destination enters the keyboard tab order; focus reveals that tile and pauses drift until focus leaves. Destination pages retain a skip link, visible focus, descriptive photo text, and a responsive single-column layout on phones. The inline scanner moves focus to Close when opened, returns focus to Scan a QR when closed, supports Escape, and announces camera and claim feedback through polite live status messages.
