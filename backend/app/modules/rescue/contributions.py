"""Rescue transfer instructions and reconciliation; no reuse of Shop payment credentials."""

import hashlib
import hmac
import json
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, has_staff_permission
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.models.fulfillment import WebhookEvent
from app.models.rescue import RescueFund, RescueLedger
from app.models.rescue_workflow import (
    RescueCampaign,
    RescueDonationEvent,
    RescueDonationIntent,
    RescueRefund,
)
from app.models.user import User
from app.modules.rescue import service as svc
from app.modules.rescue import workflow_schemas as s
from app.modules.rescue import workflow_service as ws
from app.modules.rescue.router import finance, mutate
from app.modules.rescue.schemas import LedgerIn

router = APIRouter(prefix="/api/v1", tags=["rescue-contributions"])


def enabled():
    settings = get_settings()
    return bool(
        settings.rescue_donations_enabled
        and settings.rescue_fund_policy_confirmed
        and all(
            (
                settings.rescue_recipient_name,
                settings.rescue_bank_name,
                settings.rescue_bank_account,
                settings.rescue_merchant_id,
            )
        )
    )


async def campaign_totals(db, campaign):
    fund = await db.get(RescueFund, campaign.fund_id)
    balance = await svc.balances(db, fund.id)
    return {
        "id": campaign.id,
        "animal_id": campaign.animal_id,
        "title": fund.title,
        "purpose": fund.purpose,
        "surplus_policy": fund.surplus_policy,
        "target": campaign.target,
        "opens_at": campaign.opens_at,
        "closes_at": campaign.closes_at,
        "status": campaign.status,
        "confirmed": balance["confirmed"],
        "accepting": enabled()
        and campaign.status == "open"
        and campaign.opens_at <= svc.now() < campaign.closes_at
        and balance["confirmed"] < campaign.target,
    }


@router.get("/rescue/campaigns")
async def campaigns(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(RescueCampaign)
            .where(RescueCampaign.status != "draft")
            .order_by(RescueCampaign.created_at.desc())
            .limit(100)
        )
    ).all()
    return {"enabled": enabled(), "campaigns": [await campaign_totals(db, c) for c in rows]}


@router.get("/admin/rescue/contributions")
async def administration(user: User = Depends(finance), db: AsyncSession = Depends(get_db)):
    result = {"enabled": enabled()}
    for name, model in [
        ("campaigns", RescueCampaign),
        ("intents", RescueDonationIntent),
        ("events", RescueDonationEvent),
        ("refunds", RescueRefund),
    ]:
        result[name] = [
            svc.row_dict(r)
            for r in (
                await db.scalars(select(model).order_by(model.created_at.desc()).limit(200))
            ).all()
        ]
    return result


