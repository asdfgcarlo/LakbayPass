# Destination pages

MODE: operate

The six protected `/destinations/<slug>` pages inherit the warm off-white, dark-text system from DESIGN.md. Each uses its existing destination photo, its own restrained accent, and short destination and attraction descriptions. `templates/destinations/base.html` shares the gallery return link, semantic mission list (Itinerary 10 pts, Local Foods 15 pts, Activities 20 pts), saved point total, and one Scan a QR action below the list. The inline scanner requests the rear camera on tap, automatically submits decoded QR text, and renders saved claimed states and totals.

Canvas tiles are native same-tab anchors, including captions and recycled copies. Pointer movement beyond 6px pans and suppresses navigation; taps and Enter open the destination. One representative of each destination enters the tab order, pauses drift during keyboard focus, and is brought into view when necessary.

## Scanner direction contract

THESIS: Claim a destination mission directly from its list, with a saved result visible in that same list. Extend the existing destination page rather than creating a separate scanner route.

OWN-WORLD: Retain warm off-white, white, charcoal, system typography, 10px controls, and existing destination accents. Use the established charcoal primary action; no new palette or decorative camera UI.

STORY: The signed-in player sees available or claimed missions and an account total, taps Scan a QR, grants camera access, and gets explicit saved points or a specific recoverable error. Claims are once per mission per account.

FIRST VIEWPORT: Preserve the photo/story composition. The mission list and account total lead into one Scan a QR action. The inline scanner expands underneath, with its title and Close action above the live preview. Hide the preview whenever the camera is stopped.

FORM: Code-led extension of the existing operate surface; no replacement visual world or concept roll. The signature interaction is real camera decoding followed by the exact row changing to Claimed and the saved account total updating. Review closed, camera-ready, submitting, claimed, duplicate, wrong/unknown QR, denied/missing/busy camera, late permission, small-phone, touch, and keyboard states.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Verification: 29 Python tests pass, including isolated MySQL tests for all 18 exact mappings, Cebu Local Foods +15, repeat +0, another account +15, eight simultaneous claims, import reruns, conflict detection, and uniqueness constraints. `tests/scanner.browser.cjs` passes real QR pixels through actual jsQR/video/HTTP/MySQL with substituted camera acquisition; it verifies six scanner entry points, camera errors/cleanup, keyboard/touch operation, saved reload, and widths 320/390/768/1440. The gallery destination browser regressions pass. Scanner captures live in `.impeccable/review/scanner-*.png`; their blank white live previews are deliberate test camera frames, never failed asset loads. No new shipping photos or raster assets were created.

Final finish-review disposition: **ship**, with no material findings in the reviewed UI/implementation scope. All six scanner captures and the documentation handoff were verified. `tests/canvas.browser.cjs` also passes, preserving drift, seamless loops, fixed tile counts, dragging, touch, and keyboard controls. Physical camera hardware remains outside the automated evidence. PRODUCT.md and DESIGN.md describe the finished scanner without changing the incumbent design tokens or sidecar.

Description references:

- [Puerto Princesa tourism: Mitra Ranch](https://citytourism.puertoprincesa.ph/mitra-ranch/)
- [UNESCO: Vigan](https://whc.unesco.org/en/list/502/)
- [Cebu tourism: Samboan](https://tourism.cebu.gov.ph/explore/samboan/)
- [Siquijor provincial tourism](https://siquijorprovince.com/siquijor-mountain-tour/)
- [Surigao del Norte: island destinations](https://surigaodelnorte.gov.ph/island-destination/)
- [Camiguin: where to go](https://camiguin.gov.ph/where-to-go/)
