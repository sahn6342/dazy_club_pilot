import re as _re
from pydantic import BaseModel, Field, field_validator, model_validator

_PHONE_RE = _re.compile(r"^\d{10}$")
_EMAIL_RE = _re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
_VALID_SPORTS = {"cricket", "badminton", "pickleball"}


def _validate_contact(v: str) -> str:
    s = v.strip()
    if not _PHONE_RE.match(s) and not _EMAIL_RE.match(s):
        raise ValueError("Must be a 10-digit mobile number or a valid email address.")
    return s


class SportDto(BaseModel):
    id: str
    slug: str
    name: str
    tagline: str
    description: str
    highlights: list[str]


class GalleryItemDto(BaseModel):
    id: str
    title: str
    sportSlug: str
    tone: str
    imageUrl: str | None = None


class TestimonialDto(BaseModel):
    id: str
    name: str
    context: str
    quote: str


class NotificationDto(BaseModel):
    id: str
    title: str
    body: str
    surface: str


class ContactEnquiryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    contact: str = Field(min_length=1)
    interestedSport: str | None = None
    message: str | None = Field(default=None, max_length=2000)

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, v: str) -> str:
        return _validate_contact(v)

    @field_validator("interestedSport")
    @classmethod
    def validate_sport(cls, v: str | None) -> str | None:
        if not v:  # "" means "Any / not sure" on the web form — same as no preference
            return None
        if v not in _VALID_SPORTS:
            raise ValueError(f"interestedSport must be one of {sorted(_VALID_SPORTS)}.")
        return v


class CorporateEnquiryRequest(BaseModel):
    contactName: str = Field(min_length=1, max_length=80)
    company: str = Field(min_length=1, max_length=120)
    contact: str = Field(min_length=1)
    estimatedGroupSize: int = Field(gt=0, le=10000)
    eventType: str | None = Field(default=None, max_length=120)
    preferredDate: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    preferredSport: str | None = None
    message: str | None = Field(default=None, max_length=2000)

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, v: str) -> str:
        return _validate_contact(v)

    @field_validator("preferredSport")
    @classmethod
    def validate_sport(cls, v: str | None) -> str | None:
        if not v:  # "" means "Any / not sure" on the web form — same as no preference
            return None
        if v not in _VALID_SPORTS:
            raise ValueError(f"preferredSport must be one of {sorted(_VALID_SPORTS)}.")
        return v

    @field_validator("preferredDate", mode="before")
    @classmethod
    def blank_date_means_none(cls, v: str | None) -> str | None:
        if not v:  # "" means "no preference" on the web form — same as unset
            return None
        return v


class SlotDto(BaseModel):
    id: str
    courtId: str | None = None
    courtName: str | None = None
    sportSlug: str
    date: str
    startTime: str
    endTime: str
    available: bool
    maxPlayers: int
    price: float | None = None          # base price per slot (from schedule rule)
    discountPercent: int | None = None  # block-level discount %
    finalPrice: float | None = None     # price after block discount; what client shows

    model_config = {"frozen": False}


class BookingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    contact: str = Field(min_length=1)
    slotId: str | None = Field(default=None, min_length=1)   # legacy single-slot field
    slotIds: list[str] = Field(default_factory=list)         # preferred; supports multi-slot
    sportSlug: str = Field(min_length=1)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    startTime: str = Field(pattern=r"^\d{2}:\d{2}$")
    players: int = Field(ge=1, le=12)  # public API field — mapped to party_size internally
    promoCode: str | None = Field(default=None, max_length=40)
    message: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def resolve_slot_ids(self) -> "BookingRequest":
        if not self.slotIds and self.slotId:
            self.slotIds = [self.slotId]
        elif self.slotIds and not self.slotId:
            self.slotId = self.slotIds[0]
        if not self.slotIds:
            raise ValueError("Either slotId or slotIds is required.")
        if len(self.slotIds) > 8:
            raise ValueError("Cannot book more than 8 consecutive slots at once.")
        return self

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, v: str) -> str:
        return _validate_contact(v)

    @field_validator("sportSlug")
    @classmethod
    def validate_sport(cls, v: str) -> str:
        if v not in _VALID_SPORTS:
            raise ValueError(f"sportSlug must be one of {sorted(_VALID_SPORTS)}.")
        return v


