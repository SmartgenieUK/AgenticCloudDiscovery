import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const Dashboard = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .me()
      .then((data) => {
        setUser(data);
        setError("");
      })
      .catch((err) => {
        setError(err.message);
        setUser(null);
      });
  }, []);

  return (
    <div className="auth-shell">
      <h1 className="form-title">Congratulations on logging in</h1>
      <p className="muted">Here is your account summary.</p>
      {error && <div className="error">{error}</div>}
      {user && (
        <div style={{ marginBottom: "16px", display: "grid", gap: "8px" }}>
          <div className="badge">Signed in as {user.email}</div>
          <div>
            <strong>Name:</strong> {user.name || "Not provided"}
          </div>
          <div>
            <strong>Phone:</strong> {user.phone || "Not provided"}
          </div>
          <div>
            <strong>Designation:</strong> {user.designation || "Not provided"}
          </div>
          <div>
            <strong>Company address:</strong> {user.company_address || "Not provided"}
          </div>
          <div>
            <strong>Auth provider:</strong> {user.auth_provider}
          </div>
          <div>
            <strong>Last login:</strong> {user.last_login_at || "—"}
          </div>
        </div>
      )}
      <div className="actions">
        <button className="secondary" onClick={() => navigate("/login")}>
          Return to login
        </button>
      </div>
    </div>
  );
};

export default Dashboard;
