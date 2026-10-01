# MarketScope v5.11.45 — Earnings frame popup restrictions

Earnings requests importance=2,3, countries=5, and calType=week. Economic calendar remains unchanged at importance=3. Week is a relative provider parameter, not a hardcoded historical date.

The earnings iframe now uses sandbox="allow-scripts allow-same-origin allow-forms". It does not grant popup, popup escape, top navigation, modal dialog, or download permissions. These restrictions block new-window popups, top-level redirects and script alert/confirm/prompt dialogs in conforming browsers. Scripts and forms remain permitted for provider calendar controls.

This cannot suppress HTML overlays, cookie banners, advertisements or sign-in prompts drawn within the cross-origin page. The provider's full-page earnings endpoint may ignore economic-widget filter parameters; this release cannot guarantee automatic current-week/U.S./two-and-three-star filtering. The UI explicitly explains both limits. No proxy or browser security bypass is introduced. Sandboxing may affect provider features; the external source link remains available.

Existing compact crop and Back to Economic Calendar are preserved. No financial calculations are changed. Not deployed; live provider behavior under the new sandbox is unverified.

Validation: 713 automated tests passed (72 warnings). Tests check sandbox permissions, relative-week/U.S./importance parameters, calendar switching and existing regression coverage. They do not verify live provider filtering or overlay suppression.