class EnquiryReceived(BaseModel):
    status: str = "received"


# ── Admin models ──

class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CustomerRecord(BaseModel):
    id: str
    name: str
    phone: str
    email: str | None = None
    createdAt: str

    model_config = {"from_attributes": True}


class BookingRecord(BaseModel):
    id: str
    bookingRef: str
    customer_id: str | None = None
    court_id: str | None = None
    slotId: str
    name: str
    contact: str
    sportSlug: str
    date: str
    startTime: str
    endTime: str
    party_size: int
    price: float | None = None
    promo_code: str | None = None
    message: str | None = None
    status: str = "pending"  # pending | confirmed | cancelled
    createdAt: str
    is_primary: bool = True
    paymentStatus: str = "unpaid"  # unpaid | paid | refunded
    depositAmount: float | None = None

    model_config = {"frozen": False}


class BookingPaymentVerifyRequest(BaseModel):
    """Client-callback payload after checkout — provider-agnostic field names
    (the noop provider and Razorpay's razorpay_order_id/razorpay_payment_id/
    razorpay_signature both map onto these)."""
    providerOrderId: str = Field(min_length=1)
    providerPaymentId: str = Field(min_length=1)
    signature: str | None = None


class BookingRefundRequest(BaseModel):
    reason: str | None = None


class BookingPaymentDto(BaseModel):
    id: str
    bookingRef: str
    provider: str
    providerOrderId: str
    providerPaymentId: str | None = None
    amount: float
    status: str
    checkoutJson: str | None = None
    createdAt: str

    model_config = {"from_attributes": True}


class BookingLookupResult(BaseModel):
    """Self-service booking lookup (Detailed-Roadmap growth track, F2-style
    self-service). No login — identity is the ref + matching contact, same
    trust model as the café pre-order endpoint."""
    bookingRef: str
    name: str
    status: str
    sport: str
    date: str
    startTime: str
    endTime: str
    slotCount: int
    price: float | None = None
    paymentRequired: bool
    checkout: dict | None = None


class DashboardDto(BaseModel):
    date: str  # venue-local calendar date these figures are computed for
    bookingsToday: int
    bookingRevenueToday: float
    cafeRevenueToday: float
    occupancyToday: float  # 0..1, booked slots / bookable slots today


class PaymentModeTotal(BaseModel):
    mode: str
    total: float
    count: int


class DayCloseDto(BaseModel):
    date: str
    totalRevenue: float
    totalTransactions: int
    byMode: list[PaymentModeTotal]


class NotificationMessageDto(BaseModel):
    id: str
    refType: str
    refId: str
    channel: str
    recipient: str
    status: str  # sent | skipped | failed
    errorMessage: str | None = None
    createdAt: str

    model_config = {"from_attributes": True}


class EnquiryRecord(BaseModel):
    id: str
    type: str  # contact | corporate
    name: str
    contact: str
    company: str | None = None
    eventType: str | None = None
    estimatedGroupSize: int | None = None
    preferredDate: str | None = None
    preferredSport: str | None = None
    interestedSport: str | None = None
    message: str | None = None
    status: str = "new"  # new | handled
    createdAt: str

    model_config = {"frozen": False}


class GalleryItemAdmin(BaseModel):
    id: str
    title: str
    sportSlug: str
    tone: str
    imageUrl: str | None = None
    approved: bool = True

    model_config = {"frozen": False}


class GalleryItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    sportSlug: str = Field(min_length=1)
    tone: str = Field(min_length=1, max_length=60)
    imageUrl: str | None = None
    approved: bool = True

    @field_validator("sportSlug")
    @classmethod
    def validate_sport(cls, v: str) -> str:
        if v not in _VALID_SPORTS:
            raise ValueError(f"sportSlug must be one of {sorted(_VALID_SPORTS)}.")
        return v


