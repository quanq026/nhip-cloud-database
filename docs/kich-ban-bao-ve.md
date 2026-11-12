# Kịch bản demo và câu hỏi bảo vệ

Các lệnh Kubernetes chạy trên `nhip-cp`, trong thư mục source. Trước buổi demo, kiểm tra tài khoản, SSH, credit Azure và sao lưu D1. Các lệnh scale, cập nhật và tắt node thay đổi hệ thống đang chạy.

## 1. Giới thiệu cụm và vị trí Pod

```sh
kubectl get nodes -o wide
kubectl get deployments,pods,services -n nhip -o wide
kubectl get endpointslices -n nhip
```

**Giải thích:** Cụm có 1 control plane và 2 worker. Frontend và backend là hai Deployment riêng; bình thường mỗi Deployment có 2 Pod, một trên mỗi worker. Backend Pod gồm Flask và D1 gateway. Service cung cấp địa chỉ ổn định để frontend gọi backend và đưa frontend ra NodePort.

**Có thể bị hỏi:** Vì sao `kubectl get nodes` không hiện EXTERNAL-IP? Đây là Kubernetes trên VM tự quản lý; cột đó không tự chứng minh VM không có IP public. Địa chỉ public được Azure quản lý, xem trong Azure Portal hoặc `az vm list-ip-addresses`.

## 2. Dữ liệu được lưu ở đâu?

**Trả lời:** Cloudflare D1 lưu hai bảng `users` và `tasks`, liên kết bằng `user_id`. Flask lấy danh tính từ session và giới hạn query theo người dùng. Backend gọi D1 qua một gateway nội bộ và HTTPS REST API.

**Có thể bị hỏi:** Xóa Pod backend có mất dữ liệu không? Dữ liệu ứng dụng nằm ở D1 nên việc xóa Pod không tự xóa bảng hoặc dữ liệu D1. Secret, DNS, mạng và khả năng truy cập D1 vẫn cần hoạt động để Pod mới phục vụ.

**Có thể bị hỏi:** D1 có nằm trong cluster? Không. D1 là dịch vụ database của Cloudflare; các Pod chạy trên Azure. Cách này đơn giản cho demo, nhưng phụ thuộc Internet và giới hạn Cloudflare API.

**Có thể bị hỏi:** Đăng ký hoạt động thế nào? Người dùng nhập email và mật khẩu; backend kiểm tra dữ liệu, băm mật khẩu và tạo user trong D1. Bảng `users` có `UNIQUE` cho email để tránh trùng. Bản demo chưa có xác minh email hay khôi phục mật khẩu.

## 3. Scale backend

```sh
kubectl scale deployment/nhip-backend -n nhip --replicas=4
kubectl rollout status deployment/nhip-backend -n nhip
kubectl get pods -n nhip -l app=nhip-backend -o wide
kubectl scale deployment/nhip-backend -n nhip --replicas=2
kubectl rollout status deployment/nhip-backend -n nhip
```

**Kết quả đã ghi nhận ngày 12/11/2026:** 4 backend Pod sẵn sàng, 2 Pod trên mỗi worker; sau đó đưa về 2 replica. Deployment điều chỉnh số Pod, còn Service cập nhật danh sách endpoint sẵn sàng.

## 4. Rollout v2 và rollback v1

Mở trang đăng nhập tại một trong ba subdomain. Huy hiệu **Backend · v1/v2** hiển thị phiên bản backend trả lời request gần nhất; nó tự cập nhật khoảng 5 giây một lần khi trang đăng nhập đang mở.

```sh
kubectl set image deployment/nhip-backend -n nhip app=docker.io/quanq026/nhip-k8s-backend:v2
kubectl rollout status deployment/nhip-backend -n nhip
kubectl get pods -n nhip -l app=nhip-backend -o wide

kubectl rollout undo deployment/nhip-backend -n nhip
kubectl rollout status deployment/nhip-backend -n nhip
```

**Giải thích:** `v2` là image demo được build với `APP_VERSION=v2`; rollback đưa Deployment về revision trước. Trong lúc rollout, các Pod v1 và v2 có thể cùng chạy nên huy hiệu có thể luân phiên theo Pod trả lời. Sau khi rollout hoàn tất, chờ lần cập nhật tiếp theo hoặc tải lại trang.

**Giới hạn đã ghi nhận:** Một request ngay sau rollback ngày 12/11/2026 từng trả 502; các request sau trả 200. Chưa xác định nguyên nhân, không khẳng định cập nhật hoàn toàn không gián đoạn.

