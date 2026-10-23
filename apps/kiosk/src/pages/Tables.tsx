import React, { useCallback, useEffect, useState } from "react";
import { api, CafeTable } from "../lib/api";
import { KioskHeader } from "../components/KioskHeader";
import { KioskFooter } from "../components/KioskFooter";

const STATUS_COLOR: Record<string, string> = {
  free: "#4caf50",
  occupied: "#e57373",
  reserved: "#ffb74d",
};

export function Tables() {
  const [tables, setTables] = useState<CafeTable[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api.get<CafeTable[]>("/cafe/tables")
      .then(setTables)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load tables."));
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, [load]);

  const byArea = tables.reduce<Record<string, CafeTable[]>>((acc, t) => {
    const k = t.area ?? "Floor";
    acc[k] = [...(acc[k] ?? []), t];
    return acc;
  }, {});

  return (
    <div className="kiosk-layout">
      <KioskHeader active="tables" />

      <div className="kiosk-body tables-body">
        {error && <p className="kiosk-error">{error}</p>}
        {tables.length === 0 && !error && (
          <p className="kiosk-empty">No tables configured. Add tables in Admin → Café → Tables.</p>
        )}
        {Object.entries(byArea).map(([area, areaT]) => (
          <section key={area} className="table-area">
            <h2 className="area-label">{area}</h2>
            <div className="table-grid">
              {areaT.map((t) => (
                <button
                  key={t.id}
                  className="table-btn"
                  style={{ borderColor: STATUS_COLOR[t.status] }}
                >
                  <span className="table-label">{t.label}</span>
                  <span className="table-cap">{t.capacity} seats</span>
                  <span className="table-status" style={{ color: STATUS_COLOR[t.status] }}>
                    {t.status}
                  </span>
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
      <KioskFooter />
    </div>
  );
}
