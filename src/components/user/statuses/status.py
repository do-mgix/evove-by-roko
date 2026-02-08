from datetime import datetime, timedelta


class Status:
    DURATION_MAP = {
        0: timedelta(minutes=30),
        1: timedelta(hours=3),
        2: timedelta(days=1),
        3: timedelta(days=5),
    }

    def __init__(self, sid, name, duration_type, param_links=None, active_from=None, active_until=None):
        if duration_type not in self.DURATION_MAP:
            raise ValueError(f"Invalid duration type: {duration_type}")
        self._id = sid
        self._name = name
        self._duration_type = duration_type
        self._param_links = list(param_links or [])
        self._active_from = active_from
        self._active_until = active_until

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def duration_type(self):
        return self._duration_type

    @property
    def active_until(self):
        return self._active_until

    def add_param_link(self, param_id, value):
        self._param_links.append({"param_id": param_id, "value": value})

    def activate(self, now=None):
        now = now or datetime.now()
        duration = self.DURATION_MAP[self._duration_type]
        self._active_from = now
        self._active_until = now + duration

    def clean(self):
        self._active_from = None
        self._active_until = None

    def is_active(self, now=None):
        if not self._active_until:
            return False
        now = now or datetime.now()
        return now < self._active_until

    def remaining_str(self, now=None):
        if not self._active_until:
            return "inactive"
        now = now or datetime.now()
        remaining = self._active_until - now
        if remaining.total_seconds() <= 0:
            return "expired"
        total_seconds = int(remaining.total_seconds())
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        if days > 0:
            return f"{days}d {hours}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "duration_type": self.duration_type,
            "param_links": self._param_links,
            "active_from": self._active_from.isoformat() if self._active_from else None,
            "active_until": self._active_until.isoformat() if self._active_until else None,
        }

    @classmethod
    def from_dict(cls, data):
        active_from = data.get("active_from")
        active_until = data.get("active_until")
        af = datetime.fromisoformat(active_from) if active_from else None
        au = datetime.fromisoformat(active_until) if active_until else None
        return cls(
            data["id"],
            data["name"],
            data["duration_type"],
            data.get("param_links", []),
            active_from=af,
            active_until=au,
        )
