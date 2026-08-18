"""
SQLAlchemy engine + session management for SQLite persistence.
To swap to PostgreSQL: change DAZY_DB_URL env var (and add a driver). Zero repo rewrites.
"""
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Loaded here (earliest config-reading module) so DAZY_*/RAZORPAY_*/SMTP_* env
# vars from apps/api/.env are visible before any other module's `os.environ.get`
# runs at import time (e.g. deps.py's payment/notification provider factories).
load_dotenv()

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "dazy.db")
DB_PATH = os.environ.get("DAZY_DB_PATH", _DEFAULT_PATH)
DB_URL = os.environ.get("DAZY_DB_URL", f"sqlite:///{DB_PATH}")

_connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,  # allows attribute reads during row -> Pydantic conversion
)


class Base(DeclarativeBase):
    pass


@contextmanager
def _session():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def init_db() -> None:
    """Bring the schema to head via Alembic migrations (replaces create_all)."""
    from alembic.config import Config
    from alembic import command

    cfg = Config(os.path.join(_BASE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BASE_DIR, "alembic"))
    cfg.set_main_option("sqlalchemy.url", DB_URL)
    command.upgrade(cfg, "head")


# CMS seed (moved from deps.py)
def _cms_seed():
    from models import CmsEntry
    return [
        CmsEntry(key="faq_booking", label="FAQ: How to book", value="Head to the Book section, pick your sport and date, select an available slot, and fill in your details. You'll get a booking reference immediately."),
        CmsEntry(key="faq_sports", label="FAQ: Which sports", value="Cricket, Badminton, and Pickleball are available. More sports may be added in future."),
        CmsEntry(key="faq_corporate", label="FAQ: Corporate events", value="Yes. Use the corporate enquiry form above and our team will get back to you to plan your event."),
        CmsEntry(key="faq_group_size", label="FAQ: Max group size", value="Cricket supports up to 11 players, Pickleball up to 6, and Badminton up to 4 per court slot. For larger groups, use the corporate enquiry form."),
        CmsEntry(key="hero_tagline", label="Hero tagline", value="Premium sports energy, built for your next game."),
        CmsEntry(key="hero_copy", label="Hero body copy", value="Dazy.club brings together Cricket, Badminton, and Pickleball in one premium venue. Whether it's a casual weekend game or a corporate event, we've got your court."),
        CmsEntry(key="footer_tagline", label="Footer tagline", value="Premium sports experience. Cricket, Badminton & Pickleball."),
        CmsEntry(key="venue_name", label="Venue name", value="Dazy.club"),
        CmsEntry(key="venue_address", label="Venue address", value="123 Sports Complex, Bengaluru, Karnataka 560001"),
        CmsEntry(key="venue_phone", label="Venue phone", value="+91 98765 43210"),
        CmsEntry(key="venue_email", label="Venue email", value="hello@dazy.club"),
        CmsEntry(key="venue_hours", label="Venue hours", value="Mon–Sun: 6:00 AM – 10:00 PM"),
        CmsEntry(key="social_instagram", label="Instagram handle / URL", value=""),
        CmsEntry(key="social_facebook", label="Facebook page URL", value=""),
    ]


def seed_if_empty() -> None:
    """Idempotent: insert seed data only for empty tables.
    Seeds gallery/testimonials/cms, plus one venue and one court per sport."""
    import uuid
    from datetime import datetime, timezone
    from sqlalchemy import select, func
    from seed import GALLERY_ITEMS, TESTIMONIALS, SPORTS
    from db_models import GalleryRow, TestimonialRow, CmsRow, VenueRow, CourtRow, ScheduleRuleRow, PromoCodeRow

    # Daily schedule blocks reproducing the original 12-slot grid (60-min slots,
    # lunch gap 12:00-14:00 and 17:00-18:00 break).
    _BLOCKS = [("06:00", "12:00"), ("14:00", "17:00"), ("18:00", "21:00")]
    # Default base price per slot, per sport (INR).
    _DEFAULT_PRICE = {"cricket": 1200, "badminton": 500, "pickleball": 700}

    now = datetime.now(timezone.utc).isoformat()
    with _session() as s:
        if s.scalar(select(func.count()).select_from(GalleryRow)) == 0:
            for g in GALLERY_ITEMS:
                s.add(GalleryRow(id=g.id, title=g.title, sportSlug=g.sportSlug, tone=g.tone, imageUrl=g.imageUrl, approved=True))
        if s.scalar(select(func.count()).select_from(TestimonialRow)) == 0:
            for t in TESTIMONIALS:
                s.add(TestimonialRow(id=t.id, name=t.name, context=t.context, quote=t.quote, approved=True))
        if s.scalar(select(func.count()).select_from(CmsRow)) == 0:
            for e in _cms_seed():
                s.add(CmsRow(key=e.key, label=e.label, value=e.value))
        # Venue — seeded once, never cleared.
        venue_id = "venue-dazy"
        if s.scalar(select(func.count()).select_from(VenueRow)) == 0:
            s.add(VenueRow(id=venue_id, name="Dazy.club", timezone="Asia/Kolkata", active=True, createdAt=now))
        # Courts — re-seeded whenever the table is empty (e.g. after test teardown).
        if s.scalar(select(func.count()).select_from(CourtRow)) == 0:
            for sport in SPORTS:
                s.add(CourtRow(
                    id=f"court-{sport.slug}",
                    venue_id=venue_id,
                    sport=sport.slug,
                    name="Court 1",
                    capacity=1,
                    active=True,
                    createdAt=now,
                ))
        # Schedule rules: one row per court / weekday / block (reproduces the 12-slot grid).
        if s.scalar(select(func.count()).select_from(ScheduleRuleRow)) == 0:
            for sport in SPORTS:
                court_id = f"court-{sport.slug}"
                price = _DEFAULT_PRICE.get(sport.slug)
                for weekday in range(7):
                    for open_t, close_t in _BLOCKS:
                        s.add(ScheduleRuleRow(
                            id=str(uuid.uuid4()),
                            court_id=court_id,
                            weekday=weekday,
                            open_time=open_t,
                            close_time=close_t,
                            slot_minutes=60,
                            price=price,
                            discount_percent=None,
                        ))
        # Sample promo codes (idempotent).
        if s.scalar(select(func.count()).select_from(PromoCodeRow)) == 0:
            s.add(PromoCodeRow(
                id=str(uuid.uuid4()), code="WELCOME10", kind="percent", value=10,
                active=True, valid_from=None, valid_to=None, max_uses=None,
                used_count=0, sport_slug=None, createdAt=now,
            ))
            s.add(PromoCodeRow(
                id=str(uuid.uuid4()), code="FLAT100", kind="flat", value=100,
                active=True, valid_from=None, valid_to=None, max_uses=None,
                used_count=0, sport_slug=None, createdAt=now,
            ))
