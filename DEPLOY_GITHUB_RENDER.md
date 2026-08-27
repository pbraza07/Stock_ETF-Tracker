# Deploy MarketScope with GitHub + Render

This package is already configured for a **free Render Web Service**. No market-data API key is required.

## Part 1 — Upload to GitHub

1. Sign in to GitHub.
2. Click **New repository**.
3. Name it something like `marketscope-stock-tracker`.
4. Choose **Private** if this is only for you, or **Public** if you want others to see the source.
5. Create the repository without adding a README, `.gitignore`, or license (this ZIP already contains the needed files).
6. Unzip this package on your computer.
7. In the new GitHub repository, choose **Add file > Upload files**.
8. Upload the **contents inside** `Stock_Market_Tracker_GitHub_Render_v2` so that `app.py`, `render.yaml`, `requirements.txt`, and the `providers` folder appear at the repository root.
9. Commit the upload to the `main` branch.

## Part 2 — Deploy on Render (Blueprint method — easiest)

1. Sign in to Render.
2. Connect your GitHub account to Render if it is not already connected.
3. In Render, choose **New > Blueprint**.
4. Select the GitHub repository you just created.
5. Render will automatically detect the root-level `render.yaml`.
6. Review the service named `marketscope-stock-etf-tracker`.
7. Click **Deploy Blueprint** / **Apply**.
8. Render will install the Python dependencies and start Streamlit.
9. After deployment succeeds, open the generated `https://...onrender.com` URL.

No environment variables, Yahoo API key, Twelve Data key, Polygon key, or paid data subscription is needed.

## Alternative — create a Web Service manually

If you do not use the Blueprint flow, use these values:

- **Runtime / Language:** Python
- **Plan:** Free
- **Build command:** `python -m pip install --upgrade pip && pip install -r requirements.txt`
- **Start command:** `streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true --browser.gatherUsageStats=false`
- **Health check path:** `/_stcore/health`
- **Python:** controlled by `.python-version` (`3.12`)

## Updating the live app later

After Render is linked to your GitHub repository, update files in GitHub and commit them. Render can rebuild/redeploy from the linked branch, so GitHub becomes your source code master copy.

## Important Free Render behavior

- Free Render web services can spin down when idle. The next visit wakes the app again.
- Free Render storage is ephemeral. This version therefore does **not** rely on `data/watchlist.json` being rewritten in the cloud.
- On Render, your changed tracker list is encoded into the page URL as `?symbols=...`. After adding/removing symbols, bookmark the current URL if you want that exact custom list to be easy to reopen.
- The committed `data/watchlist.json` remains the default watchlist for a new browser/base URL.

## Yahoo Finance data note

The app uses Yahoo Finance through the open-source `yfinance` client. It does not scrape Investing.com or Yahoo HTML pages and it does not require a paid API key. Free website-derived market data can be delayed, temporarily rate-limited, or differ from a broker's consolidated exchange feed. Use your brokerage for order-critical quotes.
