# Sơ đồ database PetHome

Nguồn: backend/app/models/*.py, migration đến 0008, docker-compose.yml. Schema theo mã nguồn; chưa xác nhận database đang chạy do không truy cập được Docker.

35 bảng nghiệp vụ PostgreSQL và 2 Redis (không tính alembic_version).

## Hệ thống lưu trữ

```mermaid
flowchart LR
 API[FastAPI] --> PG[(PostgreSQL 16 / pgvector)]
 API --> C[(redis-cache / LRU)]
 API --> Q[(redis-queue / AOF)]
 W[ARQ worker] --> PG
 W --> Q
```

## Tài khoản: 5 bảng

```mermaid
erDiagram
 users ||--o{ customer_addresses : user_id
 users ||--o{ refresh_tokens : user_id
 refresh_tokens |o--o{ refresh_tokens : parent_token_id
 users ||--o{ password_reset_tokens : user_id
 users ||--o{ staff_role_changes : actor_user_id
 users ||--o{ staff_role_changes : target_user_id
```

## Sản phẩm: 5 bảng

```mermaid
erDiagram
 categories |o--o{ categories : parent_id
 categories ||--o{ products : category_id
 products ||--o{ product_variants : product_id
 products ||--o{ product_images : product_id
 product_variants |o--o{ product_images : variant_id
 products ||--o{ reviews : product_id
 order_items ||--o| reviews : order_item_id
 users |o--o{ reviews : user_id
 users |o--o{ reviews : approved_by
```

## Bán hàng: 7 bảng

```mermaid
erDiagram
 users |o--o| carts : user_id
 carts ||--o{ cart_items : cart_id
 product_variants ||--o{ cart_items : variant_id
 users |o--o{ orders : user_id
 promotions |o--o{ orders : promotion_id
 orders ||--o{ order_items : order_id
 products ||--o{ order_items : product_id
 product_variants ||--o{ order_items : variant_id
 orders ||--o{ order_status_history : order_id
 users |o--o{ order_status_history : actor_user_id
 promotions ||--o{ promotion_usages : promotion_id
 orders ||--o| promotion_usages : order_id
 users |o--o{ promotion_usages : user_id
```

## Kho: 4 bảng

```mermaid
erDiagram
 product_variants ||--o{ inventory_lots : variant_id
 inventory_lots ||--o{ stock_movements : lot_id
 users |o--o{ stock_movements : actor_user_id
 order_items ||--o{ lot_allocations : order_item_id
 inventory_lots ||--o{ lot_allocations : lot_id
 order_items ||--o{ returned_stock : order_item_id
 inventory_lots ||--o{ returned_stock : lot_id
 users |o--o{ returned_stock : inspected_by
```

## Thanh toán và giao hàng: 4 bảng

```mermaid
erDiagram
 orders ||--o{ payments : order_id
 orders ||--o{ fulfillments : order_id
 carrier_accounts {
  uuid id PK
  string carrier_code UK
 }
 webhook_events {
  uuid id PK
  string provider
  string external_event_id
 }
```

carrier_accounts và fulfillments cùng có carrier_code nhưng không khai báo FK giữa chúng. webhook_events không có FK.

## Cộng đồng và cứu hộ: 9 bảng

```mermaid
erDiagram
 users ||--o{ community_posts : author_user_id
 users |o--o{ community_posts : moderated_by
 users ||--o{ community_uploads : uploader_user_id
 community_posts ||--o{ community_post_images : post_id
 community_uploads ||--o{ community_post_images : upload_id
 community_posts ||--o{ community_reports : post_id
 users ||--o{ community_reports : reporter_user_id
 users |o--o{ community_reports : handled_by
 community_posts ||--o{ adoption_requests : post_id
 users ||--o{ adoption_requests : user_id
 users |o--o{ adoption_requests : handled_by
 community_posts |o--o{ community_audit_logs : post_id
 users |o--o{ community_audit_logs : actor_user_id
 adoption_requests |o--o{ community_audit_logs : request_id
 users ||--o{ community_receipts : user_id
 users ||--o{ community_notifications : user_id
 community_job_outbox {
  uuid id PK
  string job_type
  jsonb payload
  string status
 }
```

community_job_outbox không có FK. community_receipts.resource_id là tham chiếu logic.

## Analytics: 1 bảng

```mermaid
erDiagram
 analytics_events {
  uuid event_id PK
  string kind PK
  datetime created_at
  string visitor_hash
  string session_hash
  string page
  string section
  string source
  string device
  float value
 }
```

Khóa chính ghép (event_id, kind); không có FK.

## Chú thích

- Đường nối là FK khai báo trong model. || = đúng một, o| hoặc |o = không hoặc một, o{ = không hoặc nhiều.
- Bảng ngoài nhóm được lặp lại để thấy quan hệ liên nhóm.
- Tập trung vào bảng và quan hệ, không liệt kê đầy đủ cột, CHECK, index và unique có điều kiện.
- stock_movements.ref_id/ref_type và tham chiếu trong JSON không phải FK.
