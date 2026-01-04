"""API key permission validation and security checks.

This module provides:
- API permission checking
- Security recommendations
- Pre-flight validation for trading
"""

from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class APIPermissions:
    """API key permissions status."""

    can_trade: bool
    can_read: bool
    can_withdraw: bool
    ip_restricted: bool
    ip_whitelist: list[str]


class APIKeyValidator:
    """Validate API key permissions and configuration.

    Checks that API keys have appropriate permissions for trading
    and warns about security risks.

    Usage:
        validator = APIKeyValidator(exchange)
        if await validator.run_preflight_check():
            # Safe to trade
            pass
    """

    def __init__(self, exchange: Any):
        """Initialize API key validator.

        Args:
            exchange: Exchange instance to validate.
        """
        self._exchange = exchange

    async def check_permissions(self) -> APIPermissions:
        """Check API key permissions.

        Note: Exact implementation varies by exchange.
        Most exchanges don't expose permissions directly via API.

        Returns:
            APIPermissions with detected capabilities.
        """
        can_read = False
        can_trade = False
        can_withdraw = False

        # Try to fetch account info to verify read permission
        try:
            await self._exchange.fetch_balance()
            can_read = True
            # If we can read, likely can trade (most APIs)
            can_trade = True
        except Exception as e:
            logger.warning("api_read_check_failed", error=str(e))

        # Note: We cannot reliably detect withdrawal permission
        # without attempting a withdrawal, which is not safe.
        # We assume it might be enabled and warn accordingly.

        return APIPermissions(
            can_trade=can_trade,
            can_read=can_read,
            can_withdraw=can_withdraw,  # Unknown, assume possible
            ip_restricted=False,  # Cannot determine via API
            ip_whitelist=[],
        )

    def validate_for_trading(self, permissions: APIPermissions) -> list[str]:
        """Validate permissions are suitable for trading bot.

        Args:
            permissions: Detected API permissions.

        Returns:
            List of issues and warnings.
        """
        issues = []

        if not permissions.can_read:
            issues.append("CRITICAL: API key cannot read account data")

        if not permissions.can_trade:
            issues.append("CRITICAL: API key cannot place trades")

        # Always warn about potential withdrawal capability
        issues.append(
            "WARNING: Verify withdrawal permission is DISABLED in exchange settings. "
            "This is the most important security measure."
        )

        if not permissions.ip_restricted:
            issues.append(
                "WARNING: Consider enabling IP whitelisting for your API key. "
                "This is the most effective protection against key compromise."
            )

        return issues

    async def run_preflight_check(self) -> bool:
        """Run full API key preflight check.

        Returns:
            True if all critical checks pass.
        """
        logger.info("running_api_preflight_check")

        permissions = await self.check_permissions()
        issues = self.validate_for_trading(permissions)

        critical_issues = []
        warnings = []

        for issue in issues:
            if issue.startswith("CRITICAL"):
                critical_issues.append(issue)
                logger.error("api_check_failed", issue=issue)
            else:
                warnings.append(issue)
                logger.warning("api_check_warning", issue=issue)

        if critical_issues:
            return False

        logger.info(
            "api_preflight_passed",
            can_trade=permissions.can_trade,
            warnings=len(warnings),
        )
        return True

    def get_security_recommendations(self) -> list[str]:
        """Get security recommendations for API key setup.

        Returns:
            List of security recommendations.
        """
        return [
            "1. DISABLE withdrawal permission - This is the single most important protection",
            "2. Enable IP whitelisting - Restricts API access to specific IP addresses",
            "3. Use a dedicated API key for this bot - Don't share keys between applications",
            "4. Store keys securely - Use environment variables or system keyring",
            "5. Rotate keys periodically - Change API keys every 3-6 months",
            "6. Monitor API usage - Check exchange for unusual activity",
            "7. Use testnet first - Validate bot behavior before using real funds",
            "8. Start with small amounts - Gradually increase position sizes",
        ]


# IP Whitelisting documentation
IP_WHITELISTING_GUIDE = """
## IP Whitelisting Setup

IP whitelisting is the most effective protection against compromised API keys.

### Binance
1. Go to API Management in your Binance account
2. Click "Edit restrictions" on your API key
3. Select "Restrict access to trusted IPs only"
4. Add your server's IP address(es)

### Finding Your IP
- Home: Visit whatismyip.com (note: may change with dynamic IP)
- VPS: Check your provider's control panel
- Use a VPN with static IP for consistent access

### Best Practices
- Use a VPS with static IP for production
- If using home IP, consider a VPN with static IP
- Add backup IP if you have multiple access points
- Update IP list when your server changes
"""
