'use client';

import { createContext, useContext, useEffect, useState } from 'react';

interface User {
  id: number;
  email: string;
  full_name: string;
  company_name: string | null;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  company_name: string;
  role?: string;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('vc_token');
    const storedUser = localStorage.getItem('vc_user');
    if (stored && storedUser) {
      setToken(stored);
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        // Corrupted storage — clear it
        localStorage.removeItem('vc_token');
        localStorage.removeItem('vc_user');
      }
    }
    setIsLoading(false);
  }, []);

  const _storeSession = (accessToken: string, userData: User) => {
    setToken(accessToken);
    setUser(userData);
    localStorage.setItem('vc_token', accessToken);
    localStorage.setItem('vc_user', JSON.stringify(userData));
  };

  const login = async (email: string, password: string) => {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid email or password.');
    }
    const data = await res.json();

    // Fetch full user profile to get all fields including company_name
    const me = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    if (!me.ok) throw new Error('Failed to load user profile.');
    const userData: User = await me.json();

    _storeSession(data.access_token, userData);
  };

  const register = async (data: RegisterData) => {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      // Pydantic validation errors come as a list
      if (Array.isArray(err.detail)) {
        throw new Error(err.detail.map((e: { msg: string }) => e.msg).join(' '));
      }
      throw new Error(err.detail || 'Registration failed.');
    }
    const tokenData = await res.json();

    // Fetch full profile after registration
    const me = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${tokenData.access_token}` },
    });
    if (!me.ok) throw new Error('Failed to load user profile.');
    const userData: User = await me.json();

    _storeSession(tokenData.access_token, userData);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('vc_token');
    localStorage.removeItem('vc_user');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
