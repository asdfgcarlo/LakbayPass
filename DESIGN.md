---
name: LakbayPass
description: Quiet clay authentication and a warm off-white destination canvas.
colors:
  page: "#f5f3ee"
  card: "#ffffff"
  text: "#2c2d29"
  muted: "#696a63"
  line: "#92958b"
  error: "#963c35"
  primary-hover: "#42443c"
  primary-active: "#20211d"
  primary-disabled: "#5e6056"
  canvas-bg: "#f5f3ee"
  canvas-text: "#2c2d29"
  canvas-muted: "#696a63"
  canvas-control: "#ffffff"
  canvas-border: "#92958b"
typography:
  title: {fontFamily: 'Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif', fontSize: "28px", fontWeight: 650, lineHeight: 1.25, letterSpacing: "-0.7px"}
  body: {fontFamily: 'Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif', fontSize: "15px", fontWeight: 400, lineHeight: 1.6}
  label: {fontFamily: 'Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif', fontSize: "14px", fontWeight: 600, lineHeight: 1.5}
  input: {fontFamily: 'Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif', fontSize: "16px", fontWeight: 400, lineHeight: 1.5}
  button: {fontFamily: 'Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif', fontSize: "15px", fontWeight: 600, lineHeight: 1.5}
  canvas-destination: {fontFamily: 'Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif', fontSize: "14px", fontWeight: 600, lineHeight: "20px"}
  canvas-attraction: {fontFamily: 'Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif', fontSize: "12px", fontWeight: 400, lineHeight: "18px"}
rounded: {card: "16px", control: "10px", password-toggle: "7px", brand: "4px", canvas-controls: "999px"}
spacing: {label-gap: "8px", form-gap: "20px", card-inline: "36px", card-top: "38px", card-bottom: "28px"}
components:
  button-primary: {backgroundColor: "{colors.text}", textColor: "{colors.card}", typography: "{typography.button}", rounded: "{rounded.control}", padding: "14px 44px", height: "52px", width: "100%"}
  button-primary-hover: {backgroundColor: "{colors.primary-hover}", textColor: "{colors.card}"}
  button-primary-active: {backgroundColor: "{colors.primary-active}", textColor: "{colors.card}"}
  button-primary-disabled: {backgroundColor: "{colors.primary-disabled}", textColor: "{colors.card}"}
  input: {backgroundColor: "{colors.card}", textColor: "{colors.text}", typography: "{typography.input}", rounded: "{rounded.control}", padding: "12px 14px", height: "50px", width: "100%"}
  auth-card: {backgroundColor: "{colors.card}", textColor: "{colors.text}", rounded: "{rounded.card}", padding: "38px 36px 28px", width: "100%"}
  canvas-controls: {backgroundColor: "{colors.canvas-control}", textColor: "{colors.canvas-text}", rounded: "{rounded.canvas-controls}", padding: "6px"}
---
# Design System: LakbayPass

## Overview
**Creative North Star: "Quiet Clay"**
Minimalist login and registration use white surfaces, warm off-white surroundings, and subtle clay lighting. Dark text keeps the forms readable. The signed-in dashboard carries the same warm off-white palette, dark captions, white controls, and a centered supplied logo behind the destination tiles.
**Key Characteristics:**
- White accent and warm neutrals.
- Restrained clay depth and curved controls.
- Persistent labels, clear focus, and explicit state feedback.

## Colors
White is the confirmed accent and card/control surface. Warm Off-White provides the page and notice background. Charcoal serves text, actions, and focus; Warm Gray supports descriptions; Soft Olive Gray defines field borders. Warm Error Red is reserved for validation with explanatory text.
**The White Accent Rule.** Keep white as the accent; do not introduce pastel highlights.
The canvas palette is scoped to the dashboard: Canvas Background fills the viewport, Canvas Text carries place names and navigation, Canvas Muted supports attraction captions, Canvas Control grounds the bottom controls, and Canvas Border defines their outline and divider.
Destination pages retain warm off-white and white surfaces. Their scoped `--accent` colors apply to mission points, the mission-list top border, and text selection: Palawan #3d5a36, Vigan #795833, Cebu #24645c, Siquijor #87613b, Siargao #21606b, and Camiguin #245d7b.

## Typography
Use the system font stack in the tokens. Titles have tight tracking and balanced wrapping; their size becomes 26px at 480px and 24px at 350px. Keep input text at 16px on phones. Field errors use 13px regular text with 1.5 line height; Show/Hide uses 13px semibold. Authentication branding uses the supplied logo image.
The dashboard uses the supplied logo image as its centered backdrop. Destination and attraction captions use the canvas type tokens.

