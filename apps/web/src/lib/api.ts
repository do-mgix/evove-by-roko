const BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";
export const API_BASE = BASE;

const TOKEN_KEY = "roko_token";
const USER_KEY = "roko_username";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
export function getUsername(): string | null {
  try {
    return localStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
}
export function setSession(token: string, username: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, username);
  } catch {
    /* private mode: the session lives for this page only */
  }
}
export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    /* nothing to clear */
  }
}

/** Called when the server rejects our session, so the app can show the login
 *  screen instead of every panel erroring on its own. */
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    clearSession();
    onUnauthorized?.();
  }
  return res;
}

export type Session = { token: string; username: string; expires_at: string };

async function authCall(path: string, username: string, password: string): Promise<Session> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `falhou (${res.status})`);
  setSession(body.token, body.username);
  return body;
}

export function login(username: string, password: string): Promise<Session> {
  return authCall("/auth/login", username, password);
}

export function register(username: string, password: string): Promise<Session> {
  return authCall("/auth/register", username, password);
}

export async function logout(): Promise<void> {
  try {
    await request("/auth/logout", { method: "POST" });
  } finally {
    clearSession();
  }
}

/** Revokes every session of the profile, on every device, this one included. */
export async function logoutEverywhere(): Promise<void> {
  try {
    await request("/auth/logout-all", { method: "POST" });
  } finally {
    clearSession();
  }
}

export type SessionInfo = {
  user_id: number;
  username: string;
  created_at: string;
  session: { created_at: string; expires_at: string };
  active_sessions: number;
};

export async function fetchSessionInfo(): Promise<SessionInfo> {
  const res = await request("/auth/me");
  if (!res.ok) throw new Error(`Failed to fetch session (${res.status})`);
  return res.json();
}

/** "5010108" -> "5 01 01 08": action · parent class · child class · position.
 *  Anything that is not a 7-digit action code, or a prefix of one, passes through. */
export function formatCode(code: string | null | undefined): string {
  const s = String(code ?? "");
  if (!/^5\d{0,8}$/.test(s)) return s;
  const head = [s.slice(0, 1), s.slice(1, 3), s.slice(3, 5), s.slice(5, 7)].filter(Boolean).join(" ");
  // a patch: the base's seven digits, then its own two
  return s.length > 7 ? `${head} · ${s.slice(7, 9)}` : head;
}

export type Action = {
  id: string;
  name: string;
  type: number;
  diff: number;
  value: number;
  score: number;
  token_cost: number;
  token_gain: number;
  tiers?: TierOption[];
  // root first, down to the attribute it is registered under; a patch's is its base's
  path?: { key: string; name: string }[];
  // the leaves it feeds and their weights; a patch's are its base's
  leaves?: { key: string; name: string; weight: number }[];
  // patches only; `weight` is the share of the patch's marks the attribute receives
  base_action_id?: string;
  attributes?: { id: number; name: string; weight: number }[];
};

export async function fetchActions(): Promise<Action[]>{
  const res = await request("/actions");
  if (!res.ok) throw new Error(`Failed to fetch actions (${res.status})`);
  return res.json();
};

export type ActResult = {
  id: string;
  name: string;
  value: number;          // executions of this action
  score: number;          // marks earned on this action
  marks: number;          // marks this act yielded
  nominal: number;        // marks the chosen tier is worth on its own
  window_marks: number;   // marks in the action's window after this act
  window_limit: number;
  user_marks: number;
  token_gain: number;
  token_cost: number;
  tokens_wasted: number;
  tokens: number;
};

