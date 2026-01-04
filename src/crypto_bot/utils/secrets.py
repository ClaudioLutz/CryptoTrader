"""Secure secret management for API keys and credentials.

This module provides:
- Multi-source secret loading (environment variables, system keyring)
- CLI for managing secrets
- Secure storage best practices
"""

import os
from typing import Optional

import structlog
from pydantic import SecretStr

logger = structlog.get_logger()


class SecretManager:
    """Manages loading secrets from multiple sources.

    Priority order:
    1. Environment variables (highest - Docker/K8s friendly)
    2. System keyring (secure desktop storage)

    Usage:
        manager = SecretManager()
        api_key = manager.get_secret("EXCHANGE_API_KEY")
        if api_key:
            # Use api_key.get_secret_value() when needed
            pass
    """

    def __init__(self, service_name: str = "crypto_trading_bot"):
        """Initialize secret manager.

        Args:
            service_name: Service name for keyring storage.
        """
        self._service_name = service_name
        self._keyring_available = self._check_keyring()

    def _check_keyring(self) -> bool:
        """Check if system keyring is available."""
        try:
            import keyring

            keyring.get_keyring()
            return True
        except Exception:
            return False

    def get_secret(self, key: str) -> Optional[SecretStr]:
        """Get secret from available sources.

        Checks sources in priority order:
        1. Environment variable
        2. System keyring

        Args:
            key: Secret key name.

        Returns:
            SecretStr if found, None otherwise.
        """
        # Try environment variable first
        env_value = os.getenv(key)
        if env_value:
            logger.debug("secret_loaded", source="environment", key=key)
            return SecretStr(env_value)

        # Try system keyring
        if self._keyring_available:
            try:
                import keyring

                keyring_value = keyring.get_password(self._service_name, key)
                if keyring_value:
                    logger.debug("secret_loaded", source="keyring", key=key)
                    return SecretStr(keyring_value)
            except Exception as e:
                logger.warning("keyring_error", key=key, error=str(e))

        return None

    def get_secret_value(self, key: str) -> Optional[str]:
        """Get secret value as plain string.

        Args:
            key: Secret key name.

        Returns:
            Secret value if found, None otherwise.
        """
        secret = self.get_secret(key)
        return secret.get_secret_value() if secret else None

    def set_secret_keyring(self, key: str, value: str) -> bool:
        """Store secret in system keyring.

        Args:
            key: Secret key name.
            value: Secret value.

        Returns:
            True if stored successfully.
        """
        if not self._keyring_available:
            logger.error("keyring_not_available")
            return False

        try:
            import keyring

            keyring.set_password(self._service_name, key, value)
            logger.info("secret_stored", key=key, storage="keyring")
            return True
        except Exception as e:
            logger.error("keyring_store_failed", key=key, error=str(e))
            return False

    def delete_secret_keyring(self, key: str) -> bool:
        """Delete secret from system keyring.

        Args:
            key: Secret key name.

        Returns:
            True if deleted successfully.
        """
        if not self._keyring_available:
            return False

        try:
            import keyring

            keyring.delete_password(self._service_name, key)
            logger.info("secret_deleted", key=key)
            return True
        except Exception:
            return False

    def has_secret(self, key: str) -> bool:
        """Check if a secret exists.

        Args:
            key: Secret key name.

        Returns:
            True if secret exists in any source.
        """
        return self.get_secret(key) is not None

    @property
    def keyring_available(self) -> bool:
        """Check if keyring is available."""
        return self._keyring_available


def secrets_cli() -> int:
    """CLI for managing trading bot secrets.

    Returns:
        Exit code (0 for success).
    """
    import argparse
    import getpass

    parser = argparse.ArgumentParser(description="Manage trading bot secrets")
    subparsers = parser.add_subparsers(dest="command")

    # Set command
    set_parser = subparsers.add_parser("set", help="Store a secret")
    set_parser.add_argument("key", help="Secret key name")

    # Get command
    get_parser = subparsers.add_parser("get", help="Check if secret exists")
    get_parser.add_argument("key", help="Secret key name")

    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete a secret")
    del_parser.add_argument("key", help="Secret key name")

    # List command
    subparsers.add_parser("list", help="List required secrets")

    args = parser.parse_args()
    manager = SecretManager()

    if args.command == "set":
        value = getpass.getpass(f"Enter value for {args.key}: ")
        if manager.set_secret_keyring(args.key, value):
            print(f"Secret '{args.key}' stored successfully")
            return 0
        else:
            print("Failed to store secret (keyring may not be available)")
            return 1

    elif args.command == "get":
        if manager.has_secret(args.key):
            print(f"Secret '{args.key}' found (not displaying value)")
            return 0
        else:
            print(f"Secret '{args.key}' not found")
            return 1

    elif args.command == "delete":
        if manager.delete_secret_keyring(args.key):
            print(f"Secret '{args.key}' deleted")
            return 0
        else:
            print("Failed to delete secret")
            return 1

    elif args.command == "list":
        required_secrets = [
            "EXCHANGE_API_KEY",
            "EXCHANGE_API_SECRET",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
            "DISCORD_WEBHOOK_URL",
        ]
        print("Required secrets:")
        for key in required_secrets:
            status = "\u2705" if manager.has_secret(key) else "\u274c"
            print(f"  {status} {key}")
        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    import sys

    sys.exit(secrets_cli())
