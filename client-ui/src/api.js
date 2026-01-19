const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path, options = {}) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "include",
    ...options,
  });
  const contentType = resp.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await resp.json() : {};
  if (!resp.ok) {
    const message = data?.detail || "Request failed";
    throw new Error(message);
  }
  return data;
}

export const api = {
  loginEmail: (payload) => request("/auth/login-email", { method: "POST", body: JSON.stringify(payload) }),
  registerEmail: (payload) => request("/auth/register-email", { method: "POST", body: JSON.stringify(payload) }),
  completeProfile: (payload) => request("/auth/complete-profile", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request("/me"),
};
