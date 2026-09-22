#!/bin/sh
set -eu

current=$(sha256sum package.json package-lock.json | sha256sum | awk '{print $1}')
saved=$(cat node_modules/.deps-hash 2>/dev/null || true)

if [ "$current" != "$saved" ]; then
  npm ci
  echo "$current" > node_modules/.deps-hash
fi

exec "$@"