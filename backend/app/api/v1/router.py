from fastapi import APIRouter

from app.api.v1.routes import auth, health, history, schemas, sql, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(schemas.router)
api_router.include_router(sql.router)
api_router.include_router(history.router)
