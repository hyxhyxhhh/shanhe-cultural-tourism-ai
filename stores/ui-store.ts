import { create } from "zustand";

interface UIState {
  sidebarCollapsed: boolean;
  notificationOpen: boolean;
  currentProjectId: string;
  toggleSidebar: () => void;
  setNotificationOpen: (open: boolean) => void;
  setCurrentProjectId: (projectId: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  notificationOpen: false,
  currentProjectId: "sh-xi-001",
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setNotificationOpen: (notificationOpen) => set({ notificationOpen }),
  setCurrentProjectId: (currentProjectId) => set({ currentProjectId })
}));
