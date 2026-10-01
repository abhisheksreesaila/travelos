# GitAway on Railway (docs/setup.md "Deploy to Railway"). Railway builds this file automatically.
FROM ghcr.io/prefix-dev/pixi:0.80.0 AS build
WORKDIR /app
# Dependencies first, so a code-only change reuses this layer. The "prod" environment leaves out pytest and playwright.
COPY pixi.toml pixi.lock ./
RUN pixi install --locked -e prod
RUN pixi shell-hook -e prod --manifest-path pixi.toml > /shell-hook.sh

FROM ubuntu:24.04
COPY --from=build /app/.pixi/envs/prod /app/.pixi/envs/prod
COPY --from=build /shell-hook.sh /shell-hook.sh
WORKDIR /app
COPY main.py ./
COPY gitaway ./gitaway
COPY assets ./assets
COPY migrations ./migrations
COPY docs/trip-template.md ./docs/trip-template.md
RUN printf '#!/bin/bash\nset -e\n. /shell-hook.sh\nmkdir -p "$GITAWAY_DATA_DIR"\ncd "$GITAWAY_DATA_DIR"\nexec python /app/main.py\n' > /entrypoint.sh && chmod +x /entrypoint.sh
# Production defaults; Railway's variables override them. The volume is mounted at /data (all databases live there).
ENV GITAWAY_ENV=production GITAWAY_DATA_DIR=/data
EXPOSE 8080
CMD ["/entrypoint.sh"]
