FROM node:22-alpine AS base

FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci
# lightningcss (Tailwind v4) ships its native binary as a platform-specific
# optional dependency. When the lockfile was generated on Windows/macOS,
# npm ci may skip the linux-musl variant and break `next build` on alpine.
# Install the matching binary explicitly (alpine is always musl).
RUN npm install --no-save "lightningcss-linux-$(node -p 'process.arch')-musl"

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
RUN mkdir .next && chown -R nextjs:nodejs .next public

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

COPY infra/env.sh /app/env.sh
RUN chmod +x /app/env.sh

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME=0.0.0.0

ENTRYPOINT ["/app/env.sh"]
CMD ["node", "server.js"]
