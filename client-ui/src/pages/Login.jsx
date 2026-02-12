import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

const Login = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Reset password state
  const [showReset, setShowReset] = useState(false);
  const [resetForm, setResetForm] = useState({ email: "", new_password: "", confirm_password: "" });
  const [resetMsg, setResetMsg] = useState("");
  const [resetting, setResetting] = useState(false);

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

  const handleReset = async (e) => {
    e.preventDefault();
    setError("");
    setResetMsg("");
    setResetting(true);
    try {
      const data = await api.resetPassword(resetForm);
      setResetMsg(data.message || "Password reset successfully.");
      setResetForm({ email: "", new_password: "", confirm_password: "" });
    } catch (err) {
      setError(err.message);
    } finally {
      setResetting(false);
    }
  };

  const toggleReset = () => {
    setShowReset((v) => !v);
    setError("");
    setResetMsg("");
    // Pre-fill email from login form
    if (!showReset && form.email) {
      setResetForm((prev) => ({ ...prev, email: form.email }));
    }
  };

  return (
    <div className="auth-shell">
      {!showReset ? (
        <>
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
          <div style={{ marginTop: "8px", textAlign: "right" }}>
            <button className="link" style={{ background: "none", padding: 0, border: "none", cursor: "pointer" }} onClick={toggleReset}>
              Forgot password?
            </button>
          </div>
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
        </>
      ) : (
        <>
          <h1 className="form-title">Reset Password</h1>
          <p className="muted">Enter your email and a new password.</p>
          {error && <div className="error">{error}</div>}
          {resetMsg && <div className="success">{resetMsg}</div>}
          <form onSubmit={handleReset}>
            <div>
              <label htmlFor="reset-email">Email</label>
              <input
                id="reset-email"
                type="email"
                required
                value={resetForm.email}
                onChange={(e) => setResetForm({ ...resetForm, email: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="reset-new-pw">New Password</label>
              <input
                id="reset-new-pw"
                type="password"
                required
                minLength={8}
                value={resetForm.new_password}
                onChange={(e) => setResetForm({ ...resetForm, new_password: e.target.value })}
              />
            </div>
            <div>
              <label htmlFor="reset-confirm-pw">Confirm Password</label>
              <input
                id="reset-confirm-pw"
                type="password"
                required
                minLength={8}
                value={resetForm.confirm_password}
                onChange={(e) => setResetForm({ ...resetForm, confirm_password: e.target.value })}
              />
            </div>
            <div className="actions">
              <button className="primary" type="submit" disabled={resetting}>
                {resetting ? "Resetting..." : "Reset Password"}
              </button>
              <button className="secondary" type="button" onClick={toggleReset}>
                Back to Login
              </button>
            </div>
          </form>
        </>
      )}
    </div>
  );
};

export default Login;
