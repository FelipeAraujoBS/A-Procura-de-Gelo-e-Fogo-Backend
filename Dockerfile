# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src

RUN npm run build

# Production stage
FROM node:22-alpine AS runner

WORKDIR /app

RUN apk add --no-cache dumb-init sqlite

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist
COPY entrypoint.sh ./entrypoint.sh
COPY scripts/create_test_db.py ./scripts/create_test_db.py
RUN chmod +x ./entrypoint.sh

ENV NODE_ENV=production
ENV PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:5000/health || exit 1

ENTRYPOINT ["dumb-init", "./entrypoint.sh"]
CMD ["node", "dist/server.js"]
