# API image: the Hono server (dist/serve.mjs) and the migrator (dist/migrate.mjs).
# Development does not use this; see `pnpm api:dev`. Build: `pnpm api:up` or
#   docker build -t pgtm-api .

FROM node:24-alpine AS build
# pnpm pinned to the repo's packageManager. Installed with npm here, outside the project
# (devEngines blocks npm only inside it).
RUN npm install --global pnpm@12.10.1
WORKDIR /repo

# Manifests first, so dependency layers are cached until they change.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/model/package.json packages/model/
COPY packages/backend/package.json packages/backend/
COPY packages/fetcher/package.json packages/fetcher/
RUN pnpm install --frozen-lockfile --filter @pgtm/backend...

COPY tsconfig.base.json ./
COPY packages/model packages/model
COPY packages/backend packages/backend
RUN pnpm --filter @pgtm/backend build \
 && pnpm --filter @pgtm/backend deploy --prod --legacy /out \
 && cp -r packages/backend/dist /out/dist

FROM node:24-alpine AS runtime
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /out/package.json ./
COPY --from=build --chown=node:node /out/node_modules ./node_modules
COPY --from=build --chown=node:node /out/dist ./dist
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/v1/health').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]
CMD ["node", "dist/serve.mjs"]
