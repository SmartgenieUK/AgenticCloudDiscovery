import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

const Login = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.loginEmail(form);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider) => {
    setError("");
    setLoading(true);
    try {
      const data = await api.startOAuth(provider);
      window.location = data.authorization_url;
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <h1 className="form-title">Login</h1>
      <p className="muted">Access the Agentic Cloud Discovery console.</p>
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email">Email</label>
          <input id="email" name="email" type="email" autoComplete="email" required value={form.email} onChange={handleChange} />
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete="current-password" required value={form.password} onChange={handleChange} />
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Login"}
          </button>
        </div>
      </form>
      <div className="oauth-buttons" style={{ marginTop: "12px" }}>
        <button className="secondary" onClick={() => handleOAuth("google")} disabled={loading}>
          Continue with Google
        </button>
        <button className="secondary" onClick={() => handleOAuth("microsoft")} disabled={loading}>
          Continue with Microsoft
        </button>
      </div>
      <p className="muted" style={{ marginTop: "16px" }}>
        No account? <Link className="link" to="/register">Create account</Link>
      </p>
    </div>
  );
};

export default Login;
