# Nhịp — Ứng dụng quản lý công việc

Bài project môn Cloud Computing: ứng dụng quản lý công việc cá nhân chạy trên VPS FPT Cloud, sử dụng Cloudflare D1 làm cơ sở dữ liệu.

## Chức năng

- Đăng nhập bằng tài khoản đã cấp.
- Thêm, xem, sửa, xóa và đánh dấu hoàn thành công việc.
- Đặt hạn hoàn thành và lọc công việc theo trạng thái.
- Mỗi tài khoản chỉ thao tác trên công việc của mình.

## Kiến trúc

```text
Trình duyệt → Cloudflare DNS / proxy / cache → Nginx trên VPS
                                                  ├─ Tệp tĩnh trên VPS
                                                  └─ Flask → Unix socket → D1 gateway
                                                                             ↓ HTTPS
                                                                        Cloudflare D1
```

Cloudflare D1 chứa hai bảng `users` và `tasks`. Ứng dụng và gateway chạy trong Docker trên VPS. Cloudflare D1 được truy cập qua REST API; dự án không triển khai Cloudflare Worker hay R2. D1 REST API dùng giới hạn API chung của Cloudflare và phù hợp cho phạm vi demo tải nhỏ.

## Cấu trúc chính

| Tệp | Nội dung |
|---|---|
| `app.py` | Backend Flask, đăng nhập và API công việc |
| `static/` | Giao diện web |
| `d1_proxy.py` | Gateway nội bộ giới hạn kết nối đến D1 của dự án |
| `schema-d1.sql` | Bảng và chỉ mục D1 |
| `nginx.conf` | Nginx, HTTPS và cache tài nguyên tĩnh |
| `stage.sh`, `start-nginx.sh` | Khởi động container trên VPS hiện có |
| `backup-d1.py` | Xuất bản backup D1 |
| `renew-certificates.sh` | Gia hạn chứng chỉ và reload Nginx |
| `OPERATIONS.md` | Thông tin triển khai, sao lưu và lưu ý rollback |
| `docs/bao-cao-tien-do.md` | Báo cáo tiến độ giữa kỳ |

Script và cấu hình hiện gắn với môi trường VPS, tên miền và database của dự án. Cần điều chỉnh chúng trước khi dùng cho môi trường khác. Secret, mật khẩu, private key và bản sao dữ liệu được giữ bên ngoài repository.
