import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { setToken, isAuthenticated } from "../lib/auth";

const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "↵"];

export function Login() {
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const pinRef = useRef(pin);
  pinRef.current = pin;

  useEffect(() => {
    if (isAuthenticated()) navigate("/menu", { replace: true });
  }, []);

  function handleDigit(d: string, currentPin?: string) {
    if (d === "⌫") { setPin((p) => p.slice(0, -1)); return; }
    if (d === "↵") { submit(currentPin ?? pinRef.current); return; }
    const base = currentPin ?? pinRef.current;
    if (base.length < 4) {
      const next = base + d;
      setPin(next);
      if (next.length === 4) submit(next);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Don't intercept digit keys while the username text input has focus.
      if (document.activeElement instanceof HTMLInputElement) {
        if (e.key === "Enter") submit(pinRef.current);
        return;
      }
      if (e.key >= "0" && e.key <= "9") handleDigit(e.key);
      else if (e.key === "Backspace") { e.preventDefault(); handleDigit("⌫"); }
      else if (e.key === "Enter") submit(pinRef.current);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [username]);

  async function submit(currentPin?: string) {
    const p = currentPin ?? pinRef.current;
    if (!username.trim() || p.length < 4) {
      setError("Enter staff name and 4-digit PIN.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await api.post<{ access_token: string }>("/cafe/login", { username, pin: p });
      setToken(res.access_token);
      navigate("/menu");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Login failed.");
    } finally {
      setLoading(false);
      setPin("");
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="login-title">Dazy.club Kiosk</h1>
        <input
          className="login-input"
          placeholder="Staff username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
        />
        <div className="pin-display">
          {Array.from({ length: 4 }, (_, i) => (
            <span key={i} className={`pin-dot ${i < pin.length ? "filled" : ""}`} />
          ))}
        </div>
        <div className="pin-pad">
          {DIGITS.map((d) => (
            <button
              key={d}
              className={`pin-btn${d === "↵" ? " confirm" : d === "⌫" ? " back" : ""}`}
              onClick={() => handleDigit(d)}
              disabled={loading}
            >
              {d}
            </button>
          ))}
        </div>
        {error && <p className="login-error">{error}</p>}
      </div>
    </div>
  );
}
