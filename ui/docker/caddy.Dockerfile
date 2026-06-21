# Caddy: TLS + static viewer + WS/api reverse proxy / TLS終端＋静的ビューア配信＋リバプロ
# Build context = repo root (inlg/). Builds THIS repo's viewer (ui/viewer).
FROM node:22-slim AS build
RUN corepack enable
WORKDIR /viewer
COPY ui/viewer/ ./
RUN pnpm install --no-frozen-lockfile
# Root-level distribution (/demo etc.), so base path is empty.
ENV BASE_PATH=""
RUN pnpm run build

FROM caddy:2
COPY --from=build /viewer/build /srv
COPY ui/Caddyfile /etc/caddy/Caddyfile
# Language WS routes (optional). Placeholder unless scripts/gen_i18n.py regenerates it.
COPY ui/caddy/langs.caddy /etc/caddy/langs.caddy
