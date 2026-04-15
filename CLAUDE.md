# Polymarket Weather Arbitrage Bot

## Projekti kontekst

Kahe arendaja Pythoni bot mis vordleb NOAA + Open-Meteo ilmaprognoose Polymarketi weather marketite hindadega ja teeb mispricing'ust kasu. Tootab Windows PowerShellis. Reaalne raha alates Phase 4-st.

## Kaivitamise kasud (PowerShell)

```powershell
# Esmane setup
uv sync
docker compose up -d
uv run alembic upgrade head

# Andmete kogumine (jookseb 24/7)
uv run python -m polybot.cli collect-data

# Backtest
uv run python scripts/backtest.py --start 2026-04-01 --end 2026-04-15

# Dry run trading
uv run python -m polybot.cli trade --dry-run

# LIVE trading (ettevaatust!)
uv run python -m polybot.cli trade --live --i-understand-i-can-lose-money

# Testid
uv run pytest -v --cov=polybot

# Lint + format
uv run ruff check .
uv run ruff format .
```

## Absoluutsed reeglid

1. EI MUUDA `.env` faili kunagi automaatselt
2. EI commit'ita `.env`-i ega private key'd kunagi
3. Default = `--dry-run`. Live trade vajab kaks explicit flag'i.
4. Geocheck enne iga orderit (kui blocked, abort)
5. Kill switch on alati aktiivne (max daily loss $20 default)
6. Max positsioon = 10% bankroll'ist quarter-Kelly'ga, esimene kuu max $5
7. Iga trade peab olema PostgreSQL audit logis
8. Resolution source peab matchima meie data source'iga, muidu skip turg
9. `place_real_order()` muudatused vajavad explicit kasutaja kinnitust
10. Test coverage > 70% enne live mode'i

## Wallet info

- Network: Polygon (chain_id 137)
- Currency: USDC (settlement), POL (gas)
- Signature type: 2 (GNOSIS_SAFE proxy) [VERIFY this matches actual setup]
- Funder: vaata `.env` `FUNDER_ADDRESS`
- Bot wallet on **eraldi** pohi-wallet'ist

## API endpointid

- Gamma (markets discovery, public): `https://gamma-api.polymarket.com`
- Data (positions, leaderboard, public): `https://data-api.polymarket.com`
- CLOB (orderbook + trading): `https://clob.polymarket.com`
- WebSocket: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- Geocheck: `https://polymarket.com/api/geoblock`
- Open-Meteo: `https://api.open-meteo.com/v1/forecast`
- NOAA NWS: `https://api.weather.gov`

## Geo

Eesti pole geoblokeeritud. VPS'i jaoks kasuta eu-west-1 (Iirimaa) AWS regiooni voi OVH Frankfurt. **MITTE** Saksa, Hollandi, Prantsusmaa serverit kuna need on blokeeritud.

## Toojaotus

- **Magnus:** data layer, infrastructure, deployment, risk module
- **Kaasarendaja:** signal layer, backtest, strategy tuning

## Git workflow

- `main` branch on alati deployable
- Feature branches: `feat/data-noaa`, `feat/signal-ensemble`, jne
- Iga PR vajab review enne merge'i
- Pre-commit hook valideerib et `.env` ja private keys pole staged

## Mida MITTE Claude Code'il teha

- ARA kaivita `--live` kaske ise
- ARA muuda kill switch threshold'e ilma kusimata
- ARA tuhjenda PostgreSQL andmeid
- ARA paista oma loomingulisust risk management'is, jargi spec'i tapselt
- ARA installi taiendavaid pakette ilma `pyproject.toml` update'imata
- ARA kasuta em-dash voi en-dash sumboleid kommentides ega dokumentatsioonis. Kasuta koma, koolonit voi sulge.
