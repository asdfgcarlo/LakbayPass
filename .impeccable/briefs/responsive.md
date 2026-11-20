# Mobile account navigation and responsive layouts

Mode: Operate for account navigation, auth, profile, rewards and admin. Preserve
the gallery's established Experience mode and all existing destination content.

User request: hamburger menu for mobile containing Profile, Current Points,
Redeem Points and Log Out; fix responsiveness across the HTML/CSS surfaces.

Inherit the established warm off-white/white palette, system type, quiet borders,
and native navigation. A shared native details/summary menu replaces desktop
account actions through 767px on every signed-in page. Admins retain an additional
Admin Dashboard link. Menu points always mean available spendable balance.

The header stays compact with the welcome or gallery-return link opposite a
44px hamburger. The destination logo remains alongside the menu. An anchored
white panel has 48px rows, keyboard focus, explicit current-page state, and a
height limit for short screens. Escape, outside pointer/focus, selected links,
page departure and desktop resize close it. No modal or focus trap is needed.
Native links and disclosure work without JavaScript. Opening the menu pauses
gallery drift temporarily, preserving the user's playback choice. Scanner
progress refreshes both destination and menu balances.

Fix content reflow at the owning stylesheet: tablet destination images/stories
stack, tablet rewards use horizontal cards, phone mission checklists use labelled
rows, long content wraps, and auth/signed-in pages account for screen safe areas.
Desktop composition and supplied images, descriptions, and reward names remain.

Verify all 12 rendered routes at 320, 390, 600, 700, 767, 768, 844, 1024 and 1440px,
including short landscape, long identity text, zero progress, unavailable data,
native fallback, keyboard/touch navigation, current balance, and gallery gestures.
Use synthetic visual fixtures without connecting to the app database. Chromium
emulation and synthetic touch provide evidence; physical iOS/Android hardware
is outside the available verification. No new raster assets or design tokens.

## Verification completed

`tests/responsive.browser.cjs` passes all 12 routes at nine viewport sizes,
including the 767/768px navigation boundary and 600x320 landscape. It also passes
native link activation, touch and keyboard controls, Escape and outside close,
balance refresh after a restored destination page, temporary gallery pause,
desktop resize, zero/unavailable balances, and no-JavaScript navigation.

All 78 enabled Python tests pass; the provider-only compatibility test is skipped
in the isolated local MySQL run. The canvas and destination browser regressions
pass. Real QR pixels, HTTP and isolated MySQL claims pass the scanner browser
suite, including updates to the menu balance, repeat claims, camera failure and
cleanup states, and open-scanner layouts at 320/390/768/1440px. Its test database
name now stays below MySQL's lock-name limit, and its teardown reports early
fixture failures instead of hiding them behind an unresolved exit wait.

Twenty responsive captures under `review/responsive/` and six current scanner
captures were opened and verified. Lazy profile images were loaded before full
page captures; Chrome's transient tap highlight was allowed to settle for the
open-menu capture. The final polish pass found no material clipping, overlap,
missing content, or unreachable navigation in this tested scope.

The mechanical detector ran once: only inherited palette documentation advisories
and the standalone Jinja fragment's missing inherited text color were reported.
The new menu uses the existing auth/gallery tap highlight. DESIGN.md and its
sidecar remain unchanged; pre-existing drift was not repaired. Physical camera
hardware, physical phones and Safari remain outside the automated evidence.
