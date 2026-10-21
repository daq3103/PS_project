# Cloudflare Tunnel demo

Public Petshop local ra internet bằng **Cloudflare Tunnel** (`cloudflared`) thay vì ngrok.

## Ưu điểm so với ngrok

- Không cần authtoken cho quick tunnel.
- Không giới hạn số lượng request/tháng.
- URL demo dạng `https://<random>.trycloudflare.com`.

## Yêu cầu

- Stack chính đang chạy: `docker compose up -d` từ thư mục gốc repo.
- Network Docker `ps_project_default` đã tồn tại.

## Cách dùng

```powershell
cd cloudflare-tunnel-demo
.\run.ps1
```

Xem URL công khai:

```powershell
docker compose logs -f
```

Tìm dòng tương tự:

```text
https://<random-string>.trycloudflare.com
```

## Dừng / dọn dẹp

```powershell
.\stop.ps1
```

Hoặc xóa luôn folder `cloudflare-tunnel-demo/`.

## Muốn domain cố định?

Quick tunnel chỉ cho URL ngẫu nhiên. Nếu muốn domain riêng (ví dụ `demo.yourdomain.com`):

1. Thêm domain vào Cloudflare.
2. Tạo tunnel trong Cloudflare Zero Trust dashboard → copy **Tunnel token**.
3. Tạo file `.env` ở đây:
   ```env
   TUNNEL_TOKEN=your_tunnel_token
   TUNNEL_HOSTNAME=demo.yourdomain.com
   ```
4. Thay `command` trong `docker-compose.yml` thành:
   ```yaml
   command:
     - "tunnel"
     - "run"
     - "--token"
     - "${TUNNEL_TOKEN}"
   ```

## Lưu ý

- Tunnel này expose nginx (port 80) nên cả frontend và API đều public.
- Chỉ dùng cho demo, xóa container khi không cần.
