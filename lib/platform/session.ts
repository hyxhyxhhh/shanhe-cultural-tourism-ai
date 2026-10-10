"use client";

import { useSyncExternalStore } from "react";
import type { LoginResponse } from "@/lib/types/access";

const SESSION_KEY = "shanhe-session-user";
const LEGACY_SESSION_KEY = "shanhe-demo-session";
const listeners = new Set<() => void>();
let cachedValue: string | null | undefined;
let cachedSession: LoginResponse | null = null;
let restorePromise: Promise<void> | null = null;
let restorationComplete = false;

function emitChange() {
  listeners.forEach((listener) => listener());
}

export function saveDemoSession(session: LoginResponse) {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  cachedValue = undefined;
  emitChange();
}

export function getDemoSession(): LoginResponse | null {
  const value = window.localStorage.getItem(SESSION_KEY);
  if (value === cachedValue) return cachedSession;
  cachedValue = value;
  if (!value) {
    cachedSession = null;
    return null;
  }
  try {
    cachedSession = JSON.parse(value) as LoginResponse;
    return cachedSession;
  } catch {
    window.localStorage.removeItem(SESSION_KEY);
    cachedValue = null;
    cachedSession = null;
    return null;
  }
}

export function clearDemoSession() {
  window.localStorage.removeItem(SESSION_KEY);
  cachedValue = undefined;
  emitChange();
}

async function restoreSession() {
  try {
    const response = await fetch("/api/auth/me", {
      cache: "no-store",
      credentials: "same-origin"
    });
    if (!response.ok) {
      clearDemoSession();
      return;
    }
    saveDemoSession((await response.json()) as LoginResponse);
  } catch {
    // Keep the last safe user DTO during a temporary network failure. The
    // HttpOnly cookie remains the source of truth for authenticated requests.
  }
}

function ensureSessionRestored() {
  window.localStorage.removeItem(LEGACY_SESSION_KEY);
  restorePromise ??= restoreSession().finally(() => {
    restorationComplete = true;
    emitChange();
  });
}

export async function logoutDemoSession() {
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin"
    });
  } catch {
    // Local session state must still be cleared when the API is unavailable.
  } finally {
    clearDemoSession();
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  ensureSessionRestored();
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function useDemoSession() {
  return useSyncExternalStore(subscribe, getDemoSession, () => null);
}

export function useClientReady() {
  return useSyncExternalStore(subscribe, () => restorationComplete, () => false);
}
