import { writable } from "svelte/store";

// Bumped whenever a log is created. LogsPanel refetches.
export const logsVersion = writable(0);
export function bumpLogs() {
  logsVersion.update((v) => v + 1);
}

// Bumped whenever user state changes (xp, build_points, attributes...). Dashboard/MePage refetch.
export const userVersion = writable(0);
export function bumpUser() {
  userVersion.update((v) => v + 1);
}

// A page that has a step of its own to undo (a selected action, say) claims
// Android's back button while it is open: the handler returns true when it
// handled the press, and App only goes home when nobody did.
let backHandler: (() => boolean) | null = null;
export function setBackHandler(fn: (() => boolean) | null) {
  backHandler = fn;
}
export function handleBack(): boolean {
  return backHandler ? backHandler() : false;
}