class GalleryItemAdminUpdate(BaseModel):
    title: str | None = None
    sportSlug: str | None = None
    tone: str | None = None
    imageUrl: str | None = None
    approved: bool | None = None


class TestimonialAdmin(BaseModel):
    id: str
    name: str
    context: str
    quote: str
    approved: bool = True

    model_config = {"frozen": False}


class TestimonialAdminUpdate(BaseModel):
    approved: bool | None = None


class TestimonialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    context: str = Field(min_length=1, max_length=120)
    quote: str = Field(min_length=1, max_length=500)
    approved: bool = True


class TestimonialUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    context: str | None = Field(default=None, max_length=120)
    quote: str | None = Field(default=None, max_length=500)
    approved: bool | None = None


class CmsEntry(BaseModel):
    key: str
    label: str
    value: str

    model_config = {"frozen": False}


class CmsEntryUpdate(BaseModel):
    value: str | None = None
    label: str | None = None


class CmsCreate(BaseModel):
    key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1)


class BookingStatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|confirmed|completed|cancelled|no_show)$")


class EnquiryStatusUpdate(BaseModel):
    status: str = Field(pattern="^(new|handled)$")


# ── User / manager models ──

class UserRecord(BaseModel):
    id: str
    username: str
    hashed_password: str
    role: str = "manager"  # admin | manager
    createdAt: str
    createdBy: str

    model_config = {"frozen": False}


def validate_password_for_role(password: str, role: str) -> None:
    """Shared by UserCreate and the admin update route (which knows the
    target's current/effective role, unlike a UserUpdate model validator)."""
    if role == "manager" and len(password) < 8:
        raise ValueError("Manager password must be at least 8 characters.")
    if role in ("cashier", "kitchen"):
        if not password.isdigit() or len(password) != 4:
            raise ValueError("Staff PIN must be exactly 4 digits.")


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=4)
    role: str = Field(default="manager", pattern="^(manager|cashier|kitchen)$")

    @model_validator(mode="after")
    def validate_password_strength(self) -> "UserCreate":
        validate_password_for_role(self.password, self.role)
        return self


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=4)
    role: str | None = Field(default=None, pattern="^(manager|cashier|kitchen)$")


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    createdAt: str
    createdBy: str


class PasswordResetRequest(BaseModel):
    password: str = Field(min_length=4)


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Audit log ──

class AuditLogDto(BaseModel):
    id: str
    at: str
    actor: str
    actorRole: str | None = None
    action: str
    entityType: str | None = None
    entityId: str | None = None
    detail: str | None = None
    ip: str | None = None

    model_config = {"from_attributes": True}


# ── Schedule (admin) ──

class CourtDto(BaseModel):
    id: str
    venue_id: str
    sport: str
    name: str
    capacity: int
    active: bool
    createdAt: str = ""

    model_config = {"from_attributes": True}


class CourtCreate(BaseModel):
    venue_id: str = Field(min_length=1)
    sport: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=80)
    capacity: int = Field(ge=1, le=100, default=1)

    @field_validator("sport")
    @classmethod
    def validate_sport(cls, v: str) -> str:
        if v not in _VALID_SPORTS:
            raise ValueError(f"sport must be one of {sorted(_VALID_SPORTS)}.")
        return v


class CourtUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    capacity: int | None = Field(default=None, ge=1, le=100)
    active: bool | None = None


class ScheduleRuleDto(BaseModel):
    id: str
    court_id: str
    weekday: int
    open_time: str
    close_time: str
    slot_minutes: int
    price: float | None = None
    discount_percent: int | None = None

    model_config = {"from_attributes": True}


class ScheduleRuleCreate(BaseModel):
    court_id: str = Field(min_length=1)
    weekday: int = Field(ge=0, le=6)
    open_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    close_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    slot_minutes: int = Field(default=60, gt=0, le=720)
    price: float | None = Field(default=None, ge=0)
    discount_percent: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def open_before_close(self) -> "ScheduleRuleCreate":
        if self.open_time >= self.close_time:
            raise ValueError("open_time must be before close_time.")
        return self


