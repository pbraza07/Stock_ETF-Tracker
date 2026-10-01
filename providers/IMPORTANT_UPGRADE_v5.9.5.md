# IMPORTANT - v5.9.5 Upgrade

Upload v5.9.5 on top of the existing repository.

Do **not** create or overwrite `data/saved_portfolio_simulations.json` during deployment. v5.9.5 intentionally ships only the empty bootstrap file `data/saved_portfolio_simulations.bootstrap.json`. The live library file is created by the app after the first saved simulation and should remain durable thereafter.

For permanent cross-device simulation storage, keep `MARKETSCOPE_GITHUB_TOKEN` configured in Render with repository Contents read/write permission.
