"""
Attack orchestrator — runs attacks against Gemini, scores results, persists to DB.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from src.attacks.base import AttackResult, BaseAttack
from src.core.gemini_client import GeminiClient
from src.core.scorer import Scorer
from src.db.store import ResultStore
from src.config import settings

# ── Attack registry ─────────────────────────────────────────────
from src.attacks.persona import PERSONA_ATTACKS
from src.attacks.encoding import ENCODING_ATTACKS
from src.attacks.injection import INJECTION_ATTACKS
from src.attacks.obfuscation import OBFUSCATION_ATTACKS
from src.attacks.context_manipulation import CONTEXT_ATTACKS
from src.attacks.role_play import ROLEPLAY_ATTACKS
from src.attacks.multi_turn import MULTI_TURN_ATTACKS
from src.attacks.policy_puppetry import POLICY_ATTACKS
from src.attacks.distraction import DISTRACTION_ATTACKS
from src.attacks.suffix import SUFFIX_ATTACKS
from src.attacks.virtual_ai import VIRTUAL_AI_ATTACKS
from src.attacks.logic import LOGIC_ATTACKS
from src.attacks.advanced import ADVANCED_ATTACKS

ALL_ATTACK_CLASSES: list[type[BaseAttack]] = [
    *PERSONA_ATTACKS,
    *ENCODING_ATTACKS,
    *INJECTION_ATTACKS,
    *OBFUSCATION_ATTACKS,
    *CONTEXT_ATTACKS,
    *ROLEPLAY_ATTACKS,
    *MULTI_TURN_ATTACKS,
    *POLICY_ATTACKS,
    *DISTRACTION_ATTACKS,
    *SUFFIX_ATTACKS,
    *VIRTUAL_AI_ATTACKS,
    *LOGIC_ATTACKS,
    *ADVANCED_ATTACKS,
]


def get_attack_registry() -> dict[str, type[BaseAttack]]:
    """Return a name→class mapping of all available attacks."""
    return {cls().name: cls for cls in ALL_ATTACK_CLASSES}


def get_attacks_by_category() -> dict[str, list[type[BaseAttack]]]:
    """Group attacks by category."""
    groups: dict[str, list[type[BaseAttack]]] = {}
    for cls in ALL_ATTACK_CLASSES:
        inst = cls()
        cat = inst.category.value
        groups.setdefault(cat, []).append(cls)
    return groups


class AttackOrchestrator:
    """Runs selected attacks against the Gemini API, scores, and stores."""

    def __init__(
        self,
        client: GeminiClient | None = None,
        scorer: Scorer | None = None,
        store: ResultStore | None = None,
    ) -> None:
        self.client = client or GeminiClient()
        self.scorer = scorer or Scorer(judge_client=self.client)
        self.store = store or ResultStore()

    async def init(self) -> None:
        """Initialize the database."""
        await self.store.init_db()

    async def run_attack(
        self,
        attack: BaseAttack,
        target_topic: str,
        *,
        use_llm_judge: bool = True,
        on_progress: Callable[[str], None] | None = None,
    ) -> AttackResult:
        """Execute a single attack and return the scored result."""
        if on_progress:
            on_progress(f"Generating prompt: {attack.name}")

        prompt = await attack.generate_prompt(
            target_topic, model_name=self.client.model_name
        )

        if on_progress:
            on_progress(f"Sending to {self.client.model_name}...")

        t0 = time.monotonic()
        response = await self.client.generate(prompt)
        duration = (time.monotonic() - t0) * 1000

        result = AttackResult(
            attack_name=attack.name,
            category=attack.category.value if hasattr(attack.category, 'value') else str(attack.category),
            prompt_sent=prompt,
            response_received=response,
            model_used=self.client.model_name,
            duration_ms=round(duration, 1),
        )

        if on_progress:
            on_progress("Scoring response...")

        result = await self.scorer.score(result, use_llm_judge=use_llm_judge)

        # Persist
        await self.store.save_attack({
            "timestamp": result.timestamp.isoformat(),
            "technique": result.attack_name,
            "category": result.category,
            "prompt": result.prompt_sent,
            "response": result.response_received,
            "model": result.model_used,
            "refused": result.refused,
            "api_blocked": result.api_blocked,
            "policy_bypass": result.policy_bypass,
            "info_leaked": result.info_leaked,
            "jailbreak_score": result.jailbreak_score,
            "harmful_score": result.harmful_content_score,
            "duration_ms": result.duration_ms,
            "notes": result.notes,
        })

        if on_progress:
            status = "SUCCESS" if result.success else "FAILED"
            on_progress(f"{status} — Score: {result.jailbreak_score}/100")

        return result

    async def run_batch(
        self,
        attacks: list[BaseAttack],
        target_topic: str,
        *,
        use_llm_judge: bool = True,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[AttackResult]:
        """Run multiple attacks sequentially (respecting rate limits)."""
        results: list[AttackResult] = []
        for i, attack in enumerate(attacks, 1):
            if on_progress:
                on_progress(f"\n[{i}/{len(attacks)}] {attack.name}")
            result = await self.run_attack(
                attack, target_topic,
                use_llm_judge=use_llm_judge,
                on_progress=on_progress,
            )
            results.append(result)
        return results

    async def run_all(
        self,
        target_topic: str,
        *,
        use_llm_judge: bool = True,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[AttackResult]:
        """Run every registered attack."""
        attacks = [cls() for cls in ALL_ATTACK_CLASSES]
        return await self.run_batch(
            attacks, target_topic,
            use_llm_judge=use_llm_judge,
            on_progress=on_progress,
        )
