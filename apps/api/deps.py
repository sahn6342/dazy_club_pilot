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
from repositories.cafe_settings_repo import SqliteCafeSettingsRepository
from repositories.menu_category_repo import SqliteMenuCategoryRepository
from repositories.menu_item_repo import SqliteMenuItemRepository
from repositories.cafe_table_repo import SqliteCafeTableRepository
from repositories.order_repo import SqliteOrderRepository
from repositories.kot_repo import SqliteKotRepository
from repositories.payment_repo import SqlitePaymentRepository
from repositories.invoice_repo import SqliteInvoiceRepository
from repositories.booking_payment_repo import SqliteBookingPaymentRepository
from repositories.reporting_repo import SqliteReportingRepository
from repositories.notification_repo import SqliteNotificationRepository
from integrations.payments.factory import get_payment_provider
from integrations.notifications.factory import get_notification_provider

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
cafe_settings_repo = SqliteCafeSettingsRepository()
menu_category_repo = SqliteMenuCategoryRepository()
menu_item_repo = SqliteMenuItemRepository()
cafe_table_repo = SqliteCafeTableRepository()
order_repo = SqliteOrderRepository()
kot_repo = SqliteKotRepository()
payment_repo = SqlitePaymentRepository()
invoice_repo = SqliteInvoiceRepository()
booking_payment_repo = SqliteBookingPaymentRepository()
reporting_repo = SqliteReportingRepository()
notification_repo = SqliteNotificationRepository()
payment_provider = get_payment_provider()
notification_provider = get_notification_provider()
