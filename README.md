# Nhịp — quản lý công việc trên Azure Kubernetes

Nhịp là ứng dụng quản lý công việc cá nhân cho bài giữa kỳ CKA. Frontend và backend chạy trên cụm Kubernetes gồm ba VM Azure. Dữ liệu được lưu trong Cloudflare D1.

## Chức năng

- Đăng ký bằng email, đăng nhập; mỗi người chỉ truy cập công việc của mình.
- Thêm, xem, sửa, xóa và đánh dấu hoàn thành công việc.
- Đặt hạn và lọc theo trạng thái hoặc công việc quá hạn.

Đăng ký dùng email và mật khẩu từ 8 ký tự; tài khoản được đăng nhập ngay sau khi tạo. Mật khẩu được băm trước khi lưu vào D1. Đây là bản demo, chưa có xác minh email hoặc chức năng khôi phục mật khẩu.

## Kiến trúc

```text
Trình duyệt
    ↓ HTTPS
Cloudflare DNS / proxy / cache
    ↓
Nginx trên VM nhận request
    ↓ NodePort 30080
Service frontend → 2 Pod frontend (Nginx, tệp tĩnh)
    ↓
Service backend  → 2 Pod backend (Flask + D1 gateway)
    ↓ HTTPS REST API
Cloudflare D1: users, tasks
```

Mỗi backend Pod có hai container: Flask và D1 gateway, giao tiếp qua Unix socket. Gateway đọc token từ Kubernetes Secret và gửi query tới D1. Ứng dụng không dùng Cloudflare Worker hoặc R2.

| Node | Vai trò | IP nội bộ | HTTPS |
|---|---|---|---|
| `nhip-cp` | Control plane và registry | `10.44.1.10` | https://cp.akaine.io.vn |
| `nhip-worker1` | Worker | `10.44.1.11` | https://worker1.akaine.io.vn |
| `nhip-worker2` | Worker | `10.44.1.12` | https://worker2.akaine.io.vn |

Tên miền chính: https://akaine.io.vn. Mỗi subdomain trỏ vào node tương ứng; Kubernetes Service có thể chuyển request đến Pod ở worker khác. Các địa chỉ cùng sử dụng D1; cookie phiên gắn với từng hostname.

## SSH vào từng VPS

Chạy lệnh tương ứng trên máy của bạn. Khi hiện `password:`, nhập mật khẩu SSH đã được cấp; mật khẩu không hiển thị khi gõ.

**Control plane:**

```sh
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no azureuser@48.218.48.140
```

**Worker 1:**

```sh
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no azureuser@74.176.68.41
```

**Worker 2:**

```sh
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no azureuser@48.218.52.218
```

SSH dùng IP public trực tiếp vì các subdomain website đang bật Cloudflare proxy. Cổng 22 chỉ mở cho IP quản trị đã cấu hình trong Azure NSG; khi đổi mạng, cần cập nhật quy tắc trước khi kết nối. Đăng nhập bằng SSH key vẫn được hỗ trợ.

## Công nghệ và tài nguyên

- Azure Japan East, resource group `rg-nhip-k8s`: ba VM `Standard_B2als_v2`, mỗi VM 2 vCPU, 4 GiB RAM và SSD 32 GB.
- Kubernetes `v1.35.10` cài bằng `kubeadm`, containerd `2.2.1` và Flannel `v0.28.10`.
- Namespace `nhip`: hai replica frontend và hai replica backend, phân bố trên hai worker khi cụm hoạt động bình thường.
- Docker build image; registry HTTPS `10.44.1.10:5000` nằm trong VNet và lưu các tag `v1`/`v2` của bài demo. Registry phụ thuộc control plane.
- Nginx trên từng VM kết thúc HTTPS, chuyển request vào NodePort; Cloudflare proxy và Full (strict) được bật cho từng subdomain.

## Cấu trúc source

| Đường dẫn | Nội dung |
|---|---|
| `app.py`, `d1_proxy.py` | Flask API và gateway tới D1 |
| `static/`, `Dockerfile.frontend` | Giao diện và image Nginx frontend |
| `Dockerfile`, `Dockerfile.proxy` | Image backend và D1 gateway |
| `schema-d1.sql` | Cấu trúc bảng `users`, `tasks` |
| `k8s/` | Namespace, Deployment, Service, cấu hình Nginx và script build image |
| `infra/azure/` | Template Azure và script chuẩn bị node |
| `backup-d1.py` | Xuất backup D1 |
| `docs/azure-k8s.md` | Hướng dẫn hạ tầng, triển khai và vận hành chi tiết |
| `docs/kich-ban-bao-ve.md` | Kịch bản demo và câu hỏi bảo vệ |
| `docs/bao-cao-tien-do.md` | Tóm tắt tiến độ giữa kỳ |

