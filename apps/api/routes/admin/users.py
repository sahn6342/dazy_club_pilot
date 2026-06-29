import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status, Depends
from models import UserCreate, UserUpdate, UserPublic, UserRecord
from auth import require_superadmin, hash_password
from deps import user_repo

router = APIRouter()


def _public(u: UserRecord) -> UserPublic:
    return UserPublic(id=u.id, username=u.username, role=u.role, createdAt=u.createdAt, createdBy=u.createdBy)


@router.get("/admin/users", response_model=list[UserPublic])
def list_users(_admin=Depends(require_superadmin)):
    return [_public(u) for u in user_repo.get_all()]


@router.post("/admin/users", response_model=UserPublic, status_code=201)
def create_user(body: UserCreate, admin=Depends(require_superadmin)):
    if user_repo.get_by_username(body.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.")
    record = UserRecord(
        id=str(uuid.uuid4()),
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
        createdAt=datetime.now(timezone.utc).isoformat(),
        createdBy=admin["sub"],
    )
    user_repo.create(record)
    return _public(record)


@router.patch("/admin/users/{user_id}", response_model=UserPublic)
def update_user(user_id: str, body: UserUpdate, _admin=Depends(require_superadmin)):
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    updates = {}
    if body.password is not None:
        updates["hashed_password"] = hash_password(body.password)
    if updates:
        user_repo.update(user_id, updates)
    return _public(user_repo.get_by_id(user_id))


@router.delete("/admin/users/{user_id}", status_code=204)
def delete_user(user_id: str, _admin=Depends(require_superadmin)):
    if not user_repo.delete(user_id):
        raise HTTPException(status_code=404, detail="User not found.")
