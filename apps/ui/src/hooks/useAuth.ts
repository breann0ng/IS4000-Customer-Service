import { useCallback, useEffect, useState } from "react";
import "@/api/client";
import {
  loginApiAuthLoginPost,
  getProfileApiAuthMeGet,
} from "@/api/generated";
import type { UserProfile } from "@/api/generated";

interface AuthState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    try {
      const { data } = await getProfileApiAuthMeGet({ throwOnError: true });
      setUser(data);
    } catch {
      localStorage.removeItem("access_token");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const { data: tokenData } = await loginApiAuthLoginPost({
        throwOnError: true,
        body: { username, password },
      });
      localStorage.setItem("access_token", tokenData.access_token);
      const { data: profile } = await getProfileApiAuthMeGet({ throwOnError: true });
      setUser(profile);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    setUser(null);
  }, []);

  return {
    user,
    isAuthenticated: user !== null,
    isLoading,
    error,
    login,
    logout,
  };
}
