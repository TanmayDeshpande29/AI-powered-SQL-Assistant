from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.user import PasswordChange, UserRead, UserUpdate
from app.services import auth as auth_service

router = APIRouter(prefix="/users", tags=["users"])


# "/me" instead of "/{user_id}": the user is taken from the verified token, so one
# user can never read or edit another (this closes the old IDOR hole).
@router.get("/me", response_model=UserRead)
async def read_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(data: UserUpdate, user: CurrentUser, db: DbSession):
    user.name = data.name
    await db.commit()
    return user


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_my_password(data: PasswordChange, user: CurrentUser, db: DbSession):
    await auth_service.change_password(db, user, data.current_password, data.new_password)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, db: DbSession):
    await db.delete(user)  # query_history rows go with it (ON DELETE CASCADE)
    await db.commit()
