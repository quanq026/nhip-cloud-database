#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo 'Run as root.' >&2; exit 1; fi
if [ -e /etc/kubernetes/admin.conf ]; then
  echo 'A control plane already exists; refusing to initialize again.' >&2
  exit 1
fi
umask 077
kubeadm init --skip-token-print \
  --apiserver-advertise-address=10.44.1.10 \
  --pod-network-cidr=10.244.0.0/16 \
  --kubernetes-version=v1.35.10 \
  --cri-socket=unix:///run/containerd/containerd.sock \
  --node-name=nhip-cp 2>&1 \
  | sed -E 's/[a-z0-9]{6}\.[a-z0-9]{16}/[REDACTED]/g; s/sha256:[a-f0-9]{64}/[REDACTED]/g' \
  > /var/log/nhip-kubeadm-init.log
install -d -m 700 -o azureuser -g azureuser /home/azureuser/.kube
install -m 600 -o azureuser -g azureuser /etc/kubernetes/admin.conf /home/azureuser/.kube/config
echo 'Control plane initialized.'
