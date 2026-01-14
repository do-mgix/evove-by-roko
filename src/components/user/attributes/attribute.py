class Attribute:
    SCORE_POWER_FACTOR = 12
    # construtor do Atributo
    def __init__(self, aid, name, related_actions=None, children=None, parent=None):
        self._id = aid
        self._name = name
        self._parent = parent if parent is not None else []
        self._children = children if children is not None else []
        self._related_actions = []
        self._related_action_ids = related_actions if related_actions is not None else []
        self._children_ids = children if children is not None else []
        self._parent_ids = parent if parent is not None else []
        self._power = 0
    
    @property
    def power(self):
        if self._related_actions:
            return sum(action.score for action in self._related_actions)
        else:
            return 0.0

    # getter de score = soma dos scores das ações - Verifica casos de parent e child
    @property
    def total_score(self) -> float: 
        if self._children:                         
            return sum(child.power for child in self._children)
        else:         
            return self.power

    # tratamento visual de power
    @property
    def power_display(self) -> str:
        return f"{self._power / 1000}%"

    def add_related_action(self, action):
        if self._children:
            raise ValueError("A parent attribute cannot have related actions.")
        self._related_actions.append(action)

    def set_parent(self, parent):
        if parent not in self._parent:
            self._parent.append(parent)            

    def add_child(self, child_attribute):
        if child_attribute not in self._children:
            print(child_attribute)
            self._children.append(child_attribute)
            child_attribute.set_parent(self) # Ensure child also knows its parent       


    # json things - tranformar em dict
    def to_dict(self):
        return {
            "id": self._id,
            "name": self._name,
            "related_actions": [a.id for a in self._related_actions],            
            "children": [c._id for c in self._children],
            "parent": [p._id for p in self._parent],
            "total_score": self.total_score,
        }

    @classmethod
    def from_dict(cls, data):
        # related_actions from JSON are IDs; they will be resolved later
        attr = cls(
            data["id"],
            data["name"],
            data.get("related_actions", []),
            data.get("children", []),
            data.get("parent", []),
        )
        return attr

    def resolve_related_actions(self, actions_dict: dict):
        """Resolve stored related action IDs to Action objects.
        `actions_dict` should map action IDs to Action instances.
        """
        for aid in getattr(self, "_related_action_ids", []):
            action = actions_dict.get(aid)
            if action:
                self._related_actions.append(action)
        if hasattr(self, "_related_action_ids"):
            del self._related_action_ids


    def resolve_children(self, children_dict: dict):
        for cid in getattr(self, "_children_ids", []):
            child = children_dict.get(cid)
            if child:
                self._children.append(child)
        if hasattr(self, "_children_ids"):
            del self._children_ids

    def resolve_parent(self, parent_dict: dict):
        for pid in getattr(self, "_parent_ids", []):
            parent = parent_dict.get(pid)
            if parent:
                self._parent.append(parent)
        if hasattr(self, "_parent_ids"):
            del self._parent_ids            
