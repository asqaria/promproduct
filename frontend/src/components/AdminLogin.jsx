import React, { useState } from "react";

export default function AdminLogin({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Hardcoded credentials
    const ADMIN_USERNAME = "admin";
    const ADMIN_PASSWORD = "Admin3216@$";

    // Simulate a small delay for better UX
    await new Promise((resolve) => setTimeout(resolve, 300));

    if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
      // Store in localStorage (not secure for production, but adequate for this use case)
      localStorage.setItem("adminToken", "authenticated");
      onLogin();
    } else {
      setError("Invalid username or password");
    }

    setLoading(false);
  };

  return (
    <div className="admin-login-container">
      <div className="login-card">
        <h2>Admin Login</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={loading}
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>
      </div>
    </div>
  );
}
