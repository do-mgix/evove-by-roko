class Tag:
    def __init__(self, tid, name):
        self._id = tid
        self._name = name

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["id"],
            data["name"],
        )
