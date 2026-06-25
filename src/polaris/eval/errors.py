"""Eval pipeline 對外錯誤型別。

CLI 用這兩種錯誤區分「設定未完成」與「外部服務執行失敗」，讓使用者看到
短而可行動的訊息，而不是第三方 SDK 的完整 stack trace。
"""


class EvalConfigurationError(RuntimeError):
    """缺少 optional dependency、API key、模型名稱或資料契約不符。"""


class EvalExecutionError(RuntimeError):
    """RAGAS 或 Judge 已設定，但實際呼叫失敗。"""


__all__ = ["EvalConfigurationError", "EvalExecutionError"]