## 5. Tắt một worker

Trong ví dụ dưới đây, chỉ dừng `nhip-worker2` trong resource group `rg-nhip-k8s`; VM đang phục vụ sẽ gián đoạn trong lúc thử. Chạy các lệnh `az` trên máy đã đăng nhập Azure CLI và `kubectl` trên control plane. Không tắt control plane hoặc VM thuộc `RG-K8S`.

```sh
az vm stop --resource-group rg-nhip-k8s --name nhip-worker2
kubectl get nodes -o wide
kubectl get pods -n nhip -o wide
az vm start --resource-group rg-nhip-k8s --name nhip-worker2
```

Chờ lệnh tắt hoàn tất trước khi bật lại. Sau khi node `Ready`, kiểm tra lại Pod; nếu cần phân bố lại, thực hiện `kubectl rollout restart` từng Deployment và chờ rollout hoàn tất.

**Kết quả đã ghi nhận:** Đã thử lần lượt cả `worker1` và `worker2`. Khi một worker `NotReady`, 2 frontend và 2 backend được tạo trên worker còn lại; website qua node còn sống trả `/readyz` 200. Cả hai worker đều được khởi động lại và Pod được phân bố lại. Lần đo gần nhất khoảng 132 giây khi tắt worker1 và 130 giây khi tắt worker2; đây không phải SLA. Địa chỉ riêng của worker bị tắt không phục vụ khi VM đó ngừng.

Kết quả có thời gian và trạng thái từng bước: [worker1](minh-chung/worker1.json), [worker2](minh-chung/worker2.json).

Có thể thực hiện từng kịch bản từ máy quản trị, chờ kịch bản đầu hoàn tất trước khi chạy kịch bản sau:

```sh
python infra/azure/demo-worker.py worker1
python infra/azure/demo-worker.py worker2
```

Script yêu cầu Azure CLI đăng nhập đúng subscription và SSH key vào control plane. Kiểm tra VM và node thủ công nếu script bị gián đoạn.

## 6. Câu hỏi ngắn

| Câu hỏi | Trả lời |
|---|---|
| Deployment khác Pod thế nào? | Pod chạy container; Deployment duy trì số Pod và quản lý rollout/rollback. |
| Service dùng để làm gì? | Chọn các Pod theo nhãn và cung cấp địa chỉ ổn định cho truy cập nội bộ hoặc NodePort. |
| Docker và containerd khác nhau ở đâu? | Docker build/push image; kubelet dùng containerd làm runtime để chạy container trên node. |
| Vì sao cần Flannel? | Flannel là CNI tạo mạng cho Pod giao tiếp giữa các node. |
| Vì sao có nhiều Nginx? | Nginx trên VM nhận HTTPS; Nginx frontend trong Pod phục vụ tệp tĩnh và chuyển API tới backend. |
| CP chuyển request tới worker nào? | Sau đăng nhập, giao diện hiện node frontend và backend của request trạng thái gần nhất. `NHIP_ACCESS` và `NHIP_ROUTE` ghi thêm node/Pod. Kubernetes Service quyết định endpoint cho mỗi kết nối; số request mẫu không chứng minh tỉ lệ cân bằng tải. |
| Hệ thống có HA hoàn chỉnh không? | Chưa. Có nhiều replica ứng dụng nhưng control plane và từng hostname vẫn có điểm phụ thuộc riêng; việc pull image phụ thuộc Docker Hub. |
| Secret Kubernetes có phải mã hóa hoàn toàn? | Secret tránh đặt giá trị trực tiếp trong manifest, nhưng vẫn cần kiểm soát RBAC, etcd và quyền truy cập; không đưa secret lên Git. |
| Nếu D1 hoặc kết nối Internet lỗi? | `/readyz` phụ thuộc D1 và có thể báo lỗi; Pod không xử lý request bình thường đến khi kết nối được phục hồi. |
| Nếu tắt VM Azure có còn phí? | Có thể còn phí ổ đĩa và IP; dừng trong OS cũng không đồng nghĩa deallocate. Kiểm tra trạng thái VM và Billing. |

## 7. Sau demo

Đưa backend về 2 replica và image `docker.io/quanq026/nhip-k8s-backend:v1`; xác nhận ba node `Ready`, mỗi Deployment `2/2`, dữ liệu D1 còn nguyên và website truy cập được. Lưu ảnh minh chứng, không chụp token, kubeconfig hoặc thông tin đăng nhập.
