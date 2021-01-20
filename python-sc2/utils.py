from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.unit import Unit
from sc2.units import Units

class OpponentInfo:
    """
    Using This Class

    First make an instance of the class in your bot like this:
    # self.my_opponent = OpponentInfo(self)
    
    You should call add_expansion() and add_unit() whenever scouting an enemy townhall structure or unit. Like this:
    # async def on_enemy_unit_entered_vision(self, enemyunit):
    #     if enemyunit.of_type({HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}):
    #         self.my_opponent.add_expansion(enemyunit)
    #     elif not enemyunit.is_structure:  # this class will skip buildings, but it will be loud about it.
    #         self.my_opponent.add_unit(unit)
    The add_expansion function will handle checking for duplicates.

    Likewise you should call remove_expansion whenever an enemy townhall structure is destroyed. Like this:
    # async def on_unit_destroyed(self, tag):
        # enemylost = self._enemy_units_previous_map.get(tag) or self._enemy_structures_previous_map.get(tag)  # gets last unit or structure (for this function you only really need structure)
        # if enemylost:
            # if enemylost.of_type({HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}):
                # self.my_opponent.remove_expansion(enemylost)
    
    To remove an enemy expansion without marking it as desroyed (I don't know why you would want to do this) do:
    # self.my_opponent.remove_expansion(unit_object, destroyed = False)


    """
    def __init__(self, bot):
        self.bot = bot
        self.mineral_gas_ratio = 2  # How many minerals are 'worth' 1 gas in value calculations?

        self.race = None  # TODO: self.bot.enemy_race but deal with random
        self.workers_lost = 0
        self.expansions = {}
        """
        self.expansions = {
            tag : {
                'is_main': <boolean>,
                'position': <position>,
                'started': <game seconds float>,
                'finished': <game seconds float>
            }
        }
        """
        self.expansions_destroyed = {}
        """
        self.expansions_destroyed = {
            tag : {
                'position': <position>,
                'started': <game seconds float>,
                'finished': <game seconds float>,
                'destroyed': <game seconds float>
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
        """
        See notes at top of class for usage.
        """
        assert isinstance(expo, Unit)
        if expo.tag in self.expansions:  # this townhall already in expansions
            return  # TODO: check position to see if terran floated it from somewhere
        for tag, sd in self.expansions.items():
            if expo.position.distance_to(sd['position']) < 2:  # if an existing expansion is in the same place as this new one
                old_expo = self.expansions.pop(tag)  # remove old expo from the list
                self.expansions[expo.tag] = old_expo  # add this one with all the old one's same info
                break  # no need to go through the rest of the for loop TODO: could be return maybe?
        else:  # for/else - expansion is not already in list - now is the first time we scouted it!
            started_at = self.bot.time - (expo.build_progress * 71)  # expansions take 71 seconds to build
            finish_at = self.bot.time + ((1 - expo.build_progress) * 71)  # if already done, time will be current game time
            self.expansions[expo.tag] = {
                'is_main': (expo.position == self.bot.enemy_start_locations[0].position),
                'position': expo.position,
                'started': started_at,
                'finished': finish_at
            }
        if expo.position not in self.bot.expansion_locations_list:
            print(f"scouted expansion {expo} is at an UNEXPECTED LOCATION")

    def remove_expansion(self, expo, destroyed = True):
        """
        See notes at top of class for usage.
        Removes an expansion from self.expansions, if destroyed adds details to self.expansions_destroyed
        """
        assert isinstance(expo, Unit)
        if expo.tag not in self.expansions:
            raise Exception  # tried to remove an expansion that wasn't in OpponentInfo.expansions
        elif expo.tag in self.expansions_destroyed:
            raise Exception  # tried to remove an expansion that was already marked as destroyed
        old_expo = self.expansions.pop(expo.tag)  # remove expansion from self.expansions
        if destroyed:  # also add to self.expansions_destroyed
            self.expansions_destroyed[expo.tag] = {
                'position': expo.position,
                'started': old_expo['started'],
                'finished': old_expo['started'],
                'destroyed': self.bot.time
            }

    def add_unit(self, unit):
        # pass it a unit object and it will populate all the relevant dictionary fields
        # TODO: merge add_unit and add_expansion such that you only have to call one function in on_enemy_unit_entered_vision()
        assert isinstance(unit, Unit)
        if unit.is_structure:
            print("Tried to add a structure using OopponentInfo.add_unit(). Don't do that.")
            return
        self.army_units[unit.tag] = {
            'type_id': unit.type_id,
            'value_minerals': self.bot.calculate_unit_value(unit.type_id).minerals,
            'value_gas': self.bot.calculate_unit_value(unit.type_id).vespene,
            'supply': self.bot.calculate_supply_cost(unit.type_id),  # TODO: calculate_supply_cost doesn't behave as expected, see documentation and fix
            'first_seen': self.bot.time
        }

    def get_army_supply(self):
        army_supply = 0
        for tag, udict in self.army_units.items():
            army_supply += udict['supply']
        return army_supply

    def get_army_value(self, f='tuple'):
        value_minerals = 0
        value_gas = 0
        for tag, udict in self.army_units.items():
            value_minerals += udict['value_minerals']
            value_gas += udict['value_gas']
        if f == 'tuple':
            return (value_minerals, value_gas)
        elif f == 'int':
            self.mineral_gas_ratio
        else:
            raise Exception  # invalid format for OpponentInfo.get_army_value

    def get_unit_composition(self):
        """
        types_list = []
        for unit in :
            types.list.append(unit.type_id)

        """
        pass




class ArmyGroup:
    """
    Army groups allow control of an individual group of units

    Units in an army group are generally organized such that they all follow the same behavior
    i.e. all units in the marine army group focus banelings when they're nearby
    while all units in the marauder army group focus lurkers first

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
        self.target_fire_units = set()  # set of UnitTypeIds
        # Marine - {BANELING, INFESTOR, HIGHTEMPLAR, DARKTEMPLAR}
        # Marauder - {}
    
    def set_state(self, s):
        assert s in ["IDLE", "ATTACKING"]  # possible states
        self.state = s
    
    def trigger_attack(self, pos=None):
        if pos: self.attack_position = pos
        self.state = "ATTACKING"
        #for u in self.get_units(): u.attack(self.attack_position)  # sends all forces, even if doing something else
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


