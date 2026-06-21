# Werewolf game server (Go) image / 人狼ゲームサーバ (Go) イメージ
# Build context = repo root (discussion-bench/). Mirrors aiwolf-nlp-demo's game-server build.
FROM golang:1.24 AS build
WORKDIR /src
COPY server/aiwolf/ ./
RUN CGO_ENABLED=0 go build -o /out/server .

FROM alpine:3.20
WORKDIR /app
RUN mkdir -p config log cache && touch config/.env
COPY --from=build /out/server /app/server
EXPOSE 8080
ENTRYPOINT ["/app/server"]
# Config is mounted at /app/config by compose; default to the 5-player werewolf config.
CMD ["-c", "/app/config/default_5.yml"]
