"use client";

import { useSyncExternalStore } from "react";
import { ROLE_ACCESS, WORKFLOW_IDS } from "@/lib/platform/access";
import type { PermissionMatrix, RoleAccess, UserRoleId } from "@/lib/types/access";

const PERMISSIONS_KEY = "shanhe-demo-permissions";
const listeners = new Set<() => void>();
let cachedValue: string | null | undefined;
let cachedMatrix: PermissionMatrix = ROLE_ACCESS;

function cloneAccess(access: RoleAccess): RoleAccess {
  return {
    cockpitIds: [...access.cockpitIds],
    capabilityIds: [...access.capabilityIds],
    workflowIds: access.workflowIds.filter((id) => WORKFLOW_IDS.includes(id))
  };
}

function defaultMatrix(): PermissionMatrix {
  return Object.fromEntries(
    Object.entries(ROLE_ACCESS).map(([roleId, access]) => [roleId, cloneAccess(access)])
  ) as PermissionMatrix;
}

function emitChange() {
  listeners.forEach((listener) => listener());
}

function readMatrix(): PermissionMatrix {
  const value = window.localStorage.getItem(PERMISSIONS_KEY);
  if (value === cachedValue) return cachedMatrix;
  cachedValue = value;
  if (!value) {
    cachedMatrix = defaultMatrix();
    return cachedMatrix;
  }
  try {
    const stored = JSON.parse(value) as Partial<PermissionMatrix>;
    cachedMatrix = Object.fromEntries(
      Object.entries(ROLE_ACCESS).map(([roleId, defaults]) => [
        roleId,
        cloneAccess(roleId === "platform-admin" ? defaults : (stored[roleId as UserRoleId] ?? defaults))
      ])
    ) as PermissionMatrix;
    return cachedMatrix;
  } catch {
    window.localStorage.removeItem(PERMISSIONS_KEY);
    cachedValue = null;
    cachedMatrix = defaultMatrix();
    return cachedMatrix;
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function usePermissionMatrix() {
  return useSyncExternalStore(subscribe, readMatrix, () => ROLE_ACCESS);
}

export function useRoleAccess(roleId?: UserRoleId) {
  const matrix = usePermissionMatrix();
  return roleId ? matrix[roleId] : null;
}

export function saveRoleAccess(roleId: UserRoleId, access: RoleAccess) {
  if (roleId === "platform-admin") return;
  const matrix = readMatrix();
  const next: PermissionMatrix = { ...matrix, [roleId]: cloneAccess(access) };
  window.localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(next));
  cachedValue = undefined;
  emitChange();
}

export function resetRoleAccess(roleId: UserRoleId) {
  if (roleId === "platform-admin") return;
  saveRoleAccess(roleId, ROLE_ACCESS[roleId]);
}
