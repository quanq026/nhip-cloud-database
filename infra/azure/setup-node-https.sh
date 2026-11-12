#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo 'Run as root.' >&2; exit 1; fi
node_host=${1:?expected node hostname}
case "$node_host" in
  cp.akaine.io.vn|worker1.akaine.io.vn|worker2.akaine.io.vn) ;;
  *) echo 'Unexpected node hostname.' >&2; exit 1 ;;
esac
site=/etc/nginx/sites-available/nhip-node
if [ -e "$site" ] || [ -e /etc/nginx/sites-enabled/nhip-node ]; then
  echo 'Node site already exists; inspect before retrying.' >&2
  exit 1
fi
install -d -m 755 /var/www/nhip-acme
cat > "$site" <<EOF
server {
    listen 80;
    server_name $node_host;
    location ^~ /.well-known/acme-challenge/ { root /var/www/nhip-acme; }
    location / { return 308 https://$node_host\$request_uri; }
}
EOF
ln -s "$site" /etc/nginx/sites-enabled/nhip-node
nginx -t
systemctl reload nginx
certbot certonly --webroot --webroot-path /var/www/nhip-acme \
  -d "$node_host" --non-interactive --agree-tos --register-unsafely-without-email
cat >> "$site" <<EOF
server {
    listen 443 ssl;
    server_name $node_host;
    ssl_certificate /etc/letsencrypt/live/$node_host/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$node_host/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    server_tokens off;
    client_max_body_size 8k;
    add_header Strict-Transport-Security "max-age=2592000" always;
    location ^~ /.well-known/acme-challenge/ { root /var/www/nhip-acme; }
    location / {
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_pass http://127.0.0.1:30080;
    }
}
EOF
nginx -t
systemctl reload nginx
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/nhip-nginx-reload.sh <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/nhip-nginx-reload.sh
systemctl enable --now certbot.timer
echo "HTTPS configured for $node_host."
