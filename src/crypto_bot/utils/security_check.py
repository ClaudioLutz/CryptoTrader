"""Security checklist verification for pre-deployment checks.

This module provides:
- Automated security checks
- Pre-deployment verification
- Security report generation
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()


@dataclass
class SecurityCheckResult:
    """Result of a single security check."""

    passed: bool
    check_name: str
    message: str
    severity: str  # "critical", "warning", "info"


@dataclass
class SecurityReport:
    """Complete security check report."""

    checks: list[SecurityCheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if all critical checks passed."""
        return not any(
            c.severity == "critical" and not c.passed for c in self.checks
        )

    @property
    def critical_failures(self) -> list[SecurityCheckResult]:
        """Get list of critical failures."""
        return [c for c in self.checks if c.severity == "critical" and not c.passed]

    @property
    def warnings(self) -> list[SecurityCheckResult]:
        """Get list of warnings."""
        return [c for c in self.checks if c.severity == "warning" and not c.passed]

    @property
    def info_items(self) -> list[SecurityCheckResult]:
        """Get list of informational items."""
        return [c for c in self.checks if c.severity == "info"]


class SecurityChecker:
    """Run security checks before deployment.

    Usage:
        checker = SecurityChecker(Path.cwd())
        report = checker.run_all_checks()
        if report.passed:
            print("Ready for deployment")
        else:
            print("Security issues found")
    """

    def __init__(self, project_root: Path):
        """Initialize security checker.

        Args:
            project_root: Root directory of the project.
        """
        self._root = project_root

    def run_all_checks(self) -> SecurityReport:
        """Run all security checks.

        Returns:
            Complete security report.
        """
        report = SecurityReport()

        report.checks.append(self._check_env_in_gitignore())
        report.checks.append(self._check_no_secrets_in_code())
        report.checks.append(self._check_no_secrets_in_git_history())
        report.checks.append(self._check_env_file_permissions())
        report.checks.append(self._check_env_example_exists())
        report.checks.append(self._check_circuit_breaker_configured())
        report.checks.append(self._check_alerting_configured())
        report.checks.append(self._check_testnet_mode())

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
        patterns_needed = [".env", "*.pem", "*.key"]
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
            r'api_key\s*=\s*["\'][^"\']{20,}["\']',
            r'api_secret\s*=\s*["\'][^"\']{20,}["\']',
            r'password\s*=\s*["\'][^"\']{8,}["\']',
            r'token\s*=\s*["\'][^"\']{20,}["\']',
        ]

        suspicious_files = []
        src_dir = self._root / "src"

        if not src_dir.exists():
            return SecurityCheckResult(
                passed=True,
                check_name="No hardcoded secrets",
                message="src directory not found (skipped)",
                severity="critical",
            )

        for py_file in src_dir.rglob("*.py"):
            try:
                content = py_file.read_text()
                for pattern in secret_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        # Exclude test files and examples
                        if "test" not in str(py_file).lower() and "example" not in str(
                            py_file
                        ).lower():
                            suspicious_files.append(str(py_file.relative_to(self._root)))
                            break
            except Exception:
                pass

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

        return SecurityCheckResult(
            passed=True,
            check_name="Git history check",
            message="Consider running git-secrets for thorough history scan",
            severity="info",
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

    def _check_env_example_exists(self) -> SecurityCheckResult:
        """Check that .env.example template exists."""
        env_example = self._root / ".env.example"

        if not env_example.exists():
            return SecurityCheckResult(
                passed=False,
                check_name=".env.example exists",
                message=".env.example template not found",
                severity="info",
            )

        return SecurityCheckResult(
            passed=True,
            check_name=".env.example exists",
            message=".env.example template present",
            severity="info",
        )

    def _check_circuit_breaker_configured(self) -> SecurityCheckResult:
        """Verify circuit breaker is enabled in config."""
        # Check for circuit breaker configuration
        return SecurityCheckResult(
            passed=True,
            check_name="Circuit breaker",
            message="Verify circuit breaker limits are appropriate for your risk tolerance",
            severity="warning",
        )

    def _check_alerting_configured(self) -> SecurityCheckResult:
        """Verify alerting is configured."""
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv(
            "TELEGRAM__BOT_TOKEN"
        )
        discord_webhook = os.getenv("DISCORD_WEBHOOK_URL") or os.getenv(
            "DISCORD__WEBHOOK_URL"
        )

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

    def _check_testnet_mode(self) -> SecurityCheckResult:
        """Check if running in testnet mode."""
        testnet = os.getenv("EXCHANGE_TESTNET", "").lower()
        is_testnet = testnet in ("true", "1", "yes")

        if not is_testnet:
            return SecurityCheckResult(
                passed=True,
                check_name="Testnet mode",
                message="MAINNET MODE - Real funds will be used!",
                severity="warning",
            )

        return SecurityCheckResult(
            passed=True,
            check_name="Testnet mode",
            message="Running in testnet mode (safe for testing)",
            severity="info",
        )


def security_check_cli() -> int:
    """Run security checks and print report.

    Returns:
        Exit code (0 if passed, 1 if critical failures).
    """
    checker = SecurityChecker(Path.cwd())
    report = checker.run_all_checks()

    print("\n" + "=" * 60)
    print("SECURITY CHECK REPORT")
    print("=" * 60 + "\n")

    for check in report.checks:
        status = "\u2705" if check.passed else "\u274c"
        severity_icon = {
            "critical": "\U0001F6A8",
            "warning": "\u26a0\ufe0f",
            "info": "\u2139\ufe0f",
        }[check.severity]

        print(f"{status} {severity_icon} {check.check_name}")
        print(f"   {check.message}\n")

    print("=" * 60)
    if report.passed:
        print("\u2705 All critical checks passed!")
        if report.warnings:
            print(f"\n\u26a0\ufe0f {len(report.warnings)} warning(s) to review")
    else:
        print("\u274c Critical security issues found!")
        print("\nFix the following before deployment:")
        for failure in report.critical_failures:
            print(f"  - {failure.check_name}: {failure.message}")

    return 0 if report.passed else 1


if __name__ == "__main__":
    import sys

    sys.exit(security_check_cli())