## Layout
A centered shell is full width up to 448px. The page fills the viewport with 100svh and a 100vh fallback, allowing natural scrolling. Desktop page padding is 48px 24px; card padding is 38px 36px 28px. Brand-to-card spacing is 28px, heading-to-form spacing is 30px, form gap is 20px, and label gap is 8px.
At 480px and below, page padding is 28px 16px, card padding is 28px 24px 20px, brand spacing is 22px, and heading spacing is 26px. At 350px and below, page side padding is 12px and card side padding is 20px. Account-switch text wraps naturally above a quiet divider.
The dashboard fills the viewport with clipped, repeated landscape tiles; the header stays fixed at the top and compact controls at bottom center. Tile width × height / column gap / row gap is 380×270 / 104 / 72px above 1100px, 320×230 / 64 / 64px at 1100px, 252×184 / 36 / 56px at 600px, and 220×164 / 28 / 52px at 360px. Captions reserve 52px throughout.
Destination pages use a centered 1160px maximum shell with a split photo/story overview and a separate mission list. The account total sits with the mission heading; one Scan a QR action follows the list and expands an inline scanner beneath it. At 680px and below, both sections stack into one column, the hero uses a 1.6 aspect ratio, and the scanner action fills its column. The header pairs Back to gallery with the supplied logo.

## Elevation & Depth
The white card uses diffuse lower-right shadow, upper-left highlight, and restrained inset lighting. Exact shadow states are recorded in the sidecar and static/auth.css.
**The Quiet Depth Rule.** Controls change color and shadow without moving or scaling.
Canvas photos remain flat; warm off-white background gradients protect the fixed header and footer, and the white control capsule uses a restrained shadow (0 8px 28px #2c2d2914).

## Shapes
Cards use the card radius; inputs and primary actions share the control radius. Inputs and notices have one-pixel borders. The smaller Show/Hide control nests inside its field. Forced-colors mode supplies system-color card and button borders.
Canvas media has square corners; its control capsule and playback action are pill shaped, with circular direction buttons. Forced-colors mode supplies one-pixel system-color borders for the capsule and media.

## Components
**Primary action:** Full width, minimum 52px high, charcoal with white text and a right arrow. Hover, active, and pending states use the named variants. Pending submission disables the action and hides its arrow.
**Fields:** Persistent labels above white outlined inputs, 50px high. Focus uses a two-pixel charcoal outline, offset three pixels; buttons and links use four pixels. Invalid fields have error borders and adjacent polite live messages associated through aria-describedby.
**Password:** Reserve space for Show/Hide, retain a minimum 44px target, and report pressed state. Native required/email validation remains available without JavaScript.
**Feedback:** Success notices use off-white fill and a quiet border. Submission changes the action label, sets form aria-busy, and announces status; failed validation focuses the first invalid field.
**Authentication navigation:** Use `static/lakbayLogo.png` in the shared login/registration header with LakbayPass alternative text. Its 280px-wide, 144px-high image box preserves the artwork's proportions while cropping transparent outer padding. Account links are underlined, thicken on hover, and retain 44px targets.
State transitions last 160ms with ease-out for colors and shadows only; reduced-motion removes transitions.
**The Visible State Rule.** Preserve labels, focus outlines, adjacent error text, and explicit submission feedback.
**Destination canvas branding:** Use `static/lakbayLogo.png` as a fixed, centered, decorative backdrop behind every tile. Its image width is min(980px, 145vw), height is automatic, and opacity is 0.16. Keep pointer events disabled so it cannot intercept dragging or controls. The header retains welcome and logout navigation. Captions use a solid Canvas Background surface to protect text contrast.
**Destination canvas:** All tiles drift together 15px left and 5px up per second in a fixed recycled pool that adapts to viewport size. Drag/swipe pauses drift until release; reduced motion starts paused. Preserve Play/Pause, arrow-key and direction controls, the stable accessible place list, clear placeholder labels, minimum 44px targets, and the two-pixel Canvas Text focus outline with a four-pixel offset. Control hover/press fills are #eeeee8/#e1e3d9; reduced motion removes their 160ms color transition.
**Destination navigation:** All six actual JPGs are present. The photo and caption form one real same-tab link, with the same href on repeated copies. Click/tap opens the destination; movement beyond 6px becomes a drag without navigation. Keep one keyboard representative per destination, reveal it on focus, and pause drift while it is focused.
**Destination details:** The protected `/destinations/<slug>` route allows exactly six slugs and their matching detail templates; authenticated unknown slugs return 404. All six extend `destinations/base.html`, reusing the resolved photo, destination and attraction descriptions, and Back to gallery navigation. A shared mission list displays Itinerary 10 pts, Local Foods 15 pts, and Activities 20 pts, with a text Claimed state above each saved reward and an account total beside the mission heading. Retain destination accents for the point values.
**Destination scanner:** Scan a QR uses the established charcoal action, white text, 10px corners, and a minimum 52px height. The inline scanner uses a quiet top divider, a title and Close action, and a plain live preview with a 4:3 aspect ratio and maximum 400px height. Close and retry controls use white surfaces, outlined borders, 10px corners, and minimum 44px targets. Show the preview only while the camera is active. Opening moves focus to Close; Close or Escape restores focus to Scan a QR. Camera instructions, pending claims, saved results, and recoverable errors use explicit polite status text; claim feedback sits in a white bordered notice. Saved results update the matching mission row and account total. Keep the photo/story composition and existing palette intact; operational setup belongs in [database/README.md](database/README.md).

## Do's and Don'ts
- **Do** use white surfaces, warm off-white surroundings, and dark readable text.
- **Do** keep login and registration on the same shared component system.
- **Do** retain compact-screen spacing, subtle clay lighting, and reduced-motion support.
- **Don't** add pastel accents.
- **Don't** replace labels or validation text with color alone.
- **Don't** add movement to state transitions.
