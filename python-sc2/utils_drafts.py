
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

def worker_rush_defense(bot):
    pass
    # if bot.townhalls.exists and bot.getTimeInSeconds() < 5*60:

    #         cannonRushUnits = bot.units & []
    #         for th in bot.townhalls:
    #             cannonRushUnits |= bot.known_enemy_units.closer_than(30, th.position)
    #         pylons = cannonRushUnits(PYLON)
    #         probes = cannonRushUnits.filter(lambda x:x.type_id in [PROBE, SCV, DRONE, ZERGLING])
    #         cannons = cannonRushUnits.filter(lambda x:x.type_id in [PHOTONCANNON, SPINECRAWLER])

    #         if (pylons.amount + probes.amount > 0 or cannons.amount > 0) and bot.opponent_data["army_supply_visible"] < 3 and bot.units(SPINECRAWLER).ready.amount < 1 and bot.units(QUEEN).amount < 4:
    #             if not hasattr(bot, "defendCannonRushProbes"):
    #                 bot.defendCannonRushProbes = {}
    #                 bot.defendCannonRushCannons = {}

    #             assignedDroneTagsSets = [x for x in bot.defendCannonRushProbes.values()] + [x for x in bot.defendCannonRushCannons.values()]
    #             assignedDroneTags = set()
    #             for sett in assignedDroneTagsSets:
    #                 assignedDroneTags |= sett
    #             unassignedDrones = bot.units(DRONE).filter(lambda x: x.tag not in assignedDroneTags and x.health > 6)
    #             unassignedDroneTags = set((x.tag for x in unassignedDrones))

    #             # adding probe and cannons as threats
    #             for probe in probes:
    #                 if probe.tag not in bot.defendCannonRushProbes:
    #                     bot.defendCannonRushProbes[probe.tag] = set()
    #             for cannon in cannons:
    #                 if cannon.tag not in bot.defendCannonRushCannons:
    #                     bot.defendCannonRushCannons[cannon.tag] = set()

    #             # filter out dead units chasing probe
    #             for probeTag, droneTags in bot.defendCannonRushProbes.items():
    #                 drones = bot.units(DRONE).filter(lambda x:x.tag in droneTags)
    #                 lowHpDrones = drones.filter(lambda x:x.health < 7)
    #                 for drone in lowHpDrones:
    #                     mf = bot.state.mineral_field.closest_to(bot.townhalls.closest_to(drone))
    #                     await bot.do(drone.gather(mf))
    #                     drones.remove(drone)
    #                 bot.defendCannonRushProbes[probeTag] = set(x.tag for x in drones) # clear dead drones
    #                 # if probe not alive anymore or outside of range, send drones to mining
    #                 # print(drones, unassignedDrones)
    #                 if probeTag not in [x.tag for x in probes]:
    #                     bot.defendCannonRushProbes.pop(probeTag)
    #                     break # iterating over a changing dictionary

    #                 # if probe still alive, check if it has a drone chasing it
    #                 elif drones.amount < 1 and unassignedDrones.amount > 0:
    #                     # if no drones chasing it, get a random drone and assign it to probe
    #                     probe = probes.find_by_tag(probeTag)
    #                     newDrone = unassignedDrones.closest_to(probe)
    #                     mf = bot.state.mineral_field.closest_to(bot.townhalls.closest_to(newDrone))
    #                     if probe is not None and newDrone is not None:
    #                         unassignedDroneTags.remove(newDrone.tag)      
    #                         unassignedDrones.remove(newDrone) # TODO: need to test if this works                      
    #                         # unassignedDrones = unassignedDrones.filter(lambda x: x.tag in unassignedDroneTags)
    #                         bot.defendCannonRushProbes[probeTag].add(newDrone.tag)
    #                         await bot.do(newDrone.attack(probe))
    #                         await bot.do(newDrone.gather(mf, queue=True))

    #             # filter out dead units attacking a cannon
    #             for cannonTag, droneTags in bot.defendCannonRushCannons.items():
    #                 drones = bot.units(DRONE).filter(lambda x:x.tag in droneTags)
    #                 bot.defendCannonRushCannons[cannonTag] = set(x.tag for x in drones) # clear dead drones
    #                 # if cannon not alive anymore or outside of range, send drones to mining
    #                 if cannonTag not in [x.tag for x in cannons]:
    #                     bot.defendCannonRushCannons.pop(cannonTag)
    #                     break # iterating over a changing dictionary
    #                 # if probe still alive, check if it has a drone chasing it
    #                 elif drones.amount < 4 and unassignedDrones.amount > 0:
    #                     # if no drones chasing it, get a random drone and assign it to probe
    #                     for i in range(4 - drones.amount):
    #                         if unassignedDrones.amount <= 0:
    #                             break
    #                         cannon = cannons.find_by_tag(cannonTag)
    #                         newDrone = unassignedDrones.closest_to(cannon)
    #                         mf = bot.state.mineral_field.closest_to(bot.townhalls.closest_to(newDrone))
    #                         if cannon is not None and newDrone is not None:
    #                             unassignedDroneTags.remove(newDrone.tag)
    #                             unassignedDrones.remove(newDrone)
    #                             bot.defendCannonRushCannons[cannonTag].add(newDrone.tag)
    #                             await bot.do(newDrone.attack(cannon))
    #                             await bot.do(newDrone.gather(mf, queue=True))

def update_scouting_info(bot):
    # update scouting_data, not to be confused with opponent_data
    if not hasattr(bot, "scouting_data"):
        bot.scouting_data = []
        # add spawn locations if they are not in the list
        for base in bot.enemy_start_locations:
            already_seen = next((x for x in bot.scouting_data if x["location"].distance_to(base) < 10), None)
            if already_seen is None:
                bot.scouting_data.append({
                    "location": base,
                    "scout_time": 0,
                    "assigned_scout_tag": None
                })       
    else:
        # add existing enemy buildings
        if bot.known_enemy_structures.exists:
            for struct in bot.known_enemy_structures:
                already_seen = next((x for x in bot.scouting_data if x["location"] == struct.position.to2), None)
                if already_seen is None:
                    bot.scouting_data.append({
                        "location": struct.position.to2,
                        "scout_time": 0, # only start scouting hidden bases at 5 minutes
                        "assigned_scout_tag": None
                    })