@router.post("/admin/rescue/campaigns", status_code=201)
async def create_campaign(
    body: s.CampaignIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        fund = await db.scalar(
            select(RescueFund).where(RescueFund.id == body.fund_id).with_for_update()
        )
        if not fund or body.closes_at <= body.opens_at:
            svc.fail("Cần quỹ và khoảng thời gian hợp lệ.", status=422)
        if body.animal_id:
            from app.models.rescue import RescueAnimal

            if not await db.get(RescueAnimal, body.animal_id):
                svc.fail("Không tìm thấy hồ sơ bé.", status=404)
        if await db.scalar(select(RescueCampaign.id).where(RescueCampaign.fund_id == fund.id)):
            svc.fail("Quỹ đã có chiến dịch; tạo quỹ mới nếu mục đích khác.")
        row = RescueCampaign(**body.model_dump())
        db.add(row)
        await db.flush()
        svc.audit(db, user, row.id, "campaign_create")
        return svc.row_dict(row)

    return await mutate(db, user, "campaign", key, body, create)


@router.post("/admin/rescue/campaigns/{ident}/action")
async def campaign_action(
    ident: UUID,
    body: s.CampaignAction,
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(
        select(RescueCampaign).where(RescueCampaign.id == ident).with_for_update()
    )
    if not row:
        svc.fail("Không tìm thấy chiến dịch.", status=404)
    if row.version != body.version or row.status == "closed":
        svc.fail("Chiến dịch đã thay đổi hoặc kết thúc.", "VERSION_CONFLICT")
    if body.action == "open":
        if not has_staff_permission(user, "platform_manage"):
            svc.fail("Chủ trạm duyệt mở chiến dịch.", "PERMISSION_DENIED", 403)
        if not enabled() or row.closes_at <= svc.now():
            svc.fail(
                "Chưa đủ cấu hình nhận, đối soát và chính sách tiền đóng góp.",
                "DONATIONS_NOT_ENABLED",
                503,
            )
    row.status = {"open": "open", "pause": "paused", "close": "closed"}[body.action]
    row.version += 1
    svc.audit(db, user, row.id, "campaign_" + body.action, reason=body.reason)
    return svc.row_dict(row)


async def ensure_enabled():
    if not enabled():
        svc.fail("Trạm chưa mở nhận tiền trực tuyến.", "DONATIONS_NOT_ENABLED", 503)


@router.post("/rescue/donation-intents", status_code=201, dependencies=[Depends(ensure_enabled)])
async def donation(
    body: s.DonationIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not enabled():
        svc.fail(
            "Trạm chưa mở nhận tiền trực tuyến. Bạn có thể liên hệ để trao đổi cách đồng hành.",
            "DONATIONS_NOT_ENABLED",
            503,
        )

    async def create():
        c = await db.scalar(
            select(RescueCampaign).where(RescueCampaign.id == body.campaign_id).with_for_update()
        )
        if not c or not (await campaign_totals(db, c))["accepting"]:
            svc.fail("Chiến dịch đã dừng nhận khoản mới.", "CAMPAIGN_CLOSED")
        fund = await db.get(RescueFund, c.fund_id)
        settings = get_settings()
        row = RescueDonationIntent(
            campaign_id=c.id,
            user_id=user.id,
            code=svc.code("UH-"),
            amount=body.amount,
            anonymous=body.anonymous,
            expires_at=svc.now() + timedelta(hours=24),
            purpose_snapshot={
                "title": fund.title,
                "purpose": fund.purpose,
                "surplus_policy": fund.surplus_policy,
                "surplus_action": c.surplus_action,
                "merchant": settings.rescue_merchant_id,
                "bank": settings.rescue_bank_name,
                "account": settings.rescue_bank_account,
                "recipient": settings.rescue_recipient_name,
            },
        )
        db.add(row)
        await db.flush()
        await ws.consent(db, user.id, row.id, "contribution", True)
        return {
            **svc.row_dict(row),
            "instructions": "Chuyển đúng số tiền và ghi mã trong nội dung. Khoản đóng góp chỉ được xác nhận khi trạm đối soát được tiền thực nhận.",
        }

    return await mutate(db, user, "donation", key, body, create)


@router.get("/rescue/me/donations")
async def my_donations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [
        svc.row_dict(r)
        for r in (
            await db.scalars(
                select(RescueDonationIntent)
                .where(RescueDonationIntent.user_id == user.id)
                .order_by(RescueDonationIntent.created_at.desc())
                .limit(100)
            )
        ).all()
    ]


async def reconcile(db, user, body, *, resolve_id=None):
    digest = hashlib.sha256(
        json.dumps(
            body.model_dump(exclude={"note"}), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    await ws.lock(db, "donation-event:" + body.reference)
    previous = await db.scalar(
        select(RescueDonationEvent).where(RescueDonationEvent.reference == body.reference)
    )
    resolving = bool(
        previous
        and previous.id == resolve_id
        and previous.status
        in ("unmatched", "amount_mismatch", "merchant_mismatch", "other_ledger_conflict")
    )
    if previous and not resolving:
        if previous.digest != digest:
            svc.fail(
                "Mã giao dịch đã có nội dung khác; cần người đối soát kiểm tra.",
                "PAYMENT_RECONCILIATION_REQUIRED",
            )
        return {"id": str(previous.id), "status": previous.status}
    intent = await db.scalar(
        select(RescueDonationIntent).where(RescueDonationIntent.code == body.code).with_for_update()
    )
    status = "unmatched"
    if intent:
        campaign = await db.get(RescueCampaign, intent.campaign_id)
        # The snapshot binds old transfers even after new contributions are paused.
        if body.merchant != intent.purpose_snapshot["merchant"]:
            status = "merchant_mismatch"
        elif body.amount != intent.amount and not resolving:
            status = "amount_mismatch"
        elif intent.ledger_id and not resolving:
            status = "duplicate_payment"
        else:
            await db.scalar(
                select(RescueFund).where(RescueFund.id == campaign.fund_id).with_for_update()
            )
            # Exactly the same global receipt lock used by Shop and the manual rescue ledger.
            from sqlalchemy import text

            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": "external-receipt:" + body.reference},
            )
            shop = await db.scalar(
                select(WebhookEvent.id).where(WebhookEvent.external_event_id == body.reference)
            )
            existing = await db.scalar(
                select(RescueLedger).where(RescueLedger.reference == body.reference)
            )
            if shop or (
                existing
                and (
                    existing.fund_id != campaign.fund_id
                    or existing.kind != "received"
                    or existing.amount != body.amount
                )
            ):
                status = "other_ledger_conflict"
            else:
                await db.scalar(
                    select(RescueFund).where(RescueFund.id == campaign.fund_id).with_for_update()
                )
                received = existing
                if not received:
                    received = RescueLedger(
                        fund_id=campaign.fund_id,
                        actor_id=user.id,
                        kind="received",
                        amount=body.amount,
                        reference=body.reference,
                        note=body.note,
                        anonymous=intent.anonymous,
                    )
                    db.add(received)
                    await db.flush()
                settled = int(
                    await db.scalar(
                        select(func.coalesce(func.sum(RescueLedger.amount), 0)).where(
                            RescueLedger.reverses_id == received.id, RescueLedger.kind == "settled"
                        )
                    )
                )
                if settled < body.amount:
                    db.add(
                        RescueLedger(
                            fund_id=campaign.fund_id,
                            actor_id=user.id,
                            kind="settled",
                            amount=body.amount - settled,
                            reference=body.reference + ":settled",
                            reverses_id=received.id,
                            note="Đối soát tiền thực nhận của " + intent.code,
                            anonymous=True,
                        )
                    )
                previous_receipt = intent.ledger_id
                if not intent.ledger_id:
                    intent.ledger_id = received.id
                await db.flush()
                balance = await svc.balances(db, campaign.fund_id)
                late = (
                    bool(previous_receipt)
                    or body.amount != intent.amount
                    or campaign.status != "open"
                    or svc.now() >= campaign.closes_at
                    or svc.now() > intent.expires_at
                    or balance["confirmed"] > campaign.target
                )
                status = "surplus_review" if late else "matched"
                intent.status = "needs_review" if late else "confirmed"
                from app.modules.community.service import notify

                await notify(
                    db,
                    intent.user_id,
                    "Trạm đã đối soát khoản đóng góp của bạn."
                    + (
                        " Khoản đến sau hạn hoặc vượt mục tiêu đang được xử lý theo chính sách đã công bố."
                        if late
                        else ""
                    ),
                    "/account/rescue",
                    f"donation:{intent.id}:confirmed",
                )
    if resolving:
        if status not in ("matched", "surplus_review"):
            svc.fail(
                "Vẫn chưa đối chiếu được giao dịch. Giữ ngoại lệ để kiểm tra tiếp.",
                "PAYMENT_RECONCILIATION_REQUIRED",
            )
        svc.audit(
            db,
            user,
            previous.id,
            "donation_exception_resolve",
            old_status=previous.status,
            corrected_amount=body.amount,
            corrected_code=body.code,
            reason=body.note,
        )
        previous.status = status + "_resolved"
        previous.resolved_by = user.id
        previous.intent_id = intent.id
        return {"id": str(previous.id), "status": previous.status}
    event = RescueDonationEvent(
        reference=body.reference,
        intent_id=intent.id if intent else None,
        amount=body.amount,
        status=status,
        digest=digest,
        note=body.note,
        resolved_by=user.id,
    )
    db.add(event)
    await db.flush()
    svc.audit(db, user, event.id, "donation_reconcile", status=status)
    return {"id": str(event.id), "status": status}


@router.post("/admin/rescue/donations/reconcile")
async def manual_reconcile(
    body: s.DonationConfirm, user: User = Depends(finance), db: AsyncSession = Depends(get_db)
):
    return await reconcile(db, user, body)


@router.post("/webhooks/rescue/transfers")
async def transfer_callback(
    request: Request,
    signature: str = Header(default="", alias="X-Rescue-Signature"),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        key="rl:rescue-callback:" + client_ip(request), limit=100, window_seconds=60
    )
    raw = await request.body()
    secret = get_settings().rescue_webhook_secret
    if (
        len(raw) > 8000
        or len(secret) < 32
        or not hmac.compare_digest(
            hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), signature
        )
    ):
        svc.fail("Không xác minh được thông báo giao dịch.", "INVALID_SIGNATURE", 403)
    from pydantic import ValidationError

    try:
        body = s.DonationConfirm.model_validate_json(raw)
    except ValidationError:
        svc.fail("Thông báo giao dịch không hợp lệ.", status=422)
    owner = await db.scalar(
        select(User)
        .where(User.role == "owner", User.is_active.is_(True))
        .order_by(User.created_at)
        .limit(1)
    )
    if not owner:
        svc.fail("Cần người phụ trách đối soát.", status=503)
    return await reconcile(db, owner, body)


@router.post("/admin/rescue/refunds", status_code=201)
async def refund(
    body: s.RefundIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        entry = await db.get(RescueLedger, body.entry_id)
        if not entry or entry.kind != "received":
            svc.fail("Chọn khoản thu gốc cần hoàn.", status=422)
        row = RescueRefund(**body.model_dump(), requester_id=user.id)
        db.add(row)
        await db.flush()
        return svc.row_dict(row)

    return await mutate(db, user, "refund", key, body, create)


@router.post("/admin/rescue/refunds/{ident}/action")
async def refund_action(
    ident: UUID,
    body: s.RefundAction,
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    previous = await db.get(RescueRefund, ident)
    if not previous:
        svc.fail("Không tìm thấy đề nghị hoàn.", status=404)
    entry = await db.get(RescueLedger, previous.entry_id)
    await db.scalar(select(RescueFund).where(RescueFund.id == entry.fund_id).with_for_update())
    row = await db.scalar(
        select(RescueRefund)
        .where(RescueRefund.id == ident)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row.status == "paid" and body.action == "confirm_paid" and row.reference == body.reference:
        return svc.row_dict(row)
    if body.action == "reject":
        if row.status not in ("requested", "approved"):
            svc.fail("Đề nghị đã kết thúc.")
        row.status = "rejected"
    elif body.action == "approve":
        if row.requester_id == user.id or row.status != "requested":
            svc.fail("Cần người khác duyệt đề nghị hoàn đang chờ.", "PERMISSION_DENIED", 403)
        refunded = int(
            await db.scalar(
                select(func.coalesce(func.sum(RescueLedger.amount), 0)).where(
                    RescueLedger.kind == "refund", RescueLedger.reverses_id == entry.id
                )
            )
        )
        pending = int(
            await db.scalar(
                select(func.coalesce(func.sum(RescueRefund.amount), 0)).where(
                    RescueRefund.entry_id == entry.id, RescueRefund.status == "approved"
                )
            )
        )
        if (
            refunded + pending + row.amount > entry.amount
            or (await svc.balances(db, entry.fund_id))["available"] < row.amount
        ):
            svc.fail("Số hoàn vượt khoản gốc hoặc phần quỹ còn khả dụng.")
        row.approver_id, row.status = user.id, "approved"
    else:
        if row.status != "approved" or len(body.reference) < 6:
            svc.fail("Cần đề nghị được duyệt và chứng từ hoàn thực tế.", status=422)
        row.status = "paid"  # Release this reservation inside the same transaction before debit.
        await db.flush()
        await svc.ledger(
            db,
            user,
            entry.fund_id,
            LedgerIn(
                kind="refund",
                amount=row.amount,
                reference=body.reference,
                note=row.reason,
                reverses_id=entry.id,
            ),
        )
        row.reference = body.reference
    svc.audit(db, user, row.id, "refund_" + body.action)
    await db.flush()
    return svc.row_dict(row)


@router.post("/admin/rescue/donation-events/{ident}/review")
async def review_exception(
    ident: UUID,
    body: s.DonationReviewIn,
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    row = await db.scalar(
        select(RescueDonationEvent).where(RescueDonationEvent.id == ident).with_for_update()
    )
    if not row or row.reference != body.reference:
        svc.fail("Chứng từ không khớp ngoại lệ.", status=422)
    if body.decision == "record":
        if row.status not in (
            "unmatched",
            "amount_mismatch",
            "merchant_mismatch",
            "other_ledger_conflict",
        ):
            svc.fail("Giao dịch không ở trạng thái chờ ghép chứng từ.")
        return await reconcile(
            db, user, s.DonationConfirm(**body.model_dump(exclude={"decision"})), resolve_id=row.id
        )
    if row.status not in ("surplus_review", "surplus_review_resolved") or not row.intent_id:
        svc.fail("Chỉ xử lý phần dư của khoản thu đã đối soát.")
    intent = await db.get(RescueDonationIntent, row.intent_id)
    actual_receipt = await db.scalar(
        select(RescueLedger).where(
            RescueLedger.reference == row.reference, RescueLedger.kind == "received"
        )
    )
    if not actual_receipt:
        svc.fail("Cần khoản thu gốc đã đối soát.")
    if body.decision == "keep_in_fund":
        if intent.purpose_snapshot.get("surplus_action") != "hold":
            svc.fail("Chính sách gốc không cho tạm giữ đúng quỹ; cần kiểm tra phương án hoàn.")
        row.status = "resolved_hold"
    else:
        result = await refund(
            s.RefundIn(entry_id=actual_receipt.id, amount=body.amount, reason=body.note),
            "event-refund:" + str(row.id),
            user,
            db,
        )
        row.status = "refund_requested"
        svc.audit(db, user, row.id, "donation_refund_proposed", refund_id=result["id"])
    row.resolved_by = user.id
    svc.audit(
        db, user, row.id, "donation_surplus_decision", decision=body.decision, reason=body.note
    )
    return {"id": str(row.id), "status": row.status}
