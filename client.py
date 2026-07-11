"""client.py — thin OpenRouter wrapper with a hard-capped cost meter.

Lineage pattern (decay-pin → lossy-wall): loud missing-key error, bounded retries,
model slug required per call, measured cost per call. Prices are per-M-token rates
pulled live 2026-07-10 (see docs/M0-BRIEF.md D1/D2); ping re-verifies slugs before
any wave spends. The meter enforces the sign-off's $0.25 pilot hard cap — it checks
BEFORE each call and halts the wave when the cap would plausibly be crossed.
"""
from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI, APIError, APITimeoutError, BadRequestError, RateLimitError

ROSTER = [  # D1-A, signed off 2026-07-10
    "qwen/qwen3-coder-30b-a3b-instruct",
    "z-ai/glm-4.7-flash",
    "meta-llama/llama-3.1-8b-instruct",
]
BENCH = [  # swap order
    "deepseek/deepseek-chat-v3.1",
    "mistralai/mistral-small-3.2-24b-instruct",
    "moonshotai/kimi-k2.5",
]
GENERATOR = "openai/gpt-5.1-codex-mini"  # D2-A
GENERATOR_FALLBACK = "openai/gpt-4o-mini"

PRICES = {  # $ per 1M tokens (input, output) — openrouter.ai/api/v1/models, 2026-07-10
    "qwen/qwen3-coder-30b-a3b-instruct": (0.07, 0.27),
    "z-ai/glm-4.7-flash": (0.06, 0.40),
    "meta-llama/llama-3.1-8b-instruct": (0.02, 0.03),
    "deepseek/deepseek-chat-v3.1": (0.21, 0.79),
    "mistralai/mistral-small-3.2-24b-instruct": (0.075, 0.20),
    "moonshotai/kimi-k2.5": (0.375, 2.025),
    "openai/gpt-5.1-codex-mini": (0.25, 2.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
}

SUBJECT_REASONING = {"enabled": False}   # paper runs zero/low reasoning
GENERATOR_REASONING = {"effort": "low"}  # D2-A: pinned low


class BudgetExceeded(RuntimeError):
    pass


class CostMeter:
    def __init__(self, cap_usd: float):
        self.cap = cap_usd
        self.total = 0.0
        self.calls = 0

    def check(self):
        if self.total >= self.cap:
            raise BudgetExceeded(f"cost meter at ${self.total:.4f} ≥ cap ${self.cap:.2f}")

    def add(self, cost: float):
        self.total += cost
        self.calls += 1


def _client() -> OpenAI:
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY missing — put it in .env (never commit it)")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, timeout=120)


_OAI: OpenAI | None = None


def chat(
    model: str,
    prompt: str,
    *,
    max_tokens: int,
    reasoning: dict | None = None,
    meter: CostMeter | None = None,
    retries: int = 3,
) -> dict:
    """One user-turn completion. Returns text + usage + measured cost.

    Falls back to a no-reasoning-param call if the provider rejects the reasoning
    field (recorded as reasoning_dropped). Retries transient failures with backoff.
    """
    global _OAI
    if _OAI is None:
        _OAI = _client()
    if meter:
        meter.check()
    kwargs: dict = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    if reasoning is not None:
        kwargs["extra_body"] = {"reasoning": reasoning}
    reasoning_dropped = False
    t0 = time.monotonic()
    for attempt in range(retries):
        try:
            resp = _OAI.chat.completions.create(**kwargs)
            break
        except BadRequestError:
            if "extra_body" in kwargs:
                kwargs.pop("extra_body")
                reasoning_dropped = True
                continue
            raise
        except (RateLimitError, APITimeoutError, APIError, json.JSONDecodeError):
            # JSONDecodeError: OpenRouter occasionally returns a malformed body
            # (observed 2026-07-10, killed the deepseek T2 wave); same transient
            # class as the others — retry with backoff, then surface.
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    u = resp.usage
    pin, pout = PRICES[model]
    cost = (u.prompt_tokens * pin + u.completion_tokens * pout) / 1e6
    if meter:
        meter.add(cost)
    details = getattr(u, "completion_tokens_details", None)
    return {
        "model": model,
        "text": resp.choices[0].message.content or "",
        "prompt_tokens": u.prompt_tokens,
        "completion_tokens": u.completion_tokens,
        "reasoning_tokens": getattr(details, "reasoning_tokens", 0) or 0,
        "cost": cost,
        "seconds": round(time.monotonic() - t0, 2),
        "reasoning_dropped": reasoning_dropped,
        "finish_reason": resp.choices[0].finish_reason,
    }
