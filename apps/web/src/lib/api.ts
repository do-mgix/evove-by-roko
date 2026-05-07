const BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";

const STORAGE_KEY = "roko_username";

export function getUsername(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}
export function setUsername(name: string) {
  localStorage.setItem(STORAGE_KEY, name);
}
export function clearUsername() {
  localStorage.removeItem(STORAGE_KEY);
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const username = getUsername();
  const headers = new Headers(init.headers);
  if (username) headers.set("X-Evove-Username", username);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(`${BASE}${path}`, { ...init, headers });
}

export type Action = {
  id: string;
  name: string;
  type: number;
  diff: number;
  value: number;
  score: number;
};

export async function fetchActions(): Promise<Action[]> {
  const res = await request("/actions");
  if (!res.ok) throw new Error(`Failed to fetch actions (${res.status})`);
  return res.json();
}

export type ActResult = {
  id: string;
  name: string;
  value: number;
  score: number;
  score_diff: number;
  user_score: number;
};

export async function actOnAction(id: string, opts: { value?: number; note?: string } = {}): Promise<ActResult> {
  const res = await request(`/actions/${id}/act`, { method: "POST", body: JSON.stringify(opts) });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to act (${res.status})`);
  }
  return res.json();
}

export type UserState = {
  username: string;
  day: number;
  consecutive_days: number;
  xp: number;
  level: number;
  rank_letter: string;
  rank_symbol: string;
  local_level_roman: string;
  local_levels_total: number;
  next_xp: number;
  xp_cost: number;
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

export type Attribute = {
  id: string;
  name: string;
  total_score: number;
  related_actions_count: number;
};

export async function fetchAttributes(): Promise<Attribute[]> {
  const res = await request("/attributes");
  if (!res.ok) throw new Error(`Failed to fetch attributes (${res.status})`);
  return res.json();
}

export type LogEntry = {
  id: number;
  timestamp: string;
  content: string;
  xp: number;
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

export async function fetchUsers(): Promise<string[]> {
  const res = await request("/users");
  if (!res.ok) throw new Error(`Failed to fetch users (${res.status})`);
  return res.json();
}

export type PackageAction = {
  name: string;
  type: number;
  diff: number;
  cost: number;
  token_cost?: number;
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

export async function createUser(name: string): Promise<{ name: string }> {
  const res = await request("/users", { method: "POST", body: JSON.stringify({ name }) });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Failed to create user (${res.status})`);
  }
  return res.json();
}
