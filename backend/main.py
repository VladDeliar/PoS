from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import pymongo.errors

from .database import connect_db, close_db
from .redis_manager import redis_manager
from .utils.data_fetchers import init_default_data

from .routers import (
    pages, admin_pages, categories, products, orders,
    menu_items, combos, modifiers, settings,
    promo_codes, feedbacks, stats, websocket,
    delivery_zones
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        connect_db()
        await redis_manager.connect()
        init_default_data()
    except Exception as e:
        print(f"Startup error: {e}")
    yield
    # Shutdown
    close_db()
    await redis_manager.close()


app = FastAPI(title="POS", lifespan=lifespan)

# Static files - шлях до frontend/static
BASE_DIR = Path(__file__).parent.parent  # Повертаємось до кореня проекту
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")


# ============ Exception Handlers ============

@app.exception_handler(pymongo.errors.ServerSelectionTimeoutError)
async def mongodb_timeout_handler(request: Request, exc: Exception):
    error_html = """
    <html>
        <head><title>Database Error</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>503 - Database Unavailable</h1>
            <p>Could not connect to MongoDB. Please check your connection.</p>
        </body>
    </html>
    """
    return HTMLResponse(content=error_html, status_code=503)


# ============ Include Routers ============

app.include_router(pages.router)
app.include_router(admin_pages.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(menu_items.router)
app.include_router(combos.router)
app.include_router(modifiers.router)
app.include_router(settings.router)
app.include_router(promo_codes.router)
app.include_router(feedbacks.router)
app.include_router(stats.router)
app.include_router(websocket.router)
app.include_router(delivery_zones.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
