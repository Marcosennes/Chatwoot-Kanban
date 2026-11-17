from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse

from app.chatwoot_client import chatwoot_client
from app.database import close_pool, init_pool
from app.routers import api, conversations, kanban, webhooks


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_pool()
    await chatwoot_client.init()
    yield
    await chatwoot_client.close()
    await close_pool()


SIDEBAR_SCRIPT = Path(__file__).resolve().parent / "static" / "chatwoot-sidebar.js"

app = FastAPI(title="Chatwoot-Kanban", lifespan=lifespan)

app.include_router(conversations.router)
app.include_router(api.router)
app.include_router(kanban.router)
app.include_router(webhooks.router)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/kanban")


@app.get("/chatwoot-sidebar.js", include_in_schema=False)
async def chatwoot_sidebar_script() -> FileResponse:
    return FileResponse(
        SIDEBAR_SCRIPT,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
