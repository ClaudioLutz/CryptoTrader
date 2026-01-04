"""Tamper-evident audit logging for trading actions.

This module provides:
- Hash-chained audit log for integrity verification
- Structured audit events for trading actions
- CLI for audit log verification
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger("audit")


@dataclass
class AuditEvent:
    """A single audit log event."""

    timestamp: str
    event_type: str
    actor: str  # "bot", "user", "system"
    action: str
    details: dict[str, Any]
    previous_hash: str
    event_hash: str


class AuditLogger:
    """Append-only audit log with hash chain for integrity.

    Each event includes a hash of the previous event, creating
    a chain that makes tampering detectable.

    Usage:
        audit = AuditLogger(Path("logs/audit.jsonl"))
        audit.log_order_placed(
            order_id="123",
            symbol="BTC/USDT",
            side="buy",
            amount="0.1",
            price="42000",
        )

        # Verify integrity
        is_valid, failed_line = audit.verify_chain()
    """

    def __init__(self, log_file: Path):
        """Initialize audit logger.

        Args:
            log_file: Path to audit log file.
        """
        self._log_file = log_file
        self._previous_hash = "0" * 64  # Genesis hash

        # Ensure directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Load previous hash if log exists
        if log_file.exists():
            self._load_previous_hash()

    def _load_previous_hash(self) -> None:
        """Load hash of last event from existing log."""
        try:
            with open(self._log_file, "r") as f:
                last_line = None
                for line in f:
                    if line.strip():
                        last_line = line
                if last_line:
                    event = json.loads(last_line)
                    self._previous_hash = event.get("event_hash", self._previous_hash)
        except Exception as e:
            logger.warning("audit_load_error", error=str(e))

    def _calculate_hash(self, event_data: dict[str, Any]) -> str:
        """Calculate SHA-256 hash of event.

        Args:
            event_data: Event data to hash.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        # Exclude event_hash from calculation
        data = {k: v for k, v in event_data.items() if k != "event_hash"}
        canonical = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def log(
        self,
        event_type: str,
        action: str,
        details: dict[str, Any],
        actor: str = "bot",
    ) -> AuditEvent:
        """Log an auditable event.

        Args:
            event_type: Type of event (order, config, risk, etc.).
            action: Action performed.
            details: Event details.
            actor: Who performed the action.

        Returns:
            The logged audit event.
        """
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
        logger.info(
            "audit_event",
            event_type=event_type,
            action=action,
            actor=actor,
            event_hash=event.event_hash[:16],
        )

        return event

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """Verify integrity of audit log chain.

        Returns:
            Tuple of (is_valid, failed_line_number).
            failed_line_number is None if valid.
        """
        if not self._log_file.exists():
            return True, None

        previous_hash = "0" * 64
        line_number = 0

        with open(self._log_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue

                line_number += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    return False, line_number

                # Verify previous hash matches
                if event.get("previous_hash") != previous_hash:
                    return False, line_number

                # Verify event hash
                stored_hash = event.get("event_hash", "")
                calculated_hash = self._calculate_hash(event)
                if stored_hash != calculated_hash:
                    return False, line_number

                previous_hash = stored_hash

        return True, None

    def get_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent audit events.

        Args:
            event_type: Filter by event type.
            limit: Maximum number of events.

        Returns:
            List of audit events (newest first).
        """
        if not self._log_file.exists():
            return []

        events = []
        with open(self._log_file, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event_type is None or event.get("event_type") == event_type:
                        events.append(event)
                except json.JSONDecodeError:
                    continue

        # Return newest first, limited
        return list(reversed(events[-limit:]))

    # Convenience methods for common events
    def log_order_placed(
        self,
        order_id: str,
        symbol: str,
        side: str,
        amount: str,
        price: str,
    ) -> AuditEvent:
        """Log order placement."""
        return self.log(
            event_type="order",
            action="placed",
            details={
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
            },
        )

    def log_order_filled(
        self,
        order_id: str,
        fill_price: str,
        fill_amount: str,
    ) -> AuditEvent:
        """Log order fill."""
        return self.log(
            event_type="order",
            action="filled",
            details={
                "order_id": order_id,
                "fill_price": fill_price,
                "fill_amount": fill_amount,
            },
        )

    def log_order_cancelled(
        self,
        order_id: str,
        reason: Optional[str] = None,
    ) -> AuditEvent:
        """Log order cancellation."""
        return self.log(
            event_type="order",
            action="cancelled",
            details={
                "order_id": order_id,
                "reason": reason or "user_request",
            },
        )

    def log_config_change(
        self,
        setting: str,
        old_value: Any,
        new_value: Any,
    ) -> AuditEvent:
        """Log configuration change."""
        return self.log(
            event_type="config",
            action="changed",
            details={
                "setting": setting,
                "old_value": str(old_value),
                "new_value": str(new_value),
            },
            actor="user",
        )

    def log_circuit_breaker(
        self,
        trigger: str,
        details: dict[str, Any],
    ) -> AuditEvent:
        """Log circuit breaker trigger."""
        return self.log(
            event_type="risk",
            action="circuit_breaker_triggered",
            details={"trigger": trigger, **details},
            actor="system",
        )

    def log_bot_started(
        self,
        strategy: str,
        symbol: str,
        dry_run: bool,
    ) -> AuditEvent:
        """Log bot startup."""
        return self.log(
            event_type="system",
            action="bot_started",
            details={
                "strategy": strategy,
                "symbol": symbol,
                "dry_run": dry_run,
            },
            actor="system",
        )

    def log_bot_stopped(
        self,
        reason: str,
    ) -> AuditEvent:
        """Log bot shutdown."""
        return self.log(
            event_type="system",
            action="bot_stopped",
            details={"reason": reason},
            actor="system",
        )


def verify_audit_cli() -> int:
    """CLI to verify audit log integrity.

    Returns:
        Exit code (0 if valid, 1 if tampered).
    """
    import argparse

    parser = argparse.ArgumentParser(description="Verify audit log integrity")
    parser.add_argument(
        "--log-file",
        default="logs/audit.jsonl",
        help="Path to audit log file",
    )
    parser.add_argument(
        "--show-events",
        type=int,
        default=0,
        help="Show last N events",
    )

    args = parser.parse_args()
    log_path = Path(args.log_file)

    if not log_path.exists():
        print(f"Audit log not found: {log_path}")
        return 1

    audit = AuditLogger(log_path)
    valid, failed_line = audit.verify_chain()

    if valid:
        print("\u2705 Audit log integrity verified")

        if args.show_events > 0:
            print(f"\nLast {args.show_events} events:")
            events = audit.get_events(limit=args.show_events)
            for event in events:
                print(
                    f"  [{event['timestamp']}] {event['event_type']}.{event['action']}"
                )

        return 0
    else:
        print(f"\u274c Audit log tampering detected at line {failed_line}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(verify_audit_cli())
