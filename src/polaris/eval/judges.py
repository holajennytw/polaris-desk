"""G2/G3/G4 才啟用的 Claude + GPT + Gemini 三方 Judge。

三個 provider 共用同一 JSON 契約。任何缺 key、無法解析或 API 失敗都採
fail-closed，並在 vote 中保留原因，避免錯誤被誤當成品質通過。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from polaris.eval.errors import EvalConfigurationError
from polaris.eval.runner import EvalRecord


@dataclass(frozen=True)
class JudgeVote:
    provider: str
    model: str
    passed: bool
    reason: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "passed": self.passed,
            "reason": self.reason,
            "error": self.error,
        }


def judge_records(
    records: list[EvalRecord],
    *,
    clients: dict[str, tuple[str, Callable[[str, str], str]]] | None = None,
) -> dict[str, list[JudgeVote]]:
    """逐題執行三方 Judge；測試可注入 provider callable。"""

    clients = clients or _build_clients()
    votes_by_item: dict[str, list[JudgeVote]] = {}
    for record in records:
        prompt = _judge_prompt(record)
        votes_by_item[record.item.item_id] = [
            _invoke_judge(provider, model, caller, prompt)
            for provider, (model, caller) in clients.items()
        ]
    return votes_by_item


def majority_passed(votes: list[JudgeVote]) -> bool:
    return sum(1 for vote in votes if vote.passed) >= 2


def parse_verdict(provider: str, model: str, raw: str) -> JudgeVote:
    """解析 ``{"verdict":"PASS|FAIL","reason":"..."}``，格式錯誤即 FAIL。"""

    try:
        payload = json.loads(raw)
        verdict = str(payload["verdict"]).strip().upper()
        reason = str(payload["reason"]).strip()
        if verdict not in {"PASS", "FAIL"} or not reason:
            raise ValueError("verdict/reason 值無效")
        return JudgeVote(provider, model, verdict == "PASS", reason)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return JudgeVote(
            provider,
            model,
            False,
            "Judge 回傳格式無效",
            error=str(exc),
        )


def _invoke_judge(
    provider: str,
    model: str,
    caller: Callable[[str, str], str],
    prompt: str,
) -> JudgeVote:
    try:
        return parse_verdict(provider, model, caller(model, prompt))
    except Exception as exc:  # noqa: BLE001 - provider failure must become a recorded FAIL
        error = f"{type(exc).__name__}: {exc}".rstrip()
        return JudgeVote(provider, model, False, "Judge 呼叫失敗", error=error)


def _build_clients() -> dict[str, tuple[str, Callable[[str, str], str]]]:
    required = {
        "gemini": ("GEMINI_API_KEY", "JUDGE_GEMINI_MODEL"),
        "openai": ("OPENAI_API_KEY", "JUDGE_OPENAI_MODEL"),
        "anthropic": ("ANTHROPIC_API_KEY", "JUDGE_ANTHROPIC_MODEL"),
    }
    missing = [
        variable
        for key_var, model_var in required.values()
        for variable in (key_var, model_var)
        if not os.getenv(variable)
    ]
    if missing:
        raise EvalConfigurationError(
            "三方 Judge 設定不完整，缺少：" + ", ".join(sorted(missing))
        )
    return {
        "gemini": (os.environ["JUDGE_GEMINI_MODEL"], _call_gemini),
        "openai": (os.environ["JUDGE_OPENAI_MODEL"], _call_openai),
        "anthropic": (os.environ["JUDGE_ANTHROPIC_MODEL"], _call_anthropic),
    }


def _call_gemini(model: str, prompt: str) -> str:
    from google import genai

    response = genai.Client(api_key=os.environ["GEMINI_API_KEY"]).models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text or ""


def _call_openai(model: str, prompt: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise EvalConfigurationError("請安裝 `.[eval-gate]` 以使用 GPT Judge") from exc
    response = OpenAI(api_key=os.environ["OPENAI_API_KEY"]).responses.create(
        model=model,
        input=prompt,
    )
    return response.output_text


def _call_anthropic(model: str, prompt: str) -> str:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise EvalConfigurationError("請安裝 `.[eval-gate]` 以使用 Claude Judge") from exc
    response = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]).messages.create(
        model=model,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text"))


def _judge_prompt(record: EvalRecord) -> str:
    return (
        "你是金融研究品質評審。依據問題、參考答案、檢索語料與系統回答，"
        "判斷回答是否正確、接地、切題且沒有買賣建議。"
        '只輸出 JSON：{"verdict":"PASS 或 FAIL","reason":"簡短理由"}。\n\n'
        f"問題：{record.item.question}\n"
        f"參考答案：{record.ground_truth}\n"
        f"檢索語料：{json.dumps(record.contexts, ensure_ascii=False)}\n"
        f"系統回答：{record.answer}"
    )


__all__ = ["JudgeVote", "judge_records", "majority_passed", "parse_verdict"]
