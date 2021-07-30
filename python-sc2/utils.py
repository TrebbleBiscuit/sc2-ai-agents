from sc2.data import Race
from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.unit import Unit
from sc2.units import Units

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
            self.threats = self.bot.enemy_units.visible.closer_than(self.defense_range, townhall.position)
            # overwrites it every time ughhhh
        return self.threats.exclude_type({LARVA})


### From burny-bots-python-sc2 CreepyBot
###

def get_unit_info(bot, unit, field="food_required"):
    # get various unit data, see list below
    # usage: get_unit_info(ROACH, "mineral_cost")
    assert isinstance(unit, (Unit, UnitTypeId))
    if isinstance(unit, Unit):
        # unit = unit.type_id
        unit = unit._type_data._proto
    else:
        unit = bot._game_data.units[unit.value]._proto
    # unit = bot._game_data.units[unit.value]
    # print(vars(unit)) # uncomment to get the list below
    if hasattr(unit, field):
        return getattr(unit, field)
    else:
        return None
    """
    name: "Drone"
    available: true
    cargo_size: 1
    attributes: Light
    attributes: Biological
    movement_speed: 2.8125
    armor: 0.0
    weapons {
        type: Ground
        damage: 5.0
        attacks: 1
        range: 0.10009765625
        speed: 1.5
    }
    mineral_cost: 50
    vespene_cost: 0
    food_required: 1.0
    ability_id: 1342
    race: Zerg
    build_time: 272.0
    sight_range: 8.0
    """



    # update scouting info depending on visible units that we can see
    # if we see buildings that are not
    # depot, rax, bunker, spine crawler, spore, nydus, pylon, cannon, gateway
    # then assume that is the enemy spawn location

def process_scouting(bot):
    if not hasattr(bot, 'opponent_data'):
        bot.opponent_data = {
            "spawn_location": None,         # for 4player maps
            "expansions": [],               # stores a list of Point2 objects of expansions
            "expansions_tags": set(),       # stores the expansions above as tags so we dont count them double
            "race": None,
            "army_tags_scouted": [],        # list of dicts with entries: {"tag": 123, "scout_time": 15.6, "supply": 2}
            "army_supply_scouted": 0,
            "army_supply_nearby": 0,
            "army_supply_visible": 0
        }
    # set enemy spawn location
    ignore_these_buildings = [SUPPLYDEPOT, SUPPLYDEPOTLOWERED, BARRACKS, BUNKER, SPINECRAWLER, SPORECRAWLER, NYDUSNETWORK, NYDUSCANAL, PYLON, PHOTONCANNON, GATEWAY]
    if bot.opponent_data["spawn_location"] is None and len(bot.enemy_start_locations) > 0:
        if bot.enemy_structures.exists:
            filtered_units = bot.enemy_structures.filter(lambda x:x.type_id not in ignore_these_buildings)
            if filtered_units.exists:
                bot.opponent_data["spawn_location"] = filtered_units.random.position.closest(bot.enemy_start_locations)

    # figure out the race of the opponent
    if bot.opponent_data["race"] is None and bot.enemy_units.exists:
        unit_race = get_unit_info(bot, bot.enemy_units.random, "race")
        racesDict = {
            Race.Terran.value: "Terran",
            Race.Zerg.value: "Zerg",
            Race.Protoss.value: "Protoss",
        }
        bot.opponent_data["race"] = unit_race

    # figure out how much army supply enemy has:
    visible_enemy_units = bot.enemy_units.not_structure.filter(lambda x:x.type_id not in [DRONE, SCV, PROBE, LARVA, EGG])
    for unit in visible_enemy_units:
        isUnitInInfo = next((x for x in bot.opponent_data["army_tags_scouted"] if x["tag"] == unit.tag), None)
        if isUnitInInfo is not None:
            bot.opponent_data["army_tags_scouted"].remove(isUnitInInfo)
        # if unit.tag not in bot.opponent_data["army_tags_scouted"]:
        if bot.townhalls.ready.exists:
            bot.opponent_data["army_tags_scouted"].append({
                "tag": unit.tag,
                "scout_time": bot.time,
                "supply": get_unit_info(bot, unit) or 0,
                "distance_to_base": bot.townhalls.ready.closest_to(unit).distance_to(unit),
            })

    # get opponent army supply (scouted / visible)
    scout_timeout_duration =  90 # TODO: set the time on how long until the scouted army supply times out
    bot.opponent_data["army_supply_scouted"] = sum(x["supply"] for x in bot.opponent_data["army_tags_scouted"] if x["scout_time"] > bot.time - scout_timeout_duration)
    bot.opponent_data["army_supply_nearby"] = sum(x["supply"] for x in bot.opponent_data["army_tags_scouted"] if x["scout_time"] > bot.time - scout_timeout_duration and x["distance_to_base"] < 60)
    bot.opponent_data["army_supply_visible"] = sum(get_unit_info(bot, x) or 0 for x in visible_enemy_units)

    # get opponent expansions
    if bot.iteration % 20 == 0:
        enemy_townhalls = bot.enemy_structures.filter(lambda x:x.type_id in [HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS])
        for th in enemy_townhalls:
            if len(bot.opponent_data["expansions"]) > 0 and th.position.closest(bot.opponent_data["expansions"]).distance_to(th.position.to2) < 20:
                continue
            if th.tag not in bot.opponent_data["expansions_tags"]:
                bot.opponent_data["expansions_tags"].add(th.tag)
                bot.opponent_data["expansions"].append(th.position.to2)
                print("found a new enemy base!")
                print(bot.opponent_data["expansions"])
