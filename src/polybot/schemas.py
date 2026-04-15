"""Pydantic models (schemas) shared across the application."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# -- Polymarket market models --


class TokenInfo(BaseModel):
    """A single outcome token in a market."""

    token_id: str
    outcome: str  # e.g. "Yes", "No"
    price: Decimal = Decimal("0")


class Market(BaseModel):
    """Polymarket market metadata from Gamma API."""

    condition_id: str
    question_id: str = ""
    title: str = ""
    description: str = ""
    outcomes: list[str] = Field(default_factory=list)
    tokens: list[TokenInfo] = Field(default_factory=list)
    end_date: datetime | None = None
    active: bool = True
    volume: Decimal = Decimal("0")
    category: str = ""
    resolution_source: str = ""
    question: str = ""


class OrderbookLevel(BaseModel):
    """Single price/size level in an orderbook."""

    price: Decimal
    size: Decimal


class Orderbook(BaseModel):
    """Orderbook for a single token."""

    token_id: str
    bids: list[OrderbookLevel] = Field(default_factory=list)
    asks: list[OrderbookLevel] = Field(default_factory=list)
    midpoint: Decimal = Decimal("0")
    spread: Decimal = Decimal("0")
    timestamp: datetime | None = None


# -- Weather forecast models --


class CityCoordinates(BaseModel):
    """City with lat/lon for weather lookups."""

    name: str
    lat: float
    lon: float
    noaa_station_id: str = ""
    noaa_gridpoint: str = ""  # e.g. "OKX/33,37"


# Pre-defined cities for weather markets
CITIES = {
    "nyc": CityCoordinates(
        name="New York City",
        lat=40.7128,
        lon=-74.0060,
        noaa_station_id="KNYC",
        noaa_gridpoint="OKX/33,37",
    ),
    "chicago": CityCoordinates(
        name="Chicago",
        lat=41.8781,
        lon=-87.6298,
        noaa_station_id="KORD",
        noaa_gridpoint="LOT/75,72",
    ),
    "london": CityCoordinates(
        name="London",
        lat=51.5074,
        lon=-0.1278,
    ),
    "seattle": CityCoordinates(
        name="Seattle",
        lat=47.6062,
        lon=-122.3321,
        noaa_station_id="KSEA",
        noaa_gridpoint="SEW/124,67",
    ),
    "atlanta": CityCoordinates(
        name="Atlanta",
        lat=33.7490,
        lon=-84.3880,
        noaa_station_id="KATL",
        noaa_gridpoint="FFC/50,87",
    ),
}


class SingleModelForecast(BaseModel):
    """Forecast from one model source."""

    source: str  # noaa, gfs, ecmwf, icon
    target_date: date
    temp_high_f: float | None = None
    temp_low_f: float | None = None
    temp_high_c: float | None = None
    temp_low_c: float | None = None
    raw: dict = Field(default_factory=dict)


class ForecastBundle(BaseModel):
    """Collection of forecasts from multiple models for one city/date."""

    city: str
    target_date: date
    forecasts: list[SingleModelForecast] = Field(default_factory=list)
    fetched_at: datetime | None = None


# -- WebSocket event models --


class PriceChangeEvent(BaseModel):
    """Price change event from Polymarket WebSocket."""

    token_id: str = ""
    price: Decimal = Decimal("0")
    timestamp: datetime | None = None
    raw: dict = Field(default_factory=dict)
