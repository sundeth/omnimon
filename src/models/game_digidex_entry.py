
class GameDigidexEntry:
    def __init__(self, name, attribute, stage, module, version, sprite, known, name_format):
        self.name = name
        self.attribute = attribute
        self.stage = stage
        self.module = module
        self.version = version
        self.sprite = sprite
        self.known = known
        self.name_format = name_format

    def get_sprite(self, index=0):
        return self.sprite