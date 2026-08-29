# MarketScope v5.9.19 — Server PDF Storage + Mobile Share Viewer

Authoritative baseline: **v5.9.18**. This release preserves all v5.9.18 universe-status, two-year card-chart, PDF, simulator, sorting, analytics, and Render/GitHub behavior and adds the PDF workflow below.

## What changed

1. **Every newly saved portfolio PDF is now a real server file** under `static/generated_pdfs/` before its library record is committed.
2. **Durable PDF recovery** is added through GitHub at `data/generated_pdfs/` when `MARKETSCOPE_GITHUB_TOKEN` is configured.
3. Optional server-disk durability is supported with `MARKETSCOPE_PDF_PERSIST_DIR` for a mounted Render persistent disk.
4. **Older v5.9.18 saved simulations auto-migrate**: if no stored PDF exists, MarketScope rebuilds it from the saved simulation record, saves the server copy, and attempts the durable backup.
5. The Saved Simulations library now includes **📱 Open / Share PDF** in addition to the existing Download PDF button.
6. The mobile viewer uses the browser's **native Web Share API** to pass the actual PDF file to the iPhone/iPad/Android share sheet, including Mail, Messages, group chats, AirDrop, Files, and other installed apps where supported.
7. The viewer includes **← MarketScope**. If the viewer was opened from the app, it focuses/closes back to the original app tab when possible; otherwise it returns to the MarketScope root.
8. Streamlit static serving is enabled with `[server] enableStaticServing = true`, which supports `.pdf` files under `app/static/...`.
9. Deleting a saved simulation now also deletes its server PDF and, when authorized, its durable GitHub PDF artifact.
10. Runtime PDF/library GitHub commits append **`[skip render]`** so data-only saves do not trigger an unnecessary Render redeploy.

## Render requirement

Keep `MARKETSCOPE_GITHUB_TOKEN` configured in Render for durable PDF persistence across free-instance restart/redeploy. Without it, MarketScope still saves the real PDF on the current server, but Render's local filesystem can be ephemeral.

If a paid Render persistent disk is mounted, set `MARKETSCOPE_PDF_PERSIST_DIR` to that mounted directory to keep an additional server-disk copy.
