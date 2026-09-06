# 🎃 HHN 35 Wait-Time Website

This version is designed to run online for free.

## Architecture

Queue-Times → GitHub Actions (every 10 min) → `data/waits.csv` → Streamlit Community Cloud → your website.

Your MacBook does NOT need to stay on.

## Files

- `app.py` — website/dashboard
- `collector.py` — wait-time collector
- `.github/workflows/collect.yml` — automatic 10-minute schedule
- `data/waits.csv` — historical data
- `requirements.txt` — website dependencies
- `collector_requirements.txt` — collector dependencies

## Important

After creating your GitHub repository, edit `app.py` and replace:

`YOUR_USERNAME/HHN-35-Wait-Tracker`

with your actual GitHub username/repository.

Then deploy `app.py` on Streamlit Community Cloud.

## GitHub Actions

GitHub scheduled workflows use UTC and can be delayed during busy periods. The workflow is configured for every 10 minutes and can also be started manually from the Actions tab.

## Queue-Times

The collector uses Queue-Times' Universal Orlando real-time feed and a live-page fallback. Review the provider's current API terms/attribution requirements before public use.
