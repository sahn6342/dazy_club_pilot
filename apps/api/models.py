from pydantic import BaseModel, Field


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
    name: str = Field(min_length=1)
    contact: str = Field(min_length=1)
    interestedSport: str | None = None
    message: str | None = None


class CorporateEnquiryRequest(BaseModel):
    contactName: str = Field(min_length=1)
    company: str = Field(min_length=1)
    contact: str = Field(min_length=1)
    estimatedGroupSize: int = Field(gt=0)
    eventType: str | None = None
    preferredDate: str | None = None
    preferredSport: str | None = None
    message: str | None = None


class SlotDto(BaseModel):
    id: str
    courtId: str | None = None
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
    name: str = Field(min_length=1)
    contact: str = Field(min_length=1)
    slotId: str = Field(min_length=1)
    sportSlug: str = Field(min_length=1)
    date: str = Field(min_length=1)
    startTime: str = Field(min_length=1)
    players: int = Field(ge=1, le=12)  # public API field — mapped to party_size internally
    promoCode: str | None = None
    message: str | None = None


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

    model_config = {"frozen": False}


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
    approved: bool = True

    model_config = {"frozen": False}


class GalleryItemAdminUpdate(BaseModel):
    title: str | None = None
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


class CmsEntry(BaseModel):
    key: str
    label: str
    value: str

    model_config = {"frozen": False}


class CmsEntryUpdate(BaseModel):
    value: str


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


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    role: str = Field(default="manager", pattern="^(manager)$")


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=8)


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    createdAt: str
    createdBy: str


# ── Schedule (admin) ──

class CourtDto(BaseModel):
    id: str
    venue_id: str
    sport: str
    name: str
    capacity: int
    active: bool

    model_config = {"from_attributes": True}


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
    price: float | None = None
    discount_percent: int | None = Field(default=None, ge=0, le=100)


class ScheduleRuleUpdate(BaseModel):
    open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    slot_minutes: int | None = Field(default=None, gt=0, le=720)
    price: float | None = None
    discount_percent: int | None = Field(default=None, ge=0, le=100)


class ScheduleExceptionDto(BaseModel):
    id: str
    court_id: str
    day: str
    closed: bool
    open_time: str | None = None
    close_time: str | None = None

    model_config = {"from_attributes": True}


class ScheduleExceptionCreate(BaseModel):
    court_id: str = Field(min_length=1)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    closed: bool = True
    open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


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


class PromoCodeUpdate(BaseModel):
    active: bool | None = None
    value: float | None = Field(default=None, gt=0)
    valid_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    valid_to: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    max_uses: int | None = Field(default=None, gt=0)
