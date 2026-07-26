"""Medical OS platform core."""

from app.platform.quality_gate import QualityGateResult, run_quality_gate

__all__ = ["QualityGateResult", "run_quality_gate"]
