from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.auth.router import router as auth_router  # noqa: E402
from app.documents.router import router as documents_router  # noqa: E402
from app.reputation.router import router as reputation_router  # noqa: E402
from app.credentials.router import router as credentials_router  # noqa: E402
from app.agent.router import router as agent_router  # noqa: E402

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(reputation_router)
app.include_router(credentials_router)
app.include_router(agent_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
