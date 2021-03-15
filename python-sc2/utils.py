from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.unit import Unit
from sc2.units import Units

class OpponentInfo:
    """
    Using This Class

    First make an instance of the class in your bot like this:
    # self.my_opponent = OpponentInfo(self)
    
    You should call add_expansion() and add_army_unit() whenever scouting an enemy townhall structure or unit. Like this:
    # async def on_enemy_unit_entered_vision(self, enemyunit):
    #     if enemyunit.of_type({HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}):
    #         self.my_opponent.add_expansion(enemyunit)
    #     elif not enemyunit.is_structure:  # this class will skip buildings, but it will be loud about it.
    #         self.my_opponent.add_army_unit(unit)
    The add_expansion function will handle checking for duplicates.

    Likewise you should call remove_expansion whenever an enemy townhall structure is destroyed. Like this:
    # async def on_unit_destroyed(self, tag):
    #     enemylost = self._enemy_units_previous_map.get(tag) or self._enemy_structures_previous_map.get(tag)  # gets last unit or structure (for this function you only really need structure)
    #     if enemylost:
    #         if enemylost.of_type({HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}):
    #         self.my_opponent.remove_expansion(enemylost)
    
    To remove an enemy expansion without marking it as desroyed (I don't know why you would want to do this) do:
    # self.my_opponent.remove_expansion(unit_object, destroyed = False)


    """
    def __init__(self, bot):
        self.bot = bot
        self.mineral_gas_ratio = 2  # How many minerals are 'worth' 1 gas in value calculations?
        self.race = self.bot.enemy_race  # TODO: deal with random
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
            'value_minerals': <mineral value>,
            'value_gas': <gas value>,
            'supply': <supply taken>,  # TODO: calculate_supply_cost doesn't behave as expected, see documentation and fix
            'first_seen': <gane seconds float>
        }
        """

    def handle_enemy_unit_entered_vision(self, unit):
        if unit.type_id in {EGG, LARVA, BROODLING, MULE}:
            return  # we ignore these units
        elif unit.type_id in {SCV, PROBE, DRONE}:
            pass  # TODO: keep track of enemy workers
        elif unit.type_id in {HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}:
            self.add_expansion(unit)  # keep track of enemy expansions
        elif unit.is_structure:
            pass  # ignore other enemy structures for now
        else:  # army unit
            self.add_army_unit(unit)
        pass  # call add_expansion or add_army_unit if needed

    def handle_on_unit_destroyed(self, tag):
        # allied units should be silently ignored but you shouldn't pass them to this function anyway
        enemy_lost = self._enemy_units_previous_map.get(tag) or self._enemy_structures_previous_map.get(tag)
        if enemy_lost.is_structure:
            if enemy_lost.type_id in {HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}:
                self.remove_expansion(tag)
        else:
            self.remove_unit(tag)

    # async def on_unit_destroyed(self, tag):
    #     enemylost = self._enemy_units_previous_map.get(tag) or self._enemy_structures_previous_map.get(tag)  # gets last unit or structure (for this function you only really need structure)
    #     if enemylost:
    #         if enemylost.of_type({HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}):
    #         self.my_opponent.remove_expansion(enemylost)

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

    def remove_expansion(self, expo, destroyed=True):
        """
        See notes at top of class for usage.
        Removes an expansion from self.expansions, if destroyed adds details to self.expansions_destroyed
        """
        if isinstance(expo, Unit):  # convert to tag, plug back in
            self.remove_expansion(expo.tag, destroyed=destroyed)
        assert isinstance(expo, int)
        if expo not in self.expansions:
            raise Exception  # tried to remove an expansion that wasn't in OpponentInfo.expansions
        elif expo in self.expansions_destroyed:
            raise Exception  # tried to remove an expansion that was already marked as destroyed
        old_expo = self.expansions.pop(expo)  # remove expansion from self.expansions
        if destroyed:  # also add to self.expansions_destroyed
            self.expansions_destroyed[expo] = {
                'position': old_expo.position,
                'started': old_expo['started'],
                'finished': old_expo['started'],
                'destroyed': self.bot.time
            }

    def add_army_unit(self, unit):
        # pass it a unit object and it will populate all the relevant dictionary fields
        # only pass this function units you really want added. probably shouldn't add enemy workers and stuff.
        assert isinstance(unit, Unit)
        if unit.is_structure:
            print("Tried to add a structure using OpponentInfo.add_army_unit(). Don't do that.")
            print("Skipping...")
            return
        self.army_units[unit.tag] = {
            'type_id': unit.type_id,
            'value_minerals': self.bot.calculate_unit_value(unit.type_id).minerals,
            'value_gas': self.bot.calculate_unit_value(unit.type_id).vespene,
            'supply': self.bot._game_data.units[unit.type_id.value]._proto.food_required,
            'first_seen': self.bot.time
        }

    def remove_unit(self, unit):
        # TODO: calculate total value lost
        pass

    def get_army_supply(self):
        army_supply = 0
        for tag in self.army_units:
            army_supply += self.army_units[tag]['supply']
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
            return value_minerals + (self.mineral_gas_ratio * value_gas)
        else:
            raise Exception  # invalid format for OpponentInfo.get_army_value

    def get_unit_composition(self):
        types_set = set()
        for unit in self.army_units:
            types_set.add(unit.type_id)
        return types_set

    def get_estimated_worker_count(self):
        pass
        # workers take 12 seconds to build
        # orbital takes 25 seconds to morph


class ArmyGroup:
    """
    Army groups allow control of an individual group of units

    Units in an army group are generally organized such that they all follow the same behavior
    i.e. all units in the marine army group focus banelings when they're nearby
    while all units in the marauder army group focus lurkers first

    Usage in bot class:
        self.my_army = ArmyGroup(self)  # make sure to pass self as an argument when initializing
        self.my_army.add_to(self.forces)  # add to army
        for unit in my_army.get_units():
        # for unit in self.units.tags_in(self.my_army.unit_tags):  # how to get units object
        #     do things with army units
    """
    def __init__(self, bot):
        self.bot = bot
        self.unit_tags = set()
        self.state = "DEFENDING"
        self.attack_position = self.bot.enemy_start_locations[0]
        self.defense_idle_position = self.bot.start_location.sort_by_distance(self.bot.expansion_locations_list)[1].towards(self.bot.game_info.map_center, 16)
        self.defense_range = 30  # Attack threats this distance from any friendly townhalls
        self.threats = None  # use get_threats() instead of getting this
        #self.respond_to_nearby_threats = True
        #self.target_fire_units = set()  # set of UnitTypeIds
        # Marine - {BANELING, INFESTOR, HIGHTEMPLAR, DARKTEMPLAR}
        # Marauder - {BANELING, INFESTOR, ULTRALISK, HIGHTEMPLAR, DARKTEMPLAR, STALKER, SIEGETANKSIEGED, SIEGETANK}
    
    def set_state(self, s):
        assert s in ["DEFENDING", "ATTACKING"]  # possible states
        self.state = s

    def trigger_attack(self, pos=None):
        if pos: self.attack_position = pos
        self.state = "ATTACKING"
        #for u in self.get_units(): u.attack(self.attack_position)  # sends all forces, even if doing something else
        self.do_state()

    def end_attack(self, pos=None):
        if pos: self.defense_idle_position = pos
        self.state = "DEFENDING"
        for u in self.get_units(): u.attack(self.defense_idle_position)
        self.do_state()

    def do_state(self):  # this should be called often
        if self.state == "DEFENDING":
            for u in self.get_units().idle:
                if self.bot.iteration % 4 == 0: u.attack(self.defense_idle_position)  
        elif self.state == "ATTACKING":
            for u in self.get_units().idle:  # only sends idle forces
                u.attack(self.attack_position)  # TODO: if nearby threats attack those instead
        else:
            raise Exception  # invalid state for ArmyGroup

    def get_units(self, of_type=None):
        """
        Returns a Units object.
        of_type (optional) - a {set} of UnitTypeIds (i.e. MARINE) or single UnitTypeId
        """
        if of_type:
            assert isinstance(of_type, (set, UnitTypeId))
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

    def get_threats(self):
        for townhall in self.bot.townhalls:  # threats are visible units closer than self.defense_range to a nearby townhall
            self.threats = self.bot.known_enemy_units.visible.closer_than(self.defense_range, townhall.position)
            # overwrites it every time ughhhh
        return self.threats.exclude_type({LARVA})
