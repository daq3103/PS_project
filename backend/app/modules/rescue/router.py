import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cookies import _secure, set_csrf_cookie
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_optional, has_staff_permission
from app.core.rate_limit import client_ip, enforce_rate_limit
from app.core.security import hash_token, new_csrf_token
from app.models.community import CommunityPost
from app.models.rescue import RescueAnimal as Animal
from app.models.rescue import RescueCase as Case
from app.models.rescue import RescueEpisode as Episode
from app.models.rescue import RescueEvent as Event
from app.models.rescue import RescueExpense as Expense
from app.models.rescue import RescueFund as Fund
from app.models.rescue import RescueLedger as Ledger
from app.models.rescue import RescueLocation as Location
from app.models.rescue import RescueReport as Report
from app.models.rescue import RescueTask as Task
from app.models.user import User
from app.modules.rescue import schemas as s
from app.modules.rescue import service as svc

router = APIRouter(prefix="/api/v1", tags=["rescue-operations"])


def require(permission):
    async def check(user: User = Depends(get_current_user)):
        if not has_staff_permission(user, permission):
            svc.fail("Bạn chưa được cấp quyền cho phần việc này.", "PERMISSION_DENIED", 403)
        return user

    return check


manage = require("rescue_manage")
finance = require("rescue_finance")


async def care(user: User = Depends(get_current_user)):
    if not (svc.manager(user) or has_staff_permission(user, "rescue_care")):
        svc.fail("Bạn cần quyền chăm sóc trạm.", "PERMISSION_DENIED", 403)
    return user


async def mutate(db, user, action, key, body, handler):
    return await svc.operation(
        db, f"{user.id}:{action}", key, body.model_dump(mode="json"), handler
    )


@router.get("/rescue/config")
async def config(request: Request, response: Response):
    if not request.cookies.get("rescue_session"):
        response.set_cookie(
            "rescue_session",
            secrets.token_urlsafe(32),
            max_age=60 * 86400,
            httponly=True,
            secure=_secure(),
            samesite="lax",
        )
    if not request.cookies.get("csrf_token"):
        set_csrf_cookie(response, new_csrf_token())
    response.headers["Cache-Control"] = "no-store"
    from app.modules.rescue.contributions import enabled

    return {
        "area": "Hà Nội",
        "donations_enabled": enabled(),
        "notice": "Tin được ghi nhận để người phụ trách kiểm tra. Chỉ xác nhận hỗ trợ sau khi trạm liên hệ; website không xác nhận đội cứu hộ đang tới.",
    }


@router.get("/rescue/animals")
async def public_animals(
    species: str | None = Query(None, pattern="^(dog|cat)$"),
    offset: int = Query(0, ge=0),
    min_age: int | None = Query(None, ge=0, le=480),
    max_age: int | None = Query(None, ge=0, le=480),
    size: str | None = Query(None, pattern="^(small|medium|large)$"),
    q: str | None = Query(None, max_length=100),
    available: bool = False,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Animal)
        .where(Animal.publication.isnot(None))
        .order_by(Animal.created_at.desc(), Animal.id)
        .offset(offset)
        .limit(24)
    )
    if species:
        stmt = stmt.where(Animal.publication["species"].astext == species)
    if min_age is not None or max_age is not None:
        from sqlalchemy import Integer, cast

        age = cast(Animal.publication["age_months"].astext, Integer)
        if min_age is not None:
            stmt = stmt.where(age >= min_age)
        if max_age is not None:
            stmt = stmt.where(age <= max_age)
        if min_age is not None and max_age is not None and min_age > max_age:
            svc.fail("Tuổi tối thiểu không được vượt tuổi tối đa.", status=422)
    if size:
        stmt = stmt.where(Animal.publication["profile"]["size"].astext == size)
    if q:
        stmt = stmt.where(
            or_(
                Animal.publication["name"].astext.ilike("%" + q + "%"),
                Animal.publication["profile"]["color"].astext.ilike("%" + q + "%"),
                Animal.publication["profile"]["breed"].astext.ilike("%" + q + "%"),
                Animal.publication["public_area"].astext.ilike("%" + q + "%"),
            )
        )
    if available:
        stmt = stmt.where(
            Animal.adoption_state == "open",
            Animal.ownership_hold.is_(False),
            Animal.post_id.in_(
                select(CommunityPost.id).where(
                    CommunityPost.lifecycle_status == "open",
                    CommunityPost.moderation_status == "approved",
                    CommunityPost.expires_at > svc.now(),
                )
            ),
        )
    rows = (await db.scalars(stmt)).all()
    posts = {
        p.id: p
        for p in (
            await db.scalars(
                select(CommunityPost).options(selectinload(CommunityPost.images)).where(
                    CommunityPost.id.in_([a.post_id for a in rows if a.post_id])
                )
            )
        ).all()
    }
    return [await enriched_public(db, a, posts.get(a.post_id)) for a in rows]


