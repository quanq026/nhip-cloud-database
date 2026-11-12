#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo 'Run as root.' >&2; exit 1; fi
ca=/tmp/nhip-registry-ca.crt
test -s "$ca"
directory=/etc/containerd/certs.d/10.44.1.10:5000
install -d -m 755 "$directory"
install -m 644 "$ca" "$directory/ca.crt"
cat > "$directory/hosts.toml" <<'EOF'
server = "https://10.44.1.10:5000"
[host."https://10.44.1.10:5000"]
  capabilities = ["pull", "resolve"]
  ca = "/etc/containerd/certs.d/10.44.1.10:5000/ca.crt"
EOF
python3 - <<'PY'
from pathlib import Path
p = Path('/etc/containerd/config.toml')
old = p.read_text()
source = "config_path = '/etc/containerd/certs.d:/etc/docker/certs.d'"
target = "config_path = '/etc/containerd/certs.d'"
if old.count(source) != 1:
    raise SystemExit('Unexpected containerd registry configuration; no change made.')
backup = p.with_name('config.toml.before-nhip-registry')
if backup.exists():
    raise SystemExit('Containerd backup exists; inspect before retrying.')
backup.write_text(old)
p.write_text(old.replace(source, target))
PY
systemctl restart containerd
echo 'Containerd registry trust configured.'
