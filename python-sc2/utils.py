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
                'position': <position>,
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
        """
        Assumes every existing enemy townhall is already an entry in self.expansions
        Call this function in on_enemy_unit_entered_vision() to make sure everything's always as recent as possible  (???)

        i dont even know what's going on
        """

        """
        assert isinstance(to_add, Unit):
        if expo.tag already in self.expansions:  # this townhall already in expansions
            return
        elif (
            len(self.opponent_info["expansions"]) > 0  # at least 1 expansion recorded on list
            and expo.position.closest([self.expansions[tag]['position'] for tag in self.expansions]).distance_to(expo.position) < 2  # this expo is in the same place as the one on the list
        ):  # TODO: ^^^ test this monstrosity
            closest_expo_tag = expo.position.closest([self.expansions[tag]['position'] for tag in self.expansions]).tag
            self.expansions[expo.tag]['is_main'] = 
            self.expansions[expo.tag]['position']
            self.expansions[expo.tag]['created'] = 
            self.expansions[expo.tag]['finished'] = 
            self.expansions.pop(expo.position.closest(self.expansions))  # remove old expo from the list, replace with this one
        # pass it a unit object and it will populate all the relevant dictionary fields
        # check if expo at same position is already in list
        # if so, copy its information into the new tag and delete the old tag



        for th in enemy_townhalls:
            if th in self.opponent_info['expansions']:  # this th already in set
                continue
            if len(self.opponent_info["expansions"]) > 0 and th.position.closest(self.opponent_info["expansions"]).distance_to(th.position) < 2:  # the townhall in question very close to one already in the list
                # this is here b/c a command center and an orbital would otherwise show up as different expansions
                self.opponent_info['expansions'].remove(th.position.closest(self.opponent_info["expansions"]))  # remove old expansion from set
                self.opponent_info['expansions'].add(th)  # add new expansion
            else:  # new expansion!
                self.opponent_info["expansions"].add(th)
                print("found a new enemy base!")
                if th.build_progress < 1:
                    print(f"its build progress is {th.build_progress}")
                    started_at = self.time - (th.build_progress * 71)
                    finish_at = self.time + ((1 - th.build_progress) * 71)
                    print(f"current game time is {self.time}")
                    print(f"scouted townhall was started at time {started_at}")
                    print(f"scouted townhall will finish at time {finish_at}")
                if th.position in self.expansion_locations_list:
                    print("expansion is at an expected location")
                else:
                    print("expansion is at an UNEXPECTED LOCATION")
        """

    def check_expansions(self):
        """
        Checks enemy structures, if there is no tag for an entry on our expansion list, delete it
        """

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

    def get_army_value(self, f='tuple'):
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
        self.target_fire_units = set()
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


