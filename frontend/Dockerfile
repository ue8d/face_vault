# Next.js standalone ビルド
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:20-slim AS builder
WORKDIR /app
# クライアントバンドルに焼き込むAPIベース（ブラウザから見たbackend）
ARG NEXT_PUBLIC_API_BASE=http://localhost:8017
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3017
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3017
CMD ["node", "server.js"]
