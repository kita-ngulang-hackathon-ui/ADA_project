"use client";

// Login (entry page). Standalone (no app shell) — it sits outside the (console) group.
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!email || !password) {
      setError("Enter your email and password to continue.");
      return;
    }

    // TODO: call the console API session endpoint via lib/api.ts.
    setError(null);
    router.push("/dashboard");
  }

  return (
    <div className="login-page">
      <div className="login-left">
        <div className="login-form-wrap">
          <form className="login-form" onSubmit={onSubmit} noValidate>
            <h1 className="login-title">Welcome Back</h1>
            <p className="login-subtitle">
              Enter your email and password to continue to your account
            </p>

            {error && (
              <p className="login-error" role="alert">
                {error}
              </p>
            )}

            <div className="login-field">
              <label className="label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                className="input login-input"
                placeholder="example@gmail.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </div>

            <div className="login-field">
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                className="input login-input"
                placeholder="Enter your password..."
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>

            <div className="login-options">
              <label className="login-remember" htmlFor="remember">
                <input
                  id="remember"
                  name="remember"
                  type="checkbox"
                  className="login-checkbox"
                  checked={remember}
                  onChange={(event) => setRemember(event.target.checked)}
                />
                Remember me
              </label>

              <a className="login-forgot" href="#">
                Forgot Your Password?
              </a>
            </div>

            <button type="submit" className="button-primary login-submit">
              Log In
            </button>
          </form>
        </div>

        <footer className="login-footer">
          <span>Copyright © Kita Ngulang LTD.</span>
          <a href="#">Privacy Policy</a>
        </footer>
      </div>

      <div className="login-right">
        <p className="login-tagline">
          Manage your financial technology enterprise with
        </p>

        <div className="w-full">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/ada-logo-full.png"
            alt="ADA Solutions"
            className="login-brand-logo mx-auto"
          />
        </div>
      </div>
    </div>
  );
}
