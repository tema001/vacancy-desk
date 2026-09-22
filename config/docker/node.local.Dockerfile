FROM node:24-trixie-slim

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci \
 && sha256sum package.json package-lock.json | sha256sum | awk '{print $1}' > node_modules/.deps-hash

COPY config/docker/frontend-entrypoint.sh /usr/local/bin/frontend-entrypoint.sh
RUN chmod +x /usr/local/bin/frontend-entrypoint.sh

ENTRYPOINT ["frontend-entrypoint.sh"]