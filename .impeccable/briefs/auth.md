# Authentication screens

MODE: operate
FORM: user-pinned minimalist single-column forms with subtle clay depth; seed:0b06e4b8358639ce. The user's prescribed layout and confirmed white accent take precedence over generated alternative directions.

## Direction contract

- Warm off-white page, white card and controls, dark readable text, charcoal primary action.
- A centered, shared 448px maximum-width form with the supplied `static/lakbayLogo.png` above it. One column at every viewport.
- Card corners and soft offset/inset shadows supply the gentle clay effect. Controls use thin visible borders.
- Login: email, password, Show/Hide, Log in, Create an account.
- Register: username, email, password, Show/Hide, Create account, Log in.
- Both screens use the same typography, spacing, labels, focus treatment, and 44px minimum tap controls.
- Preserve current Flask/MySQL routes, signup fields, session keys, and stored-password compatibility. No unsupported recovery link.

## First viewport

At 1440×900 and 390×844, show the brand, complete form, primary action, and screen-switch link. At shorter phone heights, scroll vertically without clipping or horizontal overflow.

## States

Required and malformed inputs receive adjacent messages. Duplicate email is associated with email; generic invalid-login feedback is associated with password. Preserve non-sensitive values, clear password after a server response, focus the first invalid control, and announce errors. Valid submission disables the primary button and shows action-specific progress. Browser history restores the enabled action.

## Verification

- `venv/Scripts/python -m unittest discover -s tests -v`: 10 route regressions pass.
- Real MySQL browser flow: registration, duplicate registration, invalid credentials, successful login, dashboard, logout, protected dashboard redirect. The unique temporary QA account was removed afterward.
- Browser widths: 320, 360, 390, 768, 1440, 1920; both screens have no horizontal overflow or clipped controls.
- Keyboard focus, toggles, inline validation, pending state, and JavaScript-disabled native/server validation checked.
- Contrast: body/primary 13.86:1, secondary 5.46:1, placeholder 4.74:1, error 7.01:1, input border 3.04:1.
- One mechanical detector run returned no findings. Its static Jinja stylesheet-link warning was covered by checking the CSS directly and measuring computed styles in the browser.
- Final viewport screenshots are in `.impeccable/review/`.
