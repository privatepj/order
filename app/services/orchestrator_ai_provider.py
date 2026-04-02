from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List


class AdviceProvider:
    def generate(self, *, event_type: str, payload: Dict[str, Any], action_types: List[str]) -> List[Dict[str, Any]]:
        raise NotImplementedError()


class RuleTemplateAdviceProvider(AdviceProvider):
    def generate(self, *, event_type: str, payload: Dict[str, Any], action_types: List[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for action_type in action_types:
            if action_type in ("ApplyAlternativeMaterial", "CreateOutsourceOrder", "SwitchSecondarySupplier"):
                out.append(
                    {
                        "advice_type": "strategy",
                        "recommended_action": action_type,
                        "confidence": Decimal("0.7500"),
                        "reason": f"规则模板建议({event_type})",
                        "meta": {"event_type": event_type},
                    }
                )
        return out


def get_default_provider() -> AdviceProvider:
    return RuleTemplateAdviceProvider()
