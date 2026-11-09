"""Physical stock reconciliation shared by the dashboard and detailed report."""

# Legacy order_release rows only released reservations; they did not receive stock.
LOT_BALANCES_SQL = """
    SELECT il.id AS lot_id, il.lot_no, il.variant_id, il.qty_on_hand,
           COALESCE(SUM(sm.qty_delta), 0)::int AS movements_sum
    FROM inventory_lots il
    LEFT JOIN stock_movements sm ON sm.lot_id = il.id AND sm.reason <> 'order_release'
    GROUP BY il.id, il.lot_no, il.variant_id, il.qty_on_hand
"""
