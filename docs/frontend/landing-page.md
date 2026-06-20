# Landing Page — 首頁資料來源說明

> 更新日期：2026-06-20｜維護：R7
> 檔案：`frontend/src/app/page.tsx`

---

## Hero Stats 區塊

首頁中段三個 `NumberTicker` 數字卡：

| 數字 | 來源 | 備注 |
|------|------|------|
| `100%` 引用可溯源率 | 靜態常數 | 架構保證，非動態 |
| `1.07s` 平均回應時間 | 靜態常數 | 待後端 `/metrics` 端點實作後替換 |
| `索引文件 chunks` | **動態**：`api.library()` stats | 詳見下節 |

---

## 索引文件 Chunks — 動態數字（2026-06-20）

### 行為

```tsx
const { data: libData } = useSWR("library", api.library, {
  revalidateOnFocus: false,
  dedupingInterval: 300_000,   // 5 分鐘內不重複請求
});
const chunkCount = (() => {
  const raw = libData?.stats?.find(s => s.label === "Chunks")?.value;
  if (!raw) return 3481;                                // fallback
  const n = parseInt(raw.replace(/[,，,\s]/g, ""), 10);
  return isNaN(n) ? 3481 : n;
})();
```

- SWR key `"library"` 與 `/library` 頁共用，使用者若已造訪資料庫頁，首頁不重複請求
- `stats` 格式：`{ label: string, value: string }[]`，比對 `label === "Chunks"`
- value 為後端回傳的格式化字串（如 `"82,341"`），去除千位符號後 `parseInt`
- **Fallback `3481`**：後端未部署 / USE_MOCK / 解析失敗時使用

### 後端契約

`GET /library` → `stats[].{ label: "Chunks", value: "<formatted number>" }`

後端實作後，此數字自動反映 BigQuery `polaris_core` 的實際 chunk 總數。
後端尚未實作時，使用 `public/mocks/library.json` mock 值（`"82,341"`）。

---

## 其他靜態內容

首頁其餘區塊（lp-feat 功能卡、lp-card 模擬視窗、LP footer）均為靜態 JSX，不依賴 API。
