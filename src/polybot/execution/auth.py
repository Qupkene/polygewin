"""Polymarket CLOB authentication setup.

Reads private key from .env, creates or derives API credentials,
and returns a configured ClobClient.
"""

import structlog

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

from polybot.config import get_settings

logger = structlog.get_logger()

# Polymarket chain ID (Polygon mainnet)
CHAIN_ID = 137


async def setup_clob_client() -> ClobClient:
    """Create and authenticate a ClobClient.

    Reads POLYMARKET_PRIVATE_KEY and FUNDER_ADDRESS from environment.
    Derives or creates API credentials for the CLOB.

    Returns:
        Authenticated ClobClient ready for trading.

    Raises:
        ValueError: If private key or funder address is missing.
    """
    settings = get_settings()

    if not settings.polymarket_private_key:
        raise ValueError(
            "POLYMARKET_PRIVATE_KEY is not set. "
            "Export your key from polymarket.com Settings and add to .env"
        )

    if not settings.funder_address:
        raise ValueError(
            "FUNDER_ADDRESS is not set. "
            "This is your proxy wallet address from polymarket.com Settings > Deposit"
        )

    # Signature type:
    # 1 = POLY_PROXY (Magic Link users)
    # 2 = GNOSIS_SAFE (Google/email login users)
    signature_type = settings.polymarket_signature_type

    logger.info(
        "clob_client_init",
        funder=settings.funder_address[:10] + "...",
        signature_type=signature_type,
        chain_id=CHAIN_ID,
    )

    # Create the client
    client = ClobClient(
        host=settings.clob_api_url,
        key=settings.polymarket_private_key,
        chain_id=CHAIN_ID,
        funder=settings.funder_address,
        signature_type=signature_type,
    )

    # Derive API credentials (creates them on first call)
    try:
        client.set_api_creds(client.create_or_derive_api_creds())
        logger.info("clob_client_authenticated")
    except Exception:
        logger.exception("clob_client_auth_failed")
        raise

    return client
