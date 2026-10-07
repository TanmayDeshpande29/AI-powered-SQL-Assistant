from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.auth import LoginRequest, RefreshRequest, SignupRequest, TokenPair
from app.schemas.user import UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, db: DbSession):
    return await auth_service.register_user(db, data)


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: DbSession):
    user = await auth_service.authenticate(db, data.email, data.password)
    return auth_service.issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: DbSession):
    return await auth_service.refresh_tokens(db, data.refresh_token)
