class Attribute:
    SCORE_POWER_FACTOR = 12
    # construtor do Atributo
    def __init__(self, attr_id, attr_name, related_actions=None, children=None, parent=None):
        self._attr_id = attr_id
        self._attr_name = attr_name
        self._parent = parent if parent is not None else []
        self._children = children if children is not None else []
        self._related_actions = []
        # Store incoming related action IDs temporarily; they will be resolved after actions are loaded
        self._related_action_ids = related_actions if related_actions is not None else []
        self._power = 0
    

    # Append de child 
    def add_child(self, child_attribute: 'Attribute'):
        if child_attribute not in self._children:
            self._children.append(child_attribute)
            child_attribute.parent = self # Ensure child also knows its parent
    
    @property
    def attr_name(self):
        return self._attr_name

    @property
    def attr_id(self):
        return self._attr_id

    @property
    def parent(self):
        return self._parent

    @property
    def children(self):
        return self._children

    @property
    def related_actions(self):
        return self._related_actions

    @property
    def power(self):
        return self._power


    # certificar que um atributo pai não possui ações relacionadas ( para não contar dobrado )
    @related_actions.setter
    def related_actions(self, actions: list):
        if self._children:
            raise ValueError("A parent attribute cannot have related actions.")
        self._related_actions = actions

    # getter de score = soma dos scores das ações - Verifica casos de parent e child
    @property
    def total_score(self) -> float: 
        total = 0.0
        if self.children:                         
            for child in self.children:
                total += child.total_score
        else: 
            # Como related_actions é uma lista, somamos o score de cada ação nela
            if self.related_actions:
                total = sum(action.score for action in self._related_actions)
        return total


    # tratamento visual de power
    @property
    def power_display(self) -> str:
        return f"{self._power / 1000}%"

    def AddRelatedAction(self, action):
        """Add an Action object to the related actions list.
        The method accepts an Action instance; the caller should ensure the object is valid.
        """
        self._related_actions.append(action)
        
    # json things - tranformar em dict
    def to_dict(self):
        return {
            "id": self.attr_id,
            "name": self.attr_name,
            "related_actions": [a.id for a in self._related_actions],
            "children": [c.id for c in self._children],
            "parent": [p.id for p in self._parent],
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
