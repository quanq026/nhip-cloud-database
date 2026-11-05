#!/usr/bin/env bash
set -euo pipefail
cd /opt/cloud-midterm-d1
test -s secrets/cf-api-token
test -s /opt/cloud-midterm/secrets/session_key
docker network inspect cdb-net >/dev/null
for name in cdb-d1-proxy cdb-app-d1; do
  if docker container inspect "$name" >/dev/null 2>&1; then
    echo "Container $name already exists; inspect it before retrying." >&2
    exit 1
  fi
done
chown root:10001 run
chmod 750 run
docker build -t cloud-midterm-d1-app:1 .
docker build -t cloud-midterm-d1-proxy:1 -f Dockerfile.proxy .
docker run -d --name cdb-d1-proxy --network cdb-net --restart unless-stopped \
  --user 0:10001 --cap-drop ALL --security-opt no-new-privileges --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  -e D1_ACCOUNT_ID=c6ababb4c45c2abec4bf14b84340a2d4 \
  -e D1_DATABASE_ID=eb4b1d10-e6c2-4b83-a861-0fb04bb1747d \
  -v "$PWD/secrets/cf-api-token:/run/secrets/d1_token:ro" \
  -v "$PWD/run:/run/d1" cloud-midterm-d1-proxy:1
docker run -d --name cdb-app-d1 --network cdb-net --network-alias app-d1 --restart unless-stopped \
  --cap-drop ALL --security-opt no-new-privileges --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  -e SECRET_KEY_FILE=/run/secrets/session_key -e PUBLIC_ORIGIN=https://akaine.io.vn \
  -v /opt/cloud-midterm/secrets/session_key:/run/secrets/session_key:ro \
  -v "$PWD/run:/run/d1:ro" cloud-midterm-d1-app:1
echo 'D1 application and local gateway started without publishing ports.'
