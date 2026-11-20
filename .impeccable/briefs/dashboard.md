# Infinite destination canvas

MODE: experience
FORM: User-pinned warm off-white infinite gallery, based on the supplied Webflow Infinite Canvas live demo. Build directly in the existing Flask/Jinja app; keep authentication and logout navigation.

## Direction contract

- Warm off-white, full-viewport gallery matching login and registration, with dark readable captions, white controls, large landscape rectangles, and generous gaps. Tiles cross the viewport edges.
- Center `static/lakbayLogo.png` as a fixed decorative watermark behind every tile, with pointer events disabled. Use 0.16 opacity and width min(980px, 145vw). Keep caption surfaces solid warm off-white for text contrast. Place compact playback and four directional buttons at the bottom; preserve the signed-in welcome and logout link.
- Repeat the six specified destinations in a three-column, two-row logical pattern. All six actual destination JPGs are present; keep the labeled neutral placeholder as an individual missing-image fallback.
- Make each whole photo/caption tile a real same-tab link; repeated copies reuse its href. Click/tap opens the place, while pointer movement beyond 6px becomes a drag and suppresses navigation.
- One global position drives every tile at −15px/s horizontally and −5px/s vertically. Recycle a bounded tile pool; rebuild only when responsive pool dimensions change.
- Mouse/touch dragging pauses drift without changing the selected playback state. Arrow keys, direction buttons, Play/Pause, and Space on the gallery are keyboard accessible.
- Reduced motion starts paused and can be explicitly played. Pause animation offscreen or in a hidden tab; resume without time jumps.
- Keep all controls at least 44px and within the viewport, including small phones. Provide a stable, nonduplicated destination list for assistive technology and a six-tile static fallback without JavaScript.
- Keep exactly six keyboard tile representatives, one per destination. Reveal a focused tile within the viewport and pause drift until its focus leaves.

## Destination pages

- Protect `/destinations/<slug>` with the same login check as the dashboard. Only `palawan`, `vigan`, `cebu`, `siquijor`, `siargao`, and `camiguin` render their matching detail templates; authenticated unknown slugs return 404.
- All six extend `destinations/base.html`: photo hero, destination and attraction descriptions, Back to gallery, and a shared mission list (Itinerary 10 pts, Local Foods 15 pts, Activities 20 pts). No scanner exists; retain the disabled “Scanner coming soon” action.
- `static/destination.css` uses warm off-white/white surfaces and a 1160px maximum shell; the split overview and mission columns stack at 680px. Mission points, the mission-list top border, and text selection use scoped accents: Palawan #3d5a36, Vigan #795833, Cebu #24645c, Siquijor #87613b, Siargao #21606b, Camiguin #245d7b.

## Asset replacement

The six expected JPGs are supplied in `static/destinations`. Gallery and detail pages share the server photo resolver and its individual fallback; the gallery also handles failed image loads in the browser.

## Verification evidence

- Route regression suite: 19 tests, including all six detail templates, photos, mission values, gallery return links, disabled scanner state, login protection, and unknown-slug 404s.
- Browser suite `tests/canvas.browser.cjs`: complete multi-period two-axis movement is pixel identical; visible nodes move continuously across the wrap boundary; real-time drift matches 15px/5px per second; tile count and child nodes remain stable during animation.
- Mouse drag, native CDP touch swipe, autoplay pause during drag/resume after release, paused dragging, directional buttons, arrow keys, reduced-motion initialization and preference changes, cancellation, static fallback, and responsive control bounds are exercised.
- Rendered viewports: 1440×900, 768×1024, 390×844, 320×568; screenshots in `.impeccable/review/canvas-<width>.png`.
