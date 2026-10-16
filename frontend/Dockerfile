FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Run as the image's unprivileged node user, UID 1000 (#033). The app files stay owned by root,
# so the server cannot change its own code. Next.js writes only its cache, which the cluster
# mounts as an emptyDir.
RUN mkdir -p .next/cache && chown 1000:1000 .next/cache
USER 1000:1000

EXPOSE 3000

CMD ["node", "--max-http-header-size=65536", "server.js"]