class ScheduleRuleUpdate(BaseModel):
    open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    slot_minutes: int | None = Field(default=None, gt=0, le=720)
    price: float | None = Field(default=None, ge=0)
    discount_percent: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def open_before_close(self) -> "ScheduleRuleUpdate":
        if self.open_time and self.close_time and self.open_time >= self.close_time:
            raise ValueError("open_time must be before close_time.")
        return self


class ScheduleExceptionDto(BaseModel):
    id: str
    court_id: str | None = None  # None = venue-wide (all courts)
    day: str
    closed: bool
    open_time: str | None = None
    close_time: str | None = None

    model_config = {"from_attributes": True}


class ScheduleExceptionCreate(BaseModel):
    court_id: str | None = None  # None = venue-wide (all courts)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    closed: bool = True
    open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")

    @model_validator(mode="after")
    def times_consistent(self) -> "ScheduleExceptionCreate":
        if not self.closed:
            if not self.open_time or not self.close_time:
                raise ValueError("open_time and close_time are required for special-hours exceptions.")
            if self.open_time >= self.close_time:
                raise ValueError("open_time must be before close_time.")
        else:
            if self.open_time or self.close_time:
                raise ValueError("open_time and close_time must be empty when closed=true.")
        return self


# ── Promo codes (admin) ──

class PromoCodeDto(BaseModel):
    id: str
    code: str
    kind: str
    value: float
    active: bool
    valid_from: str | None = None
    valid_to: str | None = None
    max_uses: int | None = None
    used_count: int
    sport_slug: str | None = None
    createdAt: str

    model_config = {"from_attributes": True}


class PromoCodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    kind: str = Field(pattern="^(percent|flat)$")
    value: float = Field(gt=0)
    active: bool = True
    valid_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    valid_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    max_uses: int | None = Field(default=None, gt=0)
    sport_slug: str | None = None

    @model_validator(mode="after")
    def validate_promo_constraints(self) -> "PromoCodeCreate":
        if self.kind == "percent" and self.value > 100:
            raise ValueError("Percent discount cannot exceed 100.")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be after valid_to.")
        return self


class PromoCodeUpdate(BaseModel):
    active: bool | None = None
    kind: str | None = Field(default=None, pattern="^(percent|flat)$")
    value: float | None = Field(default=None, gt=0)
    valid_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    valid_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    max_uses: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_update_constraints(self) -> "PromoCodeUpdate":
        if self.kind == "percent" and self.value is not None and self.value > 100:
            raise ValueError("Percent discount cannot exceed 100.")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be after valid_to.")
        return self


# ── Café POS (Phase 0) ──

class CafeSettingsDto(BaseModel):
    id: str
    legalName: str | None = None
    gstin: str | None = None
    fssaiNumber: str | None = None
    addressLine: str | None = None
    city: str | None = None
    stateName: str | None = None
    stateCode: str | None = None
    scheme: str = "regular"
    priceIncludesTax: bool = True
    defaultTaxRate: float = 5.0
    invoiceSeriesPrefix: str = "INV"
    billOfSupplySeriesPrefix: str = "BOS"
    logoUrl: str | None = None
    declaration: str | None = None
    footerNote: str | None = None
    roundingEnabled: bool = True
    createdAt: str = ""
    updatedAt: str = ""

    model_config = {"from_attributes": True}


class CafeSettingsUpdate(BaseModel):
    legalName: str | None = None
    gstin: str | None = None
    fssaiNumber: str | None = None
    addressLine: str | None = None
    city: str | None = None
    stateName: str | None = None
    stateCode: str | None = None
    scheme: str | None = Field(default=None, pattern="^(regular|composition|unregistered)$")
    priceIncludesTax: bool | None = None
    defaultTaxRate: float | None = Field(default=None, ge=0, le=100)
    invoiceSeriesPrefix: str | None = Field(default=None, min_length=1, max_length=20)
    billOfSupplySeriesPrefix: str | None = Field(default=None, min_length=1, max_length=20)
    logoUrl: str | None = None
    declaration: str | None = None
    footerNote: str | None = None
    roundingEnabled: bool | None = None


