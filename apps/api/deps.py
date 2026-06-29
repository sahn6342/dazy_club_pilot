"""
Singleton repository instances (SQLite-backed via SQLAlchemy).
To swap to PostgreSQL: change DAZY_DB_URL env var (and add a driver). Zero handler changes.
Route handlers import from here.
"""
from repositories.booking_repo import SqliteBookingRepository
from repositories.enquiry_repo import SqliteEnquiryRepository
from repositories.gallery_repo import SqliteGalleryRepository
from repositories.testimonial_repo import SqliteTestimonialRepository
from repositories.cms_repo import SqliteCmsRepository
from repositories.user_repo import SqliteUserRepository
from repositories.court_repo import SqliteCourtRepository
from repositories.schedule_repo import SqliteScheduleRepository
from repositories.customer_repo import SqliteCustomerRepository
from repositories.promo_repo import SqlitePromoRepository

booking_repo = SqliteBookingRepository()
enquiry_repo = SqliteEnquiryRepository()
gallery_repo = SqliteGalleryRepository()
testimonial_repo = SqliteTestimonialRepository()
cms_repo = SqliteCmsRepository()
user_repo = SqliteUserRepository()
court_repo = SqliteCourtRepository()
schedule_repo = SqliteScheduleRepository()
customer_repo = SqliteCustomerRepository()
promo_repo = SqlitePromoRepository()