@router.get("/rescue/animals/{slug}")
async def public_animal(slug: str, db: AsyncSession = Depends(get_db)):
    a = await db.scalar(select(Animal).where(Animal.slug == slug, Animal.publication.isnot(None)))
    if not a:
        svc.fail("Hồ sơ chưa được công bố hoặc không tồn tại.", status=404)
    post = await db.scalar(select(CommunityPost).options(selectinload(CommunityPost.images)).where(CommunityPost.id == a.post_id)) if a.post_id else None
    return await enriched_public(db, a, post)


@router.post("/rescue/reports", status_code=201)
async def report(
    body: s.ReportIn,
    request: Request,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        key=f"rl:rescue-report:{client_ip(request)}", limit=5, window_seconds=3600
    )
    cookie = request.cookies.get("rescue_session")
    if not user and not cookie:
        svc.fail("Vui lòng tải lại trang báo tin rồi gửi lại.", status=400)
    scope = str(user.id) if user else hash_token(cookie)

    async def create():
        if body.seen_at > svc.now() + timedelta(minutes=5):
            svc.fail("Thời điểm nhìn thấy không được ở tương lai.", status=422)
        r = Report(
            **body.model_dump(exclude={"consent"}),
            code=svc.code("TIN-"),
            user_id=user.id if user else None,
            session_hash=hash_token(cookie) if cookie else None,
        )
        db.add(r)
        await db.flush()
        svc.audit(db, user, r.id, "report_create", consent_version="rescue-report-v1")
        from app.modules.community.service import notify

        staff = (
            await db.scalars(
                select(User).where(
                    User.is_active.is_(True),
                    or_(User.role == "owner", User.staff_permissions.contains(["rescue_manage"]), User.staff_permissions.contains(["platform_manage"])),
                )
            )
        ).all()
        for person in staff:
            await notify(
                db,
                person.id,
                "Có tin cần trạm kiểm tra.",
                "/admin/rescue",
                f"rescue-report:{r.id}:{person.id}",
            )
        return {
            "id": str(r.id),
            "code": r.code,
            "status": r.status,
            "message": "Đã ghi nhận tin; vui lòng chờ người phụ trách xác nhận.",
        }

    return await svc.operation(db, "report:" + scope, key, body.model_dump(mode="json"), create)


@router.get("/rescue/me/reports")
async def my_reports(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    clauses = []
    if user:
        clauses.append(Report.user_id == user.id)
    if request.cookies.get("rescue_session"):
        clauses.append(Report.session_hash == hash_token(request.cookies["rescue_session"]))
    if not clauses:
        return []
    rows = (
        await db.scalars(
            select(Report).where(or_(*clauses)).order_by(Report.created_at.desc()).limit(50)
        )
    ).all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "status": r.status,
            "created_at": r.created_at,
            "acknowledged": bool(r.acknowledged_at),
        }
        for r in rows
    ]


