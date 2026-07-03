import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from media_store import MEDIA_DIR, ensure_media_dirs

from routes.health import router as health_router
from routes.sports import router as sports_router
from routes.gallery import router as gallery_router
from routes.testimonials import router as testimonials_router
from routes.notifications import router as notifications_router
from routes.enquiries import router as enquiries_router
from routes.slots import router as slots_router
from routes.bookings import router as bookings_router
from routes.payments import router as payments_router
from routes.promos import router as promos_router
from routes.venue import router as venue_router
from routes.preorders import router as preorders_router
from routes.admin.auth import router as admin_auth_router
from routes.admin.bookings import router as admin_bookings_router
from routes.admin.enquiries import router as admin_enquiries_router
from routes.admin.gallery import router as admin_gallery_router
from routes.admin.testimonials import router as admin_testimonials_router
from routes.admin.cms import router as admin_cms_router
from routes.admin.users import router as admin_users_router
from routes.admin.schedule import router as admin_schedule_router
from routes.admin.customers import router as admin_customers_router
from routes.admin.promos import router as admin_promos_router
from routes.admin.courts import router as admin_courts_router
from routes.admin.reports import router as admin_reports_router
from routes.admin.notifications import router as admin_notifications_router
from routes.cafe.auth import router as cafe_auth_router
from routes.cafe.menu import router as cafe_menu_router
from routes.cafe.tables import router as cafe_tables_router
from routes.cafe.orders import router as cafe_orders_router
from routes.cafe.kots import router as cafe_kots_router
from routes.cafe.invoices import router as cafe_invoices_router
from routes.admin.cafe.settings import router as admin_cafe_settings_router
from routes.admin.cafe.categories import router as admin_cafe_categories_router
from routes.admin.cafe.items import router as admin_cafe_items_router
from routes.admin.cafe.tables import router as admin_cafe_tables_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    from db import init_db, seed_if_empty
    init_db()
    seed_if_empty()
    yield


app = FastAPI(title="Dazy.club API", version="0.1.0", lifespan=lifespan)

# Serve uploaded media (gallery images) read-only at /media.
ensure_media_dirs()
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

_DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
_cors_origins = [
    o.strip() for o in os.environ.get("DAZY_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",") if o.strip()
]

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["*"],
)

prefix = "/api/v1"

# Public routes
app.include_router(health_router, prefix=prefix)
app.include_router(sports_router, prefix=prefix)
app.include_router(gallery_router, prefix=prefix)
app.include_router(testimonials_router, prefix=prefix)
app.include_router(notifications_router, prefix=prefix)
app.include_router(enquiries_router, prefix=prefix)
app.include_router(slots_router, prefix=prefix)
app.include_router(bookings_router, prefix=prefix)
app.include_router(payments_router, prefix=prefix)
app.include_router(promos_router, prefix=prefix)
app.include_router(venue_router, prefix=prefix)
app.include_router(preorders_router, prefix=prefix)

# Admin routes (JWT-protected except login)
app.include_router(admin_auth_router, prefix=prefix)
app.include_router(admin_bookings_router, prefix=prefix)
app.include_router(admin_enquiries_router, prefix=prefix)
app.include_router(admin_gallery_router, prefix=prefix)
app.include_router(admin_testimonials_router, prefix=prefix)
app.include_router(admin_cms_router, prefix=prefix)
app.include_router(admin_users_router, prefix=prefix)
app.include_router(admin_schedule_router, prefix=prefix)
app.include_router(admin_customers_router, prefix=prefix)
app.include_router(admin_promos_router, prefix=prefix)
app.include_router(admin_courts_router, prefix=prefix)
app.include_router(admin_reports_router, prefix=prefix)
app.include_router(admin_notifications_router, prefix=prefix)

# Kiosk (cashier) routes
app.include_router(cafe_auth_router, prefix=prefix)
app.include_router(cafe_menu_router, prefix=prefix)
app.include_router(cafe_tables_router, prefix=prefix)
app.include_router(cafe_orders_router, prefix=prefix)
app.include_router(cafe_kots_router, prefix=prefix)
app.include_router(cafe_invoices_router, prefix=prefix)

# Admin café back-office routes
app.include_router(admin_cafe_settings_router, prefix=prefix)
app.include_router(admin_cafe_categories_router, prefix=prefix)
app.include_router(admin_cafe_items_router, prefix=prefix)
app.include_router(admin_cafe_tables_router, prefix=prefix)


@app.get("/")
def root():
    return {"app": "Dazy.club API", "docs": "/docs", "health": "/api/v1/health"}
