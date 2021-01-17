class OpponentInfo:
    def __init__(self):
        self.workers_lost = 0
        self.expansions = {}
        """
        self.expansions = {
            tag : {
                'is_main': <boolean>,
                'created': <game seconds float>,
                'finished': <game seconds float>
            }
        }
        """

        self.army_units = {}
        """
        self.army_units[enemyunit.tag] = {
            'type_id': enemyunit.type_id,
            'value_minerals': self.calculate_unit_value(enemyunit.type_id).minerals,
            'value_gas': self.calculate_unit_value(enemyunit.type_id).vespene,
            'supply': self.calculate_supply_cost(enemyunit.type_id),  # TODO: calculate_supply_cost doesn't behave as expected, see documentation and fix
            'first_seen': self.time
        }
        """
    
    def add_expansion(self, expo):
        pass
        # pass it a unit object and it will populate all the relevant dictionary fields
        # check if expo at same position is already in list
        # if so, copy its information into the new tag and delete the old tag
    
    def add_unit(self, unit):
        self.army_units[unit.tag] = {
            'type_id': unit.type_id,
            'value_minerals': self.calculate_unit_value(enemyunit.type_id).minerals,
            'value_gas': self.calculate_unit_value(enemyunit.type_id).vespene,
            'supply': self.calculate_supply_cost(enemyunit.type_id),  # TODO: calculate_supply_cost doesn't behave as expected, see documentation and fix
            'first_seen': self.time
        }
            # value_minerals += self.calculate_unit_value(unit.type_id).minerals
            # value_gas += self.calculate_unit_value(unit.type_id).vespene
        # pass it a unit object and it will populate all the relevant dictionary fields
    
    #def remove_unit_by_tag(self, tag):  # can just do OpponentInfo.army_units.pop(tag) instead, same with expos

    def get_army_supply(self):
        pass
        # self.calculate_supply_cost(enemyunit.type_id)  #
        # calculate_supply_cost doesn't behave as expected, see documentation and fix

    def get_army_value(self):
        value_minerals = 0
        value_gas = 0
        for tag, udict in self.army_units.items():

            value_minerals += udict['value_minerals']
            value_gas += udict['value_gas']
        return (value_minerals, value_gas)

    def get_unit_composition(self):
        pass




class ArmyGroup:
    """
    Usage in bot class:
        self.my_army = ArmyGroup(self)
        self.my_army.add_to(self.forces)  # add to army
        for unit in my_army.get_units():
        #for unit in self.units.tags_in(self.my_army.unit_tags):  # how to get units object
            # do things with army units
    """
    def __init__(self, bot):
        self.bot = bot
        self.unit_tags = set()
    
    def get_units(self):
        return self.bot.units.tags_in(self.unit_tags)
        """
        TODO: will this actually work? I'm passing the as an argument to this class, then using bot.units.
        The question is whether or not bot.units will update. I think it should, as we're just referencing the bot
        and not actually creating an instance of the bot class... hopefully...
        """

    def add_to(self, to_add):
        """
        Input: Units, Unit, tag or list
        Add to this army group
        """
        if isinstance(to_add, Units):  # if units object, feed each unit back in
            for unit in to_add:
                self.add_to(unit)
        elif isinstance(to_add, Unit):  # if unit, convert to tag and feed back in       
            self.add_to(to_add.tag)
        elif isinstance(to_add, int):  # if tag, save to set
            if to_add not in self.threats:
                self.unit_tags.add(to_add)
        elif isinstance(to_add, list):  # if list, iterate and feed back in
            for e in to_add:
                self.add_to(e)


