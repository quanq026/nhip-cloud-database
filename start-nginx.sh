#!/usr/bin/env bash
set -euo pipefail
cd /opt/cloud-midterm-d1
docker run -d --name cdb-nginx --network cdb-net --restart unless-stopped \
  -p 80:80 -p 443:443 \
  -v "$PWD/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/static:/usr/share/nginx/html/static:ro" \
  -v "$PWD/certificates:/etc/letsencrypt:ro" \
  -v "$PWD/acme-webroot:/var/www/certbot:ro" nginx:1.28-alpine
