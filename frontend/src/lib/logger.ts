// 統一錯誤記錄。目前輸出到 console；未來替換成 Sentry 只需改這一處。
export function logError(context: string, error: unknown): void {
  const msg = error instanceof Error ? error.message : String(error);
  console.error(`[${context}] ${msg}`, error);
  // TODO: Sentry.captureException(error, { tags: { context } });
}

export function logWarn(context: string, message: string): void {
  console.warn(`[${context}] ${message}`);
}
