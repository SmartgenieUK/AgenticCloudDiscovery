import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

const Register = () => {
  const navigate = useNavigate();
  const [method, setMethod] = useState("email");
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    designation: "",
    company_address: "",
    password: "",
    confirm_password: "",
    consent: false,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState("");

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm({ ...form, [name]: type === "checkbox" ? checked : value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!form.consent) {
      setError("You must agree to Terms.");
      return;
    }
    if (method !== "email") {
      setLoading(true);
      try {
        const data = await api.startOAuth(method);
        window.location = data.authorization_url;
        return;
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
      return;
    }
    if (form.password !== form.confirm_password) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await api.registerEmail(form);
      setSuccess("Account created.");
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <h1 className="form-title">Create account</h1>
      <p className="muted">Choose a sign-up method and complete your details.</p>
      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}
      <div style={{ marginBottom: "12px" }}>
        <label htmlFor="method">Registration method</label>
        <select id="method" value={method} onChange={(e) => setMethod(e.target.value)}>
          <option value="email">Email</option>
          <option value="google">Google</option>
          <option value="microsoft">Microsoft</option>
        </select>
        {method !== "email" && <p className="muted">We will request the remaining details after {method} sign-in.</p>}
      </div>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name">Full name</label>
          <input id="name" name="name" required value={form.name} onChange={handleChange} />
        </div>
        <div>
          <label htmlFor="email">Email address</label>
          <input id="email" name="email" type="email" required value={form.email} onChange={handleChange} />
        </div>
        <div>
          <label htmlFor="phone">Phone number</label>
          <input id="phone" name="phone" required value={form.phone} onChange={handleChange} />
        </div>
        <div>
          <label htmlFor="designation">Designation / Job title</label>
          <input id="designation" name="designation" required value={form.designation} onChange={handleChange} />
        </div>
        <div>
          <label htmlFor="company_address">Company address (optional)</label>
          <input id="company_address" name="company_address" value={form.company_address} onChange={handleChange} />
        </div>
        {method === "email" && (
          <>
            <div>
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" required value={form.password} onChange={handleChange} />
            </div>
            <div>
              <label htmlFor="confirm_password">Confirm password</label>
              <input id="confirm_password" name="confirm_password" type="password" required value={form.confirm_password} onChange={handleChange} />
            </div>
          </>
        )}
        <div className="checkbox-row">
          <input id="consent" name="consent" type="checkbox" checked={form.consent} onChange={handleChange} />
          <label htmlFor="consent" style={{ margin: 0 }}>
            I agree to Terms
          </label>
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Submitting..." : "Create account"}
          </button>
        </div>
      </form>
      <p className="muted" style={{ marginTop: "16px" }}>
        Already have an account? <Link className="link" to="/login">Login</Link>
      </p>
    </div>
  );
};

export default Register;
