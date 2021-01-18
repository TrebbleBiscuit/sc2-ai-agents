from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.unit import Unit
from sc2.units import Units

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
        """
        types_list = []
        for unit in :
            types.list.append(unit.type_id)

        """
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
        self.state = "IDLE"
        self.attack_position = self.bot.enemy_start_locations[0]
        #self.respond_to_nearby_threats = True
    
    def set_state(self, s):
        assert s in ["IDLE", "ATTACKING"]  # possible states
        self.state = s
    
    def trigger_attack(self, pos=None):
        if pos: self.attack_position = pos
        self.state = "ATTACKING"
        for u in self.get_units(): u.attack(self.attack_position)  # sends all forces, even if doing something else
        self.do_state()
    
    def end_attack(self):
        self.state = "IDLE"

    def do_state(self):  # this should be called often
        if self.state == "IDLE":
            pass
        elif self.state == "ATTACKING":
            for u in self.get_units().idle:  # only sends idle forces
                u.attack(self.attack_position)
        else:
            raise Exception  # invalid state for ArmyGroup
    
    def get_units(self, of_type=None):
        """
        Returns a Units object.
        of_type (optional) - a {set} of UnitTypeIds (i.e. MARINE) or single UnitTypeId
        """
        if of_type:
            assert isinstance(of_type, set) or isinstance(of_type, UnitTypeId)
        if self.bot.units:
            return_units = self.bot.units.tags_in(self.unit_tags)
            if of_type:
                return return_units.of_type(of_type)
            else:
                return return_units

    def add_to(self, to_add):
        """
        Input: Units, Unit, tag or list
        Add to this army group if not already added
        """
        if isinstance(to_add, Units):  # if units object, feed each unit back in
            for unit in to_add:
                self.add_to(unit)
        elif isinstance(to_add, Unit):  # if unit, convert to tag and feed back in       
            self.add_to(to_add.tag)
        elif isinstance(to_add, int):  # if tag, save to set
            if to_add not in self.unit_tags:
                self.unit_tags.add(to_add)
        elif isinstance(to_add, list):  # if list, iterate and feed back in
            for e in to_add:  # e could be a tag or a unit
                self.add_to(e)
        else: raise Exception  # invalid argument type in ArmyGroup.add_to()
    
    def remove_from(self, to_rm):
        """
        Input: Units, Unit, tag or list
        Remove from this army group if a member
        """
        if isinstance(to_rm, Units):  # if units object, feed each unit back in
            for unit in to_rm:
                self.remove_from(unit)
        elif isinstance(to_rm, Unit):  # if unit, convert to tag and feed back in       
            self.remove_from(to_rm.tag)
        elif isinstance(to_rm, int):  # if tag, save to set
            if to_rm not in self.unit_tags:
                self.unit_tags.discard(to_rm)  # discard instead of remove because we don't want an exception if the tag isn't in the group
        elif isinstance(to_rm, list):  # if list, iterate and feed back in
            for e in to_rm:
                self.remove_from(e)
        else: raise Exception  # invalid argument type in ArmyGroup.remove_from()