## Xem trạng thái cụm

Trên control plane, dùng tài khoản có kubeconfig của cluster:

```sh
kubectl get nodes -o wide
kubectl get deployments,pods,services -n nhip -o wide
kubectl get endpointslices -n nhip
```

Kỳ vọng: ba node `Ready`; `nhip-frontend` và `nhip-backend` đều `2/2`; mỗi deployment có một Pod trên mỗi worker. Endpoint `/readyz` kiểm tra đường kết nối từ backend tới D1; `/version` trả phiên bản backend.

## Build và triển khai

Trên control plane, từ thư mục source đã chuẩn bị:

```sh
sudo bash k8s/build-images.sh
kubectl apply -f k8s/00-namespace.yaml
```

Trước lần triển khai đầu, tạo Secret từ **các file riêng trên máy quản trị**. Không đưa giá trị token hay session key vào Git hoặc ảnh chụp. Nếu Secret đã tồn tại, không chạy lại lệnh `create` để ghi đè ngoài ý muốn.

```sh
kubectl -n nhip create secret generic nhip-credentials \
  --from-file=d1_token=/duong-dan-an-toan/d1-token \
  --from-file=session_key=/duong-dan-an-toan/session-key
kubectl apply -f k8s/01-backend.yaml -f k8s/02-frontend.yaml
kubectl rollout status deployment/nhip-frontend -n nhip
kubectl rollout status deployment/nhip-backend -n nhip
```

Các file và script dùng tên miền, IP, registry và D1 của môi trường hiện tại. Xem [hướng dẫn Azure](docs/azure-k8s.md) trước khi tạo lại ở môi trường khác. SSH và NodePort chỉ cho phép IP quản trị đã cấu hình; cập nhật NSG khi IP này thay đổi.

## Demo Kubernetes

Chạy trên control plane khi cần trình bày:

```sh
# Scale backend lên bốn replica và đưa về hai.
kubectl scale deployment/nhip-backend -n nhip --replicas=4
kubectl rollout status deployment/nhip-backend -n nhip
kubectl get pods -n nhip -o wide
kubectl scale deployment/nhip-backend -n nhip --replicas=2
kubectl rollout status deployment/nhip-backend -n nhip

# Cập nhật backend từ v1 lên v2, rồi quay lại phiên bản trước.
kubectl set image deployment/nhip-backend -n nhip app=10.44.1.10:5000/nhip-backend:v2-routing
kubectl rollout status deployment/nhip-backend -n nhip
kubectl rollout undo deployment/nhip-backend -n nhip
kubectl rollout status deployment/nhip-backend -n nhip
```

Trang đăng nhập hiển thị huy hiệu **Backend · v1/v2** từ `/version`, tự cập nhật khoảng 5 giây. Trong lúc rollout có thể có cả Pod v1 và v2; huy hiệu thể hiện Pod trả lời request gần nhất. `v2` là image demo có dấu phiên bản khác, không phải một tính năng mới. Xem [kịch bản và câu hỏi bảo vệ](docs/kich-ban-bao-ve.md).

Để trình bày mất node, dừng **đúng `nhip-worker2` trong `rg-nhip-k8s`**, quan sát node `NotReady` và các Pod được tạo lại trên worker còn sống, sau đó khởi động lại VM. Chờ thao tác tắt hoàn tất trước khi gửi lệnh bật. Khi cả ba node đã `Ready`, có thể `kubectl rollout restart` từng deployment để phân bố lại Pod. Hostname của worker bị tắt không thể phục vụ; truy cập qua node còn hoạt động.

Đã chuẩn bị script demo tắt rồi khôi phục **từng worker**. Chạy trên máy quản trị có Azure CLI đã đăng nhập đúng subscription, Python và SSH key có quyền vào control plane. Cần xác nhận host key control plane trước; nếu known-hosts nằm ở file riêng, đặt biến môi trường `NHIP_KNOWN_HOSTS` tới file đó. Script dừng một worker, quan sát Pod chuyển sang máy còn lại, bật lại worker và phân bố lại Pod; kết quả ghi vào `demo-result-worker1.json` hoặc `demo-result-worker2.json` tại thư mục hiện tại.

```sh
python infra/azure/demo-worker.py worker1
```

Chờ worker 1 phục hồi hoàn toàn, sau đó mới chạy worker 2:

```sh
python infra/azure/demo-worker.py worker2
```

Nếu script bị ngắt hoặc báo lỗi, kiểm tra trạng thái VM trên Azure và `kubectl get nodes`; đảm bảo worker được bật lại trước khi tiếp tục.

