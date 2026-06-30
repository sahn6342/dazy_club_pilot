"""
SQLAlchemy ORM models. Column names mirror Pydantic field names (camelCase) so
row -> Pydantic conversion is a clean kwargs splat in each repository.
"""
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class VenueRow(Base):
    __tablename__ = "venues"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="Asia/Kolkata")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class CourtRow(Base):
    __tablename__ = "courts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    venue_id: Mapped[str] = mapped_column(String, ForeignKey("venues.id"), index=True, nullable=False)
    sport: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class ScheduleRuleRow(Base):
    __tablename__ = "schedule_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    court_id: Mapped[str] = mapped_column(String, ForeignKey("courts.id"), index=True, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    open_time: Mapped[str] = mapped_column(String, nullable=False)  # "HH:MM"
    close_time: Mapped[str] = mapped_column(String, nullable=False)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0..100, off the base price


class ScheduleExceptionRow(Base):
    __tablename__ = "schedule_exceptions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    court_id: Mapped[str | None] = mapped_column(String, ForeignKey("courts.id"), index=True, nullable=True)  # NULL = all courts (venue-wide)
    day: Mapped[str] = mapped_column(String, index=True, nullable=False)  # "YYYY-MM-DD"
    closed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    open_time: Mapped[str | None] = mapped_column(String, nullable=True)  # special hours if not closed
    close_time: Mapped[str | None] = mapped_column(String, nullable=True)


class CustomerRow(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)  # primary contact (phone or email)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class BookingRow(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    bookingRef: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)  # soft FK to customers.id
    court_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)  # FK to courts.id (not enforced on SQLite)
    slotId: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact: Mapped[str] = mapped_column(String, nullable=False)
    sportSlug: Mapped[str] = mapped_column(String, index=True, nullable=False)
    date: Mapped[str] = mapped_column(String, index=True, nullable=False)
    startTime: Mapped[str] = mapped_column(String, nullable=False)
    endTime: Mapped[str] = mapped_column(String, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)  # final amount charged
    promo_code: Mapped[str | None] = mapped_column(String, nullable=True)  # applied promo code, if any
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EnquiryRow(Base):
    __tablename__ = "enquiries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    contact: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    eventType: Mapped[str | None] = mapped_column(String, nullable=True)
    estimatedGroupSize: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferredDate: Mapped[str | None] = mapped_column(String, nullable=True)
    preferredSport: Mapped[str | None] = mapped_column(String, nullable=True)
    interestedSport: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, index=True, default="new", nullable=False)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class GalleryRow(Base):
    __tablename__ = "gallery"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    sportSlug: Mapped[str] = mapped_column(String, nullable=False)
    tone: Mapped[str] = mapped_column(String, nullable=False)
    imageUrl: Mapped[str | None] = mapped_column(String, nullable=True)  # absolute URL or /media/gallery/<uuid>.<ext>
    approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TestimonialRow(Base):
    __tablename__ = "testimonials"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    context: Mapped[str] = mapped_column(String, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CmsRow(Base):
    __tablename__ = "cms"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class PromoCodeRow(Base):
    __tablename__ = "promo_codes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)  # stored UPPERCASE
    kind: Mapped[str] = mapped_column(String, nullable=False)  # "percent" | "flat"
    value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[str | None] = mapped_column(String, nullable=True)  # "YYYY-MM-DD"
    valid_to: Mapped[str | None] = mapped_column(String, nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sport_slug: Mapped[str | None] = mapped_column(String, nullable=True)  # None = all sports
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="manager", nullable=False)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)
    createdBy: Mapped[str] = mapped_column(String, nullable=False)
