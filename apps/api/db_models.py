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


# ── Café POS ──

class CafeSettingsRow(Base):
    __tablename__ = "cafe_settings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    legalName: Mapped[str | None] = mapped_column(String, nullable=True)
    gstin: Mapped[str | None] = mapped_column(String, nullable=True)
    fssaiNumber: Mapped[str | None] = mapped_column(String, nullable=True)
    addressLine: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    stateName: Mapped[str | None] = mapped_column(String, nullable=True)
    stateCode: Mapped[str | None] = mapped_column(String, nullable=True)
    scheme: Mapped[str] = mapped_column(String, nullable=False, default="regular")
    priceIncludesTax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    defaultTaxRate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=5.0)
    invoiceSeriesPrefix: Mapped[str] = mapped_column(String, nullable=False, default="INV")
    billOfSupplySeriesPrefix: Mapped[str] = mapped_column(String, nullable=False, default="BOS")
    logoUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    declaration: Mapped[str | None] = mapped_column(Text, nullable=True)
    footerNote: Mapped[str | None] = mapped_column(Text, nullable=True)
    roundingEnabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)
    updatedAt: Mapped[str] = mapped_column(String, nullable=False)


class MenuCategoryRow(Base):
    __tablename__ = "menu_categories"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # food|beverage|packaged|combo
    vegType: Mapped[str | None] = mapped_column(String, nullable=True)
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class MenuItemRow(Base):
    __tablename__ = "menu_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    category_id: Mapped[str] = mapped_column(String, ForeignKey("menu_categories.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    taxRatePercent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=5.0)
    hsnSac: Mapped[str | None] = mapped_column(String, nullable=True)
    vegType: Mapped[str | None] = mapped_column(String, nullable=True)
    isPackaged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    station: Mapped[str] = mapped_column(String, nullable=False, default="kitchen")
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trackInventory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currentQty: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    reorderLevel: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    purchaseCost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String, nullable=True)
    imageUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class CafeTableRow(Base):
    __tablename__ = "cafe_tables"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    area: Mapped[str | None] = mapped_column(String, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    status: Mapped[str] = mapped_column(String, nullable=False, default="free")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sortOrder: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ── Café POS Phase 1 ──

class OrderRow(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    orderNo: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    orderType: Mapped[str] = mapped_column(String, nullable=False)
    table_id: Mapped[str | None] = mapped_column(String, ForeignKey("cafe_tables.id"), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discountAmount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    taxAmount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    roundOff: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdBy: Mapped[str] = mapped_column(String, nullable=False)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)
    updatedAt: Mapped[str] = mapped_column(String, nullable=False)


class OrderItemRow(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.id"), index=True, nullable=False)
    menu_item_id: Mapped[str] = mapped_column(String, ForeignKey("menu_items.id"), nullable=False)
    kot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    nameSnapshot: Mapped[str] = mapped_column(String, nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    unitPrice: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    taxRatePercent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=5)
    hsnSacSnapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    lineSubtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    lineTax: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    lineTotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    kotStatus: Mapped[str | None] = mapped_column(String, nullable=True)
    voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    voidReason: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class KotRow(Base):
    __tablename__ = "kots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kotNo: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.id"), index=True, nullable=False)
    station: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    printedAt: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class PaymentRow(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.id"), index=True, nullable=False)
    invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    createdBy: Mapped[str] = mapped_column(String, nullable=False)
    createdAt: Mapped[str] = mapped_column(String, nullable=False)


class InvoiceRow(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoiceNo: Mapped[str] = mapped_column(String, nullable=False)
    invoiceType: Mapped[str] = mapped_column(String, nullable=False)
    series: Mapped[str] = mapped_column(String, nullable=False)
    financialYear: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[str] = mapped_column(String, ForeignKey("orders.id"), index=True, nullable=False)
    customerName: Mapped[str | None] = mapped_column(String, nullable=True)
    customerGstin: Mapped[str | None] = mapped_column(String, nullable=True)
    taxableValue: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    cgst: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    sgst: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    roundOff: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    amountInWords: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="issued")
    issuedBy: Mapped[str] = mapped_column(String, nullable=False)
    issuedAt: Mapped[str] = mapped_column(String, nullable=False)


class InvoiceLineRow(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    invoice_id: Mapped[str] = mapped_column(String, ForeignKey("invoices.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    hsnSac: Mapped[str | None] = mapped_column(String, nullable=True)
    qty: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    taxableValue: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    gstRatePercent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    cgst: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    sgst: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    lineTotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class InvoiceSequenceRow(Base):
    __tablename__ = "invoice_sequences"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # "{series}-{financialYear}"
    series: Mapped[str] = mapped_column(String, nullable=False)
    financialYear: Mapped[str] = mapped_column(String, nullable=False)
    lastNumber: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