export async function actOnAction(id: string, opts: { option: number; note?: string }): Promise<ActResult> {
  const res = await request(`/actions/${id}/act`, { method: "POST", body: JSON.stringify(opts) });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to act (${res.status})`);
  }
  return res.json();
}

/** One of an action's six tiers. `marks` is what it is worth on its own; the
 *  window may pay less. */
export type TierOption = { index: number; label: string; marks: number };

export async function fetchActionWindow(id: string): Promise<{ window_marks: number; limit: number; hours: number; options: TierOption[] }> {
  const res = await request(`/actions/${id}/window`);
  if (!res.ok) throw new Error(`Failed to fetch window (${res.status})`);
  return res.json();
}

export type UserState = {
  username: string;
  day: number;
  consecutive_days: number;
  marks: number;
  level: number;
  rank_letter: string;
  rank_symbol: string;
  local_level_roman: string;
  local_levels_total: number;
  next_marks: number;
  level_cost: number;
  level_marks: number;
  stage: number;
  energy: number;
  skill_points: number;
  build_points: number;
  tokens: number;
  max_tokens: number;
  days_until_next_checkpoint: number;
  attributes_count: number;
  max_energy?: number;
  bonuses?: { max_energy: number; max_tokens: number; xp_multiplier: number; points_multiplier: number };
};

export async function fetchUser(): Promise<UserState> {
  const res = await request("/user");
  if (!res.ok) throw new Error(`Failed to fetch user (${res.status})`);
  return res.json();
}

/** Any attribute. All of them are the same kind of thing; a leaf is simply one
 *  with no children, and only leaves hold a score. `level` is null when the
 *  node has no leveled leaves carrying enough of its weight. */
export type AttrNode = {
  key: string;
  name: string;
  degree: number;
  is_leaf: boolean;
  rank: string;          // A..Z, a permanent checkpoint
  rank_index: number;
  marks: number;         // whole marks above the rank
  need: number;          // marks this rank asks for
  total_marks: number;
  max: boolean;          // Z completed
  // in /attributes/tree, on every child
  weight?: number;
  primary?: boolean;
  children?: AttrNode[];
  // under the registered parent of a base action: the patches that sit there
  patches?: PatchAttachment[];
  // a user attribute drawn by the same component
  custom?: boolean;
};

/** An attribute the user created. Leaves hold the score; a parent is the mean of
 *  its children. */
export type UserAttribute = {
  id: number;
  name: string;
  parent_id: number | null;
  is_leaf: boolean;
  rank: string;
  rank_index: number;
  marks: number;
  need: number;
  total_marks: number;
  max: boolean;
  children: UserAttribute[];
  patches?: { id: string; name: string; weight: number }[];
};

export type PatchAttachment = { id: string; name: string; attributes: UserAttribute[] };

/** Leaves, strongest first. */
export async function fetchAttributes(): Promise<AttrNode[]> {
  const res = await request("/attributes");
  if (!res.ok) throw new Error(`Failed to fetch attributes (${res.status})`);
  return res.json();
}

/** Every root with its power and aggregated level. */
export async function fetchAttributeRoots(): Promise<AttrNode[]> {
  const res = await request("/attributes/roots");
  if (!res.ok) throw new Error(`Failed to fetch attribute roots (${res.status})`);
  return res.json();
}

export async function fetchAttributeTree(): Promise<{ roots: AttrNode[] }> {
  const res = await request("/attributes/tree");
  if (!res.ok) throw new Error(`Failed to fetch tree (${res.status})`);
  return res.json();
}

/** A leaf that recently gained marks, from the graph or the user's own (`custom`).
 *  `seconds_ago` is measured on the server. */
export type RecentAttribute = AttrNode & { parent: string | null; seconds_ago: number };

export async function fetchRecentAttributes(limit = 10): Promise<RecentAttribute[]> {
  const res = await request(`/attributes/recent?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch recent attributes (${res.status})`);
  return res.json();
}

async function sendJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await request(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `falhou (${res.status})`);
  return data as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return sendJson<T>("POST", path, body);
}

/** Rename, or move under another attribute — `null` makes it a root. */
export function updateUserAttribute(id: number, change: { name?: string; parent_id?: number | null }) {
  return sendJson<{ id: number; name: string; parent_id: number | null }>("PATCH", `/user-attributes/${id}`, change);
}

/** Rename, or replace the attributes it trains. */
export function updatePatch(id: string, change: { name?: string; attribute_ids?: number[] }) {
  return sendJson<{ id: string; name: string; attribute_ids: number[] }>("PATCH", `/patches/${id}`, change);
}

/** The share of the patch's marks one of its attributes receives, above 0 and at most 1. */
export function setPatchWeight(patchId: string, attributeId: number, weight: number) {
  return sendJson<{ weight: number }>("PUT", `/patches/${patchId}/attributes/${attributeId}`, { weight });
}

export function unlinkPatchAttribute(patchId: string, attributeId: number) {
  return sendJson<{ ok: boolean }>("DELETE", `/patches/${patchId}/attributes/${attributeId}`);
}

export async function fetchUserAttributes(): Promise<UserAttribute[]> {
  const res = await request("/user-attributes");
  if (!res.ok) throw new Error(`Failed to fetch user attributes (${res.status})`);
  return res.json();
}

export function createUserAttribute(name: string, parentId: number | null) {
  return postJson<{ id: number; name: string; parent_id: number | null }>(
    "/user-attributes", { name, parent_id: parentId });
}

export function createPatch(body: {
  base_action_id: string;
  name: string;
  attribute_ids: number[];
  new_attributes: string[];
}) {
  return postJson<{ id: string; name: string; cost: number; build_points: number }>("/patches", body);
}

/** Every user attribute once, with its path, for pickers. */
export function flattenUserAttributes(list: UserAttribute[], parentPath = ""): { id: number; name: string; path: string }[] {
  const out: { id: number; name: string; path: string }[] = [];
  for (const a of list) {
    const path = parentPath ? `${parentPath} › ${a.name}` : a.name;
    out.push({ id: a.id, name: a.name, path });
    out.push(...flattenUserAttributes(a.children, path));
  }
  return out;
}

/** A user attribute in the shape AttrTree renders, so one component draws both trees. */
export function userAttrAsNode(a: UserAttribute): AttrNode {
  return {
    key: `user:${a.id}`,
    name: a.name,
    degree: 0,
    is_leaf: a.is_leaf,
    rank: a.rank,
    rank_index: a.rank_index,
    marks: a.marks,
    need: a.need,
    total_marks: a.total_marks,
    max: a.max,
    custom: true,
    children: a.children.map(userAttrAsNode),
  };
}

/** Every attribute once, with the path to it along primary links.
 *  A node with several parents appears in the tree under each of them; here it
 *  is listed once, so it can key a list. */
export function flattenAttributeNodes(roots: AttrNode[]): { key: string; name: string; path: string }[] {
  const out = new Map<string, { key: string; name: string; path: string }>();
  const walk = (n: AttrNode, parentPath: string) => {
    const path = parentPath ? `${parentPath} › ${n.name}` : n.name;
    if (!out.has(n.key)) out.set(n.key, { key: n.key, name: n.name, path });
    for (const c of n.children ?? []) if (c.primary !== false) walk(c, path);
  };
  for (const r of roots) walk(r, "");
  return [...out.values()];
}

export type LogEntry = {
  id: number;
  timestamp: string;
  content: string;
  marks: number;
  tokens: number;
  order: number;
};

export type LogsResponse = {
  day: number;
  offset: number;
  date: string;
  logs: LogEntry[];
};

export async function fetchLogs(offset: number = 0): Promise<LogsResponse> {
  const res = await request(`/logs?offset=${offset}`);
  if (!res.ok) throw new Error(`Failed to fetch logs (${res.status})`);
  return res.json();
}

export async function deleteLog(id: number): Promise<{ ok: boolean; id: number }> {
  const res = await request(`/logs/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to delete log (${res.status})`);
  }
  return res.json();
}

export async function updateLogNote(id: number, note: string): Promise<LogEntry> {
  const res = await request(`/logs/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ note }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to update log (${res.status})`);
  }
  return res.json();
}

export async function shiftLogDay(id: number, delta: number): Promise<LogEntry> {
  const res = await request(`/logs/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ day_delta: delta }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to shift log day (${res.status})`);
  }
  return res.json();
}

export async function reorderLogs(day: number, ids: number[]): Promise<{ ok: boolean; count: number }> {
  const res = await request("/logs/reorder", {
    method: "POST",
    body: JSON.stringify({ day, ids }),
  });
  if (!res.ok) throw new Error(`Failed to reorder logs (${res.status})`);
  return res.json();
}

export type AgendaItem = {
  id?: string;
  start: string;
  end: string | null;
  day?: string;
  label: string;
  label_kind?: string;
  label_id?: string | null;
};
export type AgendaToday = { day: string | null; items: AgendaItem[] };

export async function fetchAgendaToday(): Promise<AgendaToday> {
  const res = await request("/agenda/today");
  if (!res.ok) throw new Error(`Failed to fetch agenda (${res.status})`);
  return res.json();
}

export type CalendarDay = { log_count: number; events: AgendaItem[] };
export type CalendarMonth = { year: number; month: number; days: Record<string, CalendarDay> };

export async function fetchCalendar(year: number, month: number): Promise<CalendarMonth> {
  const res = await request(`/calendar?year=${year}&month=${month}`);
  if (!res.ok) throw new Error(`Failed to fetch calendar (${res.status})`);
  return res.json();
}

export async function fetchLogsByDate(isoDate: string): Promise<{ date: string; day?: number; logs: LogEntry[] }> {
  const res = await request(`/logs/by-date?date=${isoDate}`);
  if (!res.ok) throw new Error(`Failed to fetch logs (${res.status})`);
  return res.json();
}

export type Project = {
  id?: string;
  label: string;
  deadline: string | null;
  active: string;
  created_at: string | null;
};

export async function fetchProjects(): Promise<ProjectItem[]> {
  const res = await request("/projects");
  if (!res.ok) throw new Error('Failed to fetch projects ($(res.status))');
  return res.json();
}

export type JourneyState = {
  stage: number;
  days_until_next_checkpoint: number;
  interval_for_current_stage: number;
  next_checkpoint_at: string;
  seconds_left: number;
  hours_left: number;
  minutes_left: number;
};

export async function fetchJourney(): Promise<JourneyState> {
  const res = await request("/journey");
  if (!res.ok) throw new Error(`Failed to fetch journey (${res.status})`);
  return res.json();
}

export async function createAgendaItem(item: {
  start: string;
  end?: string | null;
  day: string;
  label: string;
  label_kind?: string;
  label_id?: string | null;
}): Promise<AgendaItem> {
  const res = await request("/agenda", { method: "POST", body: JSON.stringify(item) });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to add agenda item (${res.status})`);
  }
  return res.json();
}

