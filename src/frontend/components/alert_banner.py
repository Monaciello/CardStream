"""Alert banner component — renders AlertResult as a coloured Streamlit banner."""
from __future__ import annotations

from typing import Callable

import streamlit as st

from src.backend.transforms.alert_models import AlertResult, AlertSeverity

_SEVERITY_RENDERERS: dict[AlertSeverity, Callable[[str], object]] = {
    AlertSeverity.OK:       st.success,
    AlertSeverity.WARNING:  st.warning,
    AlertSeverity.CRITICAL: st.error,
}


def render_alert_banner(alert: AlertResult) -> None:
    """Display a single severity-coloured banner with *alert.human_summary*.

    Args:
        alert: Output of ``check_success_rate_alert``.  OK severity
            renders a green confirmation, not silence.
    """
    render = _SEVERITY_RENDERERS[alert.severity]
    render(alert.human_summary)
