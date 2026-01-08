class Attribute:
    SCORE_POWER_FACTOR = 12
    # construtor do Atributo
    def __init__(self, attr_id, attr_name):
        self._attr_id = attr_id
        self._attr_name = attr_name
        self._parent = []
        self._children =  []
        self._related_actions = []        
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
        if self._children:                         
            for child in self._children:
                total += child.total_score
        else: 
            # Como related_actions é uma lista, somamos o score de cada ação nela
            if self._related_actions:
                total = sum(action.score for action in self._related_actions)
        return total


    # tratamento visual de power
    @property
    def power_display(self) -> str:
        trated_power = ( str( self._power / 1000 ) + "%")
        return trated_power

    def AddRelatedAction(self, action_id):
        self._related_actions.append(action_id)
        
    # json things - tranformar em dict
    def to_dict(self):
        return {
            "id": self.attr_id,
            "name": self.attr_name,
            "related_actions": [a.id for a in self.related_actions],
            "children": [a.id for a in self.children],
            "parent": [a.id for a in self.parent],
            "total_score": self.total_score,

        }

    @classmethod
    def from_dict(cls, data):
        attr = cls(data["id"], data["name"])
        attr._related_action_ids = data["related_actions"]
        return attr
