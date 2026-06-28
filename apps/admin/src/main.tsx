import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const modules = [
  "Bookings",
  "Customers",
  "Pricing",
  "Notifications",
  "Gallery",
  "Testimonials",
  "CMS",
  "CRM",
  "Audit"
];

function AdminShell() {
  return (
    <main className="admin-shell">
      <aside>
        <strong>Dazy Admin</strong>
        <span>Deferred shell</span>
      </aside>
      <section>
        <p>Future scope</p>
        <h1>Admin workflows are intentionally deferred.</h1>
        <div className="module-grid">
          {modules.map((module) => (
            <article key={module}>{module}</article>
          ))}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AdminShell />
  </React.StrictMode>
);
