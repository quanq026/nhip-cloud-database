#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo 'Run as root on nhip-cp.' >&2; exit 1; fi
registry=10.44.1.10:5000
docker build --build-arg APP_VERSION=v1 -t "$registry/nhip-backend:v1-nodes" .
docker build --build-arg APP_VERSION=v2 -t "$registry/nhip-backend:v2-nodes" .
docker build -f Dockerfile.proxy -t "$registry/nhip-d1-gateway:v1" .
docker build -f Dockerfile.frontend -t "$registry/nhip-frontend:v1" .
for image in nhip-backend:v1-nodes nhip-backend:v2-nodes nhip-d1-gateway:v1 nhip-frontend:v1; do
  docker push "$registry/$image"
done
