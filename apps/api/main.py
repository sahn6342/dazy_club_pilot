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
from routes.promos import router as promos_router
from routes.venue import router as venue_router
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

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
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
app.include_router(promos_router, prefix=prefix)
app.include_router(venue_router, prefix=prefix)

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


@app.get("/")
def root():
    return {"app": "Dazy.club API", "docs": "/docs", "health": "/api/v1/health"}
