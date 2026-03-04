"""Alert threshold evaluation — pure function, no I/O."""
from __future__ import annotations

from collections import defaultdict

from src.schemas.payments import TransactionSummary

from src.backend.transforms.alert_models import AlertConfig, AlertResult, AlertSeverity


def check_success_rate_alert(
    summaries: list[TransactionSummary],
    config: AlertConfig,
) -> AlertResult:
    """Return the highest-severity failure-rate breach across merchants.

    Each merchant's worst daily failure_rate is compared against config
    thresholds.  The overall result reflects the single worst severity
    found — matching how on-call systems surface one incident, not noise.
    """
    if not summaries:
        return AlertResult(
            severity            = AlertSeverity.OK,
            breaching_merchants = [],
            human_summary       = "No transaction data in evaluation window.",
        )

    critical_merchants: list[str] = []
    warning_merchants:  list[str] = []

    worst: defaultdict[str, float] = defaultdict(float)
    for summary in summaries:
        if summary.txn_count >= config.min_transaction_count:
            worst[summary.merchant_id] = max(
                worst[summary.merchant_id], summary.failure_rate
            )

    for merchant_id, worst_rate in worst.items():
        if worst_rate >= config.critical_threshold:
            critical_merchants.append(merchant_id)
        elif worst_rate >= config.warning_threshold:
            warning_merchants.append(merchant_id)

    if critical_merchants:
        return AlertResult(
            severity            = AlertSeverity.CRITICAL,
            breaching_merchants = critical_merchants,
            human_summary       = (
                f"CRITICAL: {len(critical_merchants)} merchant(s) above "
                f"{config.critical_threshold:.0%} failure threshold — "
                f"{', '.join(critical_merchants)}"
            ),
        )

    if warning_merchants:
        return AlertResult(
            severity            = AlertSeverity.WARNING,
            breaching_merchants = warning_merchants,
            human_summary       = (
                f"WARNING: {len(warning_merchants)} merchant(s) above "
                f"{config.warning_threshold:.0%} failure threshold — "
                f"{', '.join(warning_merchants)}"
            ),
        )

    return AlertResult(
        severity            = AlertSeverity.OK,
        breaching_merchants = [],
        human_summary       = (
            f"All {len(summaries)} merchant(s) within normal thresholds."
        ),
    )
