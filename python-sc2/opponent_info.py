class OpponentInfo:
    def __init__(self):
        self.expansions = {
            # tag : {
            #     'created': <game seconds float>
            # }
        }
        self.army_supply_scouted = 0
        self.army_value_scouted = 0
    
    def add_expansion(self, expo):
        pass
        # check if expo at same position is already in list
        # if so, copy its information into the new tag and delete the old tag
