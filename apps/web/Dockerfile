# syntax=docker/dockerfile:1.7
FROM --platform=linux/amd64 docker.io/library/node:24-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d AS dependencies
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

FROM --platform=linux/amd64 docker.io/library/node:24-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d AS builder
ENV NEXT_TELEMETRY_DISABLED=1 \
    SOURCE_DATE_EPOCH=1787486400
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY apps/web/ ./
RUN npm run build \
    && test -s /app/.next/standalone/server.js \
    && test -d /app/.next/server/app/api/health/live \
    && test -d /app/.next/server/app/api/health/ready

FROM --platform=linux/amd64 docker.io/library/node:24-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d AS runtime
ARG VCS_REF=uncommitted
LABEL org.opencontainers.image.title="SOAIACORE Web" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.source="https://github.com/SOAIACORE-Corporation/Salvadorosorio-png-soai-policy"
ENV HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
RUN apt-get update \
    && apt-get install --only-upgrade -y --no-install-recommends \
      bsdutils libblkid1 liblastlog2-2 libmount1 libsmartcols1 libuuid1 \
      login mount util-linux libssl3t64 openssl-provider-legacy \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack
COPY --from=builder --chown=65532:65532 /app/.next/standalone ./
COPY --from=builder --chown=65532:65532 /app/.next/static ./.next/static
USER 65532:65532
EXPOSE 3000
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=12 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/api/health/live').then((response) => { if (!response.ok) process.exit(1) }).catch(() => process.exit(1))"]
CMD ["node", "server.js"]
