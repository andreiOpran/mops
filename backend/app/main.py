from fastapi import Depends, FastAPI

from app.db import database_ok
from app.routers.search import router as search_router

app = FastAPI(title="Monitorizare întârzieri STB", version="0.1.0")
app.include_router(search_router)


def get_database_check():
    return database_ok


@app.get("/api/health")
def health(check=Depends(get_database_check)) -> dict[str, str]:
    """Liveness of the API and its database (starting point for NFR-09)."""
    return {"status": "ok", "database": "ok" if check() else "unavailable"}