@router.get("/admin/rescue/workspace")
async def workspace(user: User = Depends(care), db: AsyncSession = Depends(get_db)):
    stmt = select(Animal).order_by(Animal.created_at.desc()).limit(100)
    if not svc.manager(user):
        stmt = stmt.where(
            or_(
                select(Episode.id)
                .where(
                    Episode.animal_id == Animal.id,
                    Episode.assignee_id == user.id,
                    Episode.ended_at.is_(None),
                )
                .exists(),
                select(Task.id)
                .where(
                    Task.animal_id == Animal.id,
                    Task.assignee_id == user.id,
                    Task.status.in_(["todo", "accepted", "in_progress"]),
                )
                .exists(),
            )
        )
    animals = (await db.scalars(stmt)).all()
    tasks_stmt = (
        select(Task)
        .where(Task.status.in_(["todo", "accepted", "in_progress"]))
        .order_by(Task.due_at)
        .limit(100)
    )
    if not svc.manager(user):
        tasks_stmt = tasks_stmt.where(Task.assignee_id == user.id)
    result = {
        "animals": [svc.row_dict(a) for a in animals],
        "tasks": [svc.row_dict(t) for t in (await db.scalars(tasks_stmt)).all()],
        "locations": [],
        "reports": [],
        "cases": [],
        "staff": [],
        "adoption_posts": [],
    }
    if not svc.manager(user):
        result["reports"] = [
            svc.row_dict(r)
            for r in (
                await db.scalars(
                    select(Report)
                    .where(
                        Report.assignee_id == user.id,
                        Report.status.in_(["assigned", "in_progress"]),
                    )
                    .limit(100)
                )
            ).all()
        ]
    if svc.manager(user):
        locations = (await db.scalars(select(Location).order_by(Location.name))).all()
        counts = dict(
            (
                await db.execute(
                    select(Episode.location_id, func.count())
                    .where(Episode.ended_at.is_(None))
                    .group_by(Episode.location_id)
                )
            ).all()
        )
        result["locations"] = [
            {**svc.row_dict(location), "occupied": counts.get(location.id, 0)}
            for location in locations
        ]
        result["reports"] = [
            svc.row_dict(r)
            for r in (
                await db.scalars(select(Report).order_by(Report.created_at.desc()).limit(100))
            ).all()
        ]
        result["cases"] = [
            svc.row_dict(c)
            for c in (
                await db.scalars(select(Case).order_by(Case.created_at.desc()).limit(100))
            ).all()
        ]
        staff = (
            await db.scalars(
                select(User).where(
                    User.is_active.is_(True),
                    or_(
                        User.role == "owner",
                        User.staff_permissions.contains(["rescue_care"]),
                        User.staff_permissions.contains(["rescue_manage"]), User.staff_permissions.contains(["platform_manage"]),
                    ),
                )
            )
        ).all()
        result["staff"] = [{"id": p.id, "name": p.full_name} for p in staff]
        result["adoption_posts"] = [
            {"id": p.id, "title": p.title}
            for p in (
                await db.scalars(
                    select(CommunityPost).where(CommunityPost.post_type == "adoption").limit(100)
                )
            ).all()
        ]
    return result


