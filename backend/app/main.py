from fastapi import FastAPI
from app.database.mongodb import user_collection
from fastapi.middleware.cors import CORSMiddleware
from app.routes.user_login_route import router as user_login_router
from app.routes.user_signup_route import router as user_signup_router
from app.routes.sql_generation_route import router as generate_sql_router
from app.routes.sql_assistants_route import router as sql_assistants_router
from app.routes.user_data_route import router as user_data_router
from app.routes.add_query_data_route import router as add_query_data_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins = ['http://localhost:5173'],
    allow_headers = ['*'],
    allow_methods = ['*'],
    allow_credentials = True
)


app.include_router(user_login_router)
app.include_router(user_signup_router)
app.include_router(generate_sql_router)
app.include_router(sql_assistants_router)
app.include_router(user_data_router)
app.include_router(add_query_data_router)
