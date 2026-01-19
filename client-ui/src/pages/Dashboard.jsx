import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const Dashboard = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);

  useEffect(() => {
    api
      .me()
      .then((data) => setUser(data))
      .catch(() => setUser(null));
  }, []);

  return (
    <div className="auth-shell">
      <h1 className="form-title">Dashboard</h1>
      <p className="muted">Authenticated placeholder view.</p>
      {user && (
        <div style={{ marginBottom: "12px" }}>
          <div className="badge">Signed in as {user.email}</div>
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
