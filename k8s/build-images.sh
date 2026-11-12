#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo 'Run as root on nhip-cp.' >&2; exit 1; fi
export DOCKER_CONFIG="${DOCKER_CONFIG:-/opt/nhip-dockerhub}"
docker build --build-arg APP_VERSION=v1 -t quanq026/nhip-k8s-backend:v1 .
docker build --build-arg APP_VERSION=v2 -t quanq026/nhip-k8s-backend:v2 .
docker build -f Dockerfile.proxy -t quanq026/nhip-k8s-d1-gateway:v1 .
docker build -f Dockerfile.frontend -t quanq026/nhip-k8s-frontend:v1 .
for image in quanq026/nhip-k8s-backend:v1 quanq026/nhip-k8s-backend:v2 quanq026/nhip-k8s-d1-gateway:v1 quanq026/nhip-k8s-frontend:v1; do
  docker push "$image"
done
