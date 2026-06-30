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
        if v is not None and v not in _VALID_SPORTS:
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
        if v is not None and v not in _VALID_SPORTS:
            raise ValueError(f"preferredSport must be one of {sorted(_VALID_SPORTS)}.")
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


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
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
