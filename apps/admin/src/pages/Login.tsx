import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { markSignedIn } from "../lib/auth";

export function Login() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      // The API answers with the session cookie; the token in the body is not stored.
      await api.post("/admin/login", {
        username: data.username,
        password: data.password,
      });
      markSignedIn();
      navigate("/");
    } catch (err: any) {
      setError(err.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <img className="login-logo" src="/logo.webp" alt="Dazy Club" width="160" height="137" />
        <div className="login-brand">Admin</div>
        <label>Username<input name="username" autoComplete="username" required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
        {error && <p className="error-msg">{error}</p>}
        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
