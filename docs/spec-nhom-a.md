# Spec Nhóm A — đóng băng (Tuần 1)

> Chốt theo thiết kế v1.3 + plan triển khai. Không còn trạng thái TBD trước khi code nghiệp vụ Tuần 2+.

## 1. JWT Access / Refresh + rotation + revoke

| Mục | Quyết định |
|---|---|
| Access token | JWT HS256, TTL **15 phút**, claim `sub` + `role` + `type=access` |
| Refresh token | Opaque `secrets.token_urlsafe(48)`, TTL **30 ngày** |
| Lưu refresh | Chỉ lưu **SHA-256 hash** trong `refresh_tokens.token_hash` |
| Cookie | `httpOnly` + `Secure` + `SameSite=Lax` (không localStorage) |
| Rotation | Mỗi lần refresh: revoke token cũ (`revoked_at=now`), phát hành token mới với `parent_token_id` trỏ cha |
| Reuse detection | Dùng lại token đã revoke → **revoke toàn bộ chuỗi** của user (`revoked_at` mọi row còn active) |

Implement đầy đủ: Tuần 2 (khách) / Tuần 5 (staff + 2FA).

## 2. CSRF double-submit

- Cookie `csrf_token` (readable bởi JS) + header `X-CSRF-Token` phải khớp.
- Middleware FastAPI áp dụng cho mọi `POST/PUT/PATCH/DELETE` từ trình duyệt.
- Bỏ qua cho webhook (HMAC riêng) và gọi nội bộ server-to-server có secret.

## 3. Pattern commit → enqueue → gọi provider idempotent (mục 4.4)

1. **Commit DB trước** (đơn / payment pending / fulfillment sẵn sàng).
2. **Enqueue ARQ** chỉ sau commit (`enqueue_after_commit` / BackgroundTasks sau `session.commit()`).
3. Job gọi provider kèm idempotency; trước khi tạo mới kiểm tra `external_transaction_id` / `tracking_code`.
4. Cron re-enqueue bản ghi `pending` > 2 phút nếu Redis lỗi lúc enqueue.
5. **Tuyệt đối không** gọi HTTP provider bên trong DB transaction.

Helper: `app/worker/enqueue.py` (`enqueue_after_commit`, `enqueue_revalidate_product`).

## 4. FEFO locking: `FOR UPDATE SKIP LOCKED` + retry 409

**Quyết định mặc định:** giữ `FOR UPDATE SKIP LOCKED` như code mẫu mục 4.2.

| Trade-off | Hệ quả |
|---|---|
| Ưu | Không deadlock; checkout không bị block dài |
| Nhược | FEFO không tuyệt đối dưới tải đồng thời; có thể 409 “thiếu tồn” giả |

**Xử lý client:** khi nhận HTTP 409 tồn kho → **retry 1 lần sau ~200ms**.

Nếu sau này bán thuốc thú y bắt buộc FEFO tuyệt đối → đổi sang `FOR UPDATE` thuần (đã sort `variant_id` chống deadlock).

## 5. Session `get_db`

```text
yield session → commit nếu OK
exception → rollback → raise
finally → close
```

File: `app/core/database.py`. Dùng chung mọi module.

## 6. Mã hóa bí mật at-rest

- Env `SECRET_ENCRYPTION_KEY` = 32 bytes hex (64 ký tự).
- Helper AES-256-GCM: `encrypt_secret` / `decrypt_secret` (`app/core/encryption.py`).
- Áp dụng cho `carrier_accounts.api_token_encrypted`, `webhook_secret_encrypted`, `users.totp_secret_encrypted`.
- **Không commit** file `.env`.

## Checklist đóng băng

- [x] JWT lifetimes + rotation + revoke chain
- [x] CSRF double-submit
- [x] Commit → enqueue → idempotent provider
- [x] SKIP LOCKED + retry 409 (mặc định)
- [x] `get_db` commit/rollback
- [x] Envelope encryption key + helpers
