# Profile memories

Mode: Operate. Extend the existing profile with private photos for the signed-in
traveler. Keep the current profile identity, points, and destination progress.

## Direction contract

THESIS: travelers collect photos with their own captions, review them before
saving, then revisit or manage each memory directly from their profile.

OWN-WORLD: inherit the warm off-white page, white controls, charcoal system
type, quiet dividers, 10px controls, and existing visible keyboard focus.

STORY: open Add Memories, choose one to three photos together or separately,
caption and remove previews, then save a private gallery. A larger native
dialog holds the photo, its description, and owner edit/delete controls.

FIRST VIEWPORT: preserve the existing split profile overview. Immediately below,
the Your memories heading and Add Memories action introduce the new gallery
before destination progress. Desktop has three photo columns; phones have one.

FORM: ordinary feature extension, code-led with no concept roll or approved comp.
The inline upload form keeps selections in view and native dialog protects focus
for the larger photo. No new imagery, animation, palette, or design token system.
seed: none (ordinary extension)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Verify desktop and phone: empty, upload previews, minimum-count error, add/remove,
cancel, saved gallery, larger image, editing/deleting, failure and busy feedback,
keyboard focus and Escape. Verify ownership, CSRF, image validation and rollback
with isolated fixtures. No production database writes during verification.

## Completed verification and review

The memories browser flow passed at 320, 390, 600, 768, 1024 and 1440px,
including incremental/multiple selection, preview removal, the exact minimum
error, the three-photo selection cap, cancel, retained input after a failed save,
persisted single-photo submissions and captions/gallery,
larger views, owner edit/delete, cross-account denial and keyboard/Escape focus.
Deletion with a new unsaved batch open preserves that batch and restores focus
to the visible picker. Seven validated captures are under `review/memories/`.

Fresh finish review: **ship** at the scope of its one resolved focus finding;
the preceding full review found no visual blockers. Independent storage review
also resolved its rollback-failure finding; deletion restores a staged photo even
when the database connection fails during rollback. The 17 memories tests use
real image decoding, private temporary files and an isolated SQL adapter.

The non-destructive `install-memories` migration succeeded against the configured
MySQL database. No existing account, points, claims or rewards were modified.
Runtime browser verification used disposable storage rather than hosted users.
The full Python suite has 96 tests: 75 passed and 21 opt-in database tests skipped.

The requested 1–3 photo limit is enforced by the form and server. Follow-up
browser verification passed zero-photo validation, rejection of a fourth selected
photo, successful single-photo saving across reloads, and the existing gallery
management flow. Scoped finish review: **ship** for this limits change. The
existing design tokens and composition remain unchanged.

The detector ran once. Jinja stylesheet resolution caused false default-color
and type warnings; the hidden viewer image receives its source before opening.
The new error/delete text now uses the established #963c35. The inherited green
and divider sidecar drift predates the feature and remains unchanged.

Documenter check: DESIGN.md and `.impeccable/design.json` continue to describe
the inherited palette, system type, charcoal buttons, white controls, 10px control
corners and visible focus. Gallery/dialog composition stays scoped to this route.
No new shipping raster assets or global tokens were introduced.
