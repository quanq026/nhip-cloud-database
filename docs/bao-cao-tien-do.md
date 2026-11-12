# Báo cáo tiến độ — Nhịp trên Azure Kubernetes

## 1. Đề tài và chức năng

Nhịp là ứng dụng quản lý công việc cá nhân: đăng ký, đăng nhập, thêm, xem, sửa, xóa, đánh dấu hoàn thành và lọc theo hạn. Dữ liệu của mỗi người được backend giới hạn theo tài khoản.

## 2. Kiến trúc

Ứng dụng chạy trên ba VM Azure: `nhip-cp`, `nhip-worker1`, `nhip-worker2`. Cụm Kubernetes dùng kubeadm, containerd và Flannel. Frontend Nginx và backend Flask có hai replica mỗi loại; dữ liệu lưu ở Cloudflare D1. Cloudflare quản lý DNS, proxy và HTTPS cho từng node.

## 3. Tiến độ

Đã tạo ba VM riêng, khởi tạo cluster với ba node Ready, build và push image có tag phiên bản lên registry nội bộ, triển khai frontend/backend trong namespace `nhip`. Đã cấp HTTPS cho từng node và tạo bản backup D1 trên Azure.

Trước khi bổ sung đăng ký, đã kiểm tra đăng nhập và đọc D1 qua ba subdomain; sáu kiểm thử API đạt. Đã thử scale backend lên bốn replica, rollout `v2` và rollback `v1`, tắt `worker2` và khôi phục cụm. Một request ngay sau rollback trả 502; các request sau trả 200, nguyên nhân chưa xác định.

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

Chưa có thông tin phân công theo từng thành viên. Cần bổ sung ảnh minh chứng và báo cáo PDF theo đề; tiếp tục tìm nguyên nhân 502 khi rollback.
