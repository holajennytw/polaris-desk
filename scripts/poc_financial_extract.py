#!/usr/bin/env python3
"""PoC：財報 PDF → financial_metrics（圖檔頁偵測 + Gemini vision 抽數字）。

R4 的「照著改」起點，對應 docs/R4_ingestion_開工指南.md §10 軌 A。
**這是 PoC、不是正式 ingestion**：證明 per-page 分流可行 + 示範 vision 抽數字的輸出形狀。

設計（對齊 repo 慣例：smart + 確定性 fallback、無金鑰 token=0）：
- 逐頁偵測 text vs image（pdftotext 抽字數）。
- text 頁  → 抽文字 + 正規化中文字元間空格（軌 B / 文字財報表可再 regex）。
- image 頁 → pdftoppm 轉 PNG → Gemini vision 抽 JSON；**無 GEMINI_API_KEY → 確定性
  placeholder**（示範欄位形狀、不呼叫 API）。

依賴：poppler（pdfinfo/pdftotext/pdftoppm，本機已裝）；google-genai（選用，有金鑰才真呼叫）。

用法：
    python scripts/poc_financial_extract.py \\
        --pdf "/path/06_Financial_Report/2330_202503.pdf" --stock-id 2330 --period 2025Q1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

#: 一頁 pdftotext 抽到的非空白字數 < 此值 → 視為掃描圖檔頁（需 vision）。
TEXT_CHAR_THRESHOLD = 50

#: 損益表關鍵指標（vision prompt 與 placeholder 共用）。
KEY_METRICS = (
    "營業收入", "營業成本", "營業毛利", "營業利益",
    "稅前淨利", "本期淨利", "基本每股盈餘",
)

VISION_PROMPT = (
    "你是財報數字抽取器。這是一頁台股合併財務報表。"
    "抽出損益表的關鍵數字，只輸出 JSON 陣列，每筆物件為 "
    '{"metric": ..., "value": ..., "unit": ...}；'
    "metric 用中文（營業收入/營業成本/營業毛利/營業利益/稅前淨利/本期淨利/基本每股盈餘），"
    "value 為純數字（去除千分位逗號），unit 用「千元」或「元」或「%」。找不到的指標就不要輸出，不得臆造。"
)


def page_count(pdf: str) -> int:
    out = subprocess.run(
        ["pdfinfo", pdf], capture_output=True, text=True, check=False
    ).stdout
    m = re.search(r"Pages:\s*(\d+)", out)
    return int(m.group(1)) if m else 0


def page_text(pdf: str, page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-f", str(page), "-l", str(page), "-layout", pdf, "-"],
        capture_output=True, text=True, check=False,
    ).stdout


def normalize_cjk(text: str) -> str:
    """移除中文字元間空格：「營 業 收 入」→「營業收入」（文字頁解析前必做）。"""
    return re.sub(r"(?<=[一-鿿])\s+(?=[一-鿿])", "", text)


def detect_kind(pdf: str, page: int) -> str:
    """回 'text' 或 'image'：抽到的字數低於門檻 → 掃描圖檔頁。"""
    n = len("".join(page_text(pdf, page).split()))
    return "text" if n >= TEXT_CHAR_THRESHOLD else "image"


def render_page_png(pdf: str, page: int, out_dir: str, dpi: int = 150) -> str:
    prefix = str(Path(out_dir) / f"page_{page}")
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-png", "-r", str(dpi), pdf, prefix],
        check=True,
    )
    pngs = sorted(Path(out_dir).glob(f"page_{page}*.png"))
    return str(pngs[0]) if pngs else ""


def _parse_json_array(raw: str) -> list[dict]:
    """容錯解析 LLM 回傳的 JSON 陣列（可能包 ```json 圍欄）。"""
    text = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def extract_via_vision(png_path: str, *, api_key: str | None) -> list[dict]:
    """有金鑰 → Gemini vision 真抽；無金鑰 → 確定性 placeholder（token=0）。

    ⚠️ R4：vision 呼叫格式請對著當前 google-genai SDK 驗一次（image part 的構造）。
    """
    if not api_key:
        return [
            {"metric": m, "value": None, "unit": "千元",
             "_note": "PLACEHOLDER（無 GEMINI_API_KEY，未呼叫 API）"}
            for m in KEY_METRICS[:3]
        ]
    from google import genai  # 延遲 import（無金鑰路徑不需要）
    from google.genai import types

    client = genai.Client(api_key=api_key)
    image_part = types.Part.from_bytes(
        data=Path(png_path).read_bytes(), mime_type="image/png"
    )
    resp = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL_PRO", "gemini-3-pro-preview"),
        contents=[VISION_PROMPT, image_part],
    )
    return _parse_json_array(resp.text)


def _to_metric_row(stock_id: str, period: str, page: int, m: dict) -> dict:
    """對齊 docs §10 的 financial_metrics long-format schema。"""
    return {
        "stock_id": stock_id,
        "fiscal_period": period,
        "metric": m.get("metric"),
        "value": m.get("value"),
        "unit": m.get("unit"),
        "source_id": f"{stock_id}_{period}_fin_p{page}",  # grounding（FR-003）
        "published_at": None,  # R4：填季末日（Q1→{年}-03-31…）
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="財報 PoC：圖檔頁偵測 + vision 抽數字")
    ap.add_argument("--pdf", required=True, help="財報 PDF 路徑")
    ap.add_argument("--stock-id", required=True, help="股票代號，如 2330")
    ap.add_argument("--period", required=True, help="季別，如 2025Q1")
    ap.add_argument("--max-pages", type=int, default=12, help="只掃前 N 頁（財報表多在前段）")
    args = ap.parse_args(argv)

    if not Path(args.pdf).is_file():
        print(f"找不到檔案：{args.pdf}", file=sys.stderr)
        return 1

    api_key = os.environ.get("GEMINI_API_KEY") or None
    total = page_count(args.pdf)
    scan = min(total, args.max_pages)
    print(f"== 財報 PoC：{Path(args.pdf).name}（共 {total} 頁，掃前 {scan} 頁）==")
    print(f"   GEMINI_API_KEY: {'已設定 → 真 vision 抽取' if api_key else '未設定 → placeholder'}\n")

    rows: list[dict] = []
    for p in range(1, scan + 1):
        kind = detect_kind(args.pdf, p)
        if kind == "image":
            with tempfile.TemporaryDirectory() as td:
                png = render_page_png(args.pdf, p, td)
                metrics = extract_via_vision(png, api_key=api_key) if png else []
            rows.extend(_to_metric_row(args.stock_id, args.period, p, m) for m in metrics)
            print(f"  p{p}: 🖼️  image → vision（抽到 {len(metrics)} 筆）")
        else:
            print(f"  p{p}: 📝 text  → 文字解析（軌 B 附註切塊；文字財報表可 regex）")

    print("\n== financial_metrics rows（軌 A，long format）==")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"\n小結：{len(rows)} 筆 → 之後 load 進 polaris_core.financial_metrics；"
          "抽完務必 R6 抽查數字錯誤率 = 0。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
