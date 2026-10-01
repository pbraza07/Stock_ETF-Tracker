# MarketScope v5.11.44 — Earnings navigation crop

The earnings view visually clips the top 250 display pixels and bottom 65 display
pixels of the embedded page to hide the navigation areas marked in the supplied
mobile screenshot. The visible calendar remains full width and 520px high with
80% scaling and the existing dark filter. The taller inner frame keeps its bottom
mobile navigation below the visible region. Top cropping also hides introductory
content before the date/filter controls.

This is a visual crop, not removal of Investing.com's cross-origin DOM. The default
offsets are estimated from the supplied screenshot, not verified on the user's
device. Responsive/provider layout changes may move content. An Adjust calendar
view expander provides top/bottom offsets; zero restores the uncropped frame.
Navigation can reappear or controls can be clipped if the provider changes layout.
Source attribution and the original economic calendar are preserved.

The importance=3 request remains; provider enforcement of query filters is still
unverified. No financial calculations change. This package is not deployed.

Validation: 712 automated tests passed (72 warnings), covering crop bounds,
uncropped recovery, interactive crop adjustment, and calendar switching.
