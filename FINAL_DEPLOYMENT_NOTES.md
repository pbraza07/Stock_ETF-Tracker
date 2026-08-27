# MarketScope v5.5 Final Deployment Notes

1. Upload v5.5 over the existing GitHub repository.
2. Preserve existing generated files in `data/` unless the package explicitly supplies a replacement recovery file.
3. Run **Refresh MarketScope universe and snapshot** once after the upload. This populates the new 2Y/4Y/6Y/7Y/8Y/9Y annualized return fields.
4. Allow Render to auto-deploy the latest commit, or use Manual Deploy → Deploy latest commit.
5. The normal daily schedule remains 6:00 PM America/New_York.

The primary stock/ETF experience is now card/button navigation rather than a dataframe table.
