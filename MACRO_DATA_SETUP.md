# Macro dashboard setup — v5.11.24

The economic calendar is again the Investing.com iframe, styled with the previous dark filter. It needs no server-side calendar API key. It is configured for the U.S., three-star importance, this week, and Eastern Time; browser/provider restrictions may still block the frame.

The Recession Indicators tab has three native charts: USPHCI, RECPROUSM156N and SAHMREALTIME.

1. Set FRED_API_KEY in Render → Environment. Use your registered FRED key, not a URL. If already configured, keep the existing variable.
2. Set the same FRED_API_KEY under GitHub → repository Settings → Secrets and variables → Actions.
3. Deploy this update, then use GitHub → Actions → Refresh macro snapshots → Run workflow to save all three series.
4. Open Recession Indicators and click Refresh recession data.

The official API requests use the requested real-time vintage bounds 1990-07-04 to 9999-12-31. These are not chart observation-date bounds. Multiple vintages are consolidated to the latest returned value per month. Keys are excluded from source, cached metadata and release archives.

The snapshot workflow runs every six hours/manual, collecting only the three FRED series. Last-good snapshots are preserved on collection failure. Public GitHub snapshots can be read after a provider failure and are labeled stale; they cannot exist until a collection succeeds. Preserve data/macro_snapshots when uploading upgrades.

If FRED fails, expand Connection details. The iframe calendar is independent of this collection. Trading Economics credentials and calendar scraping are no longer needed for the displayed calendar.
