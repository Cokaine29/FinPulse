"""FinPulse Kite Connect OAuth Authentication Module

Manages Zerodha Kite Connect login flows, session token exchange,
and serialization of session tokens to persist daily authentication states.
"""

import pickle
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from kiteconnect import KiteConnect

from finpulse.logger import get_logger

logger = get_logger("kite.auth")

SESSION_FILE = Path(__file__).parent.parent.parent / "data" / "kite_session.pkl"


class KiteAuthManager:
    """Manages Zerodha Kite Connect login session authentication."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        """Initialize the authentication manager.

        Args:
            api_key: Zerodha Kite API key.
            api_secret: Zerodha Kite API secret.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.kite = None
        
        # Instantiate Kite only if api_key is provided
        if api_key:
            self.kite = KiteConnect(api_key=api_key)
            self._load_saved_session()

    def is_configured(self) -> bool:
        """Check if Kite API keys are configured in environment."""
        return bool(self.api_key and self.api_secret)

    def _load_saved_session(self) -> None:
        """Load saved access token from disk if it was created today."""
        if not SESSION_FILE.exists():
            return
            
        try:
            with open(SESSION_FILE, "rb") as f:
                session_data = pickle.load(f)
                
            # Kite access tokens expire daily around 6:00 AM.
            # We check if the session file was modified today.
            mtime = datetime.fromtimestamp(SESSION_FILE.stat().st_mtime)
            if mtime.date() == datetime.now().date():
                self.kite.set_access_token(session_data["access_token"])
                logger.info("Loaded active Zerodha session from cache")
            else:
                logger.info("Cached Zerodha session has expired. Re-auth required.")
                # Clean up expired file
                SESSION_FILE.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to load cached Zerodha session: {e}")

    def get_login_url(self) -> str:
        """Get the URL the user must visit to authenticate."""
        if not self.is_configured():
            raise ValueError("Kite API credentials are not configured in .env")
        return self.kite.login_url()

    def complete_login(self, request_token: str) -> Dict:
        """Exchange request token for a permanent session access token."""
        if not self.is_configured():
            raise ValueError("Kite API credentials are not configured in .env")
            
        data = self.kite.generate_session(request_token, api_secret=self.api_secret)
        access_token = data["access_token"]
        self.kite.set_access_token(access_token)
        
        # Cache token to file for subsequent daily uses
        try:
            SESSION_FILE.parent.mkdir(exist_ok=True)
            with open(SESSION_FILE, "wb") as f:
                pickle.dump({"access_token": access_token}, f)
            logger.info("Saved Zerodha session cache to disk")
        except Exception as e:
            logger.error(f"Failed to save Zerodha session cache: {e}")
            
        return data

    def is_authenticated(self) -> bool:
        """Check if we have an active, validated session."""
        return self.kite is not None and self.kite.access_token is not None
