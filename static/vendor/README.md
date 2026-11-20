# QR decoder

`jsQR-1.4.0.js` is the unmodified jsQR 1.4.0 browser distribution from the
official npm package: https://registry.npmjs.org/jsqr/-/jsqr-1.4.0.tgz

Package SHA-512 integrity was checked against npm metadata before vendoring.
Project: https://github.com/cozmo/jsQR
License: Apache-2.0; see `jsQR-LICENSE.txt`.

The decoder runs locally on camera frames. Only the decoded QR text and the
current destination slug are submitted to Flask; no camera images are uploaded.
