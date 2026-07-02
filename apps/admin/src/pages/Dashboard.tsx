import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";

type Enquiry = { id: string; status: string };
type Booking = { id: string; status: string };

type DashboardData = {
  date: string;
  bookingsToday: number;
  bookingRevenueToday: number;
  cafeRevenueToday: number;
  occupancyToday: number;
};

type PaymentModeTotal = { mode: string; total: number; count: number };

type DayClose = {
  date: string;
  totalRevenue: number;
  totalTransactions: number;
  byMode: PaymentModeTotal[];
};

export function Dashboard() {
  const [enquiries, setEnquiries] = useState<Enquiry[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dashboardError, setDashboardError] = useState("");

  const [dayCloseDate, setDayCloseDate] = useState("");
  const [dayClose, setDayClose] = useState<DayClose | null>(null);
  const [dayCloseError, setDayCloseError] = useState("");

  useEffect(() => {
    api.get<Enquiry[]>("/admin/enquiries").then(setEnquiries).catch(() => {});
    api.get<Booking[]>("/admin/bookings").then(setBookings).catch(() => {});
    api.get<DashboardData>("/admin/reports/dashboard")
      .then((d) => { setDashboard(d); setDayCloseDate(d.date); setDashboardError(""); })
      .catch((err) => setDashboardError(err.message ?? "Failed to load dashboard"));
  }, []);

  useEffect(() => {
    if (!dayCloseDate) return;
    api.get<DayClose>(`/admin/reports/day-close?date=${dayCloseDate}`)
      .then((d) => { setDayClose(d); setDayCloseError(""); })
      .catch((err) => setDayCloseError(err.message ?? "Failed to load day-close"));
  }, [dayCloseDate]);

  const stats = [
    { label: "Bookings today", value: dashboard?.bookingsToday ?? "—", to: "/bookings" },
    { label: "Booking revenue today", value: dashboard ? `₹${dashboard.bookingRevenueToday.toFixed(2)}` : "—", to: "/bookings" },
    { label: "Café revenue today", value: dashboard ? `₹${dashboard.cafeRevenueToday.toFixed(2)}` : "—", to: "/cafe/orders" },
    { label: "Occupancy today", value: dashboard ? `${Math.round(dashboard.occupancyToday * 100)}%` : "—", to: "/schedule" },
    { label: "Pending bookings", value: bookings.filter((b) => b.status === "pending").length, to: "/bookings" },
    { label: "New enquiries", value: enquiries.filter((e) => e.status === "new").length, to: "/enquiries" },
  ];

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Dashboard" />
        <div className="page-body">
          {dashboardError && <p className="empty-msg" style={{ color: "var(--color-error, #f87171)" }}>{dashboardError}</p>}
          {dashboard && <p className="muted">Figures for {dashboard.date} (venue time).</p>}
          <div className="stats-grid">
            {stats.map((s) => (
              <Link to={s.to} className="stat-card" key={s.label}>
                <span className="stat-value">{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </Link>
            ))}
          </div>

          <h3 style={{ marginTop: "2rem" }}>Day-close (Z-report)</h3>
          <div className="filter-bar">
            <input type="date" value={dayCloseDate} onChange={(e) => setDayCloseDate(e.target.value)} />
          </div>
          {dayCloseError ? (
            <p className="empty-msg" style={{ color: "var(--color-error, #f87171)" }}>{dayCloseError}</p>
          ) : !dayClose ? (
            <p className="empty-msg">Loading…</p>
          ) : dayClose.totalTransactions === 0 ? (
            <p className="empty-msg">No café payments recorded for {dayClose.date}.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Payment mode</th><th>Transactions</th><th>Total</th></tr>
                </thead>
                <tbody>
                  {dayClose.byMode.map((m) => (
                    <tr key={m.mode}>
                      <td style={{ textTransform: "capitalize" }}>{m.mode}</td>
                      <td>{m.count}</td>
                      <td>₹{m.total.toFixed(2)}</td>
                    </tr>
                  ))}
                  <tr>
                    <td><strong>Total</strong></td>
                    <td><strong>{dayClose.totalTransactions}</strong></td>
                    <td><strong>₹{dayClose.totalRevenue.toFixed(2)}</strong></td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
