# Nhịp — Ứng dụng quản lý công việc

Bài project môn Cloud Computing: ứng dụng quản lý công việc cá nhân chạy trên ba VM Azure, sử dụng Kubernetes và Cloudflare D1.

## Chức năng

- Đăng nhập bằng tài khoản đã cấp.
- Thêm, xem, sửa, xóa và đánh dấu hoàn thành công việc.
- Đặt hạn hoàn thành và lọc công việc theo trạng thái.
- Mỗi tài khoản chỉ thao tác trên công việc của mình.

## Kiến trúc

```text
Trình duyệt → Cloudflare DNS / proxy / cache
                      ↓ HTTPS
              Nginx trên một VM Azure
                      ↓ NodePort 30080
              Kubernetes Service → 2 frontend Nginx Pod
                                          ↓
                                   2 backend Flask Pod
                                          ↓ Unix socket
                                   D1 gateway → HTTPS → Cloudflare D1
```

Cluster gồm một control plane và hai worker, cài bằng `kubeadm`, dùng containerd và Flannel. Mỗi deployment frontend/backend có hai replica, đang phân bố trên hai worker. Docker dùng để build image và đẩy lên registry HTTPS riêng trong VNet; tag được ghi rõ phiên bản.

Cloudflare D1 chứa hai bảng `users` và `tasks`. Ứng dụng truy cập D1 qua REST API; dự án không triển khai Cloudflare Worker hay R2. D1 REST API dùng giới hạn API chung của Cloudflare và phù hợp cho demo tải nhỏ.

## Địa chỉ truy cập

| Node | Địa chỉ HTTPS |
|---|---|
| Control plane | https://cp.akaine.io.vn |
| Worker 1 | https://worker1.akaine.io.vn |
| Worker 2 | https://worker2.akaine.io.vn |

Mỗi subdomain trỏ tới IP của node tương ứng. Kubernetes Service có thể chuyển request tiếp tới Pod trên worker khác; các địa chỉ cùng dùng một database D1. Tên miền chính https://akaine.io.vn cũng trỏ tới cụm Azure.

## Cấu trúc chính

| Tệp | Nội dung |
|---|---|
| `app.py` | Backend Flask, đăng nhập và API công việc |
| `static/` | Giao diện web |
| `d1_proxy.py` | Gateway nội bộ giới hạn kết nối đến D1 của dự án |
| `schema-d1.sql` | Bảng và chỉ mục D1 |
| `Dockerfile`, `Dockerfile.frontend`, `Dockerfile.proxy` | Image backend, frontend và D1 gateway |
| `k8s/` | Namespace, Deployment, Service và cấu hình Nginx |
| `infra/azure/` | Template ba VM và script chuẩn bị cluster |
| `backup-d1.py` | Xuất bản backup D1 |
| `docs/azure-k8s.md` | Hướng dẫn vận hành, giới hạn và lệnh demo |
| `OPERATIONS.md` | Ghi chú lịch sử về VPS FPT trước khi chuyển sang Azure |
| `docs/bao-cao-tien-do.md` | Báo cáo tiến độ giữa kỳ |

Script và cấu hình gắn với môi trường demo hiện tại; cần điều chỉnh trước khi dùng ở môi trường khác. Secret, mật khẩu, private key và backup được giữ bên ngoài repository.
