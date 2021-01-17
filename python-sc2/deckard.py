from asyncio import sleep
import random
import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.player import Bot, Computer
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2, Point3
import cv2
import numpy as np

def main():
    sc2.run_game(
        sc2.maps.get("CatalystLE"),  # select map
        [Bot(Race.Terran, DeckardBot()), Computer(Race.Zerg, Difficulty.CheatMoney)],  # select opponent race and difficulty
        realtime=False,  # if False, render as fast as possible
    )

###############################
### Deckard by Erik Nielsen ###
###    A Starcraft II AI    ###
###############################

"""
    Big TODO list

# Build a reaper to scout
Put more production buildings in main (esp factories and starports)
# Make a scouting function! Store the information somehow
# Make functions return meaningful values based on their outcome
# Make the money spending machine brrr more efficiently
# Manage optimal bases 
# Write comments for functions
# Clean up debug info panel, plan it out better
"""

class DeckardBot(sc2.BotAI):  # Do things here before the game starts
    async def on_start(self):
        # Style Parameters - should be randomized for variety
        self.be_aggressive = False          # not well implemented yet

        self.search_length = 15             # These parameters may be tuned
        self.attack_downtime = 120          # Period from attack end to next attack start (after initial norush period)
        self.attack_length = 60             # Period from attack start to attack end
        self.attack_norush_period = 480     # Time until first attack - 480 (8 min) is a good time
        if self.be_aggressive: self.attack_norush_period -= 90
        self.mineral_gas_ratio = 2          # How many minerals are 'worth' 1 gas in value calculations?
        
        self.chatty = True                  # Flavor parameter
        self.make_log = True                # Enable or disable appending to log file

        ### The following parameters are controlled by the code. Probably shouldn't change them.
        self.announced_attack = False
        self.announced_hunt = False
        self.announced_search = False
        self.announced_efficiency = False

        self.willsurrender = True           # bot will set this to false if it thinks it's a base trade
        self.surrendernow = False
        self.basetrade = False
        self.beingcheesed = False  # TODO
        self.army_destroyed_enemy_main = False
        self.army_need_vikings = False
        self.army_need_thors = False
        self.army_mood = "DEFEND"
        self.attack_start_time = -99999
        self.attack_end_time = 0
        self.search_start_time = -99999
        self.value_killed_minerals = 0
        self.value_killed_vespene = 0
        self.value_lost_minerals = 0
        self.value_lost_vespene = 0
        self.calculated_attack_downtime = self.attack_norush_period
        self.value_killed_minerals_base = self.value_killed_minerals
        self.value_killed_vespene_base = self.value_killed_vespene
        self.value_lost_minerals_base = self.value_lost_minerals
        self.value_lost_vespene_base = self.value_lost_vespene
        self.built_reaper = False
        self.scv_scouted = False
        self.scouted_pool = False  # TvZ
        self.my_stats = {
            "workers_lost": 0,
        }
        self.opponent_info = {
            "expansions": set(), # stores a set of unit objects
            "army_units_scouted": {}, # dict of dicts; see template below
            "army_supply_scouted": 0,
            "army_supply_visible": 0,
        }
        """
            'army_units_scouted': {
                <tag>: {
                   'type_id': UnitTypeId.ROACH,
                   'value_minerals': 75,
                   'value_gas': 25,
                   'supply': 2,
                   'first_seen': 273.55819722
                },
            }
            """
        """
        idea: opponent_info['expansions'] is a dict
        <unit object> : {
            'finished_at': <game time float>,
        }

        
        """
        if self.make_log:
            self.logfile = open("deckard.log", "a")  # append mode
            self.logfile.write("\nDeckard Initialized. \n")
        print("")
        print("Deckard Initialized")
        
    async def on_step(self, iteration):
        self.total_worker_supply = self.supply_workers + self.already_pending(UnitTypeId.SCV)

        if iteration == 0:  # All the stuff to do exactly once when the game starts
            self.depot_placement_positions: Set[Point2] = self.main_base_ramp.corner_depots
            # Uncomment the following if you want to build 3 supply depots in the wall instead of a barracks in the middle + 2 depots in the corner
            # self.depot_placement_positions = self.main_base_ramp.corner_depots | {self.main_base_ramp.depot_in_middle}
            self.barracks_placement_position: Point2 = self.main_base_ramp.barracks_correct_placement
            # If you prefer to have the barracks in the middle without room for addons, use the following instead
            # self.barracks_placement_position = self.main_base_ramp.barracks_in_middle
            self.sorted_expo_locations = self.start_location.sort_by_distance(self.expansion_locations_list)  # used in get_rally_point
            for w in self.workers:  # split workers
                w.gather(self.mineral_field.closest_to(w))

        if iteration == 5:
            await self.chat_send(" Deckard. B26354. GLHF.")

        # If there is no (landed) CC and under 10 workers, concede
        if self.supply_workers < 10 and not self.townhalls:
            if not self.willsurrender:
                if not self.basetrade:
                    await self.chat_send("That hurt.")
                    self.basetrade = True
            else:
                self.surrendernow = True
                if self.chatty:
                    await self.chat_send("I've seen things you people wouldn't believe.")
                    await sleep(1)
                    await self.chat_send("Attack ships on fire off the shoulder of Orion.")
                    await sleep(1.5)
                    await self.chat_send("I watched C-beams glitter in the darkness at Tannhäuser Gate.")
                    await sleep(2)
                    await self.chat_send("All those moments will be lost in time like tears in rain.")
                    await sleep(1.5)
                    await self.chat_send("Time to die.")
                    await sleep(3)
                else:
                    await self.chat_send("GG")
                    await sleep(0.5)
                await self._client.leave()

        self.ccs: Units = self.townhalls
        if not self.ccs:
            return
        else:
            self.cc: Unit = self.ccs.first

        if iteration % 4 == 0:  # Do less frequently
            await self.distribute_workers()             # will distribute workers between bases, minerals, and gas geysers efficiently
        if iteration % 8 == 0:  # Do even less frequently
            await self.repair_damaged_buildings()       # will send 1 scv to damaged buildings to help repair every time it is run
        if iteration % 30 == 0:  # Do much less frequently
            await self.finish_constructing_buildings()  # will send 1 scv to incomplete, halted building every time it is run
            await self.handle_scouted_information()
            # This stuff is useful for debugging
            # self.cc:
            ## Unit(name='CommandCenter', tag=4342153217)
            # self.townhalls:
            ## [Unit(name='CommandCenter', tag=4377018369), Unit(name='CommandCenter', tag=4342153217), Unit(name='CommandCenter', tag=4357357569)]

        # Macro
        await self.manage_spending()                # spend money
        await self.manage_orbital_energy()          # manage orbital energy
        await self.army_movement(iteration)         # manage non-worker units

        # Micro
        await self.ability_siege_tanks()            # use siege/unsiege ability
        await self.ability_stim()                   # use stim ability
        await self.ability_interference_matrix()    # use interference matrix ability
        await self.raise_lower_depots()             # use raise/lower ability
        await self.micro_marines()                  # control marines
        await self.micro_reaper()                   # control reaper and scout
        await self.scv_scout()                      # 17 scout with SCV
        # await self.react_to_scouting()              # TODO: store and utilize scouting information

        self.showdebuginfo(iteration)               # show debug information in-game
        # await self.flavor_chat(iteration)         # some kind of annoying flavor
        await self.intel()                          # display intel visualization
        if self.make_log:
            await self.telemetry()

    async def on_enemy_unit_entered_vision(self, enemyunit):
        """
        UNDER CONSTRUCTION
        if enemyunit.tag not in self.opponent_info["army_units_scouted"]:
            self.opponent_info.append{}
        """
        if not self.army_need_vikings:
            need_vikings_list = ["Colossus", "Mothership", "Tempest", "Phoenix", "Battlecruiser", "Medivac", "Viper", "Corruptor", "Brood Lord"]
            if enemyunit.name in need_vikings_list:
                self.army_need_vikings = True
        if not self.army_need_thors:
            need_thors_list = ["Mutalisk"] # Baneling? Want to eventually add capital ships and have thors toggle high impact payload
            if enemyunit.name in need_thors_list:
                self.army_need_thors = True
        
        if self.time < 120 and not self.beingcheesed:  # under 2:00
            for u in self.enemy_units.of_type(ZERGLING):  # if we scout lings
                self.beingcheesed = True
                print("I think we're being cheesed...")
                break
        
        if enemyunit.type_id not in {DRONE, PROBE, SCV, OVERLORD, LARVA, EGG, BROODLING, QUEEN, CHANGELING, CHANGELINGMARINESHIELD, BANELINGCOCOON} and not enemyunit.is_structure:
            if enemyunit.tag not in self.opponent_info['army_units_scouted']:
                self.opponent_info['army_units_scouted'][enemyunit.tag] = {
                    'type_id': enemyunit.type_id,
                    'value_minerals': self.calculate_unit_value(enemyunit.type_id).minerals,
                    'value_gas': self.calculate_unit_value(enemyunit.type_id).vespene,
                    'supply': self.calculate_supply_cost(enemyunit.type_id),  # TODO: calculate_supply_cost doesn't behave as expected, see documentation and fix
                    'first_seen': self.time
                }
                print(f"just added scouted enemy {enemyunit.type_id} {enemyunit.tag} to army_units_scouted")
                print(f"total scouted enemy army value is now: {self.get_enemy_army_value()}")
            

        """
        
        if (
            enemyunit.is_flying
            and enemyunit.name not in ["Observer", "WarpPrism", "Overlord"]
            and enemyunit.name not in need_vikings_list
            and enemyunit.name not in need_thors_list
        ):
            print(str(enemyunit) + "is flying!")
        """

    async def on_unit_destroyed(self, tag):
        if tag in self.opponent_info['army_units_scouted']:
            self.opponent_info['army_units_scouted'].pop(tag)

        lost = self._units_previous_map.get(tag) or self._structures_previous_map.get(tag)
        enemylost = self._enemy_units_previous_map.get(tag) or self._enemy_structures_previous_map.get(tag)

        if lost and str(lost.type_id) != "UnitTypeId.MULE":
            self.value_lost_minerals += self.calculate_unit_value(lost.type_id).minerals
            self.value_lost_vespene += self.calculate_unit_value(lost.type_id).vespene
            if str(lost.type_id) == "UnitTypeId.SCV":
                self.my_stats['workers_lost'] += 1

        if enemylost and str(enemylost.type_id) != "UnitTypeId.MULE":
            self.value_killed_minerals += self.calculate_unit_value(enemylost.type_id).minerals
            self.value_killed_vespene += self.calculate_unit_value(enemylost.type_id).vespene
            # UNDER CONSTRUCTION
            if enemylost.type_id in [HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS]:
                print("ENEMY LOST TOWNHALL!")
                print(enemylost)
                print(f"It was at position: {enemylost.position}")
                print("was it in the expansions list?")
                if enemylost in self.opponent_info["expansions"]: 
                    print("yes")
                    self.opponent_info["expansions"].remove(enemylost)
                else: print("no (that's weird) - probably a thing with a terran floating or morphed building?")

        

