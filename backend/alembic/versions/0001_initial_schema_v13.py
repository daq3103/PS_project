"""Initial schema v1.3 — 23 tables + indexes (design: 20 bảng nghiệp vụ cốt lõi + phụ trợ).

Revision ID: 0001
Revises:
Create Date: 2026-10-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "unaccent"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    op.execute("""
    CREATE TABLE users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE,
        phone VARCHAR(20) UNIQUE,
        password_hash VARCHAR(255),
        totp_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        totp_secret_encrypted BYTEA,
        google_id VARCHAR(255) UNIQUE,
        full_name VARCHAR(150) NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'customer'
            CHECK (role IN ('customer', 'owner', 'warehouse_staff', 'cskh_staff')),
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        staff_note TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE customer_addresses (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        recipient_name VARCHAR(150) NOT NULL,
        recipient_phone VARCHAR(20) NOT NULL,
        province_id INT NOT NULL,
        province_name VARCHAR(100) NOT NULL,
        district_id INT NOT NULL,
        district_name VARCHAR(100) NOT NULL,
        ward_code VARCHAR(50) NOT NULL,
        ward_name VARCHAR(100) NOT NULL,
        street_address VARCHAR(255) NOT NULL,
        is_default BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE refresh_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(64) NOT NULL UNIQUE,
        parent_token_id UUID REFERENCES refresh_tokens(id),
        expires_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE categories (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        parent_id UUID REFERENCES categories(id) ON DELETE SET NULL,
        name VARCHAR(150) NOT NULL,
        slug VARCHAR(150) UNIQUE NOT NULL,
        sort_order INT NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE products (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        category_id UUID NOT NULL REFERENCES categories(id),
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) UNIQUE NOT NULL,
        brand VARCHAR(100),
        pet_type VARCHAR(20) NOT NULL CHECK (pet_type IN ('dog', 'cat', 'both')),
        life_stage VARCHAR(30) CHECK (life_stage IN ('baby', 'adult', 'senior', 'all')),
        has_expiry BOOLEAN NOT NULL DEFAULT FALSE,
        short_description VARCHAR(500),
        description TEXT,
        attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
        seo_title VARCHAR(255),
        seo_description VARCHAR(500),
        rating_avg NUMERIC(3,2) NOT NULL DEFAULT 0.00,
        rating_count INT NOT NULL DEFAULT 0,
        total_sold INT NOT NULL DEFAULT 0,
        status VARCHAR(20) NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'active', 'hidden')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE product_variants (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        sku VARCHAR(100) UNIQUE NOT NULL,
        title VARCHAR(150) NOT NULL,
        options JSONB NOT NULL DEFAULT '{}'::jsonb,
        price BIGINT NOT NULL CHECK (price >= 0),
        compare_at_price BIGINT CHECK (compare_at_price >= 0),
        weight_grams INT NOT NULL CHECK (weight_grams > 0),
        length_cm INT NOT NULL DEFAULT 10 CHECK (length_cm > 0),
        width_cm INT NOT NULL DEFAULT 10 CHECK (width_cm > 0),
        height_cm INT NOT NULL DEFAULT 10 CHECK (height_cm > 0),
        low_stock_threshold INT NOT NULL DEFAULT 5,
        cached_available_qty INT NOT NULL DEFAULT 0 CHECK (cached_available_qty >= 0),
        nearest_expiry_date DATE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE product_images (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        variant_id UUID REFERENCES product_variants(id) ON DELETE SET NULL,
        r2_url TEXT NOT NULL,
        alt_text VARCHAR(255),
        sort_order INT NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE inventory_lots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        variant_id UUID NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
        lot_no VARCHAR(100) NOT NULL,
        manufactured_date DATE,
        expiry_date DATE,
        unit_cost BIGINT NOT NULL CHECK (unit_cost >= 0),
        qty_initial INT NOT NULL CHECK (qty_initial > 0),
        qty_on_hand INT NOT NULL DEFAULT 0 CHECK (qty_on_hand >= 0),
        qty_reserved INT NOT NULL DEFAULT 0 CHECK (qty_reserved >= 0),
        status VARCHAR(20) NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'expired', 'locked', 'depleted')),
        note TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_lot_available_positive CHECK (qty_on_hand >= qty_reserved),
        UNIQUE (variant_id, lot_no)
    )
    """)

    op.execute("""
    CREATE TABLE stock_movements (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        lot_id UUID NOT NULL REFERENCES inventory_lots(id) ON DELETE RESTRICT,
        qty_delta INT NOT NULL CHECK (qty_delta <> 0),
        reason VARCHAR(30) NOT NULL
            CHECK (reason IN (
                'order_deduct', 'order_release', 'return_restock', 'return_writeoff',
                'lot_import', 'stocktake_adjust', 'damaged_adjust', 'manual_correct'
            )),
        ref_type VARCHAR(30),
        ref_id UUID,
        actor_user_id UUID REFERENCES users(id),
        note TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE carts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        guest_token VARCHAR(100) UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE cart_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
        variant_id UUID NOT NULL REFERENCES product_variants(id) ON DELETE CASCADE,
        qty INT NOT NULL CHECK (qty > 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (cart_id, variant_id)
    )
    """)

    op.execute("""
    CREATE TABLE promotions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        code VARCHAR(50) UNIQUE NOT NULL,
        description VARCHAR(255),
        discount_type VARCHAR(20) NOT NULL
            CHECK (discount_type IN ('percentage', 'fixed_amount', 'free_shipping')),
        discount_value BIGINT NOT NULL CHECK (discount_value > 0),
        max_discount_amount BIGINT,
        min_order_subtotal BIGINT NOT NULL DEFAULT 0,
        usage_limit INT,
        usage_limit_per_user INT DEFAULT 1,
        used_count INT NOT NULL DEFAULT 0,
        starts_at TIMESTAMPTZ NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_promo_used_within_limit
            CHECK (usage_limit IS NULL OR used_count <= usage_limit)
    )
    """)

    op.execute("""
    CREATE TABLE orders (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_code VARCHAR(12) UNIQUE NOT NULL,
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        idempotency_key VARCHAR(100) UNIQUE NOT NULL,
        customer_name VARCHAR(150) NOT NULL,
        customer_phone VARCHAR(20) NOT NULL,
        customer_email VARCHAR(255),
        shipping_address JSONB NOT NULL,
        status VARCHAR(25) NOT NULL DEFAULT 'pending'
            CHECK (status IN (
                'pending', 'confirmed', 'packed', 'shipped',
                'delivered', 'cancelled', 'returned'
            )),
        payment_method VARCHAR(20) NOT NULL
            CHECK (payment_method IN ('cod', 'vietqr', 'vnpay', 'momo', 'zalopay')),
        payment_status VARCHAR(25) NOT NULL DEFAULT 'unpaid'
            CHECK (payment_status IN (
                'unpaid', 'paid', 'underpaid', 'overpaid', 'refund_pending', 'refunded'
            )),
        subtotal_amount BIGINT NOT NULL CHECK (subtotal_amount >= 0),
        discount_amount BIGINT NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
        shipping_fee BIGINT NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
        shipping_discount BIGINT NOT NULL DEFAULT 0 CHECK (shipping_discount >= 0),
        total_amount BIGINT NOT NULL CHECK (total_amount >= 0),
        promotion_id UUID REFERENCES promotions(id),
        coupon_code_snapshot VARCHAR(50),
        reservation_expires_at TIMESTAMPTZ,
        customer_note TEXT,
        cancel_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE order_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id UUID NOT NULL REFERENCES products(id),
        variant_id UUID NOT NULL REFERENCES product_variants(id),
        product_name_snapshot VARCHAR(255) NOT NULL,
        variant_title_snapshot VARCHAR(150) NOT NULL,
        sku_snapshot VARCHAR(100) NOT NULL,
        weight_grams_snapshot INT NOT NULL,
        qty INT NOT NULL CHECK (qty > 0),
        unit_price BIGINT NOT NULL CHECK (unit_price >= 0),
        line_total BIGINT NOT NULL CHECK (line_total >= 0)
    )
    """)

    op.execute("""
    CREATE TABLE lot_allocations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_item_id UUID NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
        lot_id UUID NOT NULL REFERENCES inventory_lots(id),
        qty INT NOT NULL CHECK (qty > 0),
        unit_cost_snapshot BIGINT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'reserved'
            CHECK (status IN ('reserved', 'deducted', 'released', 'returned')),
        allocated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_lot_allocation UNIQUE (order_item_id, lot_id)
    )
    """)

    op.execute("""
    CREATE TABLE order_status_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        from_status VARCHAR(25),
        to_status VARCHAR(25) NOT NULL,
        actor_user_id UUID REFERENCES users(id),
        actor_type VARCHAR(20) NOT NULL
            CHECK (actor_type IN ('customer', 'staff', 'system_cron', 'webhook')),
        note TEXT,
        metadata JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE promotion_usages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        promotion_id UUID NOT NULL REFERENCES promotions(id),
        order_id UUID UNIQUE NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        user_id UUID REFERENCES users(id),
        customer_phone VARCHAR(20) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'reserved'
            CHECK (status IN ('reserved', 'consumed', 'released')),
        used_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE reviews (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        order_item_id UUID UNIQUE NOT NULL REFERENCES order_items(id),
        user_id UUID REFERENCES users(id),
        reviewer_name VARCHAR(150) NOT NULL,
        rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
        content TEXT,
        image_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
        is_approved BOOLEAN NOT NULL DEFAULT FALSE,
        approved_by UUID REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE returned_stock (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_item_id UUID NOT NULL REFERENCES order_items(id),
        lot_id UUID NOT NULL REFERENCES inventory_lots(id),
        qty INT NOT NULL CHECK (qty > 0),
        status VARCHAR(30) NOT NULL DEFAULT 'pending_inspection'
            CHECK (status IN (
                'pending_inspection', 'restocked_to_lot', 'write_off_damaged'
            )),
        inspected_by UUID REFERENCES users(id),
        inspection_note TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        inspected_at TIMESTAMPTZ
    )
    """)

    op.execute("""
    CREATE TABLE payments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        provider VARCHAR(30) NOT NULL,
        transaction_type VARCHAR(20) NOT NULL
            CHECK (transaction_type IN ('charge', 'refund')),
        idempotency_key VARCHAR(100) UNIQUE NOT NULL,
        external_transaction_id VARCHAR(150),
        expected_amount BIGINT NOT NULL,
        actual_amount BIGINT DEFAULT 0,
        status VARCHAR(25) NOT NULL DEFAULT 'pending'
            CHECK (status IN (
                'pending', 'succeeded', 'underpaid', 'overpaid', 'failed'
            )),
        qr_code_url TEXT,
        raw_response JSONB DEFAULT '{}'::jsonb,
        paid_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE carrier_accounts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        carrier_code VARCHAR(30) UNIQUE NOT NULL,
        shop_id VARCHAR(100),
        api_token_encrypted BYTEA NOT NULL,
        webhook_secret_encrypted BYTEA,
        pickup_address JSONB NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    op.execute("""
    CREATE TABLE fulfillments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        carrier_code VARCHAR(30) NOT NULL,
        tracking_code VARCHAR(100) UNIQUE,
        cod_amount BIGINT NOT NULL DEFAULT 0,
        cod_reconciled BOOLEAN NOT NULL DEFAULT FALSE,
        cod_reconciled_at TIMESTAMPTZ,
        total_weight_grams INT NOT NULL CHECK (total_weight_grams > 0),
        package_count INT NOT NULL DEFAULT 1,
        shipping_fee_charged_by_carrier BIGINT,
        carrier_status VARCHAR(50),
        internal_status VARCHAR(30) NOT NULL DEFAULT 'ready_to_pick'
            CHECK (internal_status IN (
                'ready_to_pick', 'picking', 'delivering', 'delivered',
                'delivery_failed', 'returning', 'returned', 'cancelled'
            )),
        label_print_url TEXT,
        attempt_no INT NOT NULL DEFAULT 1 CHECK (attempt_no > 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (order_id, carrier_code, attempt_no)
    )
    """)

    op.execute("""
    CREATE TABLE webhook_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        provider VARCHAR(50) NOT NULL,
        external_event_id VARCHAR(150) NOT NULL,
        payload JSONB NOT NULL,
        process_status VARCHAR(20) NOT NULL DEFAULT 'processed'
            CHECK (process_status IN ('processed', 'ignored', 'failed')),
        error_message TEXT,
        received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (provider, external_event_id)
    )
    """)

    # Indexes
    op.execute(
        "CREATE INDEX idx_products_filter ON products(category_id, pet_type, status) "
        "WHERE status = 'active'"
    )
    op.execute("CREATE INDEX idx_products_attributes ON products USING GIN (attributes)")
    op.execute(
        "CREATE INDEX idx_variants_product ON product_variants(product_id) WHERE is_active = TRUE"
    )
    op.execute(
        "CREATE INDEX idx_lots_fefo_lookup ON inventory_lots("
        "variant_id, expiry_date ASC NULLS LAST, created_at ASC) "
        "WHERE status = 'active' AND (qty_on_hand > qty_reserved)"
    )
    op.execute(
        "CREATE INDEX idx_lots_expiry_warning ON inventory_lots(expiry_date) "
        "WHERE status = 'active' AND expiry_date IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_orders_expired_reservation ON orders(reservation_expires_at) "
        "WHERE status = 'pending' AND payment_status = 'unpaid'"
    )
    op.execute("CREATE INDEX idx_orders_tracking ON orders(order_code, customer_phone)")
    op.execute("CREATE INDEX idx_orders_user_history ON orders(user_id, created_at DESC)")
    op.execute(
        "CREATE INDEX idx_fulfillments_cod_unreconciled ON fulfillments("
        "internal_status, cod_reconciled) "
        "WHERE cod_amount > 0 AND cod_reconciled = FALSE"
    )
    op.execute(
        "CREATE INDEX idx_stock_movements_lot ON stock_movements(lot_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_refresh_tokens_active ON refresh_tokens(user_id) "
        "WHERE revoked_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_promotion_usages_limit ON promotion_usages("
        "promotion_id, customer_phone) "
        "WHERE status IN ('reserved', 'consumed')"
    )


def downgrade() -> None:
    tables = [
        "webhook_events",
        "fulfillments",
        "carrier_accounts",
        "payments",
        "returned_stock",
        "reviews",
        "promotion_usages",
        "order_status_history",
        "lot_allocations",
        "order_items",
        "orders",
        "promotions",
        "cart_items",
        "carts",
        "stock_movements",
        "inventory_lots",
        "product_images",
        "product_variants",
        "products",
        "categories",
        "refresh_tokens",
        "customer_addresses",
        "users",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
