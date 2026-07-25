"""Structured routing trace — logs every condition for debugging."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("doctor_boysunov.routing_trace")

ROUTING_FIX_VERSION = "2026-07-26-salom-medical-ai-v2"


@dataclass
class RoutingTrace:
    telegram_id: int
    text: str
    entry_handler: str
    checks: list[dict[str, object]] = field(default_factory=list)
    handlers_considered: list[str] = field(default_factory=list)
    selected_handler: str | None = None
    selected_reason: str | None = None
    medical_ai_called: bool = False
    medical_ai_skipped_reason: str | None = None

    def consider(self, handler: str) -> None:
        self.handlers_considered.append(handler)

    def check(
        self,
        *,
        location: str,
        condition: str,
        result: bool,
        detail: str = "",
    ) -> bool:
        entry = {
            "location": location,
            "condition": condition,
            "result": result,
            "detail": detail,
        }
        self.checks.append(entry)
        logger.info(
            "routing_trace_check telegram_id=%s text=%r location=%s condition=%s result=%s detail=%s",
            self.telegram_id,
            self.text[:120],
            location,
            condition,
            result,
            detail,
        )
        return result

    def select(self, handler: str, reason: str) -> None:
        self.selected_handler = handler
        self.selected_reason = reason
        logger.info(
            "routing_trace_select telegram_id=%s text=%r handler=%s reason=%s",
            self.telegram_id,
            self.text[:120],
            handler,
            reason,
        )

    def skip_medical_ai(self, reason: str) -> None:
        self.medical_ai_skipped_reason = reason
        logger.info(
            "routing_trace_medical_ai_skipped telegram_id=%s text=%r reason=%s",
            self.telegram_id,
            self.text[:120],
            reason,
        )

    def medical_ai(self, reason: str) -> None:
        self.medical_ai_called = True
        self.medical_ai_skipped_reason = None
        self.select("Medical AI (ask_ai)", reason)
        logger.info(
            "routing_trace_medical_ai telegram_id=%s text=%r reason=%s",
            self.telegram_id,
            self.text[:120],
            reason,
        )

    def dump(self) -> str:
        payload = {
            "routing_fix_version": ROUTING_FIX_VERSION,
            "telegram_id": self.telegram_id,
            "text": self.text,
            "entry_handler": self.entry_handler,
            "handlers_considered": self.handlers_considered,
            "checks": self.checks,
            "selected_handler": self.selected_handler,
            "selected_reason": self.selected_reason,
            "medical_ai_called": self.medical_ai_called,
            "medical_ai_skipped_reason": self.medical_ai_skipped_reason,
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        print(f"=== ROUTING TRACE ===\n{rendered}")
        logger.info("routing_trace_dump %s", rendered)
        return rendered
