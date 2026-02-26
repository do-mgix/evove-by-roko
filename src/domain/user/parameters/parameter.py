from datetime import datetime


class Parameter:
    VALUE_TYPES = {
        1: "mark",
        2: "percentage",
    }
    LOGIC_TYPES = {
        1: "Emotional",
        2: "Ambiental",
        3: "Fisiologic",
    }
    REGEN_TYPES = {
        1: "regen",
        2: "decay",
    }
    PERCENT_FACTORS = {
        1: 5,
        2: 10,
        3: 15,
        4: 20,
        5: 25,
    }
    MARK_FACTORS_PER_HOUR = {
        1: 1 / 24,
        2: 1 / 12,
        3: 1 / 6,
        4: 1 / 3,
        5: 1 / 1.5,
        6: 1 / 0.75,
    }

    def __init__(
        self,
        pid,
        name,
        value_type,
        logic_type,
        value=0,
        regen_type=None,
        regen_factor=None,
        last_check=None,
    ):
        if value_type not in self.VALUE_TYPES:
            raise ValueError(f"Invalid value type: {value_type}")
        if logic_type not in self.LOGIC_TYPES:
            raise ValueError(f"Invalid logic type: {logic_type}")
        self._id = pid
        self._name = name
        self._value_type = value_type
        self._logic_type = logic_type
        self._value = self._clamp_value(value)
        self._regen_type = regen_type
        self._regen_factor = regen_factor
        self._last_check = last_check

    def _clamp_value(self, value):
        try:
            val = float(value)
        except Exception:
            val = 0.0
        if self._value_type == 1:
            return max(-3.0, min(3.0, val))
        return max(0.0, min(100.0, val))

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def value_type(self):
        return self._value_type

    @property
    def logic_type(self):
        return self._logic_type

    @property
    def value(self):
        return self._value

    def set_value(self, value):
        self._value = self._clamp_value(value)

    def set_regen(self, regen_type, regen_factor, start_value, now=None):
        if regen_type not in self.REGEN_TYPES:
            raise ValueError(f"Invalid regen type: {regen_type}")
        if self._value_type == 1:
            if regen_factor not in self.MARK_FACTORS_PER_HOUR:
                raise ValueError(f"Invalid mark regen factor: {regen_factor}")
        else:
            if regen_factor not in self.PERCENT_FACTORS:
                raise ValueError(f"Invalid percent regen factor: {regen_factor}")
        self._regen_type = regen_type
        self._regen_factor = regen_factor
        self._value = self._clamp_value(start_value)
        now = now or datetime.now()
        self._last_check = now

    def update_value(self, now=None):
        if not self._regen_type or not self._regen_factor:
            return False
        now = now or datetime.now()
        last = self._last_check or now
        elapsed = (now - last).total_seconds() / 3600
        if elapsed <= 0:
            self._last_check = now
            return False

        if self._value_type == 1:
            rate = self.MARK_FACTORS_PER_HOUR.get(self._regen_factor, 0)
            delta = elapsed * rate
        else:
            rate = self.PERCENT_FACTORS.get(self._regen_factor, 0)
            delta = elapsed * rate

        if self._regen_type == 2:
            delta = -delta

        new_value = self._value + delta
        self._value = self._clamp_value(new_value)
        self._last_check = now
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "value_type": self.value_type,
            "logic_type": self.logic_type,
            "value": self.value,
            "regen_type": self._regen_type,
            "regen_factor": self._regen_factor,
            "last_check": self._last_check.isoformat() if self._last_check else None,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["id"],
            data["name"],
            data["value_type"],
            data["logic_type"],
            data.get("value", 0),
            data.get("regen_type"),
            data.get("regen_factor"),
            datetime.fromisoformat(data["last_check"]) if data.get("last_check") else None,
        )
