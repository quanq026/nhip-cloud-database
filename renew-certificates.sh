#!/usr/bin/env bash
set -euo pipefail
cd /opt/cloud-midterm-d1
docker run --rm \
  -v "$PWD/certificates:/etc/letsencrypt" \
  -v "$PWD/acme-webroot:/var/www/certbot" \
  -v "$PWD/secrets/certbot.ini:/run/secrets/certbot.ini:ro" \
  certbot/dns-cloudflare:latest renew --non-interactive
docker kill --signal HUP cdb-nginx >/dev/null
