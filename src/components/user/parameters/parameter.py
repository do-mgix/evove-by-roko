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

    def __init__(self, pid, name, value_type, logic_type, value=0):
        if value_type not in self.VALUE_TYPES:
            raise ValueError(f"Invalid value type: {value_type}")
        if logic_type not in self.LOGIC_TYPES:
            raise ValueError(f"Invalid logic type: {logic_type}")
        self._id = pid
        self._name = name
        self._value_type = value_type
        self._logic_type = logic_type
        self._value = self._clamp_value(value)

    def _clamp_value(self, value):
        if self._value_type == 1:
            return max(-3, min(3, int(value)))
        return max(0, min(100, int(value)))

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

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "value_type": self.value_type,
            "logic_type": self.logic_type,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["id"],
            data["name"],
            data["value_type"],
            data["logic_type"],
            data.get("value", 0),
        )
