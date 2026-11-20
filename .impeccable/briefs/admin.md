# Admin dashboard

Mode: Operate. Extend the established LakbayPass visual system.

Purpose: an administrator can view every registered account, available and
lifetime earned points, and saved reward redemptions with user and reference.
The user confirmed showing both point totals. Total users includes all accounts,
including admins, and the page states this definition.

Direction: keep the warm off-white page, charcoal system typography, white table
headers, quiet rules, and established 44px navigation targets. Two stacked data
sections keep users and redemptions directly scannable. On phones each table row
becomes a labelled two-column record without horizontal scrolling. No imagery,
charts, new palette, animations, or design-system replacement is needed.

## Direction contract

THESIS: user balances and redemption references are legible records, without
charts or a grid of metric cards standing in for the requested lists.

OWN-WORLD: inherit LakbayPass warm off-white, charcoal system typography, white
table headers, fine dividers, and visible focus. No design token changes.

STORY: sign in as admin, see all registered accounts and both balances, then
match a reward request to its user and reference. Database roles guard access.

FIRST VIEWPORT: a 32px Admin dashboard heading and introduction lead to native
section links, a 24px All users heading, total count, and the user table. Desktop
columns align balances; phone rows stack into labelled two-column records.

FORM: the precisely specified data dashboard extends the existing app; no
concept roll is required. Code-led, without an approved comp. Native anchors
move between the two sections; header links return to the gallery or log out.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Empty redemption history, forbidden access, and service errors have explicit
messages. Native links work without JavaScript. Access is checked from the
database role on every request; login sends admins directly here.

Verification: desktop and mobile renders, long account names/emails, zero
redemptions, non-admin denial, expired/deleted account, server error, fresh-role
checking, and actual MySQL balance aggregation. Preserve DESIGN.md and its tokens.

## Shipped review and verification

Finish review: **ship**. The fresh reviewer returned all five contract sections,
found no material fixes, and confirmed the inherited visual system. The shipped
surface uses native anchors, two record sections, and labelled mobile rows;
DESIGN.md and `.impeccable/design.json` remain unchanged. No new shipping raster
was introduced.

Verification completed: 79 Python tests, 78 passed and one opt-in hosted
compatibility test skipped, including 12 new admin cases and real-database
coverage. The migration and rerunnable admin setup succeeded on the hosted
MySQL 5.5 database; five accounts remained, real admin login passed, and existing
account fields, balances, cards, claims, and redemptions were preserved.

Browser checks covered 320, 390, 700, 701, 900, and 1440px widths; native
navigation, real login, regular-user 403, empty history, long usernames/emails,
both balances, and references passed. Validated captures:
[desktop](../review/admin-desktop.png), [mobile](../review/admin-mobile.png),
[empty mobile](../review/admin-empty-mobile.png), and
[forbidden mobile](../review/admin-forbidden-mobile.png).

The detector ran once. Its Jinja stylesheet-resolution findings were false
positives: the rendered CSS supplies the 32/24/16px heading/body hierarchy and
inherited palette. Pre-existing design-file drift remains outside this ordinary
Operate extension and was neither canonized nor repaired.
