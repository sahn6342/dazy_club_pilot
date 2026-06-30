import { useEffect, useState } from "react";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type Booking = {
  id: string; bookingRef: string; name: string; contact: string;
  sportSlug: string; date: string; startTime: string; endTime: string;
  party_size: number; price: number | null; promo_code: string | null; status: string; createdAt: string;
};

const STATUS_MSG: Record<string, string> = {
  confirmed: "Booking confirmed",
  completed: "Booking completed",
  cancelled: "Booking cancelled",
  no_show: "Marked as no-show",
};

export function Bookings() {
  const toast = useToast();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [filter, setFilter] = useState({ sport: "", status: "" });
  const [error, setError] = useState("");

  function load() {
    const q = new URLSearchParams();
    if (filter.sport) q.set("sport", filter.sport);
    if (filter.status) q.set("status", filter.status);
    api.get<Booking[]>(`/admin/bookings${q.size ? `?${q}` : ""}`)
      .then((data) => { setBookings(data); setError(""); })
      .catch((err) => setError(err.message ?? "Failed to load bookings"));
  }

  useEffect(() => { load(); }, [filter]);

  async function setStatus(id: string, status: string) {
    try {
      await api.patch(`/admin/bookings/${id}`, { status });
      load();
      toast.success(STATUS_MSG[status] ?? "Booking updated");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to update booking");
    }
  }

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Bookings" />
        <div className="page-body">
          <div className="filter-bar">
            <select value={filter.sport} onChange={(e) => setFilter((f) => ({ ...f, sport: e.target.value }))}>
              <option value="">All sports</option>
              <option value="cricket">Cricket</option>
              <option value="badminton">Badminton</option>
              <option value="pickleball">Pickleball</option>
            </select>
            <select value={filter.status} onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}>
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
              <option value="no_show">No-show</option>
            </select>
          </div>
          {error ? (
            <p className="empty-msg" style={{ color: "var(--color-error, #f87171)" }}>{error}</p>
          ) : bookings.length === 0 ? (
            <p className="empty-msg">No bookings yet. They will appear here once customers book on the public site.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Ref</th><th>Name</th><th>Sport</th><th>Date</th><th>Time</th>
                    <th>Players</th><th>Price</th><th>Status</th><th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((b) => (
                    <tr key={b.id}>
                      <td><code>{b.bookingRef}</code></td>
                      <td><div>{b.name}</div><small>{b.contact}</small></td>
                      <td style={{ textTransform: "capitalize" }}>{b.sportSlug}</td>
                      <td>{b.date}</td>
                      <td>{b.startTime}–{b.endTime}</td>
                      <td>{b.party_size}</td>
                      <td>{b.price != null ? `₹${b.price}` : "—"}{b.promo_code && <small className="muted"> ({b.promo_code})</small>}</td>
                      <td><StatusBadge status={b.status} /></td>
                      <td>
                        <div className="action-row">
                          {b.status === "pending" && (
                            <button className="btn-action confirm" onClick={() => setStatus(b.id, "confirmed")}>Confirm</button>
                          )}
                          {b.status === "confirmed" && (
                            <button className="btn-action confirm" onClick={() => setStatus(b.id, "completed")}>Complete</button>
                          )}
                          {b.status === "confirmed" && (
                            <button className="btn-action cancel" onClick={() => setStatus(b.id, "no_show")}>No-show</button>
                          )}
                          {(b.status === "pending" || b.status === "confirmed") && (
                            <button className="btn-action cancel" onClick={() => setStatus(b.id, "cancelled")}>Cancel</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
