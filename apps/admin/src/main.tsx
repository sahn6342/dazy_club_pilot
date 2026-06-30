import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./styles.css";

import { AuthGuard } from "./components/AuthGuard";
import { ConfirmProvider } from "./components/ConfirmDialog";
import { ToastProvider } from "./components/Toast";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Bookings } from "./pages/Bookings";
import { Enquiries } from "./pages/Enquiries";
import { Gallery } from "./pages/Gallery";
import { Testimonials } from "./pages/Testimonials";
import { CMS } from "./pages/CMS";
import { Users } from "./pages/Users";
import { Schedule } from "./pages/Schedule";
import { Promos } from "./pages/Promos";
import { ContactDetails } from "./pages/ContactDetails";
import { Courts } from "./pages/Courts";
import { CafeCategories } from "./pages/CafeCategories";
import { CafeItems } from "./pages/CafeItems";
import { CafeTables } from "./pages/CafeTables";
import { CafeSettings } from "./pages/CafeSettings";
import { CafeOrders } from "./pages/CafeOrders";

function App() {
  return (
    <ConfirmProvider>
    <ToastProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<AuthGuard><Dashboard /></AuthGuard>} />
        <Route path="/bookings" element={<AuthGuard><Bookings /></AuthGuard>} />
        <Route path="/schedule" element={<AuthGuard><Schedule /></AuthGuard>} />
        <Route path="/promos" element={<AuthGuard><Promos /></AuthGuard>} />
        <Route path="/enquiries" element={<AuthGuard><Enquiries /></AuthGuard>} />
        <Route path="/gallery" element={<AuthGuard><Gallery /></AuthGuard>} />
        <Route path="/testimonials" element={<AuthGuard><Testimonials /></AuthGuard>} />
        <Route path="/cms" element={<AuthGuard><CMS /></AuthGuard>} />
        <Route path="/courts" element={<AuthGuard><Courts /></AuthGuard>} />
        <Route path="/contact-details" element={<AuthGuard><ContactDetails /></AuthGuard>} />
        <Route path="/users" element={<AuthGuard><Users /></AuthGuard>} />
        <Route path="/cafe/categories" element={<AuthGuard><CafeCategories /></AuthGuard>} />
        <Route path="/cafe/items" element={<AuthGuard><CafeItems /></AuthGuard>} />
        <Route path="/cafe/tables" element={<AuthGuard><CafeTables /></AuthGuard>} />
        <Route path="/cafe/settings" element={<AuthGuard><CafeSettings /></AuthGuard>} />
        <Route path="/cafe/orders" element={<AuthGuard><CafeOrders /></AuthGuard>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
    </ToastProvider>
    </ConfirmProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
