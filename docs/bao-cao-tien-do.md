# Báo cáo tiến độ — Nhịp trên Azure Kubernetes

## 1. Đề tài và chức năng

Nhịp là ứng dụng quản lý công việc cá nhân: đăng nhập, thêm, xem, sửa, xóa, đánh dấu hoàn thành và lọc theo hạn. Dữ liệu của mỗi người được backend giới hạn theo tài khoản.

## 2. Kiến trúc

Ứng dụng chạy trên ba VM Azure: `nhip-cp`, `nhip-worker1`, `nhip-worker2`. Cụm Kubernetes dùng kubeadm, containerd và Flannel. Frontend Nginx và backend Flask có hai replica mỗi loại; dữ liệu lưu ở Cloudflare D1. Cloudflare quản lý DNS, proxy và HTTPS cho từng node.

## 3. Tiến độ

Đã tạo ba VM riêng, khởi tạo cluster với ba node Ready, build và push image có tag phiên bản lên registry nội bộ, triển khai frontend/backend trong namespace `nhip`. Đã cấp HTTPS cho từng node và tạo bản backup D1 trên Azure.

Đã kiểm tra đăng nhập và đọc D1 qua ba subdomain. Chưa thực hiện bài demo scale bốn replica, rollout/rollback hoặc tắt worker trong lần triển khai này.

## 4. Triển khai và minh chứng

- https://cp.akaine.io.vn — control plane.
- https://worker1.akaine.io.vn — worker 1.
- https://worker2.akaine.io.vn — worker 2.
- `kubectl get nodes` ghi nhận ba node Ready; `kubectl get pods -n nhip -o wide` ghi nhận hai replica frontend và hai replica backend phân bố trên cả hai worker.

Các subdomain đi vào node tương ứng, sau đó Kubernetes Service có thể chuyển request tới Pod trên worker khác.

## 5. Khó khăn

- East Asia đã hết hạn mức vCPU và IP public: chọn Japan East cho cụm riêng.
- Worker chưa tin chứng chỉ registry nội bộ: cấu hình CA cho containerd trên hai worker.
- D1 sử dụng SQLite và REST API: giữ gateway nội bộ để backend truy cập qua HTTPS.

## 6. Phân công và việc tiếp theo

Chưa có thông tin phân công theo từng thành viên. Cần bổ sung và chuẩn bị phần scale, cập nhật/rollback, mô phỏng tắt worker, ảnh minh chứng và báo cáo PDF theo đề.
