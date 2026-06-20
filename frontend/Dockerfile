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
# 建置時注入非機密 env（機密由 Cloud Run --set-secrets 在 runtime 注入）
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
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
