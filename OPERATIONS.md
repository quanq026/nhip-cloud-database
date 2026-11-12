# Nhịp: cấu hình VPS FPT trước khi chuyển sang Azure

**Tài liệu lịch sử ngày 05/11/2026.** Kiến trúc hiện tại dùng ba VM Azure và Kubernetes; xem `docs/azure-k8s.md`.

Cập nhật ngày 05/11/2026. Ứng dụng: https://akaine.io.vn

## Kiến trúc

```text
Trình duyệt → Cloudflare DNS/proxy/cache → HTTPS → Nginx trên VPS
                                                    ├─ /static: tệp trên VPS
                                                    └─ Flask trên VPS
                                                        ↓ Unix socket
                                                     D1 gateway trên VPS
                                                        ↓ HTTPS REST API
                                                     Cloudflare D1
```

Không triển khai Cloudflare Worker, Pages hoặc R2. D1 là database do Cloudflare quản lý, sử dụng cú pháp SQLite; Flask và Nginx chạy trên VM FPT Cloud `vm-26102812140`. D1 REST API sử dụng giới hạn API chung của Cloudflare, nên phù hợp cho bản demo tải nhỏ; cần đánh giá giới hạn và độ trễ trước khi mở rộng.

| Thành phần | Giá trị |
|---|---|
| Tên miền | `akaine.io.vn`, A record proxy qua Cloudflare |
| Origin | `167.254.69.146`, FPT Cloud |
| TLS | Let's Encrypt tại Nginx; Cloudflare Full (strict) cho riêng hostname này |
| Backend | Container `cdb-app-d1` |
| D1 gateway nội bộ | Container `cdb-d1-proxy`; socket `/run/d1/d1.sock` |
| Nginx | Container `cdb-nginx`, cổng public 80/443 |
| Database | `nhip-midterm` — `eb4b1d10-e6c2-4b83-a861-0fb04bb1747d` |
| Mã triển khai trên VPS | `/opt/cloud-midterm-d1` |

`/static/` được Nginx phục vụ với cache header; Cloudflare đã trả `cf-cache-status: HIT` cho CSS. `/api/` do Flask trả `Cache-Control: no-store`, không cache dữ liệu riêng của người dùng. Địa chỉ cũ `cloud-db-167-254-69-146.sslip.io` chuyển hướng sang tên miền mới.

## Dữ liệu và rollback

- Đã sao chép **2 người dùng và 6 công việc** từ PostgreSQL sang D1; nội dung được đối chiếu trước khi chuyển luồng truy cập.
- PostgreSQL cũ và volume `cdb-study-data` được giữ lại, container `cdb-study` đang dừng. Bản dump trước chuyển đổi nằm trong `/opt/cloud-midterm/backups/pre-d1-20261104T230513Z.dump`, cùng một bản sao trên máy quản trị.
- **D1 là nguồn dữ liệu hiện hành. PostgreSQL cũ không tự đồng bộ với các thay đổi sau chuyển đổi.** Trước khi khôi phục ứng dụng PostgreSQL, phải sao lưu D1 và chuyển các thay đổi mới về PostgreSQL; không chỉ khởi động lại ứng dụng cũ.
- Script cũ `/opt/cloud-midterm/deploy.sh` đã được thêm chốt bảo vệ khi `/opt/cloud-midterm-d1/ACTIVE` tồn tại. Bản gốc được lưu là `deploy.sh.before-d1`.

## Sao lưu và chứng chỉ

- `backup-d1.py` xuất D1 thành `.sql.gz` trong `/opt/cloud-midterm-d1/backups`, quyền chỉ dành cho root. Một bản xuất thủ công đã được tạo thành công.
- Cron chạy backup D1 lúc **02:32** và gia hạn chứng chỉ lúc **03:17**, theo múi giờ VM `Asia/Ho_Chi_Minh`. Chưa quan sát lần chạy theo lịch đầu tiên.
- Script backup không tự xóa các bản cũ; theo dõi dung lượng ổ đĩa. Bản backup trên VPS vẫn có thể mất nếu mất cả VPS.
- Cron backup PostgreSQL cũ đã được lưu lại tại `/opt/cloud-midterm/backups/postgres-backup.cron.disabled` để tránh nhầm là backup D1.

## Secret và vận hành

Token Cloudflare chỉ nằm trong `/opt/cloud-midterm-d1/secrets`, quyền root. Flask không được mount token; gateway chỉ chuyển query đến đúng database D1 của Nhịp. Token đang dùng cũng có thể có quyền với tài nguyên Cloudflare khác; nên thay bằng token D1 riêng khi có thể, và sử dụng token DNS riêng cho gia hạn chứng chỉ.

Trạng thái dịch vụ có thể xem trên VPS:

```sh
docker ps --filter name=cdb-
docker logs --tail 50 cdb-app-d1
docker logs --tail 50 cdb-nginx
```

`stage.sh` tạo container mới và từ chối chạy đè tên container đã tồn tại. `start-nginx.sh` khởi động Nginx với chứng chỉ và cấu hình hiện tại. `renew-certificates.sh` thực hiện gia hạn rồi reload Nginx. Không đưa thư mục `secrets`, bản backup hoặc private key vào source công khai.

## Báo cáo giữa kỳ trước đó

Báo cáo PDF ngày 28/10/2026 mô tả kiến trúc PostgreSQL và Caddy cùng kết quả kiểm chứng tại thời điểm đó. Kể từ 05/11/2026, kiến trúc hoạt động đã chuyển sang Nginx, Cloudflare và D1; dùng tài liệu này khi trình bày phần cập nhật. Kết quả kiểm thử cũ không được coi là kiểm thử D1 mới.
