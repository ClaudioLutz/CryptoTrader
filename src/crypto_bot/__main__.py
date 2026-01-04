"""Entry point for running crypto_bot as a module.

Usage:
    python -m crypto_bot
    python -m crypto_bot --dry-run
    python -m crypto_bot --help
"""

from crypto_bot.main import cli

if __name__ == "__main__":
    cli()
