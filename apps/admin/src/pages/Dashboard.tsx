import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import { TopBar } from "../components/TopBar";
import { api } from "../lib/api";

type Booking = { id: string; status: string; date: string };
type Enquiry = { id: string; status: string };
type GalleryItem = { id: string; approved: boolean };
type Testimonial = { id: string; approved: boolean };

export function Dashboard() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [enquiries, setEnquiries] = useState<Enquiry[]>([]);
  const [gallery, setGallery] = useState<GalleryItem[]>([]);
  const [testimonials, setTestimonials] = useState<Testimonial[]>([]);

  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    api.get<Booking[]>("/admin/bookings").then(setBookings).catch(() => {});
    api.get<Enquiry[]>("/admin/enquiries").then(setEnquiries).catch(() => {});
    api.get<GalleryItem[]>("/admin/gallery").then(setGallery).catch(() => {});
    api.get<Testimonial[]>("/admin/testimonials").then(setTestimonials).catch(() => {});
  }, []);

  const stats = [
    { label: "Bookings today", value: bookings.filter((b) => b.date === today).length, to: "/bookings" },
    { label: "Pending bookings", value: bookings.filter((b) => b.status === "pending").length, to: "/bookings" },
    { label: "New enquiries", value: enquiries.filter((e) => e.status === "new").length, to: "/enquiries" },
    { label: "Gallery items", value: gallery.length, to: "/gallery" },
    { label: "Testimonials", value: testimonials.length, to: "/testimonials" },
  ];

  return (
    <div className="admin-layout">
      <Sidebar />
      <div className="admin-main">
        <TopBar title="Dashboard" />
        <div className="page-body">
          <div className="stats-grid">
            {stats.map((s) => (
              <Link to={s.to} className="stat-card" key={s.label}>
                <span className="stat-value">{s.value}</span>
                <span className="stat-label">{s.label}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
