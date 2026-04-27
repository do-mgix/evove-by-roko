import os
from datetime import datetime

AGENDA_FILE = "/home/mgix/journal/evove-agenda"

_DAY_NAMES = ("SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM")


def _parse_hhmm(s):
    """Converts '0500' or '05:00' to minutes-since-midnight. Returns None on failure."""
    s = s.strip()
    try:
        if ":" in s:
            h, m = s.split(":", 1)
            return int(h) * 60 + int(m)
        if len(s) == 4:
            return int(s[:2]) * 60 + int(s[2:])
        if len(s) == 3:
            return int(s[:1]) * 60 + int(s[1:])
    except (ValueError, IndexError):
        pass
    return None


def parse_agenda(path=None):
    """
    Parses evove-agenda file.
    Returns dict: {day: [(start_str, end_str, label), ...]}
    """
    path = path or AGENDA_FILE
    result = {d: [] for d in _DAY_NAMES}
    if not os.path.isfile(path):
        return result

    current_day = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                upper = line.upper()
                if upper in _DAY_NAMES:
                    current_day = upper
                    continue
                if current_day is None:
                    continue
                # Expect "HHMM-HHMM : LABEL"
                if "-" not in line:
                    continue
                dash_idx = line.index("-")
                colon_idx = line.find(":", dash_idx)
                if colon_idx == -1:
                    continue
                time_part = line[:colon_idx].strip()
                label = line[colon_idx + 1:].strip()
                if "-" not in time_part:
                    continue
                start_s, end_s = time_part.split("-", 1)
                start_s = start_s.strip()
                end_s = end_s.strip()
                if _parse_hhmm(start_s) is None or _parse_hhmm(end_s) is None:
                    continue
                result[current_day].append((start_s, end_s, label))
    except OSError:
        pass

    return result


def get_today_schedule(agenda=None, now=None):
    """
    Returns (day_name, items, active_index) for the current day.
    items is a list of (start_str, end_str, label).
    active_index is None if no block is currently active.
    """
    if agenda is None:
        agenda = parse_agenda()
    if now is None:
        now = datetime.now()

    day_name = _DAY_NAMES[now.weekday()]
    items = agenda.get(day_name, [])
    current_min = now.hour * 60 + now.minute
    active_idx = None

    for i, (start_s, end_s, _label) in enumerate(items):
        s = _parse_hhmm(start_s)
        e = _parse_hhmm(end_s)
        if s is None or e is None:
            continue
        if s < e:
            if s <= current_min < e:
                active_idx = i
                break
        else:
            # Overnight span (e.g. 2200-0600)
            if current_min >= s or current_min < e:
                active_idx = i
                break

    return day_name, items, active_idx
