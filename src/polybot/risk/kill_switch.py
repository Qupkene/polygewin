"""Dead man's switch - halt trading on excessive losses."""

# Phase 3: Implement kill switch
# State persisted in DB (not memory)
# Triggers: daily PnL < MAX_DAILY_LOSS_USD, >5 consecutive losses
# Action: pause until next day UTC 00:00, send Telegram alert
