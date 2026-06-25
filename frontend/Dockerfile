# ============================================================
# polaris-web — Next.js frontend for Cloud Run
# 服務名：polaris-web  region：asia-east1
# URL：https://polaris-web-14326813937.asia-east1.run.app
# ============================================================
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# 後端位址不在 build-time 注入：前端走同 origin 的 /api，由 next.config.ts 的
# rewrites() 在 runtime 依 BACKEND_API_URL proxy 到 polaris-api。
# 刻意不設 `ENV NEXT_PUBLIC_API_BASE=$ARG`——沒帶 build-arg 時它會是空字串 ""，
# 讓 config.ts 的 /api 預設失效（API_BASE=""），正是 2026-06-25 prod outage 成因。
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# next build --output standalone 產生自含的 server.js
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Cloud Run 以 $PORT 注入監聽埠
ENV PORT=3000
EXPOSE 3000
CMD ["node", "server.js"]
