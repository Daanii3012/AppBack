from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.config import init_db
from app.routes.auth_routes import router as auth_router
from app.routes.expenses_routes import router as expenses_router
from app.routes.groups_routes import router as groups_router
from app.routes.messages_routes import router as messages_router
from app.routes.users_routes import router as users_router

app = FastAPI(title="Split Expenses API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://127.0.0.1:51932",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")
app.include_router(users_router, prefix="/users")
app.include_router(groups_router, prefix="/groups")
app.include_router(expenses_router, prefix="/groups")
app.include_router(messages_router, prefix="/groups")

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
def health_check():
    return {"status": "ok"}
