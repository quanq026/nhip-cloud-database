#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" != 0 ]; then echo 'Run as root.' >&2; exit 1; fi
role=${1:?expected cp or worker}
case "$role" in cp|worker) ;; *) echo 'Unknown node role.' >&2; exit 1;; esac
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

timeout 300 cloud-init status --wait || { echo 'cloud-init did not finish cleanly.' >&2; exit 1; }
swapoff -a
cat > /etc/modules-load.d/nhip-k8s.conf <<'EOF'
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter
cat > /etc/sysctl.d/99-nhip-k8s.conf <<'EOF'
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
sysctl --system >/dev/null
apt-get -o DPkg::Lock::Timeout=180 update -qq
apt-get -o DPkg::Lock::Timeout=180 install -y ca-certificates curl gpg containerd
if [ "$role" = cp ]; then apt-get -o DPkg::Lock::Timeout=180 install -y docker.io; fi
mkdir -p /etc/containerd /etc/apt/keyrings
if [ -s /etc/containerd/config.toml ] && [ ! -e /etc/containerd/config.toml.before-nhip ]; then
  cp -p /etc/containerd/config.toml /etc/containerd/config.toml.before-nhip
fi
containerd config default > /etc/containerd/config.toml
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml
systemctl enable --now containerd
systemctl restart containerd
if [ "$role" = cp ]; then systemctl enable --now docker; fi
curl -fsSL --retry 3 https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | gpg --dearmor --yes -o /etc/apt/keyrings/nhip-kubernetes.gpg
chmod 644 /etc/apt/keyrings/nhip-kubernetes.gpg
printf '%s\n' 'deb [signed-by=/etc/apt/keyrings/nhip-kubernetes.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' > /etc/apt/sources.list.d/nhip-kubernetes.list
apt-get -o DPkg::Lock::Timeout=180 update -qq
apt-get -o DPkg::Lock::Timeout=180 install -y kubelet=1.35.10-1.1 kubeadm=1.35.10-1.1 kubectl=1.35.10-1.1
apt-mark hold kubelet kubeadm kubectl
systemctl enable kubelet
echo 'Bootstrap packages installed.'
