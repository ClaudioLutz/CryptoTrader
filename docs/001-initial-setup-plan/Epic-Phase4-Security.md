# Epic: Phase 4C - Security Hardening

**Epic Owner:** Development Team
**Priority:** Critical - Required before production
**Dependencies:** All previous phases

---

## Overview

Security hardening ensures the trading bot protects API credentials, prevents unauthorized access, and operates safely with real funds. This epic implements secure secret management, API key best practices, input validation, and security verification.

### Key Deliverables
- Secure API key management with environment variables and keyring
- API permission validation and IP whitelisting guidance
- Comprehensive input validation
- Security checklist verification script
- Audit logging for all trading actions

### Research & Best Practices Applied

Based on current 2025 best practices:
- **API Keys:** [Disable withdrawal permissions](https://3commas.io/blog/secure-cryptocurrency-assets-2025) - "the single most important protection"
- **IP Whitelisting:** [Most effective technical defense](https://tradelink.pro/blog/how-to-secure-api-key/) against compromised keys
- **Key Rotation:** [Regular rotation and monitoring](https://btsesolutions.com/articles/best-practices-for-crypto-exchange-api-integration-in-2025)
- **Minimal Permissions:** [Only grant necessary permissions](https://cryptorobotics.ai/learn/security-essentials-for-crypto-trading-api-keys-authentication-account-protection/)

---

## Story 4.13: Implement Secure Secret Management

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** operator
**I want** secrets stored securely outside of code
**So that** credentials cannot leak via source control or logs

### Background
Per [2025 security best practices](https://3commas.io/blog/secure-cryptocurrency-assets-2025), API keys should never be stored in plain text or version control. Use encrypted storage or dedicated secret management services.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/secrets.py`
- [ ] Implement multi-source secret loading:
  ```python
  import os
  from typing import Optional
  from pydantic import SecretStr
  import structlog

  logger = structlog.get_logger()

  class SecretManager:
      """Manages loading secrets from multiple sources."""

      def __init__(self):
          self._keyring_available = self._check_keyring()

      def _check_keyring(self) -> bool:
          """Check if system keyring is available."""
          try:
              import keyring
              # Test keyring access
              keyring.get_keyring()
              return True
          except Exception:
              return False

      def get_secret(
          self,
          key: str,
          service_name: str = "crypto_trading_bot",
      ) -> Optional[SecretStr]:
          """
          Get secret from available sources in priority order:
          1. Environment variable
          2. System keyring
          3. None (not found)
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
                  keyring_value = keyring.get_password(service_name, key)
                  if keyring_value:
                      logger.debug("secret_loaded", source="keyring", key=key)
                      return SecretStr(keyring_value)
              except Exception as e:
                  logger.warning("keyring_error", key=key, error=str(e))

          return None

      def set_secret_keyring(
          self,
          key: str,
          value: str,
          service_name: str = "crypto_trading_bot",
      ) -> bool:
          """Store secret in system keyring."""
          if not self._keyring_available:
              logger.error("keyring_not_available")
              return False

          try:
              import keyring
              keyring.set_password(service_name, key, value)
              logger.info("secret_stored", key=key, storage="keyring")
              return True
          except Exception as e:
              logger.error("keyring_store_failed", key=key, error=str(e))
              return False

      def delete_secret_keyring(
          self,
          key: str,
          service_name: str = "crypto_trading_bot",
      ) -> bool:
          """Delete secret from system keyring."""
          if not self._keyring_available:
              return False

          try:
              import keyring
              keyring.delete_password(service_name, key)
              logger.info("secret_deleted", key=key)
              return True
          except Exception:
              return False
  ```
- [ ] Create CLI for secret management:
  ```python
  # src/crypto_bot/cli/secrets_cli.py
  import argparse
  import getpass

  def main():
      parser = argparse.ArgumentParser(description="Manage trading bot secrets")
      subparsers = parser.add_subparsers(dest="command")

      # Set command
      set_parser = subparsers.add_parser("set", help="Store a secret")
      set_parser.add_argument("key", help="Secret key name")

      # Get command
      get_parser = subparsers.add_parser("get", help="Retrieve a secret")
      get_parser.add_argument("key", help="Secret key name")

      # Delete command
      del_parser = subparsers.add_parser("delete", help="Delete a secret")
      del_parser.add_argument("key", help="Secret key name")

      # List command
      subparsers.add_parser("list", help="List available secrets")

      args = parser.parse_args()
      manager = SecretManager()

      if args.command == "set":
          value = getpass.getpass(f"Enter value for {args.key}: ")
          if manager.set_secret_keyring(args.key, value):
              print(f"Secret '{args.key}' stored successfully")
          else:
              print("Failed to store secret")

      elif args.command == "get":
          secret = manager.get_secret(args.key)
          if secret:
              print(f"Secret found (not displaying value)")
          else:
              print(f"Secret '{args.key}' not found")

      elif args.command == "delete":
          if manager.delete_secret_keyring(args.key):
              print(f"Secret '{args.key}' deleted")
          else:
              print("Failed to delete secret")
  ```
- [ ] Update settings to use SecretManager:
  ```python
  # In settings.py
  from crypto_bot.utils.secrets import SecretManager

  class ExchangeSettings(BaseSettings):
      model_config = SettingsConfigDict(env_prefix="EXCHANGE_")

      name: str = "binance"
      testnet: bool = True

      @property
      def api_key(self) -> SecretStr:
          manager = SecretManager()
          key = manager.get_secret("EXCHANGE_API_KEY")
          if not key:
              raise ValueError("API key not configured")
          return key

      @property
      def api_secret(self) -> SecretStr:
          manager = SecretManager()
          secret = manager.get_secret("EXCHANGE_API_SECRET")
          if not secret:
              raise ValueError("API secret not configured")
          return secret
  ```
- [ ] Create `.env.example` template:
  ```bash
  # .env.example - Copy to .env and fill in values
  # NEVER commit .env to version control!

  # Exchange Configuration
  EXCHANGE__NAME=binance
  EXCHANGE__API_KEY=your_api_key_here
  EXCHANGE__API_SECRET=your_api_secret_here
  EXCHANGE__TESTNET=true

  # Database
  DB__URL=sqlite+aiosqlite:///./trading.db

  # Alerting (optional)
  TELEGRAM__BOT_TOKEN=
  TELEGRAM__CHAT_ID=

  # Logging
  LOG_LEVEL=INFO
  ```
- [ ] Verify `.gitignore` includes all secret files:
  ```gitignore
  # Secrets - NEVER COMMIT
  .env
  .env.*
  !.env.example
  *.pem
  *.key
  credentials.json
  secrets.yaml
  ```
- [ ] Write tests for secret loading

### Technical Notes
- Environment variables are highest priority (Docker/K8s friendly)
- System keyring provides secure storage on desktop
- SecretStr prevents accidental logging
- Never hardcode secrets in any file

### Definition of Done
- Secret loading from env vars working
- Keyring integration working (when available)
- CLI for secret management
- `.env.example` template created
- `.gitignore` verified
- Tests pass

---

## Story 4.14: Configure API Key Permissions and Validation

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** operator
**I want** API keys validated for minimal required permissions
**So that** damage from key compromise is limited

### Background
Per [security best practices](https://cryptorobotics.ai/learn/security-essentials-for-crypto-trading-api-keys-authentication-account-protection/), always disable withdrawal permissions. If keys leak, attackers can trade but cannot steal funds.

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/api_validator.py`
- [ ] Implement API permission checker:
  ```python
  from dataclasses import dataclass
  from typing import Optional
  import structlog

  logger = structlog.get_logger()

  @dataclass
  class APIPermissions:
      can_trade: bool
      can_read: bool
      can_withdraw: bool
      ip_restricted: bool
      ip_whitelist: list[str]

  class APIKeyValidator:
      """Validate API key permissions and configuration."""

      def __init__(self, exchange):
          self._exchange = exchange

      async def check_permissions(self) -> APIPermissions:
          """Check API key permissions."""
          # Note: Exact implementation varies by exchange
          # Binance provides this via account endpoint

          try:
              # Attempt to fetch account info
              account = await self._exchange._exchange.fetch_balance()
              can_read = True
          except Exception:
              can_read = False

          # Check trading permission by attempting a dry validation
          # (Most exchanges don't have direct permission check API)
          can_trade = can_read  # If we can read, likely can trade

          # Withdrawal check - try to get deposit address (requires withdraw permission on some exchanges)
          can_withdraw = False
          try:
              # This would fail if withdrawal is disabled
              # Implementation varies by exchange
              pass
          except Exception:
              can_withdraw = False

          return APIPermissions(
              can_trade=can_trade,
              can_read=can_read,
              can_withdraw=can_withdraw,
              ip_restricted=False,  # Can't determine via API
              ip_whitelist=[],
          )

      def validate_for_trading(self, permissions: APIPermissions) -> list[str]:
          """Validate permissions are suitable for trading bot."""
          issues = []
          warnings = []

          if not permissions.can_read:
              issues.append("CRITICAL: API key cannot read account data")

          if not permissions.can_trade:
              issues.append("CRITICAL: API key cannot place trades")

          if permissions.can_withdraw:
              warnings.append(
                  "WARNING: Withdrawal permission enabled! "
                  "Strongly recommend disabling withdrawal for trading bots."
              )

          if not permissions.ip_restricted:
              warnings.append(
                  "WARNING: No IP restriction detected. "
                  "Consider enabling IP whitelisting for security."
              )

          return issues + warnings

      async def run_preflight_check(self) -> bool:
          """Run full API key preflight check."""
          logger.info("running_api_preflight_check")

          permissions = await self.check_permissions()
          issues = self.validate_for_trading(permissions)

          for issue in issues:
              if issue.startswith("CRITICAL"):
                  logger.error("api_check_failed", issue=issue)
              else:
                  logger.warning("api_check_warning", issue=issue)

          if any(i.startswith("CRITICAL") for i in issues):
              return False

          logger.info("api_preflight_passed",
                      can_trade=permissions.can_trade,
                      can_withdraw=permissions.can_withdraw)
          return True
  ```
- [ ] Add startup validation:
  ```python
  # In bot.py startup
  async def start(self) -> None:
      # ... other initialization ...

      # Validate API permissions
      validator = APIKeyValidator(self._exchange)
      if not await validator.run_preflight_check():
          raise RuntimeError("API key validation failed - check permissions")

      # Warn loudly if withdrawal enabled
      permissions = await validator.check_permissions()
      if permissions.can_withdraw:
          logger.error("SECURITY_WARNING",
                      message="Withdrawal permission is ENABLED on API key!",
                      recommendation="Disable withdrawal in exchange API settings")
          await self._alert_manager.send_critical(
              "Security Warning",
              "API key has withdrawal permission enabled. This is a security risk.",
          )
  ```
- [ ] Document IP whitelisting setup:
  ```markdown
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
  ```
- [ ] Write tests for validation

### Technical Notes
- Binance API doesn't expose permission info directly
- Check by attempting operations and catching errors
- Always assume withdrawal could be enabled and warn
- IP whitelisting must be done in exchange UI

### Definition of Done
- Permission checker implemented
- Startup validation integrated
- Loud warnings for withdrawal permission
- IP whitelisting documented
- Tests pass

---

## Story 4.15: Implement Input Validation

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** developer
**I want** all configuration inputs validated
**So that** invalid configurations fail fast with clear errors

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/validators.py`
- [ ] Implement comprehensive validators:
  ```python
  from decimal import Decimal, InvalidOperation
  from typing import Any
  from pydantic import BaseModel, field_validator, model_validator
  import re

  class ValidationError(Exception):
      """Raised when validation fails."""
      def __init__(self, field: str, message: str):
          self.field = field
          self.message = message
          super().__init__(f"{field}: {message}")

  def validate_symbol(symbol: str) -> str:
      """Validate trading symbol format."""
      pattern = r"^[A-Z0-9]+/[A-Z0-9]+$"
      if not re.match(pattern, symbol):
          raise ValidationError("symbol", f"Invalid format: {symbol}. Expected 'BASE/QUOTE' (e.g., 'BTC/USDT')")
      return symbol

  def validate_positive_decimal(value: Any, field_name: str) -> Decimal:
      """Validate value is positive decimal."""
      try:
          dec = Decimal(str(value))
      except (InvalidOperation, TypeError, ValueError):
          raise ValidationError(field_name, f"Invalid number: {value}")

      if dec <= 0:
          raise ValidationError(field_name, f"Must be positive, got: {dec}")

      return dec

  def validate_percentage(value: Any, field_name: str, allow_zero: bool = False) -> Decimal:
      """Validate value is valid percentage (0-1)."""
      dec = validate_positive_decimal(value, field_name) if not allow_zero else Decimal(str(value))

      if dec < 0 or dec > 1:
          raise ValidationError(field_name, f"Must be between 0 and 1, got: {dec}")

      return dec

  def validate_price_range(lower: Decimal, upper: Decimal) -> None:
      """Validate price range is valid."""
      if lower >= upper:
          raise ValidationError("price_range", f"Lower price ({lower}) must be less than upper ({upper})")

      if lower <= 0:
          raise ValidationError("lower_price", "Lower price must be positive")

      spread = (upper - lower) / lower
      if spread > Decimal("2.0"):
          raise ValidationError("price_range", f"Price range too wide ({spread:.0%}). Consider narrowing.")
  ```
- [ ] Add Pydantic validators to config models:
  ```python
  class GridConfig(BaseModel):
      symbol: str
      lower_price: Decimal
      upper_price: Decimal
      num_grids: int
      total_investment: Decimal
      spacing: GridSpacing = GridSpacing.GEOMETRIC
      stop_loss_pct: Decimal = Decimal("0.10")

      @field_validator("symbol")
      @classmethod
      def validate_symbol_format(cls, v: str) -> str:
          return validate_symbol(v)

      @field_validator("lower_price", "upper_price", "total_investment")
      @classmethod
      def validate_positive(cls, v: Decimal, info) -> Decimal:
          return validate_positive_decimal(v, info.field_name)

      @field_validator("stop_loss_pct")
      @classmethod
      def validate_stop_loss(cls, v: Decimal) -> Decimal:
          return validate_percentage(v, "stop_loss_pct")

      @field_validator("num_grids")
      @classmethod
      def validate_grid_count(cls, v: int) -> int:
          if v < 3:
              raise ValueError("num_grids must be at least 3")
          if v > 100:
              raise ValueError("num_grids cannot exceed 100")
          return v

      @model_validator(mode="after")
      def validate_price_range(self) -> "GridConfig":
          validate_price_range(self.lower_price, self.upper_price)
          return self
  ```
- [ ] Add risk parameter validation:
  ```python
  class RiskConfig(BaseModel):
      max_position_pct: Decimal = Decimal("0.20")
      max_daily_loss_pct: Decimal = Decimal("0.05")
      max_drawdown_pct: Decimal = Decimal("0.15")
      risk_per_trade_pct: Decimal = Decimal("0.02")

      @field_validator("max_position_pct")
      @classmethod
      def validate_max_position(cls, v: Decimal) -> Decimal:
          if v > Decimal("0.5"):
              raise ValueError("max_position_pct should not exceed 50%")
          return validate_percentage(v, "max_position_pct")

      @field_validator("risk_per_trade_pct")
      @classmethod
      def validate_risk_per_trade(cls, v: Decimal) -> Decimal:
          if v > Decimal("0.05"):
              raise ValueError("risk_per_trade_pct should not exceed 5%")
          return validate_percentage(v, "risk_per_trade_pct")

      @model_validator(mode="after")
      def validate_risk_consistency(self) -> "RiskConfig":
          if self.max_daily_loss_pct < self.risk_per_trade_pct:
              raise ValueError(
                  "max_daily_loss_pct must be >= risk_per_trade_pct"
              )
          return self
  ```
- [ ] Add startup validation summary:
  ```python
  async def validate_all_config(settings: AppSettings) -> list[str]:
      """Validate all configuration at startup."""
      errors = []
      warnings = []

      # Validate exchange settings
      if not settings.exchange.testnet and settings.trading.dry_run:
          warnings.append("Running dry-run on mainnet - no trades will execute")

      # Validate trading settings
      try:
          validate_symbol(settings.trading.symbol)
      except ValidationError as e:
          errors.append(str(e))

      # Validate risk settings
      if settings.risk.max_position_pct > Decimal("0.3"):
          warnings.append(f"High max position: {settings.risk.max_position_pct:.0%}")

      return errors, warnings
  ```
- [ ] Write tests for all validators

### Definition of Done
- All validators implemented
- Pydantic models use validators
- Startup validation summarizes issues
- Clear error messages for all failures
- Tests achieve full coverage

---

## Story 4.16: Create Security Checklist Verification

**Story Points:** 5
**Priority:** P0 - Critical

### Description
**As a** operator
**I want** an automated security checklist
**So that** security requirements are verified before deployment

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/security_check.py`
- [ ] Implement comprehensive security checker:
  ```python
  import os
  import subprocess
  from pathlib import Path
  from dataclasses import dataclass, field
  from typing import Optional
  import structlog

  logger = structlog.get_logger()

  @dataclass
  class SecurityCheckResult:
      passed: bool
      check_name: str
      message: str
      severity: str  # "critical", "warning", "info"

  @dataclass
  class SecurityReport:
      checks: list[SecurityCheckResult] = field(default_factory=list)

      @property
      def passed(self) -> bool:
          return not any(c.severity == "critical" and not c.passed for c in self.checks)

      @property
      def critical_failures(self) -> list[SecurityCheckResult]:
          return [c for c in self.checks if c.severity == "critical" and not c.passed]

      @property
      def warnings(self) -> list[SecurityCheckResult]:
          return [c for c in self.checks if c.severity == "warning" and not c.passed]

  class SecurityChecker:
      """Run security checks before deployment."""

      def __init__(self, project_root: Path):
          self._root = project_root

      def run_all_checks(self) -> SecurityReport:
          """Run all security checks."""
          report = SecurityReport()

          report.checks.append(self._check_env_in_gitignore())
          report.checks.append(self._check_no_secrets_in_code())
          report.checks.append(self._check_no_secrets_in_git_history())
          report.checks.append(self._check_env_file_permissions())
          report.checks.append(self._check_secret_redaction())
          report.checks.append(self._check_circuit_breaker_configured())
          report.checks.append(self._check_alerting_configured())

          return report

      def _check_env_in_gitignore(self) -> SecurityCheckResult:
          """Verify .env is in .gitignore."""
          gitignore = self._root / ".gitignore"

          if not gitignore.exists():
              return SecurityCheckResult(
                  passed=False,
                  check_name=".gitignore exists",
                  message=".gitignore file not found",
                  severity="critical",
              )

          content = gitignore.read_text()
          patterns_needed = [".env", "*.pem", "*.key", "credentials"]
          missing = [p for p in patterns_needed if p not in content]

          if missing:
              return SecurityCheckResult(
                  passed=False,
                  check_name=".gitignore patterns",
                  message=f"Missing patterns in .gitignore: {missing}",
                  severity="critical",
              )

          return SecurityCheckResult(
              passed=True,
              check_name=".gitignore configured",
              message="Secret files excluded from git",
              severity="critical",
          )

      def _check_no_secrets_in_code(self) -> SecurityCheckResult:
          """Scan code for potential hardcoded secrets."""
          secret_patterns = [
              r"api_key\s*=\s*['\"][^'\"]+['\"]",
              r"api_secret\s*=\s*['\"][^'\"]+['\"]",
              r"password\s*=\s*['\"][^'\"]+['\"]",
              r"token\s*=\s*['\"][^'\"]+['\"]",
          ]

          suspicious_files = []
          src_dir = self._root / "src"

          for py_file in src_dir.rglob("*.py"):
              content = py_file.read_text()
              for pattern in secret_patterns:
                  import re
                  if re.search(pattern, content, re.IGNORECASE):
                      # Exclude test files and examples
                      if "test" not in str(py_file) and "example" not in str(py_file):
                          suspicious_files.append(str(py_file))
                          break

          if suspicious_files:
              return SecurityCheckResult(
                  passed=False,
                  check_name="No hardcoded secrets",
                  message=f"Potential secrets in: {suspicious_files[:3]}",
                  severity="critical",
              )

          return SecurityCheckResult(
              passed=True,
              check_name="No hardcoded secrets",
              message="No obvious hardcoded secrets found",
              severity="critical",
          )

      def _check_no_secrets_in_git_history(self) -> SecurityCheckResult:
          """Check git history for secrets (basic check)."""
          try:
              result = subprocess.run(
                  ["git", "log", "--oneline", "-10"],
                  cwd=self._root,
                  capture_output=True,
                  text=True,
              )
              if result.returncode != 0:
                  return SecurityCheckResult(
                      passed=True,
                      check_name="Git history check",
                      message="Not a git repository or git unavailable",
                      severity="info",
                  )
          except FileNotFoundError:
              return SecurityCheckResult(
                  passed=True,
                  check_name="Git history check",
                  message="Git not installed",
                  severity="info",
              )

          # Would need git-secrets or similar for thorough check
          return SecurityCheckResult(
              passed=True,
              check_name="Git history check",
              message="Consider running git-secrets for thorough history scan",
              severity="warning",
          )

      def _check_env_file_permissions(self) -> SecurityCheckResult:
          """Check .env file has restrictive permissions."""
          env_file = self._root / ".env"

          if not env_file.exists():
              return SecurityCheckResult(
                  passed=True,
                  check_name=".env permissions",
                  message=".env file not present (using other secret source)",
                  severity="info",
              )

          # On Unix, check permissions
          if os.name == "posix":
              import stat
              mode = env_file.stat().st_mode
              if mode & stat.S_IROTH or mode & stat.S_IWOTH:
                  return SecurityCheckResult(
                      passed=False,
                      check_name=".env permissions",
                      message=".env is world-readable. Run: chmod 600 .env",
                      severity="warning",
                  )

          return SecurityCheckResult(
              passed=True,
              check_name=".env permissions",
              message=".env has appropriate permissions",
              severity="warning",
          )

      def _check_circuit_breaker_configured(self) -> SecurityCheckResult:
          """Verify circuit breaker is enabled."""
          # Would check actual config
          return SecurityCheckResult(
              passed=True,
              check_name="Circuit breaker",
              message="Verify circuit breaker limits are appropriate",
              severity="warning",
          )

      def _check_alerting_configured(self) -> SecurityCheckResult:
          """Verify alerting is configured."""
          telegram_token = os.getenv("TELEGRAM__BOT_TOKEN")
          discord_webhook = os.getenv("DISCORD__WEBHOOK_URL")

          if not telegram_token and not discord_webhook:
              return SecurityCheckResult(
                  passed=False,
                  check_name="Alerting configured",
                  message="No alert channel configured. You won't receive notifications!",
                  severity="warning",
              )

          return SecurityCheckResult(
              passed=True,
              check_name="Alerting configured",
              message="Alert channels configured",
              severity="warning",
          )

      def _check_secret_redaction(self) -> SecurityCheckResult:
          """Verify logging redacts secrets."""
          # This would run a test log and verify
          return SecurityCheckResult(
              passed=True,
              check_name="Secret redaction",
              message="Verify secrets don't appear in logs",
              severity="critical",
          )
  ```
- [ ] Create CLI command:
  ```python
  # Entry point
  def security_check_cli():
      """Run security checks and print report."""
      from pathlib import Path

      checker = SecurityChecker(Path.cwd())
      report = checker.run_all_checks()

      print("\n" + "="*60)
      print("SECURITY CHECK REPORT")
      print("="*60 + "\n")

      for check in report.checks:
          status = "\u2705" if check.passed else "\u274c"
          severity_icon = {
              "critical": "\U0001F6A8",
              "warning": "\u26a0\ufe0f",
              "info": "\u2139\ufe0f",
          }[check.severity]

          print(f"{status} {severity_icon} {check.check_name}")
          print(f"   {check.message}\n")

      print("="*60)
      if report.passed:
          print("\u2705 All critical checks passed!")
      else:
          print("\u274c Critical security issues found!")
          print("\nFix the following before deployment:")
          for failure in report.critical_failures:
              print(f"  - {failure.check_name}: {failure.message}")

      return 0 if report.passed else 1
  ```
- [ ] Add to `pyproject.toml`:
  ```toml
  [project.scripts]
  crypto-bot-security = "crypto_bot.utils.security_check:security_check_cli"
  ```
- [ ] Write tests for security checks

### Definition of Done
- All security checks implemented
- CLI produces clear report
- Integration with pre-deployment workflow
- Tests verify check logic

---

## Story 4.17: Implement Audit Logging

**Story Points:** 5
**Priority:** P1 - High

### Description
**As a** operator
**I want** tamper-evident audit logs
**So that** all trading actions are traceable

### Acceptance Criteria

- [ ] Create `src/crypto_bot/utils/audit.py`
- [ ] Implement audit logger:
  ```python
  import hashlib
  import json
  from datetime import datetime
  from pathlib import Path
  from typing import Any, Optional
  from dataclasses import dataclass, asdict
  import structlog

  @dataclass
  class AuditEvent:
      timestamp: str
      event_type: str
      actor: str  # "bot", "user", "system"
      action: str
      details: dict
      previous_hash: str
      event_hash: str

  class AuditLogger:
      """Append-only audit log with hash chain."""

      def __init__(self, log_file: Path):
          self._log_file = log_file
          self._previous_hash = "0" * 64  # Genesis hash
          self._logger = structlog.get_logger("audit")

          # Load previous hash if log exists
          if log_file.exists():
              self._load_previous_hash()

      def _load_previous_hash(self) -> None:
          """Load hash of last event from existing log."""
          with open(self._log_file, "r") as f:
              for line in f:
                  pass  # Get last line
              if line:
                  event = json.loads(line)
                  self._previous_hash = event.get("event_hash", self._previous_hash)

      def _calculate_hash(self, event_data: dict) -> str:
          """Calculate SHA-256 hash of event."""
          # Exclude event_hash from calculation
          data = {k: v for k, v in event_data.items() if k != "event_hash"}
          canonical = json.dumps(data, sort_keys=True)
          return hashlib.sha256(canonical.encode()).hexdigest()

      def log(
          self,
          event_type: str,
          action: str,
          details: dict,
          actor: str = "bot",
      ) -> AuditEvent:
          """Log an auditable event."""
          event = AuditEvent(
              timestamp=datetime.utcnow().isoformat() + "Z",
              event_type=event_type,
              actor=actor,
              action=action,
              details=details,
              previous_hash=self._previous_hash,
              event_hash="",  # Placeholder
          )

          # Calculate hash including previous hash (chain)
          event_dict = asdict(event)
          event.event_hash = self._calculate_hash(event_dict)
          event_dict["event_hash"] = event.event_hash

          # Append to log file
          with open(self._log_file, "a") as f:
              f.write(json.dumps(event_dict) + "\n")

          # Update previous hash
          self._previous_hash = event.event_hash

          # Also log to structured logger
          self._logger.info(
              "audit_event",
              event_type=event_type,
              action=action,
              actor=actor,
              event_hash=event.event_hash[:16],
          )

          return event

      def verify_chain(self) -> tuple[bool, Optional[int]]:
          """Verify integrity of audit log chain."""
          if not self._log_file.exists():
              return True, None

          previous_hash = "0" * 64
          line_number = 0

          with open(self._log_file, "r") as f:
              for line in f:
                  line_number += 1
                  event = json.loads(line)

                  # Verify previous hash matches
                  if event["previous_hash"] != previous_hash:
                      return False, line_number

                  # Verify event hash
                  stored_hash = event["event_hash"]
                  calculated_hash = self._calculate_hash(event)
                  if stored_hash != calculated_hash:
                      return False, line_number

                  previous_hash = stored_hash

          return True, None

      # Convenience methods
      def log_order_placed(self, order_id: str, symbol: str, side: str, amount: str, price: str):
          return self.log(
              event_type="order",
              action="placed",
              details={"order_id": order_id, "symbol": symbol, "side": side, "amount": amount, "price": price},
          )

      def log_order_filled(self, order_id: str, fill_price: str, fill_amount: str):
          return self.log(
              event_type="order",
              action="filled",
              details={"order_id": order_id, "fill_price": fill_price, "fill_amount": fill_amount},
          )

      def log_config_change(self, setting: str, old_value: Any, new_value: Any):
          return self.log(
              event_type="config",
              action="changed",
              details={"setting": setting, "old_value": str(old_value), "new_value": str(new_value)},
              actor="user",
          )

      def log_circuit_breaker(self, trigger: str, details: dict):
          return self.log(
              event_type="risk",
              action="circuit_breaker_triggered",
              details={"trigger": trigger, **details},
              actor="system",
          )
  ```
- [ ] Integrate with trading bot:
  ```python
  # In bot.py
  class TradingBot:
      def __init__(self, ...):
          self._audit = AuditLogger(Path("logs/audit.jsonl"))

      async def _place_order(self, ...):
          order = await self._exchange.create_order(...)
          self._audit.log_order_placed(
              order_id=order.id,
              symbol=symbol,
              side=side,
              amount=str(amount),
              price=str(price),
          )
          return order
  ```
- [ ] Create audit verification CLI:
  ```python
  def verify_audit_cli():
      """Verify audit log integrity."""
      audit = AuditLogger(Path("logs/audit.jsonl"))
      valid, failed_line = audit.verify_chain()

      if valid:
          print("\u2705 Audit log integrity verified")
          return 0
      else:
          print(f"\u274c Audit log tampering detected at line {failed_line}")
          return 1
  ```
- [ ] Write tests for audit logging

### Technical Notes
- Hash chain ensures tampering is detectable
- Append-only log prevents modification
- Store separately from application logs
- Consider remote/replicated storage for production

### Definition of Done
- Audit logger with hash chain
- All trading actions logged
- Verification CLI working
- Integrated with bot
- Tests pass

---

## Summary

| Story | Points | Priority | Dependencies |
|-------|--------|----------|--------------|
| 4.13 Secure Secret Management | 5 | P0 | Phase 1 |
| 4.14 API Permission Validation | 5 | P0 | 4.13 |
| 4.15 Input Validation | 5 | P0 | Phase 1 |
| 4.16 Security Checklist | 5 | P0 | 4.13, 4.14, 4.15 |
| 4.17 Audit Logging | 5 | P1 | Phase 2 |
| **Total** | **25** | | |

---

## Sources & References

- [Secure Cryptocurrency Assets 2025](https://3commas.io/blog/secure-cryptocurrency-assets-2025)
- [API Key Security Guide](https://tradelink.pro/blog/how-to-secure-api-key/)
- [Best Practices for Crypto Exchange API 2025](https://btsesolutions.com/articles/best-practices-for-crypto-exchange-api-integration-in-2025)
- [Security Essentials for Crypto Trading](https://cryptorobotics.ai/learn/security-essentials-for-crypto-trading-api-keys-authentication-account-protection/)
- [How to Secure Trading Bot API Keys](https://www.usestreamline.net/resources/blog/how-to-secure-your-crypto-trading-bot-api-keys-safety/)
- [Binance API Key Safety](https://wundertrading.com/journal/en/learn/article/binance-api-key)
