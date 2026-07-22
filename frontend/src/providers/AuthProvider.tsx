"use client";

import { createContext, useContext, useState, useEffect } from "react";
import { User } from "@/types";
import { api } from "@/lib/api";
import { useRouter, usePathname } from "next/navigation";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem("aca_token");
      if (token) {
        try {
          const userData = await api.getMe();
          setUser(userData);
        } catch (error) {
          localStorage.removeItem("aca_token");
        }
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  // Protect routes
  useEffect(() => {
    if (!loading) {
      const isAuthRoute = pathname.startsWith("/login") || pathname.startsWith("/register");
      const isDashboardRoute = pathname.startsWith("/dashboard");

      if (!user && isDashboardRoute) {
        router.push("/login");
      } else if (user && isAuthRoute) {
        router.push("/dashboard");
      }
    }
  }, [user, loading, pathname, router]);

  const login = async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    localStorage.setItem("aca_token", access_token);
    const userData = await api.getMe();
    setUser(userData);
  };

  const register = async (name: string, email: string, password: string) => {
    const { access_token } = await api.register(name, email, password);
    localStorage.setItem("aca_token", access_token);
    const userData = await api.getMe();
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem("aca_token");
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        loading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
