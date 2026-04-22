from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import User, get_current_user, get_optional_user, require_admin
from app.models.skill import Skill, SkillStatus
from app.schemas.skill import AdminLabelOut, LabelOut
from app.services.label import (
    InvalidObjectIdError,
    LabelAlreadyAppliedError,
    LabelNotFoundError,
    LabelRateLimitError,
    label_service,
)

router = APIRouter(prefix="/api/labels", tags=["labels"])
skills_labels_router = APIRouter(prefix="/api/skills", tags=["labels"])
admin_router = APIRouter(prefix="/api/admin/labels", tags=["admin-labels"])

limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=List[LabelOut])
async def list_labels(
    q: Optional[str] = Query(None, description="Prefix typeahead"),
    limit: int = Query(20, ge=1, le=100),
):
    return await label_service.search(q=q, limit=limit)


@router.get("/{name}", response_model=LabelOut)
async def get_label(name: str):
    label = await label_service.get_by_name(name)
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    return LabelOut(name=label.name, usage_count=label.usage_count)


@skills_labels_router.get("/{slug}/labels", response_model=List[LabelOut])
async def list_skill_labels(
    slug: str,
    viewer: Optional[User] = Depends(get_optional_user),
):
    skill = await Skill.find_one(Skill.slug == slug)
    if skill is None or skill.status == SkillStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    viewer_id = viewer.user_id if viewer else None
    return await label_service.list_for_skill(str(skill.id), viewer_id=viewer_id)


class AddLabelBody(LabelOut.__class__):
    pass


from pydantic import BaseModel


class AddLabelIn(BaseModel):
    name: str


class MergeLabelIn(BaseModel):
    into_id: str


class RenameLabelIn(BaseModel):
    name: str


@skills_labels_router.post(
    "/{slug}/labels",
    response_model=LabelOut,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("50/hour")
async def add_label_to_skill(
    request: Request,
    slug: str,
    body: AddLabelIn,
    user: User = Depends(get_current_user),
):
    skill = await Skill.find_one(Skill.slug == slug)
    if skill is None or skill.status == SkillStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    try:
        return await label_service.add(str(skill.id), body.name, user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LabelRateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except LabelAlreadyAppliedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@skills_labels_router.delete("/{slug}/labels/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_label_from_skill(
    slug: str,
    name: str,
    user: User = Depends(get_current_user),
):
    skill = await Skill.find_one(Skill.slug == slug)
    if skill is None or skill.status == SkillStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    try:
        await label_service.remove(str(skill.id), name, user.user_id)
    except LabelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# Admin endpoints

@admin_router.get("", response_model=List[AdminLabelOut])
async def admin_list_labels(
    user: User = Depends(get_current_user),
    _admin: User = Depends(require_admin),
):
    labels = await label_service.list_all_with_ids(include_zero=True)
    return labels


@admin_router.patch("/{label_id}", response_model=LabelOut)
async def admin_rename_label(
    label_id: str,
    body: RenameLabelIn,
    user: User = Depends(get_current_user),
    _admin: User = Depends(require_admin),
):
    try:
        return await label_service.rename(label_id, body.name, user.user_id)
    except InvalidObjectIdError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except LabelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@admin_router.post("/{label_id}/merge", response_model=LabelOut)
async def admin_merge_label(
    label_id: str,
    body: MergeLabelIn,
    user: User = Depends(get_current_user),
    _admin: User = Depends(require_admin),
):
    try:
        return await label_service.merge(label_id, body.into_id, user.user_id)
    except InvalidObjectIdError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except LabelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@admin_router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_label(
    label_id: str,
    user: User = Depends(get_current_user),
    _admin: User = Depends(require_admin),
):
    try:
        await label_service.delete(label_id, user.user_id)
    except InvalidObjectIdError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except LabelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
