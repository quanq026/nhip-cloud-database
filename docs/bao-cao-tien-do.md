# Báo cáo tiến độ giữa kỳ — Cloud Computing

## 1. Đề tài, mục tiêu và chức năng

Đề tài **Nhịp** là ứng dụng quản lý công việc cá nhân, giúp người dùng theo dõi công việc và hạn hoàn thành. Ứng dụng có chức năng đăng nhập, thêm, xem, sửa, xóa, đánh dấu hoàn thành và lọc công việc. Mỗi tài khoản quản lý công việc của mình.

## 2. Kiến trúc và công nghệ

Trình duyệt truy cập qua Cloudflare và Nginx trên VPS FPT Cloud. Nginx phục vụ tệp tĩnh và chuyển request tới Flask. Flask sử dụng gateway nội bộ để truy vấn Cloudflare D1 qua REST API. Các thành phần trên VPS được đóng gói bằng Docker.

D1 gồm bảng `users` và `tasks`, liên kết qua `user_id`. Dự án không triển khai Worker hay R2.

## 3. Tiến độ hiện tại

Đã xây dựng giao diện, backend và schema; triển khai VPS, Nginx, HTTPS và DNS Cloudflare; chuyển dữ liệu từ PostgreSQL sang D1; tạo tài khoản demo và cấu hình backup D1.

Đang tổng hợp minh chứng và chuẩn bị nội dung trình bày. Chưa kiểm thử lại toàn bộ đăng nhập và CRUD sau khi chuyển D1; chưa quan sát lần backup chạy theo lịch; chưa kiểm thử tải lớn.

## 4. Triển khai và minh chứng

Website: https://akaine.io.vn. Cloudflare đã ghi nhận cache HIT cho tài nguyên CSS. Trước khi chuyển database, PostgreSQL đã được sao lưu; dữ liệu nguồn và D1 đã được đối chiếu trước thời điểm chuyển luồng truy cập. Một bản xuất D1 đã được tạo trên VPS.

## 5. Khó khăn và hướng giải quyết

- VPS ban đầu chỉ có IP nội bộ: cấp IP public riêng.
- PostgreSQL và D1 dùng cú pháp SQL khác nhau: điều chỉnh schema và backend, đối chiếu dữ liệu trước khi chuyển.
- Dữ liệu người dùng cần được bảo vệ khi qua CDN: cache tài nguyên tĩnh, để API trả `Cache-Control: no-store`.

## 6. Phân công và kế hoạch

Các phần việc gồm database, giao diện và backend, hạ tầng VPS và Cloudflare, báo cáo và thuyết trình. **Chưa có thông tin phân công theo từng thành viên.**

Tiếp theo: kiểm tra các chức năng trên D1, theo dõi backup tự động và hoàn thiện bài trình bày.
