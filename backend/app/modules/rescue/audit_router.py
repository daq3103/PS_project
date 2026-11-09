from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_platform_manager
from app.models.rescue import (
    RescueAnimal,
    RescueAudit,
    RescueFund,
    RescueLedger,
    RescueReport,
    RescueSupply,
)
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin/rescue", tags=["rescue-audit"])
LABELS = {
    "animal": "Hồ sơ bé",
    "episode": "Đợt chăm sóc",
    "transfer": "Chuyển nơi chăm sóc",
    "responsibility": "Bàn giao trách nhiệm",
    "care": "Chăm sóc",
    "report": "Tin báo",
    "application": "Hồ sơ nhận nuôi",
    "appointment": "Lịch hẹn",
    "partner": "Người đồng hành",
    "shift": "Ca trực",
    "care_schedule": "Lịch chăm sóc",
    "supply": "Hiện vật",
    "pledge": "Hẹn tặng hiện vật",
    "campaign": "Chiến dịch",
    "donation": "Đối soát đóng góp",
    "refund": "Hoàn tiền",
    "expense": "Chi quỹ",
    "ledger": "Sổ quỹ",
    "fund": "Báo cáo quỹ",
    "asset": "Ảnh / bản chụp",
    "consent": "Lựa chọn quyền riêng tư",
    "visit_slot": "Khung giờ gặp",
    "foster": "Nhật ký nhà tạm",
    "public_update": "Mốc hành trình công khai",
}


@router.get("/audit")
async def audit(
    resource_id: UUID | None = None,
    offset: int = Query(0, ge=0),
    user: User = Depends(require_platform_manager),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(RescueAudit, User.full_name)
        .outerjoin(User, User.id == RescueAudit.actor_id)
        .order_by(RescueAudit.created_at.desc(), RescueAudit.id)
        .offset(offset)
        .limit(100)
    )
    if resource_id:
        stmt = stmt.where(RescueAudit.resource_id == resource_id)
    records = (await db.execute(stmt)).all()
    ids = [r.resource_id for r, _ in records]
    names = {}
    for model, column in [
        (RescueAnimal, RescueAnimal.code),
        (RescueReport, RescueReport.code),
        (RescueFund, RescueFund.title),
        (RescueLedger, RescueLedger.reference),
        (RescueSupply, RescueSupply.reference),
    ]:
        names.update(
            dict((await db.execute(select(model.id, column).where(model.id.in_(ids)))).all())
        )
    verbs = {
        "create": "tạo mới",
        "edit": "cập nhật",
        "publish": "duyệt công bố",
        "unpublish": "gỡ công bố",
        "open": "mở tiếp nhận",
        "pause": "tạm dừng",
        "hold": "giữ để xác minh",
        "release_hold": "kết thúc xác minh",
        "close": "kết thúc",
        "handover": "bàn giao",
        "verify": "xác minh liên hệ",
        "agreement": "ghi điều kiện bàn giao",
        "reschedule": "đổi lịch",
        "confirm": "xác nhận",
        "cancel": "hủy",
        "complete": "hoàn tất",
        "approve": "duyệt",
        "reject": "không duyệt",
        "withdraw": "rút đăng ký",
        "upload": "tải lên",
        "received": "xác nhận thực nhận",
        "settled": "đối soát thực nhận",
        "pay": "ghi đã trả",
        "confirm_paid": "ghi đã hoàn",
        "change": "cập nhật lựa chọn",
        "use": "sử dụng",
        "quarantine": "cách ly",
        "release": "kiểm tra đạt",
        "dispose": "loại bỏ",
        "stop": "dừng lịch",
        "reconcile": "đối soát",
        "resolve": "xử lý ngoại lệ",
        "decision": "ghi quyết định",
    }
    result = []
    for row, actor in records:
        key = next(
            (k for k in sorted(LABELS, key=len, reverse=True) if row.action.startswith(k)), None
        )
        result.append(
            {
                "id": row.id,
                "created_at": row.created_at,
                "actor_name": actor or "Hệ thống / người dùng xác nhận lựa chọn",
                "action_label": LABELS.get(key, "Thao tác vận hành")
                + " · "
                + next(
                    (
                        verbs[v]
                        for v in sorted(verbs, key=len, reverse=True)
                        if row.action.endswith(v)
                    ),
                    "ghi nhận",
                ),
                "resource_label": names.get(row.resource_id, "Hồ sơ liên quan"),
                "reason": str(row.details.get("reason") or row.details.get("note") or ""),
                "amount": row.details.get("amount"),
                "quantity": row.details.get("quantity"),
                "version": row.details.get("version"),
            }
        )
    return result