export async function updateAgendaItem(id: string, patch: Partial<AgendaItem>): Promise<AgendaItem> {
  const res = await request(`/agenda/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to update agenda item (${res.status})`);
  }
  return res.json();
}

export async function deleteAgendaItem(id: string): Promise<void> {
  const res = await request(`/agenda/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to delete agenda item (${res.status})`);
  }
}

export type PackageAction = {
  name: string;
  code: string | null;
  type: number;
  diff: number;
  cost: number;
  token_cost?: number;
  token_gain?: number;
};
export type Package = {
  attribute: string;
  icon?: string;
  color?: string;
  actions: PackageAction[];
};

export async function fetchPackages(): Promise<Package[]> {
  const res = await request("/shop/packages");
  if (!res.ok) throw new Error(`Failed to fetch packages (${res.status})`);
  return res.json();
}

export type CatalogLeaf = { key: string; name: string; weight: number };
export type CatalogAction = {
  name: string;
  code: string | null;
  type: number;
  diff: number;
  cost: number;
  token_cost: number;
  token_gain: number;
  package_attribute: string;
  leaves: CatalogLeaf[];
};
export type CatalogGroup = { key: string; name: string; actions: CatalogAction[] };

export async function fetchShopCatalog(): Promise<CatalogGroup[]> {
  const res = await request("/shop/catalog");
  if (!res.ok) throw new Error(`Failed to fetch catalog (${res.status})`);
  return res.json();
}

export async function buyPackageAction(attribute: string, name: string): Promise<{ id: string; name: string; build_points: number }> {
  const res = await request("/shop/actions/buy", {
    method: "POST",
    body: JSON.stringify({ attribute, name }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to buy action (${res.status})`);
  }
  return res.json();
}

export type SkillNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  cost: number;
  parent: string | null;
  effect: { type: string; value: number } | null;
};
export type SkillTree = {
  nodes: SkillNode[];
  acquired: string[];
  skill_points: number;
  bonuses: { max_energy: number; max_tokens: number; xp_multiplier: number; points_multiplier: number };
};

export async function fetchSkillTree(): Promise<SkillTree> {
  const res = await request("/skills/tree");
  if (!res.ok) throw new Error(`Failed to fetch skill tree (${res.status})`);
  return res.json();
}

export async function acquireSkill(id: string): Promise<{ acquired: string[]; skill_points: number }> {
  const res = await request(`/skills/${id}/acquire`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to acquire (${res.status})`);
  }
  return res.json();
}

