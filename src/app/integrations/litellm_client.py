from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import litellm
from app.config import AppConfig
from app.utils.logging import get_logger, log_llm_call

logger = get_logger(__name__)

litellm.drop_params = True

_MAX_RETRIES = 3
_BASE_DELAY = 5


class LiteLLMClient:
    def __init__(self, config: AppConfig | None = None, task_key: str = "", phase: str = "") -> None:
        self.config = config or AppConfig()
        self.task_key = task_key
        self.phase = phase

    async def complete(self, model_alias: str, messages: list[dict], temperature: float = 0.3, max_tokens: int = 4096) -> str:
        prompt_text = str(messages[-1].get("content", "")) if messages else ""
        prompt_len = len(prompt_text)
        start = time.time()

        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await litellm.acompletion(
                    model=model_alias,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=300,
                    api_base=os.environ.get("OPENAI_BASE_URL", ""),
                )
                result = response.choices[0].message.content
                duration_ms = int((time.time() - start) * 1000)

                usage = response.usage
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                total_tokens = prompt_tokens + completion_tokens

                _track_tokens(self.task_key, self.phase or "unknown", model_alias, prompt_tokens, completion_tokens, total_tokens, self.config.outputs_path / self.task_key if self.task_key else None)

                if self.task_key:
                    log_llm_call(
                        self.task_key, self.phase or "unknown",
                        model_alias, prompt_len, len(result or ""), duration_ms,
                        self.config.outputs_path / self.task_key,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                    )
                logger.info("llm_complete", model=model_alias, prompt=prompt_len, response=len(result or ""), ms=duration_ms, tokens=total_tokens)
                return result
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                is_rate_limit = "rate" in err_str or "429" in err_str or "throttl" in err_str
                if is_rate_limit and attempt < _MAX_RETRIES - 1:
                    delay = _BASE_DELAY * (attempt + 1)
                    logger.warning("llm_rate_limit_retry", attempt=attempt + 1, delay=delay, error=str(e)[:200])
                    await asyncio.sleep(delay)
                else:
                    duration_ms = int((time.time() - start) * 1000)
                    if self.task_key:
                        log_llm_call(
                            self.task_key, self.phase or "unknown",
                            model_alias, prompt_len, 0, duration_ms,
                            self.config.outputs_path / self.task_key,
                            error=str(e)[:200],
                        )
                    raise
        raise last_error

    async def health(self) -> bool:
        try:
            response = await litellm.acompletion(
                model="openai/glm-5",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                timeout=15,
                api_base=os.environ.get("OPENAI_BASE_URL", ""),
            )
            return bool(response.choices)
        except Exception as e:
            logger.warning("llm_health_failed", error=str(e)[:200])
            return False


_token_cache: dict[str, list[dict]] = {}


def _track_tokens(task_key: str, phase: str, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, output_dir: Path | None) -> None:
    if not task_key:
        return
    if task_key not in _token_cache:
        _token_cache[task_key] = []
    entry = {
        "phase": phase,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    _token_cache[task_key].append(entry)

    if output_dir:
        usage_path = output_dir / "token-usage.json"
        output_dir.mkdir(parents=True, exist_ok=True)
        usage_path.write_text(json.dumps({
            "task_key": task_key,
            "calls": _token_cache[task_key],
            "totals": _summarize_tokens(_token_cache[task_key]),
        }, indent=2, ensure_ascii=False), encoding="utf-8")


def _summarize_tokens(calls: list[dict]) -> dict:
    total_prompt = sum(c.get("prompt_tokens", 0) for c in calls)
    total_completion = sum(c.get("completion_tokens", 0) for c in calls)
    total = total_prompt + total_completion
    return {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total,
        "total_calls": len(calls),
        "estimated_cost_usd": round(total * 0.000001, 4),
    }


def get_token_summary(task_key: str) -> dict:
    calls = _token_cache.get(task_key, [])
    if not calls:
        return {"total_tokens": 0, "total_calls": 0}
    return _summarize_tokens(calls)
