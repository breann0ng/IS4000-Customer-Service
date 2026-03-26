import { useState } from "react";
import type { FormEvent } from "react";
import { SunIcon, MoonIcon } from "@radix-ui/react-icons";
import styles from "./LoginPage.module.css";

interface LoginPageProps {
  onLogin: (username: string, password: string) => Promise<void>;
  theme: { theme: "light" | "dark"; toggleTheme: () => void };
}

export function LoginPage({ onLogin, theme }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await onLogin(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={styles.container}>
      <button
        className={styles.themeToggle}
        onClick={theme.toggleTheme}
        aria-label="Toggle theme"
      >
        {theme.theme === "dark" ? <SunIcon width={18} height={18} /> : <MoonIcon width={18} height={18} />}
      </button>

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.logo}>
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
            <rect width="40" height="40" rx="8" fill="var(--color-accent)" />
            <path d="M12 20h16M20 12v16" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
        </div>
        <h1 className={styles.title}>Welcome back</h1>
        <p className={styles.subtitle}>Sign in to Customer Service Portal</p>

        {error && <div className={styles.error}>{error}</div>}

        <label className={styles.label}>
          <span>Username</span>
          <input
            className={styles.input}
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Enter your username"
            required
            autoFocus
          />
        </label>

        <label className={styles.label}>
          <span>Password</span>
          <input
            className={styles.input}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter your password"
            required
          />
        </label>

        <button className={styles.button} type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Continue"}
        </button>

        <p className={styles.hint}>
          Demo: jsmith / password123
        </p>
      </form>
    </div>
  );
}
