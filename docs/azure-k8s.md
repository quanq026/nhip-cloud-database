# Hướng dẫn Azure Kubernetes — Nhịp

## Tài nguyên hiện tại

| VM | Vai trò | IP nội bộ | IP public | HTTPS |
|---|---|---|---|---|
| `nhip-cp` | Control plane, registry | `10.44.1.10` | `48.218.48.140` | `cp.akaine.io.vn` |
| `nhip-worker1` | Worker | `10.44.1.11` | `74.176.68.41` | `worker1.akaine.io.vn` |
| `nhip-worker2` | Worker | `10.44.1.12` | `48.218.52.218` | `worker2.akaine.io.vn` |

Resource group `rg-nhip-k8s`, region Japan East. Mỗi VM dùng `Standard_B2als_v2`: 2 vCPU, 4 GiB RAM, ổ Standard SSD 32 GB. Cụm `RG-K8S` ở East Asia là tài nguyên khác. SSH và NodePort 30080 chỉ được phép từ IP quản trị tại thời điểm tạo; HTTPS 443 và HTTP 80 được mở để truy cập website/cấp chứng chỉ.

Tài khoản SSH trên ba VM là `azureuser`, hỗ trợ mật khẩu và SSH key. Các lệnh SSH theo từng máy được liệt kê trong [README](../README.md#ssh-vào-từng-vps). Cấu hình password login là thay đổi thực hiện sau khi tạo VM; template Azure vẫn tạo VM với SSH key và không chứa mật khẩu.

Kubernetes `v1.35.10`, containerd `2.2.1`, Flannel `v0.28.10`; Pod CIDR `10.244.0.0/16`. Namespace ứng dụng là `nhip`. `nhip-frontend` và `nhip-backend` đều có hai replica; mỗi backend Pod gồm Flask và D1 gateway dùng chung Unix socket.

## Chuẩn bị cluster

Template `infra/azure/azure-vms.json` tạo VNet, NSG, ba public IP và ba VM. File tham số chứa SSH public key và IP quản trị được tạo riêng, không lưu trong Git. Các script trong `infra/azure/` giả định đúng tên và IP nội bộ của cluster này; không chạy lại lên máy đang dùng nếu chưa đọc nội dung.

Trên từng node mới, chạy `bootstrap-node.sh` với tham số `cp` hoặc `worker`. Trên control plane, chạy `init-control-plane.sh` và cài Flannel từ manifest phiên bản cố định:

```sh
kubectl apply -f https://github.com/flannel-io/flannel/releases/download/v0.28.10/kube-flannel.yml
```

Tạo lệnh join có thời hạn ngắn trên control plane và chạy trên từng worker. Lệnh join chứa token: không đưa token hoặc kubeconfig vào Git, ảnh chụp hay log chia sẻ.

## Registry và image

Registry `10.44.1.10:5000` chạy trên control plane, chỉ bind IP riêng trong VNet, dùng TLS với CA riêng. `setup-registry.sh` tạo registry; sao chép **chứng chỉ CA công khai**, không sao chép private key, rồi chạy `configure-registry-trust.sh` trên worker. Registry này phục vụ demo và phụ thuộc control plane; không phải registry HA.

Trên control plane, từ thư mục source:

```sh
sudo bash k8s/build-images.sh
```

Script build và push frontend `v1-routing`, D1 gateway `v1`, backend `v1-routing` và `v2-routing`. Không dùng tag `latest`. Registry nằm trong VNet, nên người ngoài không thể pull image trực tiếp; họ có thể build lại từ source.

## Secret và triển khai

Tạo namespace trước, sau đó tạo Secret `nhip-credentials` từ hai file riêng: `d1_token` và `session_key`. Token Cloudflare và session key không được commit hoặc đặt trực tiếp trong YAML. Backend Flask chỉ mount session key; D1 gateway mount token và chỉ gửi query tới database được cấu hình.

```sh
kubectl apply -f k8s/00-namespace.yaml
kubectl -n nhip create secret generic nhip-credentials \
  --from-file=d1_token=/duong-dan/an-toan/d1-token \
  --from-file=session_key=/duong-dan/an-toan/session-key
kubectl apply -f k8s/01-backend.yaml -f k8s/02-frontend.yaml
kubectl get nodes -o wide
kubectl get deploy,pods,svc -n nhip -o wide
```

Nginx frontend trong Kubernetes được public qua NodePort `30080`. Nginx trên từng VM nhận HTTPS và proxy tới NodePort. `setup-node-https.sh` cấu hình Nginx và Certbot cho từng hostname; chứng chỉ Let’s Encrypt được gia hạn bằng `certbot.timer`. Cloudflare proxy và Full (strict) được bật cho ba subdomain.

## Lệnh chuẩn bị demo theo đề

Các thao tác dưới đây thay đổi trạng thái cluster. Chỉ chạy khi chuẩn bị demo; kết quả cần được ghi nhận riêng.

```sh
kubectl scale deployment/nhip-backend -n nhip --replicas=4
kubectl get pods -n nhip -o wide
kubectl scale deployment/nhip-backend -n nhip --replicas=2

kubectl set image deployment/nhip-backend -n nhip app=10.44.1.10:5000/nhip-backend:v2-routing
kubectl rollout status deployment/nhip-backend -n nhip
kubectl rollout undo deployment/nhip-backend -n nhip
kubectl rollout status deployment/nhip-backend -n nhip
```

Ngày 12/11/2026 đã thử dừng lần lượt `nhip-worker1` và `nhip-worker2`: mỗi node chuyển `NotReady`, hai frontend và hai backend được tạo trên worker còn lại, `/readyz` qua node còn lại trả 200. Cả hai VM đã được bật lại và Pod được phân bố lại. Lần đo gần nhất tính từ yêu cầu dừng đến đủ replica: worker1 khoảng 132 giây, worker2 khoảng 130 giây; đây không phải SLA. Dùng `python infra/azure/demo-worker.py worker1` hoặc `worker2` từ máy quản trị để lặp lại; chờ từng kịch bản kết thúc trước khi chạy tiếp. Khi thao tác thủ công, chờ Azure hoàn tất lệnh tắt trước khi gửi lệnh bật. Hostname trỏ đến worker bị tắt không hoạt động, dù ứng dụng vẫn phục vụ qua node còn lại.

Sau khi đăng nhập, giao diện hiển thị node frontend/backend của request trạng thái gần nhất. Log Nginx `NHIP_ACCESS` cho biết node/Pod frontend và Service upstream; log Flask `NHIP_ROUTE` cho biết cả node/Pod frontend và backend. Đây là mẫu của request cụ thể, không phải số liệu tổng tải. Endpoint trạng thái yêu cầu đăng nhập và được gọi định kỳ khoảng 5 giây, làm tăng số request tới D1 API.

Đã thử scale backend lên bốn replica và rollout `v2` rồi rollback `v1`. Một request ngay sau rollback trả 502; các request sau trả 200. Chưa xác định nguyên nhân của 502, nên không kết luận rollout không gián đoạn.

## Dữ liệu, backup và chi phí

D1 là nguồn dữ liệu chung. Các hostname sử dụng cùng database; thao tác trên một hostname có hiệu lực ở các hostname khác. Không tự khôi phục PostgreSQL cũ vì nó không đồng bộ với thay đổi sau khi chuyển D1.

Backup D1 trên `nhip-cp` nằm trong `/opt/nhip-k8s/backups`; cron chạy lúc 19:47 UTC (02:47 Việt Nam). Đã tạo một bản thủ công; chưa quan sát lần cron tự chạy. Backup không tự xóa theo thời gian, cần theo dõi dung lượng.

Ba VM mới đang chạy và tiêu thụ credit Azure. Giá niêm yết tham khảo cho ba VM, ba IP và ổ đĩa khoảng 4,13 USD/ngày; số credit thực tế còn lại chưa xác nhận. Khi không demo, có thể deallocate đúng ba VM mới; ổ đĩa và public IP vẫn có thể tính phí. Không dừng hoặc xóa resource group `RG-K8S` của cụm khác.
