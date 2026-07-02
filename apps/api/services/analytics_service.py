"""Owner-reporting composition: dashboard + day-close (Phase 4, DEC-024).

All "today" / day-boundary math resolves in the venue's IANA timezone via
services/venue_tz.py — fixes the browser/server-local "today" bug noted in
Roadmap.md. Booking dates are already stored as venue-local calendar dates
(see availability_service.py), so booking aggregates need no UTC conversion;
café payments/invoices are stored as UTC timestamps, so those go through
day_bounds_utc().
"""
from deps import reporting_repo
from models import DashboardDto, DayCloseDto, PaymentModeTotal
from services.availability_service import generate_slots
from services.venue_tz import day_bounds_utc, get_venue_zoneinfo, local_today


def dashboard() -> DashboardDto:
    tz = get_venue_zoneinfo()
    today = local_today(tz)
    start_utc, end_utc = day_bounds_utc(today, tz)

    bookings_today, booking_revenue_today = reporting_repo.booking_count_and_revenue(today)
    occupied = reporting_repo.occupied_slot_count(today)
    cafe_revenue_today = reporting_repo.cafe_revenue(start_utc, end_utc)

    total_slots = len(generate_slots(date=today, drop_past=False))
    occupancy_today = (occupied / total_slots) if total_slots else 0.0

    return DashboardDto(
        date=today,
        bookingsToday=bookings_today,
        bookingRevenueToday=booking_revenue_today,
        cafeRevenueToday=cafe_revenue_today,
        occupancyToday=round(occupancy_today, 4),
    )


def day_close(local_date: str | None = None) -> DayCloseDto:
    tz = get_venue_zoneinfo()
    date = local_date or local_today(tz)
    start_utc, end_utc = day_bounds_utc(date, tz)

    by_mode = reporting_repo.payments_by_mode(start_utc, end_utc)
    total_revenue = sum(total for _, total, _ in by_mode)
    total_transactions = sum(count for _, _, count in by_mode)

    return DayCloseDto(
        date=date,
        totalRevenue=total_revenue,
        totalTransactions=total_transactions,
        byMode=[PaymentModeTotal(mode=mode, total=total, count=count) for mode, total, count in by_mode],
    )
