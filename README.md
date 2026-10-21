# Petshop System (v1.3)

Monorepo FastAPI + Next.js 15 theo thiết kế `thiet-ke-he-thong-v1.3.docx`.

## Tuần 1 đã có

- Docker Compose: Postgres 16 (pgvector), redis-cache, redis-queue, FastAPI, ARQ worker, Next.js, Nginx
- `TZ=Asia/Ho_Chi_Minh` toàn stack
- Alembic migration schema v1.3 (CHECK, index, `stock_movements`, `refresh_tokens`, `uq_lot_allocation`, `attempt_no`, …)
- CRUD Categories / Products / Variants + ARQ → `revalidateTag`
- `get_db` commit/rollback; AES-256-GCM helpers; spec Nhóm A tại `docs/spec-nhom-a.md`

## Chạy local

```bash
cp .env.example .env
docker compose up --build
```

- Storefront: http://localhost:3000  
- API docs: http://localhost:8000/docs  
- Qua Nginx: http://localhost  

Migration chạy tự động khi `fastapi-api` / worker start (`alembic upgrade head`).

### Sinh TypeScript từ OpenAPI

```bash
cd frontend && npm run generate:api
```

### Smoke: tạo SP + đổi giá → revalidate

```bash
# 1) Tạo category
curl -s -X POST http://localhost:8000/api/v1/categories \
  -H 'Content-Type: application/json' \
  -d '{"name":"Thức ăn hạt","slug":"thuc-an-hat"}'

# 2) Tạo product (thay CATEGORY_ID)
curl -s -X POST http://localhost:8000/api/v1/products \
  -H 'Content-Type: application/json' \
  -d '{
    "category_id":"CATEGORY_ID",
    "name":"Hạt gà 1.5kg",
    "slug":"hat-ga-15kg",
    "pet_type":"dog",
    "status":"active",
    "variants":[{
      "sku":"DOG-FOOD-15",
      "title":"Túi 1.5kg",
      "price":150000,
      "weight_grams":1500,
      "cached_available_qty":20
    }]
  }'

# 3) Đổi giá variant (thay VARIANT_ID) → worker gọi revalidate
curl -s -X PATCH http://localhost:8000/api/v1/variants/VARIANT_ID \
  -H 'Content-Type: application/json' \
  -d '{"price":165000}'
```

## Bỏ qua (làm sau)

Pháp lý / domain / tài khoản GHN–payOS–email DNS — không chặn build phần mềm Tuần 1.
