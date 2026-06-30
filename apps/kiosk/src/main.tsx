import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./styles.css";

import { AuthGuard } from "./components/AuthGuard";
import { Login } from "./pages/Login";
import { Menu } from "./pages/Menu";
import { Tables } from "./pages/Tables";
import { KDS } from "./pages/KDS";
import { Orders } from "./pages/Orders";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/menu" element={<AuthGuard><Menu /></AuthGuard>} />
        <Route path="/tables" element={<AuthGuard><Tables /></AuthGuard>} />
        <Route path="/orders" element={<AuthGuard><Orders /></AuthGuard>} />
        <Route path="/kds" element={<AuthGuard><KDS /></AuthGuard>} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
