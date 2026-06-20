"""Gemini 用戶端薄封裝（@R2 / @R3）。

使用新版 **google-genai** SDK（`pip install google-genai`），
取代已淘汰的舊 `google-generativeai`。API 形態：
    from google import genai
    client = genai.Client(api_key=...)
    client.models.generate_content(model=..., contents=...)

LLM 本就走雲端 API，本地 / 雲端共用此封裝。金鑰從 settings（.env）讀。
重相依採延遲 import，未安裝 SDK 時 `import polaris` 仍正常。
"""
from __future__ import annotations

from ..config import settings


def is_real_key(key: str | None) -> bool:
    """金鑰是否「真的設定了」。

    `.env` 佔位字串是 ``'# 必填…'``——truthy 但無效。空字串 / 純空白 /
    `#` 開頭（註解佔位）一律視為未設定，避免下游以為有金鑰、卻在呼叫時才爆。
    """
    if not key:
        return False
    stripped = key.strip()
    return bool(stripped) and not stripped.startswith("#")


def available() -> bool:
    """目前 settings 內是否有可用的 Gemini 金鑰（含逗號分隔多把）。"""
    return len(settings.gemini_api_keys) > 0


def active_llm() -> "GeminiClient | None":
    """有真金鑰 → 回 GeminiClient；否則回 None（呼叫端走確定性 fallback）。

    無金鑰時**不**建立 client、不觸發 google-genai import，CI / 無金鑰開發
    皆可正常跑（憲法成本紀律）。
    """
    return GeminiClient() if available() else None


class GeminiClient:
    """Gemini 封裝。生成可走 Vertex（GCP 專案配額 / trial credit），嵌入恆走 api_key。

    - ``GEMINI_USE_VERTEX=1``：``generate`` 走 Vertex AI（ADC / runtime SA 認證，
      用專案配額繞過 AI Studio 免費日配額）；``embed`` 仍走 api_key 同一模型，
      保住 ``polaris_core`` 既有 768 向量空間（換 embedding 後端會讓檢索失準）。
    - 預設（未設）：生成與嵌入都走 api_key，與既有行為完全一致。
    - 任一模式都需要有效 ``GEMINI_API_KEY``（嵌入用）。
    """

    def __init__(self) -> None:
        keys = settings.gemini_api_keys
        if not keys:
            raise RuntimeError("缺少有效 GEMINI_API_KEY，請在 .env 填入真實金鑰")
        from google import genai  # 延遲 import

        # 嵌入恆走 api_key（向量空間與 polaris_core 一致）；逗號分隔多把 → 一把一個
        # client，429 配額耗盡時 generate/embed 自動輪到下一把。
        self._embed_clients = [genai.Client(api_key=k) for k in keys]
        # 生成：Vertex（專案配額，ADC 認證、無 api_key 可輪）或 api_key（同嵌入，可輪）。
        if settings.gemini_use_vertex:
            self._gen_clients = [
                genai.Client(
                    vertexai=True,
                    project=settings.gcp_project,
                    location=settings.vertex_location,
                )
            ]
        else:
            self._gen_clients = self._embed_clients

    @staticmethod
    def _call_rotating(clients: list, fn):
        """對每個 client 依序試 ``fn(client)``；遇 429 配額耗盡輪到下一把，
        全數耗盡則拋出最後一個 429（交給外層 ``call_with_retry`` 退避重試）。
        非配額錯誤（400 / 連線等）不輪 key，立刻拋出。"""
        from polaris.retry import is_quota_error

        last_exc: BaseException | None = None
        for client in clients:
            try:
                return fn(client)
            except Exception as exc:  # noqa: BLE001 — 僅 429 吞下輪 key，其餘照拋
                if not is_quota_error(exc):
                    raise
                last_exc = exc
        assert last_exc is not None  # clients 非空 → 走到這裡必有 429
        raise last_exc

    def generate(
        self,
        prompt: str,
        *,
        flash: bool = False,
        system_instruction: str | None = None,
    ) -> str:
        """單輪文字生成。flash=True 用便宜快速的 Flash 模型。"""
        from google.genai import types  # 延遲 import

        from polaris.compression.tokens import count_tokens
        from polaris.llm.budget import default_budget

        model = settings.gemini_model_flash if flash else settings.gemini_model_pro
        # LLM10：永遠帶 max_output_tokens 上限，擋失控長輸出。
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=settings.llm_max_output_tokens,
            temperature=0.0,
        )
        resp = self._call_rotating(
            self._gen_clients,
            lambda client: client.models.generate_content(
                model=model, contents=prompt, config=config
            ),
        )
        # LLM10：把本次估算用量記入 process 預算（超限會 raise，擋住後續呼叫）。
        default_budget.charge(count_tokens(prompt) + count_tokens(resp.text or ""))
        return resp.text

    def embed(self, text: str) -> list[float]:
        """產生 embedding（入庫與查詢都用）；維度由 .env EMBEDDING_DIM 控制。

        TODO(@R4)：W1 接 DB 後，確認回傳形狀與 batch 寫法（可一次 contents=[...] 多筆）。
        """
        from google.genai import types  # 延遲 import

        resp = self._call_rotating(
            self._embed_clients,
            lambda client: client.models.embed_content(
                model=settings.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.embedding_dim
                ),
            ),
        )
        return list(resp.embeddings[0].values)
