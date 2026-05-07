import { writable } from "svelte/store";

// Bumped whenever a log is created. LogsPanel refetches.
export const logsVersion = writable(0);
export function bumpLogs() {
  logsVersion.update((v) => v + 1);
}

// Bumped whenever user state changes (xp, build_points, attributes...). UserPanel/Dashboard refetch.
export const userVersion = writable(0);
export function bumpUser() {
  userVersion.update((v) => v + 1);
}
