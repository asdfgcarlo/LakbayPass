# LakbayPass

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

This project currently lets users create an account, log in, explore a destination gallery, read destination details, scan mission QR cards to save points, redeem rewards, and log out. Administrators can inspect registered accounts, point balances, and reward redemptions. Its broader product purpose and audience are not documented.

## Capabilities and Constraints

- Flask and Jinja templates, with MySQL persistence through Flask-MySQLdb.
- Login accepts email and password at `/` and `/login`.
- Registration accepts username, email, and password at `/register` and explicitly creates a regular user. `users.role` is `user` or `admin`, defaulting to `user`.
- Successful registration returns to login. Successful login clears the previous session and opens `/admin` for admins or `/dashboard` for regular users.
- The dashboard welcome/username link returns admins to `/admin` and opens the protected `/profile` page for regular users. The profile shows the current database username, awarded points out of 270, Bronze (0–90), Silver (91–180), or Gold (181–270) tier, and all six destinations with three named mission claim statuses each. A destination counts as visited once at least one mission is claimed. Profile reads never change claims; new users see zero progress, and unavailable data has a retry state.
- Through 767px, every signed-in page has a shared hamburger menu with Profile, Current Points (the available balance), Redeem Points, and Log Out. Admins also retain Admin Dashboard. Native disclosure and links work without JavaScript; Escape, outside pointer/focus, selection, page departure, and desktop resize close the enhanced menu. It temporarily pauses gallery movement while preserving the user's playback choice. Scanner results refresh both the page and menu balances; unavailable data is labelled instead of displaying zero.
- `/admin` is read-only. It lists every registered account, including admins, with username, email, role, available points, and lifetime earned points; its total-user count explicitly includes admins. It also lists every saved reward redemption, newest first, with username, email, reward, reference, points spent, status, and server timestamp. Native section links, Back to gallery, and Log out work without JavaScript.
- Every `/admin` request checks the current database role. Regular users receive 403; logged-out or deleted accounts return to login; database failures show a 503 retry state. Admin page responses use `Cache-Control: no-store`.
- The rerunnable `setup-admin` CLI installs roles and creates or updates only the selected admin account. Its requested default email and password are both `admin@lakbay.pass`; options select different credentials. The mission import also installs the role column. See [database setup](database/README.md) for commands; existing accounts, point balances, mission cards, claims, and redemptions are preserved.
- Redeem Point sits between the dashboard balance and Logout and opens `/redeem`: eCert (90 pts), 20% Discount for the New Card Game (180 pts), and Physical Keychain (270 pts). Successful redemptions deduct the available balance, store a request and reference, and preserve lifetime earned points, tiers, and mission completion. Repeated submissions charge once; concurrent purchases cannot overspend. Reward fulfillment is separate from recording a redemption.
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
Mobile account navigation uses a 44px hamburger and 48px rows, with a scrollable height limit on short screens. Tablet destination stories and images stack through 900px; tablet reward cards use horizontal rows, and phone profile missions show each mission with its status on a separate row. Layouts include safe-area padding and long-text wrapping.
The destination gallery must retain visible focus, controls at least 44px high, a stable accessible list of the six places, and user control over automatic motion. Exactly one tile per destination enters the keyboard tab order; focus reveals that tile and pauses drift until focus leaves. Destination pages retain a skip link, visible focus, descriptive photo text, and a responsive single-column layout on phones. The inline scanner moves focus to Close when opened, returns focus to Scan a QR when closed, supports Escape, and announces camera and claim feedback through polite live status messages.
The admin dashboard retains a skip link, visible focus, and at least 44px navigation targets. On phones, tables become labelled records with both point balances and redemption references visible, and long names and emails wrap without horizontal scrolling.
