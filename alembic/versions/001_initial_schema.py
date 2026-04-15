"""Initial schema: markets, snapshots, trades, kill switch

Revision ID: 001
Revises: None
Create Date: 2026-04-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("condition_id", sa.String(256), nullable=False),
        sa.Column("question_id", sa.String(256), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("outcomes", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Text(), nullable=False),
        sa.Column("resolution_source", sa.String(256), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_markets_condition_id", "markets", ["condition_id"], unique=True)

    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("condition_id", sa.String(256), nullable=False),
        sa.Column("token_id", sa.String(256), nullable=False),
        sa.Column("price_yes", sa.Numeric(10, 6), nullable=False),
        sa.Column("price_no", sa.Numeric(10, 6), nullable=False),
        sa.Column("spread", sa.Numeric(10, 6), nullable=True),
        sa.Column("volume_24h", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_snapshots_condition_id", "market_snapshots", ["condition_id"])
    op.create_index("ix_market_snapshots_timestamp", "market_snapshots", ["timestamp"])

    op.create_table(
        "forecast_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temp_high_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("temp_low_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("temp_mean_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("std_dev_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forecast_snapshots_city", "forecast_snapshots", ["city"])
    op.create_index("ix_forecast_snapshots_timestamp", "forecast_snapshots", ["timestamp"])

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("market_condition_id", sa.String(256), nullable=False),
        sa.Column("token_id", sa.String(256), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("size_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("price", sa.Numeric(10, 6), nullable=False),
        sa.Column("model_probability", sa.Numeric(10, 6), nullable=False),
        sa.Column("market_probability", sa.Numeric(10, 6), nullable=False),
        sa.Column("edge", sa.Numeric(10, 6), nullable=False),
        sa.Column("order_id", sa.String(256), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("pnl", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trades_market_condition_id", "trades", ["market_condition_id"])
    op.create_index("ix_trades_timestamp", "trades", ["timestamp"])

    op.create_table(
        "kill_switch_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pause_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "daily_loss_usd", sa.Numeric(10, 4), nullable=False, server_default="0"
        ),
        sa.Column("consecutive_losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reset_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("kill_switch_state")
    op.drop_table("trades")
    op.drop_table("forecast_snapshots")
    op.drop_table("market_snapshots")
    op.drop_table("markets")