class MenuCategoryDto(BaseModel):
    id: str
    name: str
    kind: str
    vegType: str | None = None
    sortOrder: int = 0
    active: bool = True
    createdAt: str = ""

    model_config = {"from_attributes": True}


class MenuCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(pattern="^(food|beverage|packaged|combo)$")
    vegType: str | None = Field(default=None, pattern="^(veg|nonveg|egg|na)$")
    sortOrder: int = 0


class MenuCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: str | None = Field(default=None, pattern="^(food|beverage|packaged|combo)$")
    vegType: str | None = Field(default=None, pattern="^(veg|nonveg|egg|na)$")
    sortOrder: int | None = None
    active: bool | None = None


class MenuItemDto(BaseModel):
    id: str
    category_id: str
    name: str
    description: str | None = None
    price: float
    taxRatePercent: float = 5.0
    hsnSac: str | None = None
    vegType: str | None = None
    isPackaged: bool = False
    station: str = "kitchen"
    available: bool = True
    trackInventory: bool = False
    currentQty: float | None = None
    reorderLevel: float | None = None
    unit: str | None = None
    purchaseCost: float | None = None
    barcode: str | None = None
    imageUrl: str | None = None
    sortOrder: int = 0
    createdAt: str = ""

    model_config = {"from_attributes": True}


class MenuItemCreate(BaseModel):
    category_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: float = Field(ge=0)
    taxRatePercent: float = Field(default=5.0, ge=0, le=100)
    hsnSac: str | None = Field(default=None, max_length=20)
    vegType: str | None = Field(default=None, pattern="^(veg|nonveg|egg|na)$")
    isPackaged: bool = False
    station: str = Field(default="kitchen", pattern="^(kitchen|bar|none)$")
    available: bool = True
    trackInventory: bool = False
    currentQty: float | None = Field(default=None, ge=0)
    reorderLevel: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=20)
    purchaseCost: float | None = Field(default=None, ge=0)
    barcode: str | None = Field(default=None, max_length=60)
    imageUrl: str | None = None
    sortOrder: int = 0


class MenuItemUpdate(BaseModel):
    category_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    taxRatePercent: float | None = Field(default=None, ge=0, le=100)
    hsnSac: str | None = None
    vegType: str | None = Field(default=None, pattern="^(veg|nonveg|egg|na)$")
    isPackaged: bool | None = None
    station: str | None = Field(default=None, pattern="^(kitchen|bar|none)$")
    available: bool | None = None
    trackInventory: bool | None = None
    currentQty: float | None = Field(default=None, ge=0)
    reorderLevel: float | None = Field(default=None, ge=0)
    unit: str | None = None
    purchaseCost: float | None = Field(default=None, ge=0)
    barcode: str | None = None
    imageUrl: str | None = None
    sortOrder: int | None = None


class CafeTableDto(BaseModel):
    id: str
    label: str
    area: str | None = None
    capacity: int = 4
    status: str = "free"
    active: bool = True
    sortOrder: int = 0

    model_config = {"from_attributes": True}


class CafeTableCreate(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    area: str | None = Field(default=None, max_length=60)
    capacity: int = Field(default=4, ge=1, le=50)
    sortOrder: int = 0


class CafeTableUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=40)
    area: str | None = None
    capacity: int | None = Field(default=None, ge=1, le=50)
    status: str | None = Field(default=None, pattern="^(free|occupied|reserved)$")
    active: bool | None = None
    sortOrder: int | None = None


class CafePinLoginRequest(BaseModel):
    username: str = Field(min_length=1)
    pin: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class MenuResponse(BaseModel):
    categories: list[MenuCategoryDto]
    items: list[MenuItemDto]


class PublicMenuItemDto(BaseModel):
    """Customer-facing menu item — omits inventory/cost internals (currentQty,
    reorderLevel, trackInventory, hsnSac) that MenuItemDto exposes to staff."""
    id: str
    category_id: str
    name: str
    description: str | None = None
    price: float
    vegType: str | None = None
    available: bool = True

    model_config = {"from_attributes": True}


class PublicMenuResponse(BaseModel):
    categories: list[MenuCategoryDto]
    items: list[PublicMenuItemDto]


