from sqlalchemy import select
from app.models.admin_archive import AdminArchive


def visible(resource_id, kind):
    return resource_id.not_in(select(AdminArchive.resource_id).where(AdminArchive.resource_kind == kind))