### Xem request đang đi qua worker nào

Sau khi đăng nhập, dòng **“Request gần nhất”** hiển thị node frontend và backend của lần lấy trạng thái gần nhất, cập nhật khoảng 5 giây. Chẳng hạn, truy cập qua `cp.akaine.io.vn` vẫn có thể được Kubernetes chuyển tới Pod trên một trong hai worker. Đây là mẫu request, không phải thống kê toàn bộ tải.

Trên control plane, xem log frontend có `frontend_node`, `frontend_pod`, trạng thái và thời gian request:

```sh
kubectl logs -n nhip -l app=nhip-frontend -c nginx --all-pods=true --tail=30 --max-log-requests=10 -f
```

Xem log backend `NHIP_ROUTE` có cả frontend và backend node/Pod tương ứng:

```sh
kubectl logs -n nhip -l app=nhip-backend -c app --all-pods=true --tail=30 --max-log-requests=10 -f
```

Nhấn `Ctrl+C` để dừng xem log. Khi worker bị tắt, `kubectl logs` tới Pod cũ trên node đó có thể timeout; xem Pod đang chạy bằng `kubectl get pods -n nhip -o wide` rồi dùng `kubectl logs -n nhip <ten-pod> -c nginx` hoặc `-c app` cho Pod còn sống. Dòng `upstream` trong log Nginx frontend là IP của Service backend; `backend_node` trong `NHIP_ROUTE` cho biết node backend thực sự trả lời.

## Kết quả kiểm tra ngày 12/11/2026

| Nội dung | Kết quả |
|---|---|
| Cluster và phân bố Pod | Ba node `Ready`; frontend/backend `2/2`, mỗi deployment có Pod trên cả hai worker. |
| Đăng nhập | Thành công trên cả ba subdomain; API danh sách công việc trả 200. |
| Kiểm thử ứng dụng | 6 kiểm thử tích hợp đạt: đăng nhập, CRUD, phân quyền, Origin/CSRF, input và đăng xuất. |
| Scale | Backend đạt 4 replica: 2 trên mỗi worker; sau đó đưa về 2. |
| Rollout/rollback | Với image trước khi thêm đăng ký, rollout `v2` trả phiên bản `v2`; đã rollback về `v1`. Một request ngay sau rollback trả 502, các request sau trả 200. Chưa xác định nguyên nhân 502. |
| Tắt worker | `nhip-worker2` chuyển `NotReady`; 2 frontend và 2 backend được tạo trên `worker1`. Website qua node còn lại trả `/readyz` 200. Worker 2 sau đó được bật lại; Pod đã phân bố về cả hai worker. |
| Tắt và phục hồi từng worker, 12/11/2026 | Đã thử tuần tự `worker1` và `worker2`. Khi một worker dừng, hai frontend và hai backend sẵn sàng trên worker còn lại; endpoint còn sống trả 200. Cả hai worker đã được bật lại và Pod phân bố lại. Lần đo worker1 khoảng 132 giây, worker2 khoảng 130 giây, tính từ yêu cầu dừng đến khi quan sát đủ replica. |
| Theo dõi request | Giao diện hiển thị frontend/backend node gần nhất; `NHIP_ACCESS` và `NHIP_ROUTE` ghi node, Pod và trạng thái request. Quan sát 12 request thấy cả hai worker phục vụ frontend và backend. |

Thời gian quan sát trong lần tắt worker khoảng **80 giây** đến khi các replica trên worker còn lại sẵn sàng; đây là một phép đo demo, không phải SLA. Lần khôi phục đầu gặp tình trạng lệnh bật được gửi trước khi Azure hoàn tất lệnh tắt; gửi lại lệnh bật sau khi tắt xong đã đưa worker trở về `Ready`.

## Dữ liệu và chi phí

D1 là nguồn dữ liệu đang sử dụng. PostgreSQL cũ là bản trước khi chuyển D1 và không tự đồng bộ. Backup D1 được xuất tại `/opt/nhip-k8s/backups` trên control plane; cron lúc 02:47 giờ Việt Nam đã được cài nhưng chưa xác nhận lần chạy tự động. Backup trên cùng VM không bảo vệ khi mất toàn bộ VM.

Ba VM mới có chi phí Azure; dự toán PAYG lúc tạo khoảng **4,13 USD/ngày** cho VM, IP và ổ đĩa, chưa tính các khoản khác. Số credit còn lại chưa xác nhận. Ba VM trong resource group `RG-K8S` là cụm khác và cũng đang chạy; không dừng hoặc xóa chúng khi dọn tài nguyên Nhịp.
