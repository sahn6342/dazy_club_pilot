import { useNavigate } from "react-router-dom";
import { clearToken } from "../lib/auth";

export function TopBar({ title }: { title: string }) {
  const navigate = useNavigate();

  function logout() {
    clearToken();
    navigate("/login");
  }

  return (
    <div className="topbar">
      <h1 className="page-title">{title}</h1>
      <button className="btn-logout" onClick={logout}>Logout</button>
    </div>
  );
}
