import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager

import time
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from brand import BRAND_NAME

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from media_store import MEDIA_DIR, ensure_media_dirs

from routes.health import router as health_router
from routes.public_config import router as public_config_router
from routes.sports import router as sports_router
from routes.gallery import router as gallery_router
from routes.testimonials import router as testimonials_router
from routes.notifications import router as notifications_router
from routes.enquiries import router as enquiries_router
from routes.slots import router as slots_router
from routes.bookings import router as bookings_router
from routes.payments import router as payments_router
from routes.internal import router as internal_router
from routes.otp import router as otp_router
from routes.admin.audit import router as admin_audit_router
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
    from config_guard import assert_production_config
    assert_production_config()  # fail closed before touching the DB
    try:
        logger.info("=== startup: running migrations ===")
        init_db()
        logger.info("=== startup: seeding initial data ===")
        seed_if_empty()
        logger.info("=== startup: complete ===")
        from services.notification_service import delivery_status
        from services.turnstile import turnstile_disabled
        if turnstile_disabled():
            logger.warning("SECURITY: Turnstile bot check is DISABLED (DAZY_TURNSTILE_DISABLED); booking, enquiry and OTP "
                           "endpoints rely on rate limits alone. Remove the variable to enable it.")
        from services.otp_service import otp_disabled
        if otp_disabled():
            logger.warning("SECURITY: OTP is DISABLED (DAZY_OTP_DISABLED): anyone who knows a phone number or email can list "
                           "its bookings. Remove the variable to require a code again.")
        for warning in delivery_status()["warnings"]:  # phone numbers are accepted, so say loudly what will NOT be delivered
            logger.warning("NOTIFICATIONS: %s", warning)
    except Exception:
        tb = traceback.format_exc()
        logger.critical("=== startup FAILED ===\n%s", tb)
        print(f"=== startup FAILED ===\n{tb}", file=sys.stderr, flush=True)
        raise
    yield


from logging_config import request_id_var
from observability import init_sentry, tag_request
from rate_limit import client_ip

init_sentry()  # no-op unless SENTRY_DSN is set

app = FastAPI(title=f"{BRAND_NAME} API", version="0.1.0", lifespan=lifespan)
access_log = logging.getLogger("access")
_REQUEST_ID_OK = __import__("re").compile(r"^[A-Za-z0-9._-]{8,64}$")


@app.exception_handler(Exception)
async def unhandled_error(request, exc):
    """Last resort: log the traceback with the request id, answer with a generic body that carries it."""
    rid = request.scope.get("request_id", "-")
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc, extra={"request_id": rid})
    return JSONResponse(status_code=500, content={"detail": "Internal server error.", "requestId": rid},
                        headers={"X-Request-ID": rid})

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
    allow_credentials=True,  # session cookies; origins above are explicit, never "*"
    expose_headers=["X-Total-Count", "Content-Disposition"],
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-OTP-Token"],
)


@app.middleware("http")
async def audit_admin_writes(request, call_next):
    """Fallback audit: every successful admin write that did not record an explicit event
    (see audit.py) is logged by method + normalised path, with the acting admin."""
    response = await call_next(request)
    path = request.url.path
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and path.startswith("/api/v1/admin/")
        and response.status_code < 400
        and not request.scope.get("audit_done")
        and path not in ("/api/v1/admin/login", "/api/v1/admin/logout")
    ):
        from audit import audit, normalise_path
        from auth import peek_actor
        action_path, entity_type, entity_id = normalise_path(path)
        audit(f"{request.method} {action_path}", peek_actor(request), request=request,
              entity_type=entity_type, entity_id=entity_id)
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    path = request.url.path
    if path.startswith(("/api/v1/admin", "/api/v1/cafe", "/api/v1/otp", "/api/v1/bookings/lookup", "/api/v1/bookings/search", "/api/v1/public-config")):
        response.headers.setdefault("Cache-Control", "no-store")  # never cache authenticated/personal responses
    return response

prefix = "/api/v1"

# Public routes
app.include_router(health_router, prefix=prefix)
app.include_router(public_config_router, prefix=prefix)
app.include_router(sports_router, prefix=prefix)
app.include_router(gallery_router, prefix=prefix)
app.include_router(testimonials_router, prefix=prefix)
app.include_router(notifications_router, prefix=prefix)
app.include_router(enquiries_router, prefix=prefix)
app.include_router(slots_router, prefix=prefix)
app.include_router(bookings_router, prefix=prefix)
app.include_router(payments_router, prefix=prefix)
app.include_router(internal_router, prefix=prefix)
app.include_router(otp_router, prefix=prefix)
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
app.include_router(admin_audit_router, prefix=prefix)

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
    return {"app": f"{BRAND_NAME} API", "docs": "/docs", "health": "/api/v1/health"}


@app.middleware("http")
async def request_context(request, call_next):
    """Outermost layer: give every request an id (a sane client-supplied X-Request-ID is kept so a
    Cloudflare/Worker id can be followed through), echo it back, and write one access line per request
    with method, path (never the query string: it can hold contact details), status, duration and client IP."""
    incoming = request.headers.get("x-request-id", "")
    rid = incoming if _REQUEST_ID_OK.match(incoming) else uuid.uuid4().hex
    request.scope["request_id"] = rid
    token = request_id_var.set(rid)
    tag_request(rid)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        path = request.url.path
        level = logging.DEBUG if path in ("/api/v1/health", "/api/v1/health/ready") and status < 400 else logging.INFO
        access_log.log(level, "%s %s -> %s", request.method, path, status, extra={
            "method": request.method, "path": path, "status": status,
            "duration_ms": round((time.perf_counter() - start) * 1000, 1), "ip": client_ip(request),
        })
        request_id_var.reset(token)