# ── Café POS Phase 1 ──

class OrderItemCreate(BaseModel):
    menu_item_id: str
    qty: float = Field(default=1, gt=0)


class PreOrderRequest(BaseModel):
    """Customer pre-order attached to a booking (Detailed-Roadmap Phase 7).
    `contact` must match the booking's contact — same lightweight identity
    check used elsewhere (no login), scoped only to this one booking ref."""
    contact: str = Field(min_length=1)
    items: list[OrderItemCreate] = Field(min_length=1)

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, v: str) -> str:
        return _validate_contact(v)


class PreOrderLineDto(BaseModel):
    name: str
    qty: float
    lineTotal: float


class PreOrderResult(BaseModel):
    orderNo: str
    total: float
    items: list[PreOrderLineDto]


class OrderCreate(BaseModel):
    orderType: str = Field(default="quick", pattern="^(quick|dine_in|takeaway)$")
    table_id: str | None = None
    items: list[OrderItemCreate] = []
    notes: str | None = None


class OrderItemDto(BaseModel):
    id: str
    order_id: str
    menu_item_id: str
    kot_id: str | None = None
    nameSnapshot: str
    qty: float
    unitPrice: float
    taxRatePercent: float
    hsnSacSnapshot: str | None = None
    lineSubtotal: float
    lineTax: float
    lineTotal: float
    kotStatus: str | None = None
    voided: bool
    voidReason: str | None = None
    createdAt: str

    model_config = {"from_attributes": True}


class PaymentCreate(BaseModel):
    mode: str = Field(pattern="^(cash|card|upi|wallet|other)$")
    amount: float = Field(gt=0)
    reference: str | None = None


class PaymentDto(BaseModel):
    id: str
    order_id: str
    invoice_id: str | None = None
    mode: str
    amount: float
    reference: str | None = None
    createdBy: str
    createdAt: str

    model_config = {"from_attributes": True}


class OrderDto(BaseModel):
    id: str
    orderNo: str
    orderType: str
    table_id: str | None = None
    customer_id: str | None = None
    booking_id: str | None = None
    status: str
    subtotal: float
    discountAmount: float
    taxAmount: float
    roundOff: float
    total: float
    notes: str | None = None
    createdBy: str
    createdAt: str
    updatedAt: str
    items: list[OrderItemDto] = []
    payments: list[PaymentDto] = []

    model_config = {"from_attributes": True}


class OrderUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|in_kitchen|served|billed|paid|cancelled|void)$")
    notes: str | None = None
    table_id: str | None = None


class VoidItemRequest(BaseModel):
    reason: str = Field(min_length=1)


class KotItemDto(BaseModel):
    id: str
    menu_item_id: str
    nameSnapshot: str
    qty: float

    model_config = {"from_attributes": True}


class KotDto(BaseModel):
    id: str
    kotNo: str
    order_id: str
    orderNo: str = ""
    station: str
    status: str
    printedAt: str | None = None
    createdAt: str
    items: list[KotItemDto] = []

    model_config = {"from_attributes": True}


class KotStatusUpdate(BaseModel):
    status: str = Field(pattern="^(preparing|ready|served)$")


class InvoiceLineDto(BaseModel):
    id: str
    invoice_id: str
    description: str
    hsnSac: str | None = None
    qty: float
    unit: str | None = None
    rate: float
    taxableValue: float
    gstRatePercent: float
    cgst: float
    sgst: float
    lineTotal: float

    model_config = {"from_attributes": True}


class InvoiceDto(BaseModel):
    id: str
    invoiceNo: str
    invoiceType: str
    series: str
    financialYear: str
    order_id: str
    customerName: str | None = None
    customerGstin: str | None = None
    taxableValue: float
    cgst: float
    sgst: float
    roundOff: float
    total: float
    amountInWords: str
    status: str
    issuedBy: str
    issuedAt: str
    lines: list[InvoiceLineDto] = []

    model_config = {"from_attributes": True}


class IssueInvoiceRequest(BaseModel):
    customerName: str | None = None
    customerGstin: str | None = None