### Above functions are called by the game, below functions are called by the above functions ###

    async def army_movement(self, iteration):
        self.forces: Units = self.units.of_type({MARINE, MARAUDER, SIEGETANK})
        self.flier: Units = self.units(UnitTypeId.VIKINGFIGHTER)
        medivacs: Units = self.units(UnitTypeId.MEDIVAC)  # TODO: if medivac movement target is far away, boost
        ravens: Units = self.units(UnitTypeId.RAVEN)
        
        if (
            self.units
            and self.enemy_structures
            and min([u.position.distance_to(self.enemy_start_locations[0]) for u in self.units]) < 5
            and min([enemybuilding.position.distance_to(self.enemy_start_locations[0]) for enemybuilding in self.enemy_structures]) > 5
        ):
            self.army_destroyed_enemy_main = True
            self.willsurrender = False

        if self.forces and iteration % 4 == 0:
            # follow the army around at a distance
            # unit.attack really just does a scan-move (like when you a-move a medivac it stays back to heal)
            # ravens will totally just run in though so keep those well back
            for unit in self.flier: unit.attack(self.forces.closest_to(self.enemy_start_locations[0]).position.towards(self.start_location, 4))
            for unit in medivacs: unit.attack(self.forces.closest_to(self.enemy_start_locations[0]).position.towards(self.start_location, 7))
            for unit in ravens: unit.attack(self.forces.closest_to(self.enemy_start_locations[0]).position.towards(self.start_location, 8))

        # Decide whether to defend or attack based off of frequency, length, and norush parameters.
        if self.time < self.search_start_time + self.search_length:
            pass  # give units time to search map for buildings
        elif self.units and self.army_destroyed_enemy_main:
            # If you've got units at the hostile starting location, hunt down their remaining buildings if there are any, else search for them.
            self.attack_end_time -= 999  # so that the attack and defend cooldowns aren't happening at the same time
            self.attack_start_time -= 999  # so that the attack and defend cooldowns aren't happening at the same time
            if not self.enemy_structures:
                if self.chatty and not self.announced_search:
                    await self.chat_send("Quite an experience to live in fear, isn't it?")
                    self.announced_search = True
                self.search_start_time = self.time
                self.army_mood = "SEARCH"
                for unit in self.forces:
                    unit.attack(self.mineral_field.random.position)
            else:
                if self.army_mood != "HUNT":
                    self.search_start_time = self.time
                    self.army_mood = "HUNT"
                    if self.chatty and not self.announced_hunt:
                        await self.chat_send("Fiery the angels fell. Deep thunder rolled around their shores, burning with the fires of Orc.")
                        self.announced_hunt = True
                    for unit in self.forces: unit.attack(self.enemy_structures.random.position)
                else:
                    # still hunting, restart timer
                    print("Still hunting...")
                    for unit in self.forces: unit.attack(self.enemy_structures.random.position)
                    self.search_start_time = self.time
        #
        # Attack
        #
        elif self.army_mood != "ATTACK" and self.time > self.attack_end_time + self.get_attack_downtime():
        #elif round(self.time) % self.attack_frequency == 0 and self.time > self.attack_norush_period and self.army_mood != "ATTACK":
            if self.enemy_units.closer_than(60, self.start_location):  # delay attack if there are enemy units nearby
                self.attack_end_time += 10
                return
            # TODO
            # if enemy total fielded value < 0.3 * our total fielded value, attack 
            if self.chatty and not self.announced_attack:
                await self.chat_send("I heard something about a four year lifespan.")
                self.announced_attack = True
            self.army_mood = "ATTACK"
            self.get_attack_length(reset=True)
            self.attack_start_time = self.time
            self.attack_end_time -= 60  # so that the attack and defend cooldowns aren't happening at the same time
            for unit in self.forces:
                unit.attack(self.get_base_target())
        elif self.time < self.attack_start_time + self.get_attack_length():
            # continue attack
            if not self.announced_efficiency and self.attack_length + 50 < self.get_attack_length():
                await self.chat_send("Come on. I'm right here, but you've got to shoot straight.")
                self.announced_efficiency = True
            if iteration % 5 == 0:
                for unit in self.forces.idle:  # only sends idle forces! 
                    unit.attack(self.get_base_target())
        #
        # Defend
        #
        elif self.time > self.attack_start_time + self.get_attack_length() and self.army_mood != "DEFEND":
        #elif round(self.time) == self.attack_start_time + round(self.get_attack_length()) and self.army_mood != "DEFEND":
            self.army_mood = "DEFEND"
            self.get_attack_downtime(reset=True)
            self.attack_end_time = self.time
            self.attack_start_time -= 60  # so that the attack and defend cooldowns aren't happening at the same time
            for unit in self.forces:
                unit.attack(self.get_rally_point())
        elif self.time > self.attack_start_time + self.get_attack_length():
            # continue defense
            if iteration % 6 == 0:
                threats = self.enemy_units.closer_than(60, self.start_location)  # TODO: make proper threats by getting hostile units close to our expansions and eventually sensor tower blips
                for unit in self.forces:
                    hostiles = self.enemy_units.closer_than(20, unit)  # hostiles are close to an individual unit
                    if hostiles:  # if hostiles near this unit exist - hostiles are more immediate threats
                        unit.attack(hostiles.closest_to(unit))  # attack the hostile closest to the unit
                    elif threats:  # if threats near our bases exist - threats are secondary to hostiles
                        for unit in self.forces.idle: unit.attack(threats.random.position)
                    elif unit.is_idle:  # chill at get_rally_point()
                        if iteration % 12 == 0:
                            unit.attack(self.get_rally_point())

    async def manage_spending(self):
        """
        TODO:
        if cant build addons, don't train units
        if can't upgrade orbital, don't train workers
        """
        await self.upgrade_command_center()
        await self.train_workers()
        await self.expand()
        await self.build_depots()
        await self.build_addons()  # must be before unit training so that buildings build addons first
        await self.train_from_barracks()
        if (  # If the conditions are met to expand but we haven't yet, save money to do so.
            self.townhalls.amount >= self.get_ideal_building_count("COMMANDCENTER")
            or self.already_pending(UnitTypeId.COMMANDCENTER)
            or self.enemy_units and self.townhalls.amount == 1
        ):
            await self.train_from_factory()
            await self.train_from_starport()
            await self.build_production()
            await self.build_upgrade_buildings()
            await self.build_missile_turrets()
            await self.research_upgrades()
            await self.build_refineries()

    async def handle_scouted_information(self):
        enemy_townhalls = self.enemy_structures.filter(lambda x:x.type_id in [HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS])
        # TODO: hatch first or pool first? be able to tell
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
                print(self.opponent_info["expansions"])
                #print(self.enemy_start_locations)
                print(f"sorted_expo_locations is {self.sorted_expo_locations}")
                """
                found a new enemy base!
                {Unit(name='Lair', tag=4345561089), Unit(name='Hatchery', tag=4380950529)}
                [(144.5, 28.5)]
                [(39.5, 139.5), (68.5, 140.5), (48.5, 106.5), (100.5, 139.5), (98.5, 113.5), (53.5, 66.5), (85.5, 54.5), (130.5, 101.5), (140.5, 143.5), (43.5, 24.5), (83.5, 28.5), (135.5, 61.5), (115.5, 27.5), (144.5, 28.5)]
                """
                # TODO: seeing a CC and then an orbital adds two tags at the same location?
        # now for non-townhall buildings
        if not self.scouted_pool:
            for pool in self.enemy_structures.of_type(SPAWNINGPOOL):
                print("found an enemy spawning pool!")
                print(f"its build progress is {pool.build_progress}")
                started_at = self.time - (pool.build_progress * 71)
                finish_at = self.time + ((1 - pool.build_progress) * 71)
                print(f"current game time is {self.time}")
                print(f"scouted pool was started at time {started_at}")
                print(f"scouted pool will finish at time {finish_at}")
                self.scouted_pool = True


    async def ability_siege_tanks(self):
        # Unsieged range is 7
        # Sieged range is 13
        for tank in self.units(UnitTypeId.SIEGETANK):
            if (
                len(self.enemy_units.in_attack_range_of(tank, bonus_distance=4)) > 1  # more than 1 hostile unit within 11 range
                or len(self.enemy_structures.in_attack_range_of(tank, bonus_distance=2)) > 1  # more than 1 hostile building within 9 range
            ):
                tank(AbilityId.SIEGEMODE_SIEGEMODE)
        for siegedtank in self.units(UnitTypeId.SIEGETANKSIEGED):
            if (
                len(self.enemy_units.in_attack_range_of(siegedtank, bonus_distance=0)) == 0  # no hostile units within 13-14 range (this fn slightly overestimates range for stationary units)
                and len(self.enemy_structures.in_attack_range_of(siegedtank, bonus_distance=0)) == 0
            ):
                siegedtank(AbilityId.UNSIEGE_UNSIEGE)

    async def ability_stim(self):
        for marine in self.units(UnitTypeId.MARINE):
            abilities = await self.get_available_abilities(marine)
            if (
                AbilityId.EFFECT_STIM_MARINE in abilities  # stim is researched
                and len(self.enemy_units.in_attack_range_of(marine, bonus_distance=1)) > 2  # more than 2 hostile units within range + 1
                and not marine.has_buff(BuffId.STIMPACK)  # stim not already active
            ):
                marine(AbilityId.EFFECT_STIM_MARINE)
        for marauder in self.units(UnitTypeId.MARAUDER):
            abilities = await self.get_available_abilities(marauder)
            if (
                AbilityId.EFFECT_STIM_MARAUDER in abilities
                and len(self.enemy_units.in_attack_range_of(marauder, bonus_distance=1)) > 2
                and not marauder.has_buff(BuffId.STIMPACKMARAUDER)
            ):
                marauder(AbilityId.EFFECT_STIM_MARAUDER)

    async def micro_marines(self):
        # TODO: if there are no enemy units are around but marine is attacking building, stutter step towards it
        if self.enemy_units:  # TODO stutter step towards buildings even if there are no enemy units
            for u in self.units(UnitTypeId.MARINE):
                closest_enemy = self.enemy_units.closest_to(u)  # TODO: filter out overlords, observers, etc
                if (
                    self.enemy_structures
                    and u.weapon_cooldown > 0  # weapon off cooldown
                    and u.distance_to(closest_enemy) > 8  # closest enemy well out of range - we are likely attacking a building
                ):
                    closest_structure = self.enemy_structures.closest_to(u)
                    kite_pos = u.position.towards(closest_structure.position, u.distance_to_weapon_ready)  # run towards
                    u.move(kite_pos)
                elif closest_enemy.ground_range <= 3:  # facing short range units, kite them back
                    if u.distance_to(closest_enemy) <= 5 and u.weapon_cooldown > 0:  # enemy in range, weapon ON cooldown
                        kite_pos = u.position.towards(closest_enemy.position, -u.distance_to_weapon_ready)  # run away
                        u.move(kite_pos)
                    elif u.distance_to(closest_enemy) <= 5 and u.weapon_cooldown == 0:  # enemy in range, weapon OFF cooldown
                        attackable_units = self.enemy_units.in_attack_range_of(u)  # TODO (or not?): filter only to units.is_attacking (if any)
                        if self.enemy_units.of_type(UnitTypeId.DARKTEMPLAR).in_attack_range_of(u):  # templar in range
                            priority_units = self.enemy_units.of_type(UnitTypeId.DARKTEMPLAR).sorted(lambda b: u.distance_to(b), reverse=True)  # TODO: needs testing
                        if self.enemy_units.of_type(UnitTypeId.BANELING).in_attack_range_of(u):  # baneling in range
                            priority_units = self.enemy_units.of_type(UnitTypeId.BANELING).sorted(lambda b: u.distance_to(b), reverse=True)  # TODO: needs testing
                        else:
                            priority_units = attackable_units.sorted(lambda u: u.health_percentage, reverse=True)  # attack weakest unit
                        target = priority_units.pop()
                        u.attack(target)
                    elif u.distance_to(closest_enemy) > 5 and u.weapon_cooldown == 0:  # enemy out of range, weapon OFF cooldown
                        potential_units = self.enemy_units.closer_than(6, u)  # attack a nearby enemy
                        if potential_units:
                            priority_units = potential_units.sorted(lambda u: u.health_percentage, reverse=True)
                            target = priority_units.pop()
                            u.attack(target)
                else:  # facing longer ranged units, run up to them
                    if u.weapon_cooldown > 0:  # weapon ON cooldown
                        if u.distance_to(closest_enemy) <= 6 and u.distance_to(closest_enemy) >= 2:  # enemy close, 
                            kite_pos = u.position.towards(closest_enemy.position, u.distance_to_weapon_ready)  # run towards
                            u.move(kite_pos)
                    elif u.weapon_cooldown == 0:  # weapon OFF cooldown
                        potential_units = self.enemy_units.closer_than(8, u)  # TODO (or not?): filter only to units.is_attacking (if any)
                        if potential_units:
                            if self.enemy_units.of_type({UnitTypeId.INFESTOR, UnitTypeId.INFESTORBURROWED}).in_attack_range_of(u):  # infestor in range
                                priority_units = self.enemy_units.of_type({UnitTypeId.INFESTOR, UnitTypeId.INFESTORBURROWED}).sorted(lambda b: u.distance_to(b), reverse=True)  # TODO: needs testing
                            if self.enemy_units.of_type(UnitTypeId.HIGHTEMPLAR).in_attack_range_of(u):  # templar in range
                                priority_units = self.enemy_units.of_type(UnitTypeId.HIGHTEMPLAR).sorted(lambda b: u.distance_to(b), reverse=True)  # TODO: needs testing
                            else:
                                priority_units = potential_units.sorted(lambda u: u.health_percentage, reverse=True)  # target fire weakest unit
                            target = priority_units.pop()
                            u.attack(target)
                    else:  # if heavily damaged
                        pass
        else:  # no enemy units
            for u in self.units(UnitTypeId.MARINE):
                if u.weapon_cooldown > 0 and self.enemy_structures:  # weapon off cooldown - probably attacking enemy building
                    closest_structure = self.enemy_structures.closest_to(u)
                    kite_pos = u.position.towards(closest_structure.position, u.distance_to_weapon_ready)  # run towards
                    u.move(kite_pos)

    async def micro_reaper(self):
        for r in self.units(UnitTypeId.REAPER):
            if self.enemy_units: closest_enemy = self.enemy_units.closest_to(r)  # need to define this here so we can check it on the next if and then use it more later
            if self.enemy_units and r.distance_to(closest_enemy) < 8:  # (not elif) enemy nearby
                dist_to_run = random.uniform(3.5, 5.5)  # randomize a bit so the reaper gets stuck less often
                r.move(r.position.towards(closest_enemy, -dist_to_run))  # run away from enemy
                dist_to_run = random.uniform(10, 15)
                r.move(r.position.towards(self.sorted_expo_locations[0], dist_to_run), queue=True)  # run towards home TODO: run towards random owned expo
            elif r.is_idle or r.is_attacking:  # not doing something already (or likely autoattacking something)
                r.move(self.get_pos_to_scout())

    async def scv_scout(self):
        if not self.scv_scouted and self.total_worker_supply == 17:
            print("scv scouting now")
            self.scv_scouted = True
            enemy_main_pos = self.enemy_start_locations[0].position
            self.workers.gathering.closest_to(enemy_main_pos).move(enemy_main_pos)

    async def ability_interference_matrix(self):
        for raven in self.units(UnitTypeId.RAVEN):
            targets = self.enemy_units.of_type({COLOSSUS, MOTHERSHIP, SIEGETANKSIEGED, BATTLECRUISER, VIPER, INFESTOR}).closer_than(16, raven)
            if targets:
                target = targets.closest_to(raven)
                abilities = await self.get_available_abilities(raven)
                if AbilityId.EFFECT_INTERFERENCEMATRIX in abilities:
                    raven(AbilityId.EFFECT_INTERFERENCEMATRIX, target)

    async def build_production(self):
        if self.workers.gathering:
            buildingscv = self.workers.gathering.random
        else:
            return
        # First Barracks
        if (
            self.tech_requirement_progress(UnitTypeId.BARRACKS) == 1
            and self.already_pending(UnitTypeId.BARRACKS) + self.structures.of_type({UnitTypeId.BARRACKS, UnitTypeId.BARRACKSFLYING}).ready.amount == 0
        ):
            if self.can_afford(UnitTypeId.BARRACKS): buildingscv.build(UnitTypeId.BARRACKS, self.barracks_placement_position)
        elif (
            self.tech_requirement_progress(UnitTypeId.BARRACKS) == 1
            and self.already_pending(UnitTypeId.BARRACKS) + self.structures.of_type({UnitTypeId.BARRACKS, UnitTypeId.BARRACKSFLYING}).ready.amount == 1
            and self.townhalls.amount > 1  # 2nd rax after expo
        ):
            if self.can_afford(UnitTypeId.BARRACKS): await self.build(UnitTypeId.BARRACKS, near=self.cc.position.towards(self.game_info.map_center, 8))
        # Then Factory
        elif self.tech_requirement_progress(UnitTypeId.FACTORY) == 1 and self.already_pending(UnitTypeId.FACTORY) + self.structures.of_type({UnitTypeId.FACTORY, UnitTypeId.FACTORYFLYING}).ready.amount < self.get_ideal_building_count("FACTORY"):
            if self.can_afford(UnitTypeId.FACTORY):
                await self.build(UnitTypeId.FACTORY, near=self.cc.position.towards(self.game_info.map_center, 8))
        # Then Starport
        elif self.tech_requirement_progress(UnitTypeId.STARPORT) == 1 and self.already_pending(UnitTypeId.STARPORT) + self.structures.of_type({UnitTypeId.STARPORT, UnitTypeId.STARPORTFLYING}).ready.amount < self.get_ideal_building_count("STARPORT"):
            if self.can_afford(UnitTypeId.STARPORT):
                await self.build(UnitTypeId.STARPORT, near=self.cc.position.towards(self.game_info.map_center, 8))
        # Then Barracks
        elif (
            self.can_afford(UnitTypeId.BARRACKS)
            and self.structures.of_type({UnitTypeId.STARPORT, UnitTypeId.STARPORTFLYING}).amount > 0
            and self.already_pending(UnitTypeId.BARRACKS) + self.structures.of_type({UnitTypeId.BARRACKS, UnitTypeId.BARRACKSFLYING}).ready.amount < self.get_ideal_building_count("BARRACKS")
        ):
            await self.build(UnitTypeId.BARRACKS, near=self.cc.position.towards(self.game_info.map_center, 8))
    
    async def build_addons(self):
        # Rax: 1 Reactor, 2 Lab, 3 Reactor, 4 Reactor, 5 Lab, 6+ Reactor
        if not self.built_reaper: return  # won't build add-ons until after reaper is made
        for rax in self.structures(UnitTypeId.BARRACKS).ready.idle:
            if (
                not rax.has_add_on
                and not self.enemy_units.closer_than(8, rax.position)
            ):
                addon_position: Point2 = rax.position + Point2((2.5, -0.5))
                if not (await self.can_place(UnitTypeId.SUPPLYDEPOT, addon_position)): rax(AbilityId.LIFT)  # if an addon won't fit, lift
                elif self.already_pending(UnitTypeId.BARRACKSREACTOR) + self.structures(UnitTypeId.BARRACKSREACTOR).ready.amount < 1:  # no reactors exist
                    if self.can_afford(UnitTypeId.BARRACKSREACTOR): rax.build(UnitTypeId.BARRACKSREACTOR)  # build reactor first
                elif self.already_pending(UnitTypeId.BARRACKSTECHLAB) + self.structures(UnitTypeId.BARRACKSTECHLAB).ready.amount < 1:  # no tech labs exist
                    if self.can_afford(UnitTypeId.BARRACKSTECHLAB): rax.build(UnitTypeId.BARRACKSTECHLAB)  # build tech lab second
                elif (
                    self.already_pending(UnitTypeId.BARRACKSREACTOR) + self.structures(UnitTypeId.BARRACKSREACTOR).ready.amount >= 3  # 3+ reactors exist
                    and self.already_pending(UnitTypeId.BARRACKSTECHLAB) + self.structures(UnitTypeId.BARRACKSTECHLAB).ready.amount < 2  # 1 tech lab exists
                ):
                    if self.can_afford(UnitTypeId.BARRACKSTECHLAB): rax.build(UnitTypeId.BARRACKSTECHLAB)  # build tech lab fifth
                else:
                    if self.can_afford(UnitTypeId.BARRACKSREACTOR): rax.build(UnitTypeId.BARRACKSREACTOR)  # build reactor (the rest)
        
        # Find a spot for lifted rax to land
        for rax in self.structures(UnitTypeId.BARRACKSFLYING).idle:
            possible_land_positions_offset = sorted(
                (Point2((x, y)) for x in range(-10, 10) for y in range(-10, 10)),
                key=lambda point: point.x ** 2 + point.y ** 2,
            )
            offset_point: Point2 = Point2((-0.5, -0.5))
            possible_land_positions = (rax.position.rounded + offset_point + p for p in possible_land_positions_offset)
            for target_land_position in possible_land_positions:
                if (
                    (await self.can_place(UnitTypeId.BARRACKS, target_land_position))
                    and (await self.can_place(UnitTypeId.SUPPLYDEPOT, target_land_position + Point2((2.5, -0.5))))
                ):
                    rax(AbilityId.LAND, target_land_position)
                    break
        
        # Iterate through all landed facs, build tech labs
        for fac in self.structures(UnitTypeId.FACTORY).ready.idle:
            if (
                not fac.has_add_on
                and not self.enemy_units.closer_than(8, fac.position)
                # and self.already_pending(UnitTypeId.STARPORT) + self.structures(UnitTypeId.STARPORT).ready.amount > 0  # must have already started starport
            ):
                if self.can_afford(UnitTypeId.FACTORYTECHLAB):
                    addon_position: Point2 = fac.position + Point2((2.5, -0.5))
                    if (await self.can_place(UnitTypeId.SUPPLYDEPOT, addon_position)):
                        fac.build(UnitTypeId.FACTORYTECHLAB)
                    else:
                        fac(AbilityId.LIFT)  # Lift if addon will not fit
        # Find a spot for lifted facs to land
        for fac in self.structures(UnitTypeId.FACTORYFLYING).idle:
            possible_land_positions_offset = sorted(
                (Point2((x, y)) for x in range(-10, 10) for y in range(-10, 10)),
                key=lambda point: point.x ** 2 + point.y ** 2,
            )
            offset_point: Point2 = Point2((-0.5, -0.5))
            possible_land_positions = (fac.position.rounded + offset_point + p for p in possible_land_positions_offset)
            for target_land_position in possible_land_positions:
                if (
                    (await self.can_place(UnitTypeId.FACTORY, target_land_position))
                    and (await self.can_place(UnitTypeId.SUPPLYDEPOT, target_land_position + Point2((2.5, -0.5))))
                ):
                    fac(AbilityId.LAND, target_land_position)
                    break
        
        """
        # Iterate through all landed starports, build reactors
        for sp in self.structures(UnitTypeId.STARPORT).ready.idle:
            if not sp.has_add_on:
                if self.can_afford(UnitTypeId.STARPORTREACTOR):
                    addon_position: Point2 = sp.position + Point2((2.5, -0.5))
                    if (await self.can_place(UnitTypeId.SUPPLYDEPOT, addon_position)):
                        sp.build(UnitTypeId.STARPORTREACTOR)
                    else:
                        sp(AbilityId.LIFT)  # Lift if addon will not fit
        """
        # Iterate through all landed starports
        for sp in self.structures(UnitTypeId.STARPORT).ready.idle:
            if not sp.has_add_on and not self.enemy_units.closer_than(8, sp.position):
                addon_position: Point2 = sp.position + Point2((2.5, -0.5))
                if not (await self.can_place(UnitTypeId.SUPPLYDEPOT, addon_position)): sp(AbilityId.LIFT)  # if an addon won't fit, lift
                elif self.already_pending(UnitTypeId.STARPORTTECHLAB) + self.structures(UnitTypeId.STARPORTTECHLAB).ready.amount < 1:  # no tech lab exists
                    if (
                        self.can_afford(UnitTypeId.STARPORTTECHLAB)
                        and len(self.units.of_type({MEDIVAC})) >= 1  # at least one medivac exists
                    ):
                        sp.build(UnitTypeId.STARPORTTECHLAB)  # build tech lab
                else:
                    if self.can_afford(UnitTypeId.STARPORTREACTOR): sp.build(UnitTypeId.STARPORTREACTOR)  # build reactor

                    
        # Find a spot for lifted starports to land
        for sp in self.structures(UnitTypeId.STARPORTFLYING).idle:
            possible_land_positions_offset = sorted(
                (Point2((x, y)) for x in range(-10, 10) for y in range(-10, 10)),
                key=lambda point: point.x ** 2 + point.y ** 2,
            )
            offset_point: Point2 = Point2((-0.5, -0.5))
            possible_land_positions = (sp.position.rounded + offset_point + p for p in possible_land_positions_offset)
            for target_land_position in possible_land_positions:
                if (
                    (await self.can_place(UnitTypeId.STARPORT, target_land_position))
                    and (await self.can_place(UnitTypeId.SUPPLYDEPOT, target_land_position + Point2((2.5, -0.5))))
                ):
                    sp(AbilityId.LAND, target_land_position)
                    break
                                
    async def build_refineries(self):
        if (
            self.already_pending(UnitTypeId.REFINERY) + self.structures(UnitTypeId.REFINERY).ready.amount < self.get_ideal_building_count("REFINERY")
            and self.can_afford(UnitTypeId.REFINERY)
        ):
            geysers = self.vespene_geyser.closer_than(10, self.cc)
            for geyser in geysers:
                if self.gas_buildings.filter(lambda unit: unit.distance_to(geyser) < 1):
                    continue
                worker: Unit = self.select_build_worker(geyser)
                if worker is None:
                    continue
                worker.build_gas(geyser)
                break  # so that it doesn't queue two refineries at once

    async def build_depots(self):
        if (self.can_afford(UnitTypeId.SUPPLYDEPOT)
            and self.already_pending(UnitTypeId.SUPPLYDEPOT) < self.get_simultaneous_depot_count()
            and self.supply_cap < 200
        ):
            # First two depots go in specific locations:
            workers: Units = self.workers.gathering
            if len(self.depot_placement_positions) == 2:  # first depot
                    target_depot_location: Point2 = self.depot_placement_positions.pop()
                    worker: Unit = workers.closest_to(target_depot_location)  # used to be workers.random
                    worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location)
            elif len(self.depot_placement_positions) == 1:  # second depot
                if self.townhalls.amount >= self.get_ideal_building_count('COMMANDCENTER') and self.supply_army + self.supply_workers >= 21:  # second depot (or wait for expo)
                    target_depot_location: Point2 = self.depot_placement_positions.pop()
                    worker: Unit = workers.closest_to(target_depot_location)  # used to be workers.random
                    worker.build(UnitTypeId.SUPPLYDEPOT, target_depot_location)
            # Then they go wherever
            if len(self.depot_placement_positions) == 0:
                await self.build(UnitTypeId.SUPPLYDEPOT, near=self.cc.position.towards(self.game_info.map_center, 8))
                return
                

    async def build_upgrade_buildings(self):
        # Engineering Bays
        if (
            self.tech_requirement_progress(UnitTypeId.ENGINEERINGBAY) == 1
            and self.already_pending(UnitTypeId.ENGINEERINGBAY) + self.structures(UnitTypeId.ENGINEERINGBAY).ready.amount < self.get_ideal_building_count("ENGINEERINGBAY")
        ):
            if self.can_afford(UnitTypeId.ENGINEERINGBAY):
                await self.build(UnitTypeId.ENGINEERINGBAY, near=self.cc.position.towards(self.game_info.map_center, -12))
        # Armory
        elif (
            self.already_pending_upgrade(UpgradeId.TERRANINFANTRYWEAPONSLEVEL1) > 0.54
            and self.already_pending(UnitTypeId.ENGINEERINGBAY) + self.structures(UnitTypeId.ENGINEERINGBAY).ready.amount > 1
            and self.already_pending(UnitTypeId.ARMORY) + self.structures(UnitTypeId.ARMORY).ready.amount < 1
        ):
            if self.can_afford(UnitTypeId.ARMORY):
                await self.build(UnitTypeId.ARMORY, near=self.cc.position.towards(self.game_info.map_center, -12))

    async def build_missile_turrets(self):
        # TODO: only build forward turret if there are no enemy ground units nearby
        fwd_turret_pos = self.sorted_expo_locations[1].towards(self.game_info.map_center, 16)
        if (
            self.tech_requirement_progress(UnitTypeId.MISSILETURRET) == 1
            and not self.already_pending(UnitTypeId.MISSILETURRET)
            and not self.structures(UnitTypeId.MISSILETURRET).closer_than(2, fwd_turret_pos)
        ):
            await self.build(UnitTypeId.MISSILETURRET, fwd_turret_pos)
        elif (
            self.tech_requirement_progress(UnitTypeId.MISSILETURRET) == 1
            and self.already_pending(UnitTypeId.ENGINEERINGBAY) + self.structures(UnitTypeId.ENGINEERINGBAY).ready.amount > 1
            and self.already_pending(UnitTypeId.MISSILETURRET) + self.structures(UnitTypeId.MISSILETURRET).ready.amount < (self.townhalls.amount + 1)
            and self.already_pending(UnitTypeId.MISSILETURRET) - self.structures(UnitTypeId.MISSILETURRET).not_ready.amount < 1  # no more than 1 queued but not started
        ):
            for cc in self.townhalls:
                if not self.structures(UnitTypeId.MISSILETURRET).closer_than(9, cc.position):  # this CC does not have a nearby turret
                    if self.can_afford(UnitTypeId.MISSILETURRET):
                        await self.build(UnitTypeId.MISSILETURRET, near=cc.position.towards(self.game_info.map_center, -4))

    async def upgrade_command_center(self):
        # returns 
        for cc in self.structures(UnitTypeId.COMMANDCENTER).ready.idle:
            abilities = await self.get_available_abilities(cc)
            if AbilityId.UPGRADETOORBITAL_ORBITALCOMMAND in abilities:
                if self.can_afford(AbilityId.UPGRADETOORBITAL_ORBITALCOMMAND):
                    cc(AbilityId.UPGRADETOORBITAL_ORBITALCOMMAND)
                else:
                    return("cant_afford")  # would otherwise do

    async def manage_orbital_energy(self):
        for cc in self.structures(UnitTypeId.ORBITALCOMMAND).ready:
            abilities = await self.get_available_abilities(cc)
            if AbilityId.CALLDOWNMULE_CALLDOWNMULE in abilities and cc.energy >= 50:
                cc(AbilityId.CALLDOWNMULE_CALLDOWNMULE, self.get_mule_target())

    async def finish_constructing_buildings(self):
        #if self.units.structure.not_ready.amount > constructingscvcount:
        for building in self.structures.not_ready:  # for each unfinished building
            if "TechLab" in building.name or "Reactor" in building.name: continue  # ignore addons
            isbuilding = False
            for worker in self.workers:  # iterate through every worker
                if worker.is_constructing_scv and worker.distance_to(building) < 3.1:  # this worker is constructing this building
                    isbuilding = True
                    break  # stop looking through workers
            if not isbuilding:  # if no workers are constructing this unfinished building
                if self.enemy_units.closer_than(8, building):
                    building(AbilityId.CANCEL_BUILDINPROGRESS)
                elif self.workers:
                    newworker = self.workers.gathering.random
                    newworker.smart(building)
                    #await self.do_actions(newworker(SMART,building))
        
        """
        if self.units.structure.not_ready.amount > self.units(SCV).is_constructing_scv.amount:  # if there is an unfinished building
            print("---------> a building is not finished !")
            for building in self.units.structure.not_ready:  # for each unfinished building
                if not self.units(SCV).is_constructing_scv.closer_than(2,building):  # if this building is not being constructed
                    ws = self.workers.gathering
                    w = ws.random
                    await self.do_actions(w(SMART,building))
        """

    async def repair_damaged_buildings(self):
        for building in self.structures.ready:
            if building.health_percentage < 1 and building.health_percentage > 0.05:
                repairingworkers = 0
                for worker in self.workers.closer_than(3, building.position):
                    if worker.is_repairing and worker.order_target == building.tag:
                        repairingworkers += 1
                if repairingworkers < 3 and self.workers.gathering:
                    self.workers.gathering.closest_to(building.position).smart(building)

    async def research_upgrades(self):
        for ebay in self.structures(UnitTypeId.ENGINEERINGBAY).ready.idle:
            abilities = await self.get_available_abilities(ebay)
            if AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL1 in abilities and self.can_afford(AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL1):
                ebay.research(UpgradeId.TERRANINFANTRYWEAPONSLEVEL1)
            elif AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL2 in abilities and self.can_afford(AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL2):
                ebay.research(UpgradeId.TERRANINFANTRYWEAPONSLEVEL2)
            elif AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL3 in abilities and self.can_afford(AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYWEAPONSLEVEL3):
                ebay.research(UpgradeId.TERRANINFANTRYWEAPONSLEVEL3)
            elif AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL1 in abilities and self.can_afford(AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL1):
                ebay.research(UpgradeId. TERRANINFANTRYARMORSLEVEL1)
            elif AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL2 in abilities and self.can_afford(AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL2):
                ebay.research(UpgradeId. TERRANINFANTRYARMORSLEVEL2)
            elif AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL3 in abilities and self.can_afford(AbilityId.ENGINEERINGBAYRESEARCH_TERRANINFANTRYARMORLEVEL3):
                ebay.research(UpgradeId. TERRANINFANTRYARMORSLEVEL3)
        for raxlab in self.structures(UnitTypeId.BARRACKSTECHLAB).ready.idle:
            abilities = await self.get_available_abilities(raxlab)
            if (  # Stimpack
                AbilityId.BARRACKSTECHLABRESEARCH_STIMPACK in abilities
                and self.can_afford(AbilityId.BARRACKSTECHLABRESEARCH_STIMPACK)
                and self.already_pending(UnitTypeId.FACTORY) + self.structures(UnitTypeId.FACTORY).ready.amount > 0
            ):
                raxlab.research(UpgradeId.STIMPACK)
            elif (  # Combat Shield
                AbilityId.RESEARCH_COMBATSHIELD in abilities
                and self.can_afford(AbilityId.RESEARCH_COMBATSHIELD)
                and self.already_pending(UnitTypeId.FACTORY) + self.structures(UnitTypeId.FACTORY).ready.amount > 0
            ):
                raxlab.research(UpgradeId.SHIELDWALL)  # why the hell is it UpgradeId.SHIELDWALL while UpgradeId.COMBATSHIELD is an entirely different thing?
            elif (  # Concussive Shells
                AbilityId.RESEARCH_CONCUSSIVESHELLS in abilities
                and self.can_afford(AbilityId.BARRACKSTECHLABRESEARCH_STIMPACK)
                and self.can_afford(AbilityId.RESEARCH_CONCUSSIVESHELLS)
            ):
                raxlab.research(UpgradeId.PUNISHERGRENADES)

    async def raise_lower_depots(self):
        prox_threshold = 15
        # depots will lower when the closest non-flying enemy unit is closer than this threshold
        lowered_depots = self.structures.of_type(SUPPLYDEPOTLOWERED)
        raised_depots = self.structures.of_type(SUPPLYDEPOT)

        # if lowered_depots:  # consider raising them
        for depot in lowered_depots:
            if self.enemy_units.filter(lambda u: not u.is_flying):
                closest_enemy = self.enemy_units.filter(lambda u: not u.is_flying).closest_to(depot)  # the non-flying enemy unit that is closest to the depot
                if closest_enemy and depot.distance_to(closest_enemy) < prox_threshold:  # enemies getting close
                    depot(AbilityId.MORPH_SUPPLYDEPOT_RAISE)
        
        for depot in raised_depots:
            if self.enemy_units.filter(lambda u: not u.is_flying):
                closest_enemy = self.enemy_units.filter(lambda u: not u.is_flying).closest_to(depot)
                #closest_enemy = Units([u for u in self.enemy_units if not u.is_flying]).closest_to(depot)
                if closest_enemy and depot.distance_to(closest_enemy) > prox_threshold:  # enemies getting farther away
                    depot(AbilityId.MORPH_SUPPLYDEPOT_LOWER)
            else:
                depot(AbilityId.MORPH_SUPPLYDEPOT_LOWER)
        
        """
        self.depots: Units = self.structures.of_type({UnitTypeId.SUPPLYDEPOT, UnitTypeId.SUPPLYDEPOTLOWERED})

        if self.depots:
            self.depot_placement_positions: Set[Point2] = {
                d for d in self.depot_placement_positions if self.depots.closest_distance_to(d) > 1
            }
        # Lower depos when no enemies are nearby
        for depot in self.structures(UnitTypeId.SUPPLYDEPOT).ready:
            for unit in self.enemy_units:
                if self.townhalls.amount == 1 and unit.distance_to(depot) < 15 and not unit.is_flying:
                    pass
                elif unit.distance_to(depot) < 10 and not unit.is_flying:  # we don't want units to be locked in the main while there are enemy units in the natural
                    pass
                depot(AbilityId.MORPH_SUPPLYDEPOT_LOWER)

            else:  # no enemy units found
                depot(AbilityId.MORPH_SUPPLYDEPOT_LOWER)
        # Raise depos when enemies are nearby if there is only 1 CC
        if self.townhalls.amount == 1:
            for depot in self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready:
                for unit in self.enemy_units:
                    if unit.distance_to(depot) < 10 and not unit.is_flying:
                        depot(AbilityId.MORPH_SUPPLYDEPOT_RAISE)
                        break
        # Or under stricter conditions if there are multiple CCs
        if self.townhalls.amount < 4:
            for depot in self.structures(UnitTypeId.SUPPLYDEPOTLOWERED).ready:
                for unit in self.enemy_units:
                    if unit.distance_to(depot) < 10 and not unit.is_flying:
                        depot(AbilityId.MORPH_SUPPLYDEPOT_RAISE)
                        break
        """

    async def flavor_chat(self, iteration):
        if self.chatty and not self.surrendernow:
            if iteration == 25:
                await self.chat_send("All right, I'm going to ask you a series of questions.")
            elif iteration == 35:
                await self.chat_send("Just relax and answer them as simply as you can.")
            elif iteration == 170:
                await self.chat_send("It's your birthday. Someone gives you a calfskin wallet.")
            elif iteration == 210:
                await self.chat_send("You've got a little boy. He shows you his butterfly collection plus the killing jar.")
            elif iteration == 250:
                await self.chat_send("You're watching television. Suddenly you realize there's a wasp crawling on your arm.")
            elif iteration == 290:
                await self.chat_send("You're reading a magazine. You come across a full page nude photo of a girl.")
            elif iteration == 300:
                await self.chat_send("You show it to your husband. He likes it so much he hangs it on your bedroom wall.")

    async def train_workers(self):
        if self.can_afford(UnitTypeId.SCV) and self.supply_workers < self.get_ideal_worker_count() and self.cc.is_idle:
            self.cc.train(UnitTypeId.SCV)

    async def train_from_barracks(self):
        for rax in self.structures(UnitTypeId.BARRACKS).ready:
            if rax.is_idle:
                if rax.has_techlab:
                    if self.can_afford(UnitTypeId.MARAUDER): rax.train(UnitTypeId.MARAUDER)
                elif not self.built_reaper:
                    if self.can_afford(UnitTypeId.REAPER):
                        rax.train(UnitTypeId.REAPER)
                        self.built_reaper = True  # TODO: always have 1 reaper until the opponent is on 3+ bases
                else:
                    if self.can_afford(UnitTypeId.MARINE): rax.train(UnitTypeId.MARINE)
            if rax.has_reactor and len(rax.orders) < 2:  # not elif
                    if self.can_afford(UnitTypeId.MARINE): rax.train(UnitTypeId.MARINE)

    async def train_from_factory(self):
        for fac in self.structures(UnitTypeId.FACTORY).ready.idle:
            if (
                self.can_afford(UnitTypeId.SIEGETANK)
                and len(self.units.of_type({SIEGETANK, SIEGETANKSIEGED})) + self.already_pending(UnitTypeId.SIEGETANK) < self.get_ideal_unit_count("SIEGETANK")
                and self.already_pending(UnitTypeId.STARPORT) + self.structures(UnitTypeId.STARPORT).ready.amount > 0  # must have already started starport
            ):
                fac.train(UnitTypeId.SIEGETANK)
            elif self.can_afford(UnitTypeId.THOR) and self.units(UnitTypeId.THOR).amount + self.already_pending(UnitTypeId.THOR) < self.get_ideal_unit_count("THOR"):
                fac.train(UnitTypeId.THOR)

    async def train_from_starport(self):
        for sp in self.structures(UnitTypeId.STARPORT).ready:
            if sp.is_idle and sp.has_techlab:
                if self.can_afford(UnitTypeId.RAVEN) and len(self.units.of_type({RAVEN})) + self.already_pending(UnitTypeId.RAVEN) < self.get_ideal_unit_count("RAVEN"):
                    sp.train(UnitTypeId.RAVEN)
                elif self.can_afford(UnitTypeId.RAVEN) and len(self.units.of_type({MEDIVAC})) + self.already_pending(UnitTypeId.MEDIVAC) < self.get_ideal_unit_count("MEDIVAC"):
                    # Tech lab starport only trains medivacs if it had a chance to buy a raven and chose not to
                    sp.train(UnitTypeId.MEDIVAC)
            elif sp.has_reactor and len(sp.orders) < 2:
                if self.can_afford(UnitTypeId.MEDIVAC) and len(self.units.of_type({MEDIVAC})) + self.already_pending(UnitTypeId.MEDIVAC) < self.get_ideal_unit_count("MEDIVAC"):
                    # Train Medivacs first
                    sp.train(UnitTypeId.MEDIVAC)
                elif self.can_afford(UnitTypeId.VIKINGFIGHTER) and len(self.units.of_type({VIKINGFIGHTER, VIKINGASSAULT})) + self.already_pending(UnitTypeId.VIKINGFIGHTER) < self.get_ideal_unit_count("VIKING"):
                    sp.train(UnitTypeId.VIKINGFIGHTER)
                    # Train Vikings
            elif sp.is_idle and len(self.units.of_type({MEDIVAC})) <= 1:  # idle sp with no addons builds up to 1 medivac - starport should just build an addon first though, so
                if self.can_afford(UnitTypeId.MEDIVAC): sp.train(UnitTypeId.MEDIVAC)

    async def expand(self):
        if (
            self.townhalls.amount < self.get_ideal_building_count("COMMANDCENTER")
            and self.can_afford(UnitTypeId.COMMANDCENTER)
            and not self.already_pending(UnitTypeId.COMMANDCENTER)
        ):
            if not self.enemy_units.closer_than(40, self.start_location) or self.townhalls.amount > 1:
                await self.expand_now()

    def get_enemy_army_value(self):
        value_minerals = 0
        value_gas = 0
        for tag, udict in self.opponent_info['army_units_scouted'].items():
            # value_minerals += self.calculate_unit_value(this_unit.type_id).minerals
            # value_gas += self.calculate_unit_value(this_unit.type_id).vespene
            value_minerals += udict['value_minerals']
            value_gas += udict['value_gas']
        return (value_minerals, value_gas)

    def get_attack_length(self, reset=False):
        if reset:
            self.value_killed_minerals_base = self.value_killed_minerals
            self.value_killed_vespene_base = self.value_killed_vespene
            self.value_lost_minerals_base = self.value_lost_minerals
            self.value_lost_vespene_base = self.value_lost_vespene

        self.total_value_killed = (self.value_killed_minerals - self.value_killed_minerals_base) + (self.mineral_gas_ratio * (self.value_killed_vespene - self.value_killed_vespene_base))
        self.total_value_lost = (self.value_lost_minerals - self.value_lost_minerals_base) + (self.mineral_gas_ratio * (self.value_lost_vespene - self.value_lost_vespene_base))
        
        return self.attack_length + (self.total_value_killed - self.total_value_lost)/80
    
    def get_attack_downtime(self, reset=False):
        if reset:
            self.calculated_attack_downtime = self.attack_downtime
        
        #total_value_killed = self.value_killed_minerals + (self.mineral_gas_ratio * self.value_killed_vespene)
        #total_value_lost = self.value_lost_minerals + (self.mineral_gas_ratio * self.value_lost_vespene)

        if self.supply_cap == 200 and self.supply_left < 3: modifier = -60
        else: modifier = 0
        
        #downtime = self.calculated_attack_downtime + modifier + (total_value_lost - total_value_killed)/100
        downtime = self.calculated_attack_downtime + modifier - self.get_resources_lost('diff')/100
        
        if downtime > 0: return downtime
        else: return 0

    def get_resources_lost(self, typ='t'):
        """
        typ=t:      Returns a tuple: (< total_value_lost >, < total_value_killed>)
        typ='diff': Returns an int: total_value_killed - total_value_lost
        """
        total_value_lost = self.value_lost_minerals + (self.mineral_gas_ratio * self.value_lost_vespene)
        total_value_killed = self.value_killed_minerals + (self.mineral_gas_ratio * self.value_killed_vespene)
        
        if typ == 't':
            return ((total_value_lost, total_value_killed))
        elif typ == 'diff':
            return total_value_killed - total_value_lost
        else: raise Exception  # invalid typ


    def get_mule_target(self):
        for cc in self.townhalls.ready:
            if cc.tag == max(self.townhalls.tags):
                return self.mineral_field.closest_to(cc)

    def get_pos_to_scout(self):
        enemy_expo_pos_list = [p.position for p in self.opponent_info["expansions"]]
        if self.enemy_start_locations[0] not in enemy_expo_pos_list:  # if not scouted their main yet
            return self.enemy_start_locations[0]  # scout their main
        to_scout = {}
        for loc in self.sorted_expo_locations:
            if loc not in enemy_expo_pos_list and loc not in [p.position for p in self.townhalls]:  # no friendly or hostile base at this location
                to_scout[loc] = 140 - loc.distance_to(self.enemy_start_locations[0])  # {(115.5, 27.5): -5.3, (135.5, 61.5): 6.3, (83.5, 28.5): 10.6, ...}  position keyed to weight
        cho = random.choices(list(to_scout.keys()), [x**3 for x in to_scout.values()])[0]  # weighted choice of cubed adjusted distance values - there has to be a better way to do this
        #print(f"to_scout is {to_scout}")
        #print(f"cho is {cho}")
        return cho
        #return random.choice(to_scout)

    def get_ideal_unit_count(self, unit):
        if unit == "SIEGETANK":
            return self.townhalls.amount
        elif unit == "THOR":
            return self.army_need_thors * self.townhalls.amount
        elif unit == "MEDIVAC":
            return round(1.7 * self.townhalls.amount)
        elif unit == "VIKING":
            return self.army_need_vikings * round(1.5 * self.townhalls.amount)
        elif unit == "RAVEN":
            if self.townhalls.amount < 4: return 1
            else: return 2
        else: raise(Exception)

    def get_ideal_building_count(self, building):
        th = self.townhalls.amount
        adjusted_time = self.time - (self.my_stats['workers_lost'] * 5) - (self.get_resources_lost('diff') / 200)
        if building == "COMMANDCENTER":
            if self.beingcheesed: adjusted_time -= 60  # take natural 60 seconds later 
            elif self.be_aggressive and th >= 2: adjusted_time -= 60  # take 3rd 60 seconds later

            if adjusted_time < 100: return 1    # 1:40
            elif adjusted_time < 330: return 2  # 5:30
            elif adjusted_time < 560: return 3  # 9:20
            elif adjusted_time < 690: return 4  # 11:30
            elif adjusted_time < 840: return 5  # 14:00
            else: return 6
        elif building == "BARRACKS":
            if th == 1: ib = 1
            elif self.townhalls.ready.amount == 2: ib = 3
            elif th == 2: ib = 1  # ?
            elif th == 3: ib = 4
            elif th == 4: ib = 7
            elif th == 5: ib = 10
            else: ib = 15
            if self.beingcheesed and th == 1: ib += 1
            if self.townhalls.ready.amount >= 2 and self.be_aggressive: ib += 2  # 2 more rax on 2+ bases
            return ib
        elif building == "FACTORY":
            if th < 5 and self.structures.of_type(UnitTypeId.BARRACKS).amount >= 1: return 1  # rax finished
            else: return 2
        elif building == "STARPORT":
            if self.townhalls.ready.amount < 3 and self.structures.of_type(UnitTypeId.FACTORY).amount == 1: return 1  # factory finished
            elif self.townhalls.ready.amount < 4: return 2
            else: return 3
        elif building == "REFINERY":
            if not self.structures.of_type({SUPPLYDEPOT, SUPPLYDEPOTLOWERED}): return 0  # until supply depot started
            elif th < 2: return th
            elif self.townhalls.ready.amount == 2: return 3
            elif th == 2: return th
            elif self.minerals > 1000 and self.vespene < 200: return th + 3
            else: return th + 1
        elif building == "ENGINEERINGBAY":
            if th > 2: return 2
            elif self.structures.of_type(UnitTypeId.STARPORT).amount == 1: return 1 
            elif adjusted_time > 200: return 1  # 3:20
            else: return 0
        else: raise(Exception)  # that building isn't in get_ideal_building_count

    def get_ideal_worker_count(self):
        idealworkers = (16 * self.townhalls.amount) + (3 * self.get_ideal_building_count("REFINERY"))
        if idealworkers < 70: return idealworkers
        else: return 70
        """
        th = self.townhalls.amount
        if th == 0:
            return 0
        elif th == 1:
            return 26
        elif th == 2:
            return 41
        elif th == 3:
            return 57
        else:
            return 70
        """
    
    def get_simultaneous_depot_count(self):
        if self.time < 120 and self.supply_left < 3: return 1
        elif self.supply_left < 3: return 2
        elif self.supply_left < 7: return 1
        else: return 0

    def get_rally_point(self):
        # return self.start_location.towards(self.game_info.map_center, 16)
        # return list(self.sorted_expo_locations)[1].towards(self.game_info.map_center, 16)
        return self.sorted_expo_locations[1].towards(self.game_info.map_center, 16)
    
    def get_valk_point(self):
        return self.townhalls.center.towards(self.game_info.map_center, 8)
        
    def get_base_target(self):
        """ Select an enemy target the units should attack. """
        # i think this whole top part is depreciated because of the hunt function and now it'll only return enemy start locations position
        # TODO: want to eventually have it return other places like the most recently taken base or somewhere after the army has been drawn away
        if self.units and min([u.position.distance_to(self.enemy_start_locations[0]) for u in self.units]) < 5:
            if self.enemy_structures: return self.enemy_structures.random.position
            return self.mineral_field.random.position
        else:
            return self.enemy_start_locations[0].position

    def showdebuginfo(self, iteration):
        self._client.debug_text_simple(text="Deckard v0.1")

        debugtext1 = "# Bases:            " + str(self.townhalls.amount) + "/" + str(self.get_ideal_building_count("COMMANDCENTER"))
        self._client.debug_text_screen(text=debugtext1, pos=Point2((0, 0.05)), color=None, size=8)

        debugtext2 = "Opponent # Bases:   " + str(len(self.opponent_info['expansions']))
        self._client.debug_text_screen(text=debugtext2, pos=Point2((0, 0.06)), color=None, size=8)

        debugtext3 = "Worker Supply:      " + str(self.supply_workers) + "/" + str(self.get_ideal_worker_count())
        self._client.debug_text_screen(text=debugtext3, pos=Point2((0, 0.07)), color=None, size=8)

        debugtext4 = "Workers Lost:       " + str(self.my_stats['workers_lost'])
        self._client.debug_text_screen(text=debugtext4, pos=Point2((0, 0.08)), color=None, size=8)

        debugtext5 = "# Barracks:         " + str(self.structures.of_type({UnitTypeId.BARRACKS, UnitTypeId.BARRACKSFLYING}).amount) + "/" + str(self.get_ideal_building_count("BARRACKS"))
        self._client.debug_text_screen(text=debugtext5, pos=Point2((0, 0.09)), color=None, size=8)

        debugtext6 = "# Refineries:       " + str(self.structures.of_type({UnitTypeId.REFINERY}).amount) + "/" + str(self.get_ideal_building_count("REFINERY"))
        self._client.debug_text_screen(text=debugtext6, pos=Point2((0, 0.10)), color=None, size=8)

        debugtext7 = "Iteration:          " + str(iteration)
        self._client.debug_text_screen(text=debugtext7, pos=Point2((0, 0.11)), color=None, size=8)

        debugtext8 = "Army Mood:          " + str(self.army_mood)
        self._client.debug_text_screen(text=debugtext8, pos=Point2((0, 0.12)), color=None, size=8)

        debugtext9 = "# Marines:          " + str(len(self.units.of_type({MARINE})))
        self._client.debug_text_screen(text=debugtext9, pos=Point2((0, 0.13)), color=None, size=8)

        debugtext10 = "# Tanks:            " + str(len(self.units.of_type({SIEGETANK, SIEGETANKSIEGED}))) + "/" + str(self.get_ideal_unit_count("SIEGETANK"))
        self._client.debug_text_screen(text=debugtext10, pos=Point2((0, 0.14)), color=None, size=8)

        debugtext11 = "# Medivacs:         " + str(len(self.units.of_type({MEDIVAC}))) + "/" + str(self.get_ideal_unit_count("MEDIVAC"))
        self._client.debug_text_screen(text=debugtext11, pos=Point2((0, 0.15)), color=None, size=8)

        debugtext12 = "Enemy Main Dead:    " + str(self.army_destroyed_enemy_main)
        self._client.debug_text_screen(text=debugtext12, pos=Point2((0, 0.16)), color=None, size=8)

        atktimer = round(self.attack_start_time + self.get_attack_length() - self.time)
        if atktimer <= 0: atktimer = "-"
        debugtext13 = "Attack Timer:       " + str(atktimer)
        self._client.debug_text_screen(text=debugtext13, pos=Point2((0, 0.17)), color=None, size=8)

        dwntimer = round(self.attack_end_time + self.get_attack_downtime() - self.time)
        if dwntimer <= 0: dwntimer = "-"
        debugtext14 = "Time Until Attack:  " + str(dwntimer)
        self._client.debug_text_screen(text=debugtext14, pos=Point2((0, 0.18)), color=None, size=8)

        rk_timer = "Recently Killed:    " + str(self.total_value_killed)
        self._client.debug_text_screen(text=rk_timer, pos=Point2((0, 0.19)), color=None, size=8)
        rl_timer = "Recently Lost:      " + str(self.total_value_lost)
        self._client.debug_text_screen(text=rl_timer, pos=Point2((0, 0.20)), color=None, size=8)

        cheesecheck = "Being Cheesed?      " + str(self.beingcheesed)
        self._client.debug_text_screen(text=cheesecheck, pos=Point2((0, 0.21)), color=None, size=8)

        
        self._client.debug_text_world("RALLY", Point3((self.get_rally_point().x, self.get_rally_point().y, self.get_terrain_z_height(self.get_rally_point()))), size=12)

        self._client.debug_text_world("VALK", Point3((self.get_valk_point().x, self.get_valk_point().y, self.get_terrain_z_height(self.get_valk_point()))), size=12)

        """
        sorted_expo_locations = self.start_location.sort_by_distance(self.expansion_locations_list)
        for n in range(len(list(sorted_expo_locations))):
            self._client.debug_text_world(str(n), Point3((list(sorted_expo_locations)[n].x, list(sorted_expo_locations)[n].y, self.get_terrain_z_height(list(sorted_expo_locations)[n]))), size=22)
        """

    async def intel(self):
        # for game_info: https://github.com/Dentosal/python-sc2/blob/master/sc2/game_info.py#L162
        # flip around. It's y, x when you're dealing with an array.

        game_data = np.zeros((self.game_info.map_size[1], self.game_info.map_size[0], 3), np.uint8)

        draw_dict = {
                     SUPPLYDEPOT: [2, (20, 200, 0)],
                     SUPPLYDEPOTLOWERED: [2, (20, 200, 0)],
                     SCV: [1, (55, 200, 0)],
                     REFINERY: [2, (55, 200, 0)],
                     BARRACKS: [3, (200, 140, 0)],
                     ENGINEERINGBAY: [3, (150, 150, 0)],
                     STARPORT: [3, (200, 140, 0)],
                     FACTORY: [3, (215, 155, 0)],
                     MARINE: [1, (255, 100, 0)],
                     MARAUDER: [1, (200, 100, 0)],
                     MEDIVAC: [1, (255, 255, 200)],
                     RAVEN: [1, (150, 150, 50)],
                    }

        for unit_type in draw_dict:
            for unit in self.units(unit_type):
                pos = unit.position
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), draw_dict[unit_type][0], draw_dict[unit_type][1], -1)
            for structure in self.structures(unit_type):
                pos = structure.position
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), draw_dict[unit_type][0], draw_dict[unit_type][1], -1)
        
        for townhall in self.townhalls:
            cv2.circle(game_data, (int(townhall.position[0]), int(townhall.position[1])), 4, (0, 255, 0), -1)  # BGR
        #for rax in self.units(BARRACKS):
        #    cv2.circle(game_data, (int(rax.position[0]), int(rax.position[1])), 6, (0, 255, 0), -1)  # BGR

        main_base_names = ["nexus", "commandcenter", "hatchery"]
        for enemy_building in self.enemy_structures:
            pos = enemy_building.position
            if enemy_building.name.lower() not in main_base_names:
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), 3, (200, 50, 212), -1)
        for enemy_building in self.enemy_structures:
            pos = enemy_building.position
            if enemy_building.name.lower() in main_base_names:
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), 4, (0, 0, 255), -1)
        for enemy_unit in self.enemy_units:
            pos = enemy_unit.position
            cv2.circle(game_data, (int(pos[0]), int(pos[1])), 1, (0, 0, 200), -1)

        # flip horizontally to make our final fix in visual representation:
        flipped = cv2.flip(game_data, 0)
        resized = cv2.resize(flipped, dsize=None, fx=2, fy=2)

        cv2.imshow('DeckardIntel', resized)
        cv2.waitKey(1)

    async def telemetry(self):
        for th in self.townhalls:
            pass


    def on_end(self, result):  # Do things here after the game ends
        print(self.my_stats)
        print("Game ended.")
        if self.make_log:
            self.logfile.write("Deckard exited nicely. \n")
            self.logfile.close()




if __name__ == "__main__":
    main()
