# Website image: Astro's standalone Node server (dist/server/entry.mjs) with its client assets.
# Build from the repo root: `docker compose --profile app build web`.

FROM node:26-alpine AS build
# pnpm pinned to the repo's packageManager; installed with npm outside the project.
RUN npm install --global pnpm@12.10.1
WORKDIR /repo

# Manifests first, so dependency layers are cached until they change.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/model/package.json packages/model/
COPY packages/backend/package.json packages/backend/
COPY packages/fetcher/package.json packages/fetcher/
COPY apps/web-front/package.json apps/web-front/
RUN pnpm install --frozen-lockfile --filter @pgtm/web-front...

COPY tsconfig.base.json ./
COPY packages/model packages/model
COPY packages/backend packages/backend
COPY apps/web-front apps/web-front
RUN pnpm --filter @pgtm/web-front build \
 && pnpm --filter @pgtm/web-front deploy --prod --legacy /out \
 && cp -r apps/web-front/dist /out/dist

FROM node:26-alpine AS runtime
ENV NODE_ENV=production HOST=0.0.0.0 PORT=4321
WORKDIR /app
COPY --from=build --chown=node:node /out/package.json ./
COPY --from=build --chown=node:node /out/node_modules ./node_modules
COPY --from=build --chown=node:node /out/dist ./dist
USER node
EXPOSE 4321
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:4321/fi/').then(r => process.exit(r.status < 500 ? 0 : 1), () => process.exit(1))"]
CMD ["node", "dist/server/entry.mjs"]