@router.post("/admin/rescue/animals", status_code=201)
async def create_animal(
    body: s.AnimalIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await mutate(db, user, "animal", key, body, lambda: svc.create_animal(db, user, body))


@router.get("/admin/rescue/animals/{animal_id}")
async def animal_detail(
    animal_id: UUID, user: User = Depends(care), db: AsyncSession = Depends(get_db)
):
    a = await svc.animal(db, animal_id, user, lock=False)
    episodes = (
        await db.scalars(
            select(Episode).where(Episode.animal_id == a.id).order_by(Episode.started_at.desc())
        )
    ).all()
    events = (
        await db.scalars(
            select(Event)
            .where(Event.animal_id == a.id)
            .order_by(Event.occurred_at.desc())
            .limit(200)
        )
    ).all()
    return {
        **svc.row_dict(a),
        "episodes": [svc.row_dict(e) for e in episodes],
        "events": [svc.row_dict(e) for e in events],
    }


@router.patch("/admin/rescue/animals/{animal_id}")
async def edit_animal(
    animal_id: UUID,
    body: s.AnimalUpdate,
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    a = await svc.animal(db, animal_id)
    if a.version != body.version:
        svc.fail("Hồ sơ vừa thay đổi. Vui lòng tải lại.", "VERSION_CONFLICT")
    if body.post_id != a.post_id:
        from app.models.community import AdoptionRequest

        if a.post_id and await db.scalar(
            select(AdoptionRequest.id).where(
                AdoptionRequest.post_id == a.post_id, AdoptionRequest.status == "approved"
            )
        ):
            svc.fail("Cần xử lý ghép đang được duyệt trước khi thay tin liên kết.")
        if body.post_id:
            new_post = await db.get(CommunityPost, body.post_id)
            if not new_post or new_post.post_type != "adoption":
                svc.fail("Cần chọn một tin nhận nuôi phù hợp.", status=422)
            if await db.scalar(
                select(Animal.id).where(Animal.post_id == body.post_id, Animal.id != a.id)
            ):
                svc.fail("Tin đã thuộc hồ sơ bé khác.")
        if a.post_id:
            from app.modules.community.service import reject_active_requests

            old_post = await db.get(CommunityPost, a.post_id)
            if old_post.lifecycle_status == "open":
                old_post.lifecycle_status = "closed"
                old_post.version += 1
            await reject_active_requests(
                db, old_post, user.id, "Trạm cập nhật hồ sơ cho đợt chăm sóc mới"
            )
        svc.audit(db, user, a.id, "adoption_post_link", old=a.post_id, new=body.post_id)
        a.post_id = body.post_id
        a.adoption_state = "not_open"
    for k, v in body.model_dump(exclude={"version", "post_id"}).items():
        setattr(a, k, v)
    a.version += 1
    svc.audit(db, user, a.id, "animal_edit", version=a.version)
    await db.flush()
    return svc.row_dict(a)


@router.post("/admin/rescue/animals/{animal_id}/action")
async def animal_action(
    animal_id: UUID,
    body: s.AnimalAction,
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await svc.publish_action(db, user, await svc.animal(db, animal_id), body)


@router.post("/admin/rescue/locations", status_code=201)
async def create_location(
    body: s.LocationIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        location = Location(**body.model_dump())
        db.add(location)
        await db.flush()
        svc.audit(db, user, location.id, "location_create")
        return svc.row_dict(location)

    return await mutate(db, user, "location", key, body, create)


@router.post("/admin/rescue/intakes", status_code=201)
async def intake(
    body: s.IntakeIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    return await mutate(db, user, "intake", key, body, lambda: svc.intake(db, user, body))


@router.post("/admin/rescue/animals/{animal_id}/transfer")
async def transfer(
    animal_id: UUID,
    body: s.TransferIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def run():
        return await svc.transfer(db, user, await svc.animal(db, animal_id), body)

    return await mutate(db, user, "transfer:" + str(animal_id), key, body, run)


@router.post("/admin/rescue/animals/{animal_id}/close")
async def close(
    animal_id: UUID,
    body: s.CloseIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def run():
        return await svc.close_episode(
            db, user, await svc.animal(db, animal_id), body.outcome, body.reason
        )

    return await mutate(db, user, "close:" + str(animal_id), key, body, run)


@router.post("/admin/rescue/animals/{animal_id}/care", status_code=201)
async def care_entry(
    animal_id: UUID,
    body: s.CareIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(care),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        await svc.animal(db, animal_id, user)
        if body.supersedes_id:
            old = await db.get(Event, body.supersedes_id)
            if not old or old.animal_id != animal_id:
                svc.fail("Bản ghi cần đính chính không thuộc bé này.", status=422)
        if body.occurred_at > svc.now() + timedelta(minutes=5):
            svc.fail("Nhật ký chỉ ghi việc đã thực hiện.", status=422)
        e = Event(**body.model_dump(), animal_id=animal_id, actor_id=user.id, details={})
        db.add(e)
        await db.flush()
        svc.audit(db, user, e.id, "care_create")
        return svc.row_dict(e)

    return await mutate(db, user, "care:" + str(animal_id), key, body, create)


@router.post("/admin/rescue/tasks", status_code=201)
async def create_task(
    body: s.TaskIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        await svc.animal(db, body.animal_id)
        await svc.assignee(db, body.assignee_id)
        episode = await svc.open_episode(db, body.animal_id)
        if not episode:
            svc.fail("Cần mở đợt chăm sóc trước khi giao việc.")
        t = Task(**body.model_dump(), episode_id=episode.id, occurrence_key=f"task:{user.id}:{key}")
        db.add(t)
        await db.flush()
        svc.audit(db, user, t.id, "task_create")
        return svc.row_dict(t)

    return await mutate(db, user, "task", key, body, create)


@router.post("/admin/rescue/tasks/{task_id}/action")
async def task_action(
    task_id: UUID,
    body: s.TaskAction,
    user: User = Depends(care),
    db: AsyncSession = Depends(get_db),
):
    t = await db.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if not t or (not svc.manager(user) and t.assignee_id != user.id):
        svc.fail("Không tìm thấy công việc của bạn.", status=404)
    allowed = {
        "todo": {"accepted", "skipped"},
        "accepted": {"in_progress", "completed", "skipped"},
        "in_progress": {"completed", "skipped"},
    }
    if t.status == body.status:
        return svc.row_dict(t)
    if body.status not in allowed.get(t.status, set()):
        svc.fail("Công việc không thể chuyển sang trạng thái này.")
    if body.status == "skipped" and len(body.reason) < 5:
        svc.fail("Cần ghi lý do bỏ qua công việc.", status=422)
    t.status = body.status
    if body.status == "completed":
        t.completed_at = svc.now()
    svc.audit(db, user, t.id, "task_" + body.status, reason=body.reason)
    await db.flush()
    return svc.row_dict(t)


@router.post("/admin/rescue/cases", status_code=201)
async def create_case(
    body: s.CaseIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        await svc.assignee(db, body.coordinator_id)
        c = Case(**body.model_dump(), code=svc.code("CA-"))
        db.add(c)
        await db.flush()
        svc.audit(db, user, c.id, "case_create")
        return svc.row_dict(c)

    return await mutate(db, user, "case", key, body, create)


@router.post("/admin/rescue/reports/{report_id}/action")
async def report_action(
    report_id: UUID,
    body: s.ReportAction,
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    r = await db.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if not r:
        svc.fail("Không tìm thấy tin báo.", status=404)
    if r.version != body.version:
        svc.fail("Tin báo vừa thay đổi. Vui lòng tải lại.", "VERSION_CONFLICT")
    terminal = {"completed", "closed", "referred", "duplicate"}
    if r.status in terminal:
        svc.fail("Tin đã kết thúc; lịch sử được giữ nguyên.")
    if body.assignee_id:
        await svc.assignee(db, body.assignee_id)
    if body.case_id and not await db.get(Case, body.case_id):
        svc.fail("Không tìm thấy ca cứu hộ.", status=404)
    if body.status in ("assigned", "in_progress") and not body.assignee_id:
        svc.fail("Cần chọn người chịu trách nhiệm.", status=422)
    r.assignee_id = body.assignee_id
    r.case_id = body.case_id
    r.urgency = body.urgency
    r.resolution = body.reason
    r.status = body.status
    r.version += 1
    svc.audit(db, user, r.id, "report_" + body.status, reason=body.reason, case_id=body.case_id)
    await db.flush()
    return svc.row_dict(r)


@router.post("/admin/rescue/reports/{report_id}/acknowledge")
async def acknowledge(
    report_id: UUID, user: User = Depends(care), db: AsyncSession = Depends(get_db)
):
    r = await db.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if not r or r.assignee_id != user.id:
        svc.fail("Tin báo không thuộc phần việc của bạn.", status=404)
    if not r.acknowledged_at:
        r.acknowledged_at = svc.now()
        r.version += 1
        svc.audit(db, user, r.id, "report_acknowledge")
    await db.flush()
    return {"status": "acknowledged"}


@router.get("/admin/rescue/finance")
async def financial_workspace(user: User = Depends(finance), db: AsyncSession = Depends(get_db)):
    funds = (await db.scalars(select(Fund).order_by(Fund.created_at.desc()).limit(100))).all()
    return {
        "funds": [{**svc.row_dict(f), **await svc.balances(db, f.id)} for f in funds],
        "entries": [
            svc.row_dict(e)
            for e in (
                await db.scalars(select(Ledger).order_by(Ledger.created_at.desc()).limit(200))
            ).all()
        ],
        "expenses": [
            svc.row_dict(e)
            for e in (
                await db.scalars(select(Expense).order_by(Expense.created_at.desc()).limit(100))
            ).all()
        ],
    }


@router.post("/admin/rescue/funds", status_code=201)
async def create_fund(
    body: s.FundIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        f = Fund(**body.model_dump())
        db.add(f)
        await db.flush()
        svc.audit(db, user, f.id, "fund_create")
        return svc.row_dict(f)

    return await mutate(db, user, "fund", key, body, create)


@router.post("/admin/rescue/funds/{fund_id}/entries", status_code=201)
async def entry(
    fund_id: UUID,
    body: s.LedgerIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    if body.kind == "refund":
        svc.fail(
            "Tạo đề nghị hoàn và chờ người khác duyệt trước khi ghi chứng từ hoàn thực tế.",
            "REFUND_APPROVAL_REQUIRED",
        )
    return await mutate(
        db, user, "ledger:" + str(fund_id), key, body, lambda: svc.ledger(db, user, fund_id, body)
    )


@router.post("/admin/rescue/expenses", status_code=201)
async def expense(
    body: s.ExpenseIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    async def create():
        if not await db.get(Fund, body.fund_id):
            svc.fail("Không tìm thấy quỹ.", status=404)
        e = Expense(**body.model_dump(), requester_id=user.id)
        db.add(e)
        await db.flush()
        svc.audit(db, user, e.id, "expense_request")
        return svc.row_dict(e)

    return await mutate(db, user, "expense", key, body, create)


@router.post("/admin/rescue/expenses/{expense_id}/action")
async def expense_action(
    expense_id: UUID,
    body: s.ExpenseAction,
    user: User = Depends(finance),
    db: AsyncSession = Depends(get_db),
):
    initial = await db.get(Expense, expense_id)
    if not initial:
        svc.fail("Không tìm thấy đề nghị chi.", status=404)
    await db.execute(select(Fund.id).where(Fund.id == initial.fund_id).with_for_update())
    e = await db.scalar(
        select(Expense)
        .where(Expense.id == expense_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if body.action == "approve":
        if e.status != "requested":
            svc.fail("Đề nghị không còn chờ duyệt.")
        if e.requester_id == user.id:
            svc.fail("Người đề nghị không tự duyệt khoản chi của mình.", "PERMISSION_DENIED", 403)
        if (await svc.balances(db, e.fund_id))["available"] < e.amount:
            svc.fail("Quỹ không đủ số có thể dùng.")
        e.approver_id = user.id
        e.status = "approved"
    elif body.action == "reject":
        if e.status not in ("requested", "approved"):
            svc.fail("Khoản chi đã kết thúc.")
        e.status = "rejected"
    elif body.action == "pay":
        if e.status == "paid":
            if e.payment_reference != body.reference:
                svc.fail("Khoản chi đã có chứng từ khác.")
            return svc.row_dict(e)
        if e.status != "approved" or len(body.reference) < 6:
            svc.fail("Cần khoản chi đã duyệt và chứng từ trả tiền.", status=422)
        from sqlalchemy import text

        from app.models.fulfillment import WebhookEvent

        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": "external-receipt:" + body.reference},
        )
        if await db.scalar(
            select(WebhookEvent.id).where(WebhookEvent.external_event_id == body.reference)
        ):
            svc.fail("Chứng từ đã có trong thanh toán Shop; cần đối soát lại.")
        if await db.scalar(select(Ledger.id).where(Ledger.reference == body.reference)):
            svc.fail("Chứng từ đã được ghi nhận.")
        db.add(
            Ledger(
                fund_id=e.fund_id,
                actor_id=user.id,
                kind="expense",
                amount=e.amount,
                reference=body.reference,
                note=e.purpose,
                anonymous=True,
            )
        )
        e.status = "paid"
        e.payment_reference = body.reference
    svc.audit(db, user, e.id, "expense_" + body.action)
    await db.flush()
    return svc.row_dict(e)


@router.post("/admin/rescue/funds/{fund_id}/publish")
async def publish_fund(
    fund_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    if not has_staff_permission(user, "platform_manage"):
        svc.fail("Chủ trạm duyệt bản báo cáo trước khi công bố.", "PERMISSION_DENIED", 403)
    f = await db.scalar(select(Fund).where(Fund.id == fund_id).with_for_update())
    if not f:
        svc.fail("Không tìm thấy quỹ.", status=404)
    f.public_report = {
        "title": f.title,
        "purpose": f.purpose,
        "surplus_policy": f.surplus_policy,
        **await svc.balances(db, fund_id),
        "as_of": svc.now().isoformat(),
    }
    from app.models.rescue import RescuePublication

    sequence = (
        int(
            await db.scalar(
                select(func.coalesce(func.max(RescuePublication.version), 0)).where(
                    RescuePublication.kind == "fund", RescuePublication.resource_id == f.id
                )
            )
        )
        + 1
    )
    db.add(
        RescuePublication(
            kind="fund",
            resource_id=f.id,
            version=sequence,
            approved_by=user.id,
            payload=f.public_report,
        )
    )
    svc.audit(db, user, f.id, "fund_publish", version=sequence)
    await db.flush()
    return f.public_report


@router.get("/rescue/transparency")
async def transparency(db: AsyncSession = Depends(get_db)):
    from app.models.rescue_workflow import RescueAsset

    funds = (
        await db.scalars(
            select(Fund)
            .where(Fund.public_report.isnot(None))
            .order_by(Fund.created_at.desc())
            .limit(100)
        )
    ).all()
    result = []
    for fund in funds:
        proofs = (
            await db.scalars(
                select(RescueAsset).where(
                    RescueAsset.resource_kind == "fund",
                    RescueAsset.resource_id == fund.id,
                    RescueAsset.public.is_(True),
                    RescueAsset.publication_allowed.is_(True),
                    RescueAsset.deleted_at.is_(None),
                )
            )
        ).all()
        result.append(
            {
                **fund.public_report,
                "fund_id": str(fund.id),
                "proofs": [
                    {"url": f"/api/proxy/api/v1/rescue/public-images/{p.id}"} for p in proofs
                ],
            }
        )
    return result


@router.get("/rescue/transparency/{fund_id}/history")
async def transparency_history(fund_id: UUID, db: AsyncSession = Depends(get_db)):
    from app.models.rescue import RescuePublication

    fund = await db.get(Fund, fund_id)
    if not fund or not fund.public_report:
        svc.fail("Báo cáo chưa được công bố.", status=404)
    versions = (
        await db.scalars(
            select(RescuePublication)
            .where(RescuePublication.kind == "fund", RescuePublication.resource_id == fund_id)
            .order_by(RescuePublication.version.desc())
            .limit(100)
        )
    ).all()
    return [
        {"version": v.version, "published_at": v.created_at, "report": v.payload} for v in versions
    ]


@router.get("/admin/rescue/supplies")
async def supplies(user: User = Depends(manage), db: AsyncSession = Depends(get_db)):
    from app.models.rescue import RescueSupply

    return [
        svc.row_dict(r)
        for r in (
            await db.scalars(
                select(RescueSupply).order_by(RescueSupply.created_at.desc()).limit(100)
            )
        ).all()
    ]


@router.post("/admin/rescue/supplies", status_code=201)
async def receive_supply(
    body: s.SupplyIn,
    key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(manage),
    db: AsyncSession = Depends(get_db),
):
    from app.models.rescue import RescueSupply

    async def create():
        if body.accepted_quantity and body.expiry_at and body.expiry_at <= svc.now():
            svc.fail("Hàng hết hạn không được ghi nhận là dùng được.", status=422)
        if await db.scalar(select(RescueSupply.id).where(RescueSupply.reference == body.reference)):
            svc.fail("Phiếu nhận này đã được ghi nhận.")
        r = RescueSupply(**body.model_dump(), actor_id=user.id)
        db.add(r)
        await db.flush()
        svc.audit(db, user, r.id, "supply_received", accepted=body.accepted_quantity)
        return svc.row_dict(r)

    return await mutate(db, user, "supply", key, body, create)


async def enriched_public(db, animal, post):
    from app.models.rescue_workflow import RescueAsset

    result = svc.public_animal(animal, post)
    assets = (
        await db.scalars(
            select(RescueAsset)
            .where(
                RescueAsset.resource_kind == "animal",
                RescueAsset.resource_id == animal.id,
                RescueAsset.public.is_(True),
                RescueAsset.publication_allowed.is_(True),
                RescueAsset.deleted_at.is_(None),
            )
            .order_by(RescueAsset.created_at)
        )
    ).all()
    result["images"] = [
        {"url": f"/api/proxy/api/v1/rescue/public-images/{a.id}", "caption": a.caption}
        for a in assets
    ] + result["images"]
    return result
