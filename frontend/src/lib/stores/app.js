/**
 * App-level state stores.
 */
import { writable } from 'svelte/store';

// Current active view
export const activeView = writable('remote'); // remote | channels | epg | timers | settings

// Sidebar visibility (mobile)
export const sidebarOpen = writable(false);

// Toast notifications
export const toasts = writable([]);

let toastId = 0;

export function showToast(message, type = 'success', duration = 3000) {
  const id = ++toastId;
  toasts.update(t => [...t, { id, message, type }]);
  setTimeout(() => {
    toasts.update(t => t.filter(toast => toast.id !== id));
  }, duration);
}
