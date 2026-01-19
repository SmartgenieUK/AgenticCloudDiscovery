import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const CompleteProfile = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    phone: "",
    designation: "",
    company_address: "",
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api
      .me()
      .then((data) => {
        setForm({
          name: data.name || "",
          phone: data.phone || "",
          designation: data.designation || "",
          company_address: data.company_address || "",
        });
      })
      .catch(() => setError("Unable to load profile."))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await api.completeProfile(form);
      setSuccess("Profile updated.");
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="auth-shell">
        <p className="muted">Loading profile…</p>
      </div>
    );
  }

  return (
    <div className="auth-shell">
      <h1 className="form-title">Complete profile</h1>
      <p className="muted">Provide the remaining details to finish sign-up.</p>
      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name">Full name</label>
          <input id="name" name="name" required value={form.name} onChange={handleChange} />
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
        <div className="actions">
          <button className="primary" type="submit">
            Save and continue
          </button>
        </div>
      </form>
    </div>
  );
};

export default CompleteProfile;
