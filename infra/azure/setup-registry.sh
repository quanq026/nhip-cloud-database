#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo 'Run as root.' >&2; exit 1; fi
if docker container inspect nhip-registry >/dev/null 2>&1; then
  echo 'Registry already exists; inspect it before retrying.' >&2
  exit 1
fi
umask 077
install -d -m 700 /opt/nhip-registry /opt/nhip-registry/certs /opt/nhip-registry/data
openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 365 \
  -keyout /opt/nhip-registry/certs/registry.key \
  -out /opt/nhip-registry/certs/registry.crt \
  -subj '/CN=nhip-registry' \
  -addext 'subjectAltName=IP:10.44.1.10' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,keyCertSign,digitalSignature,keyEncipherment' 2>/dev/null
chmod 600 /opt/nhip-registry/certs/registry.key
chmod 644 /opt/nhip-registry/certs/registry.crt
install -D -m 644 /opt/nhip-registry/certs/registry.crt /etc/docker/certs.d/10.44.1.10:5000/ca.crt
docker run -d --name nhip-registry --restart unless-stopped \
  -p 10.44.1.10:5000:5000 \
  -v /opt/nhip-registry/data:/var/lib/registry \
  -v /opt/nhip-registry/certs:/certs:ro \
  -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/registry.crt \
  -e REGISTRY_HTTP_TLS_KEY=/certs/registry.key registry:2.8.3
install -m 644 /opt/nhip-registry/certs/registry.crt /tmp/nhip-registry-ca.crt
