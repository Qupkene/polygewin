# Polymarket Weather Arbitrage Bot

Bot that compares NOAA and Open-Meteo weather forecasts with Polymarket weather market prices, identifies mispricing, and places limit orders where edge > 5%.

## Quick Start

```powershell
# Install dependencies
uv sync

# Start PostgreSQL
docker compose up -d

# Run migrations
uv run alembic upgrade head

# Copy and fill environment variables
cp .env.example .env
# Edit .env with your values

# Run data collection
uv run python -m polybot.cli collect-data

# Run dry-run trading
uv run python -m polybot.cli trade --dry-run
```

## Architecture

- **Data Layer**: Market discovery (Gamma API), orderbook (CLOB), weather forecasts (NOAA, Open-Meteo)
- **Signal Layer**: Market title parsing, ensemble forecasting, probability estimation, edge calculation
- **Risk Layer**: Quarter-Kelly sizing, daily loss limits, kill switch
- **Execution Layer**: Authentication, geocheck, order placement with audit logging

## Safety

- Default mode is always `--dry-run`
- Live trading requires `--live --i-understand-i-can-lose-money`
- Kill switch halts trading if daily loss exceeds threshold
- Geocheck before every order
- All trades logged to PostgreSQL audit trail

## Target Markets

Temperature markets for: NYC, London, Chicago, Seattle, Atlanta
