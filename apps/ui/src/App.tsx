import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useLlmMode } from "@/hooks/useLlmMode";
import { useTheme } from "@/hooks/useTheme";
import { LoginPage } from "@/pages/LoginPage";
import { ChatPage } from "@/pages/ChatPage";

export function App() {
  const { isAuthenticated, isLoading, user, login, logout } = useAuth();
  const themeState = useTheme();
  const llmMode = useLlmMode();

  if (isLoading) {
    return (
      <div style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
        color: "var(--color-text-secondary)",
        fontSize: "0.875rem",
      }}>
        Loading...
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to="/" replace />
            ) : (
              <LoginPage onLogin={login} theme={themeState} />
            )
          }
        />
        <Route
          path="/*"
          element={
            isAuthenticated ? (
              <ChatPage user={user!} onLogout={logout} theme={themeState} llmMode={llmMode} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
