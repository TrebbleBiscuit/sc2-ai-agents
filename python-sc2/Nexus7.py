import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.player import Bot, Computer
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2, Point3
from sc2.helpers import ControlGroup

from s2clientprotocol import raw_pb2 as raw_pb
from s2clientprotocol import sc2api_pb2 as sc_pb

from loguru import logger
import numpy as np
import cv2
import random

import utils

###############################
### Nexus-7 by Erik Nielsen ###
###    A Starcraft II AI    ###
###############################

class Nexus7(sc2.BotAI):
    async def on_start(self):
        # import sys
        # logger.remove()
        # logger.add(sys.stderr, level="DEBUG")
        logger.success('Nexus-7 Online')
        self.control_groups = {}  # 'Control Group 1': <ControlGroup object>

    async def on_step(self, iteration):
        self.total_worker_supply = self.supply_workers + self.already_pending(UnitTypeId.SCV)
        self.iteration = iteration  # so that we can use this within functions
        if iteration == 0:
            # self._client.game_step = 2  # only step every n frames
            self.sorted_expo_locations = self.start_location.sort_by_distance(self.expansion_locations_list)
            for w in self.workers:  # split workers
                w.gather(self.mineral_field.closest_to(w))
        
        if iteration == 7: await self.chat_send("Nexus-7. GLHF.")

        utils.process_scouting(self)  # populate self.opponent_data
        self.showdebuginfo()
        await self.intel()

        # Actions
        await self.distribute_workers()
        await self.army_movement()
        await self.observer_movement()
        await self.ability_bilnk()
        await self.ability_chronoboost()
        await self.morph_archons()
        await self.probe_scout()

        # Macro
        if self.townhalls:
            await self.train_workers()
            await self.construct_additional_pylons()
            await self.build_assimilators()
            await self.build_production()
        await self.expand()

        # Upgrades
        await self.upgrade_warp_gate()
        await self.twilight_upgrades()
        await self.forge_upgrades()

        # Unit Production
        await self.warp_in_gateway_units()
        await self.warp_in_robo_units()

    async def on_unit_destroyed(self, tag):
        for entry in self.opponent_data["army_tags_scouted"]:
            if entry['tag'] == tag:
                self.opponent_data["army_tags_scouted"].remove(entry)
        enemylost = self._enemy_units_previous_map.get(tag) or self._enemy_structures_previous_map.get(tag)
        if enemylost and enemylost.type_id in [HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS]:
            #print("ENEMY LOST TOWNHALL!")
            #print(enemylost)
            #print(f"It was at position: {enemylost.position}")
            #print("was it in the expansions list?")
            if enemylost.position in self.opponent_data["expansions"]: 
                logger.success('Destroyed Enemy Townhall!')
                self.opponent_data["expansions"].remove(enemylost.position)
            else: 
                logger.warning('Enemy lost an expansion not in opponent_data["expansions"] - probably a thing with a floating or morphed building?')

    def are_we_attacking(self):
        army_supply = self.supply_used - self.supply_workers - self.already_pending(UnitTypeId.SCV)
        # Attack at certain times - 510 sec = 8:30, 780 sec = 13:00
        if self.time > 510 and self.time < 600 or self.time > 780:
            # but only if our army isn't puny
            if army_supply > self.opponent_data['army_supply_scouted'] * .8:
                return True
        # Attack in the midgame if our army is much bigger
        elif (
            self.time > 60*6  # TODO: tweak this to as low as possible but after we get a good scout
            and army_supply > self.opponent_data['army_supply_scouted'] * 2
        ):

            return True
        return False

    async def army_movement(self):
        forces = self.units.of_type({STALKER, ZEALOT, IMMORTAL, ARCHON, HIGHTEMPLAR})
        observers = self.units.of_type(OBSERVER)
        army_supply = self.supply_used - self.supply_workers - self.already_pending(UnitTypeId.SCV)
        # # Attack with 1st Zealot
        # TODO: doesn't work because during non-attack periods all forces get amoved to the rally point
        # if self.time < 120 and len(forces) == 1 and len(forces.idle) == 1:
        #     logger.info('Attacking with first zealot')
        #     for unit in forces.idle:
        #         unit.attack(self.enemy_start_locations[0].position)
        # Attack with army
        if self.are_we_attacking():
            for unit in forces.idle:
                unit.attack(self.get_attack_target())
        elif self.iteration % 6 == 0:
            close_enemies = self.enemy_units.closer_than(60, self.start_location)
            # Attack enemies near our base
            if close_enemies:
                for unit in forces.idle:
                    unit.attack(close_enemies.random.position)
                # TODO: observers 
                # for obs2 in observers:
                #     obs2.attack(forces.closest_to(close_enemies.closest_to(obs2)))
            else:
                # Send forces to rally point
                for unit in forces:  # TODO: idle?
                    unit.attack(self.get_rally_point())
    
    def create_observer_control_groups(self):
        """ Create control groups """
        observers = self.units.of_type(OBSERVER)
        # will do nothing until an observer is made
        # then sequentially assign them to control groups one at a time
        valid_observers = []
        for obs in observers:
            try:
                o1 = self.control_groups['Observer 1']
                if obs.tag == o1.select_units(self.units)[0].tag:
                    continue  # to next observer
            except (KeyError, IndexError):
                pass
            try:
                o2 = self.control_groups['Observer 2']
                if obs.tag == o2.select_units(self.units)[0].tag:
                    continue  # to next observer
            except (KeyError, IndexError):
                pass
            valid_observers.append(obs)
        # valid_observers are not assigned to another control group
        for obs in valid_observers:
            # make sure valid_observers is of length 1
            try:
                assert len(valid_observers) == 1  # debug - observers must be assigned immediately
            except AssertionError:
                logger.error('valid_observers should be of length 1')
                valid_observers = Units(valid_observers[0])
            # if this observer is already in a control group do not reassign it
            try:
                o1 = self.control_groups['Observer 1']
                if o1.empty:
                    raise KeyError
            # KeyError if control group does not exist or is empty
            # TODO: maybe i should just init a bunch of control groups at the start of the game
            # and not have to worry about all this garbage
            except KeyError:
                self.control_groups['Observer 1'] = ControlGroup(valid_observers)
                logger.success('Assigned Observer to `Observer 1` Control Group')
                return
            try:
                o2 = self.control_groups['Observer 2']
                if o2.empty: raise KeyError
            except KeyError:
                self.control_groups['Observer 2'] = ControlGroup(valid_observers)
                logger.success('Assigned Observer to `Observer 2` Control Group')
                return
            

    async def observer_movement(self):
        self.create_observer_control_groups()
        # See if the control groups exist one by one
        # Sequential control groups will not be checked

        # Control Group 'Observer 1'
        try:
            o1cg = self.control_groups['Observer 1']
            missing = o1cg.missing_unit_tags(self.units)
            if missing:
                logger.info(f"Discarding Missing Unit Tags: {missing}")
                o1cg.discard(list(missing)[0])
            if o1cg.empty:  # do nothing if control group is empty
                pass  # move on to the next control group
            else:
                assert len(o1cg) == 1  # debug - should only have one per control group
                await self.control_observer_a()
        except KeyError:  # Do not do anything until the 'Observer 1' control group is created
            return

        # Control Group 'Observer 2'
        try:
            o2cg = self.control_groups['Observer 2']
            missing = o2cg.missing_unit_tags(self.units)
            if missing:
                logger.info(f"Discarding Missing Unit Tags: {missing}")
                o2cg.discard(list(missing)[0])
            if o2cg.empty:  # do nothing if control group is empty
                pass  # move on to the next control group
            else:
                assert len(o2cg) == 1  # debug - should only have one per control group
                await self.control_observer_b()
        except KeyError:  # Do not do anything until the 'Observer 2' control group is created
            return


    async def control_observer_a(self):
        if self.iteration % 2 == 0:
            o1cg = self.control_groups['Observer 1']
            # o1 is a Unit object, pull it out of the control group
            try:
                o1 = o1cg.select_units(self.units)[0]
            except IndexError:
                logger.warning('Got IndexError in control_observer_a')
                logger.info(f"o1cg is {o1cg}")
                return
            # Friendly forces to follow around
            forces = self.units.of_type({STALKER, ZEALOT, IMMORTAL, ARCHON, HIGHTEMPLAR})
            if forces:
                closest_force_to_enemy = forces.closest_to(self.enemy_start_locations[0])
                if closest_force_to_enemy.type_id == UnitTypeId.ZEALOT:
                    follow_distance = 8
                elif closest_force_to_enemy.type_id in {UnitTypeId.STALKER, UnitTypeId.IMMORTAL}:
                    follow_distance = 5
                else:
                    follow_distance = 6
                # follow the ally closest to the enemy
                o1.attack(closest_force_to_enemy.position.towards(self.start_location, follow_distance))

    async def control_observer_b(self):
        o2cg = self.control_groups['Observer 2']
        # Move observers around the map
        if self.iteration % 30 == 0:
            try:
                o2 = o2cg.select_units(self.units)[0]
            except IndexError:
                logger.warning('Got IndexError in control_observer_b')
                logger.info(f"o2cg is {o2cg}")
                return
            # if not scouted their main yet
            if self.enemy_start_locations[0] not in self.opponent_data["expansions"]:
                cho = self.enemy_start_locations[0]  # scout their main
            else:
                to_scout = {}
                # scout expansion locations with no friendly or hostile townhall
                for loc in self.sorted_expo_locations:
                    if loc not in self.opponent_data["expansions"] and loc not in [p.position for p in self.townhalls]:
                        # {(115.5, 27.5): -5.3, (135.5, 61.5): 6.3, (83.5, 28.5): 10.6, ...}  position keyed to weight
                        to_scout[loc] = 140 - loc.distance_to(self.enemy_start_locations[0])
                # weighted choice of adjusted distance values ()
                cho = random.choices(list(to_scout.keys()), [x**3 for x in to_scout.values()])[0]
            o2.attack(cho)
        
    async def probe_scout(self):
        try:
            self.probe_scouted
        except AttributeError:
            self.probe_scouted = False
        if not self.probe_scouted and self.total_worker_supply == 17:
            logger.success("Probe Scouting Now")
            self.probe_scouted = True
            enemy_main_pos = self.enemy_start_locations[0].position
            self.workers.gathering.closest_to(enemy_main_pos).move(enemy_main_pos)

    def get_attack_target(self):
        """ Select an enemy target the units should attack. """
        # If we have units very close to their start location
        if self.units and min([u.position.distance_to(self.enemy_start_locations[0]) for u in self.units]) < 5:
            if self.enemy_structures:
                return self.enemy_structures.random.position
            return self.mineral_field.random.position
        else:
            min_dist = 99
            closest_enemy_base = None
            for expo_pos in self.opponent_data["expansions"]:
                this_dist = expo_pos.distance_to(self.townhalls.center)  # closest enemy base to our territory
                if this_dist < min_dist:
                    min_dist = this_dist
                    closest_enemy_base = expo_pos
            if closest_enemy_base:
                return closest_enemy_base
            else:
                return self.enemy_start_locations[0].position


    async def ability_bilnk(self):
        stalkers = self.units(UnitTypeId.STALKER)
        for stalker in stalkers:
            abilities = await self.get_available_abilities(stalker)
            if (
                stalker.health_percentage < .5
                and stalker.shield_health_percentage < .3
                and AbilityId.EFFECT_BLINK_STALKER in abilities
            ):
                if self.enemy_units:
                    enemy = self.enemy_units.closest_to(stalker)
                    stalker(EFFECT_BLINK_STALKER, stalker.position.towards(enemy, -6))

    async def ability_chronoboost(self):
        if self.iteration % 4 == 0:
            cybers = self.structures(UnitTypeId.CYBERNETICSCORE).ready
            twilights = self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
            forges = self.structures(UnitTypeId.FORGE).ready
            # for nexus in self.townhalls.ready:
            for nexus in self.townhalls.ready:
                if nexus.energy >= 50:
                    for tc in filter(utils.is_valid_chrono_target, twilights):
                        # logger.info(f'Chronoing Twilight Council')
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, twilights.first)
                        return
                    for tc in filter(utils.is_valid_chrono_target, cybers):
                        # logger.info(f'Chronoing Cybernetics Core')
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, cybers.first)
                        return
                    for tc in filter(utils.is_valid_chrono_target, forges):
                        # logger.info(f'Chronoing Forge')
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, forges.first)
                        return

                    #elif not nexus.is_idle and not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                    #    nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, nexus)  # will only chrono itself, not another nexus

    async def train_workers(self):
        for nexus in self.townhalls:
            if (
                self.can_afford(UnitTypeId.PROBE)
                and self.supply_workers + self.already_pending(UnitTypeId.SCV) < self.get_ideal_worker_count()
                and nexus.is_idle
            ):
                nexus.train(UnitTypeId.PROBE)
    
    async def warp_in_gateway_units(self):
        if self.time < 150:
            for gateway in self.structures(UnitTypeId.GATEWAY).ready.idle:
                if not self.units.of_type(ZEALOT) and self.can_afford(ZEALOT):
                    gateway.train(ZEALOT)
                elif not self.units.of_type(STALKER) and self.can_afford(STALKER):
                    gateway.train(STALKER)

        for warpgate in self.structures(UnitTypeId.WARPGATE).ready:
            abilities = await self.get_available_abilities(warpgate)
            if self.units.of_type({STALKER}):  # avoid division by zero
                if (
                    self.already_pending_upgrade(UpgradeId.CHARGE) > .8  # Charge almost done
                    and len(self.units.of_type({ZEALOT})) / len(self.units.of_type({STALKER})) < 2
                    and AbilityId.WARPGATETRAIN_ZEALOT in abilities
                ):
                    target = self.structures(UnitTypeId.PYLON).ready.random.position.towards(self.game_info.map_center, 4)
                    placement = await self.find_placement(AbilityId.WARPGATETRAIN_ZEALOT, target, placement_step=1)
                    if placement is None:
                        # return ActionResult.CantFindPlacementLocation
                        logger.info("Can't find zealot placement")
                        return
                    warpgate.warp_in(UnitTypeId.ZEALOT, placement)
            if (
                AbilityId.WARPGATETRAIN_HIGHTEMPLAR in abilities
                and self.vespene > 400
            ):
                target = self.structures(UnitTypeId.PYLON).ready.random.position.towards(self.game_info.map_center, 4)
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_HIGHTEMPLAR, target, placement_step=1)
                if placement: warpgate.warp_in(UnitTypeId.HIGHTEMPLAR, placement)
            if (
                AbilityId.WARPGATETRAIN_STALKER in abilities
                and (self.supply_used < 180 or not self.units.of_type(STALKER))
            ):
                target = self.structures(UnitTypeId.PYLON).ready.random.position.towards(self.game_info.map_center, 4)
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_STALKER, target, placement_step=1)
                if placement is None:
                    # return ActionResult.CantFindPlacementLocation
                    logger.info("Can't find stalker placement")
                    return
                warpgate.warp_in(UnitTypeId.STALKER, placement)
    
    async def warp_in_robo_units(self):
        for robo in self.structures(UnitTypeId.ROBOTICSFACILITY).ready.idle:
            current_obs_count = len(self.units.of_type(UnitTypeId.OBSERVER)) + self.already_pending(UnitTypeId.OBSERVER)
            if (
                self.can_afford(UnitTypeId.OBSERVER)
                and current_obs_count <= 1
            ):
                logger.info(f'Training Observer {current_obs_count + 1}')
                robo.train(UnitTypeId.OBSERVER)
            elif (
                self.can_afford(UnitTypeId.IMMORTAL)
                and self.already_pending_upgrade(UpgradeId.BLINKTECH) == 1  # Blink already done
            ):
                robo.train(UnitTypeId.IMMORTAL)

    async def construct_additional_pylons(self):
        if (
            self.supply_left < 5 and self.already_pending(UnitTypeId.PYLON) == 0
            or self.time > 150 and self.supply_left < 2 and self.already_pending(UnitTypeId.PYLON) == 1
        ):
            if self.can_afford(UnitTypeId.PYLON) and self.townhalls.amount > 0:
                logger.info('Constructing an Additional Pylon')
                # TODO: get_pylon_location
                await self.build(UnitTypeId.PYLON, near=self.get_pylon_location())

    def get_pylon_location(self):
        n_pylons = self.already_pending(UnitTypeId.PYLON) + self.structures.of_type(UnitTypeId.PYLON).ready.amount
        if n_pylons == 0:
            # towards the main ramp
            return self.townhalls.first.position.towards(self.main_base_ramp.barracks_correct_placement, 8)
        else:
            return self.townhalls.ready.random.position.towards(self.game_info.map_center, random.uniform(6,8))

    async def build_assimilators(self):
        if (
            (self.structures(UnitTypeId.GATEWAY) or self.structures(UnitTypeId.WARPGATE))
            and self.already_pending(UnitTypeId.ASSIMILATOR) + self.structures(UnitTypeId.ASSIMILATOR).ready.amount < self.get_ideal_building_count("ASSIMILATOR")
            and self.can_afford(UnitTypeId.ASSIMILATOR)
        ):
            geysers = self.vespene_geyser.closer_than(10, self.townhalls.ready.random)
            for geyser in geysers:
                if self.gas_buildings.filter(lambda unit: unit.distance_to(geyser) < 1):
                    continue
                worker: Unit = self.select_build_worker(geyser)
                if worker is None:
                    continue
                worker.build_gas(geyser)
                break  # so that it doesn't queue two refineries at once

    async def build_production(self):
        if self.structures(UnitTypeId.PYLON).ready:
            pylon = self.structures(UnitTypeId.PYLON).ready.random
            if (  # Cybernetics Core
                self.structures(UnitTypeId.CYBERNETICSCORE).ready.amount + self.already_pending(UnitTypeId.CYBERNETICSCORE) == 0
                and self.structures(UnitTypeId.GATEWAY).ready
                and self.can_afford(UnitTypeId.CYBERNETICSCORE)
            ):
                logger.info('Building Cybernetics Core')
                await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
            elif (  # Gateways
                self.can_afford(UnitTypeId.GATEWAY)
                and self.already_pending(UnitTypeId.GATEWAY) + self.structures.of_type({UnitTypeId.GATEWAY, UnitTypeId.WARPGATE}).ready.amount < self.get_ideal_building_count("GATEWAY")
            ):
                logger.info('Building Gateway')
                await self.build(UnitTypeId.GATEWAY, near=pylon)
            elif (  # Twilight Council
                self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready.amount + self.already_pending(UnitTypeId.TWILIGHTCOUNCIL) == 0
                and self.structures(UnitTypeId.CYBERNETICSCORE).ready
                and self.can_afford(UnitTypeId.TWILIGHTCOUNCIL)
            ):
                logger.info('Building Twilight Council')
                await self.build(UnitTypeId.TWILIGHTCOUNCIL, near=pylon)
            elif ( # Forge
                self.structures(UnitTypeId.FORGE).ready.amount + self.already_pending(UnitTypeId.FORGE) < self.get_ideal_building_count("FORGE")
                and self.can_afford(UnitTypeId.FORGE)
            ):
                logger.info('Building Forge')
                await self.build(UnitTypeId.FORGE, near=pylon)
            elif (  # Robotics Facility
                self.structures(UnitTypeId.ROBOTICSFACILITY).ready.amount + self.already_pending(UnitTypeId.ROBOTICSFACILITY) < self.get_ideal_building_count("ROBOTICS FACILITY")
                and self.structures(UnitTypeId.CYBERNETICSCORE).ready
                and self.can_afford(UnitTypeId.ROBOTICSFACILITY)
            ):
                logger.info('Building Robotics Facility')
                await self.build(UnitTypeId.ROBOTICSFACILITY, near=pylon)
            elif (
                self.structures(UnitTypeId.TEMPLARARCHIVE).ready.amount + self.already_pending(UnitTypeId.TEMPLARARCHIVE) < 1
                and self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
                and self.can_afford(UnitTypeId.TEMPLARARCHIVE)
                and self.townhalls.amount >= 3
            ):  # Templar Archives
                logger.info('Building Templar Archives')
                await self.build(UnitTypeId.TEMPLARARCHIVE, near=pylon)

    async def expand(self):
        if (
            self.townhalls.amount < self.get_ideal_building_count("NEXUS")
            and self.can_afford(UnitTypeId.NEXUS)
            and not self.already_pending(UnitTypeId.NEXUS)
        ):
            exp_num = self.townhalls.amount
            if exp_num == 1 and self.enemy_units.closer_than(40, self.start_location):
                logger.debug('Not taking natural expansion due to nearby enemy')
                return
            
            if exp_num == 1:
                logger.success('Taking Natural Expansion')
            else:
                logger.success(f'Taking Expansion #{self.townhalls.amount}')
            await self.expand_now()

    async def upgrade_warp_gate(self):
        if (
            self.structures(UnitTypeId.CYBERNETICSCORE).ready
            and self.can_afford(AbilityId.RESEARCH_WARPGATE)
            and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 0
        ):
            logger.success("Upgrading Warp Gate")
            self.structures(UnitTypeId.CYBERNETICSCORE).ready.first.research(UpgradeId.WARPGATERESEARCH)

    async def twilight_upgrades(self):
        if (
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
            and self.can_afford(AbilityId.RESEARCH_BLINK)
            and self.already_pending_upgrade(UpgradeId.BLINKTECH) == 0
        ):
            logger.success('Researching Blink')
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready.first.research(UpgradeId.BLINKTECH)
        if (
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
            and self.can_afford(AbilityId.RESEARCH_CHARGE)
            and self.already_pending_upgrade(UpgradeId.BLINKTECH) == 1
            and self.already_pending_upgrade(UpgradeId.CHARGE) == 0
        ):
            logger.success('Researching Charge')
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready.first.research(UpgradeId.CHARGE)

    async def forge_upgrades(self):
        for forge in self.structures(UnitTypeId.FORGE).ready.idle:
            abilities = await self.get_available_abilities(forge)
            if (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL1 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL1)
            ):
                logger.success('Researching +1 Ground Weapons')
                forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL2 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL2)
            ):
                logger.success('Researching +2 Ground Weapons')
                forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL2)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL3 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL3)
            ):
                logger.success('Researching +3 Ground Weapons')
                forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL3)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL1 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL1)
            ):
                logger.success('Researching +1 Ground Armor')
                forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL1)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL2 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL2)
            ):
                logger.success('Researching +2 Ground Armor')
                forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL2)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL3 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL3)
            ):
                logger.success('Researching +3 Ground Armor')
                forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL3)
    
    async def morph_archons(self):
        if self.units(UnitTypeId.HIGHTEMPLAR).ready.amount >= 2:
            ht1 = self.units(UnitTypeId.HIGHTEMPLAR).ready.random
            ht2 = next((ht for ht in self.units(UnitTypeId.HIGHTEMPLAR).ready if ht.tag != ht1.tag), None)
            if ht2:
                command = raw_pb.ActionRawUnitCommand(
                        ability_id=AbilityId.MORPH_ARCHON.value,
                        unit_tags=[ht1.tag, ht2.tag],
                        queue_command=False
                    )
                action = raw_pb.ActionRaw(unit_command=command)
                await self._client._execute(action=sc_pb.RequestAction(
                        actions=[sc_pb.Action(action_raw=action)]
                    ))
    
    async def intel(self):
        # for game_info: https://github.com/Dentosal/python-sc2/blob/master/sc2/game_info.py#L162
        # flip around. It's y, x when you're dealing with an array.

        game_data = np.zeros((self.game_info.map_size[1], self.game_info.map_size[0], 3), np.uint8)

        draw_dict = {
            PYLON: [2, (20, 200, 0)],
            PROBE: [1, (55, 200, 0)],
            ASSIMILATOR: [2, (55, 200, 0)],
            GATEWAY: [3, (200, 140, 0)],
            WARPGATE: [3, (200, 140, 0)],
            FORGE: [3, (150, 150, 0)],
            ROBOTICSFACILITY: [3, (200, 140, 0)],
            TWILIGHTCOUNCIL: [3, (215, 155, 0)],
            ZEALOT: [1, (255, 100, 0)],
            STALKER: [1, (200, 100, 0)],
            ARCHON: [1, (255, 255, 200)],
            HIGHTEMPLAR: [1, (150, 150, 50)],
            OBSERVER: [1, (150, 150, 50)],
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

        main_base_names = ["Nexus", "CommandCenter", "Hatchery"]
        for enemy_building in self.enemy_structures:
            pos = enemy_building.position
            if enemy_building.name not in main_base_names:
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), 3, (200, 50, 212), -1)
            else:
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), 4, (0, 0, 255), -1)
        for enemy_unit in self.enemy_units:
            pos = enemy_unit.position
            cv2.circle(game_data, (int(pos[0]), int(pos[1])), 1, (0, 0, 200), -1)

        # flip horizontally to make our final fix in visual representation:
        flipped = cv2.flip(game_data, 0)
        resized = cv2.resize(flipped, dsize=None, fx=2, fy=2)

        cv2.imshow('Nexus7Intel', resized)
        cv2.waitKey(1)


    def on_end(self, result):
        logger.success(f'Game Ended - Result: {result}')
        # Do things here after the game ends
    
    def get_rally_point(self):
        return self.sorted_expo_locations[1].towards(self.game_info.map_center, 16)

    def get_ideal_building_count(self, building):
        th = self.townhalls.amount
        if building == "NEXUS":
            if self.time < 105: return 1    # 1:45
            elif self.time < 330: return 2  # 5:30
            elif self.time < 560: return 3  # 9:20
            elif self.time < 690: return 4  # 11:30
            elif self.time < 840: return 5  # 14:00
            else: return 6
        elif building == "GATEWAY":
            if self.townhalls.ready.amount == 1: return 1
            elif self.townhalls.ready.amount == 2:
                if self.time < 200: return 2
                else: return 3
            elif th == 3: return 5
            elif th == 4: return 7
            elif th == 5: return 10
            elif th > 5 and self.minerals > 1500: return 15
            else: return 12
        elif building == "FORGE":
            if th >= 3 and self.townhalls.ready.amount >= 3: return 2
            # else: return 0
        elif building == "ASSIMILATOR":
            if th < 2: return 1
            elif th == 2 and self.townhalls.ready.amount == 2: return 3
            elif th == 2: return 2
            elif self.minerals > 1000 and self.vespene < 400: return th*2
            else: return th + 1
        elif building == "ROBOTICS FACILITY":
            if not self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready: return 0
            elif th == 2 and self.townhalls.ready.amount == 2: return 1
            elif th == 3 and self.townhalls.ready.amount == 3: return 2
            elif th >= 4: return 3
            # else: return 0
        elif building == "ROBOTICS BAY":
            # NOT YET IMPLEMENTED
            if (
                self.structures(UnitTypeId.ROBOTICSFACILITY).ready
                and th == 3 and self.townhalls.ready.amount == 3
            ):
                return 1
            # else: return 0
        else:
            logger.error(f'Unrecognized argument - get_ideal_building_count({building})')
        return 0
    
    def get_ideal_worker_count(self):
        idealworkers = (16 * self.townhalls.amount) + (3 * self.get_ideal_building_count("ASSIMILATOR"))
        if idealworkers < 76: return idealworkers
        else: return 76

    def showdebuginfo(self):
        worker_count = self.supply_workers - self.already_pending(UnitTypeId.SCV)

        self._client.debug_text_simple(text="Nexus-7 v0.1")

        debugtext0 = "Worker Count:  " + str(worker_count) + "/" + str(self.get_ideal_worker_count())
        self._client.debug_text_screen(text=debugtext0, pos=Point2((0, 0.04)), color=None, size=8)

        debugtext1 = "Gateway Count: " + str(self.already_pending(UnitTypeId.GATEWAY) + self.structures.of_type({UnitTypeId.GATEWAY, UnitTypeId.WARPGATE}).ready.amount) + "/" + str(self.get_ideal_building_count("GATEWAY"))
        self._client.debug_text_screen(text=debugtext1, pos=Point2((0, 0.05)), color=None, size=8)

        debugtext2 = "Robo Count:    " + str(self.already_pending(UnitTypeId.ROBOTICSFACILITY) + self.structures.of_type({UnitTypeId.ROBOTICSFACILITY}).ready.amount) + "/" + str(self.get_ideal_building_count("ROBOTICS FACILITY"))
        self._client.debug_text_screen(text=debugtext2, pos=Point2((0, 0.06)), color=None, size=8)

        debugtext3 = "Army Supply:   " + str(self.supply_used - worker_count)
        self._client.debug_text_screen(text=debugtext3, pos=Point2((0, 0.07)), color=None, size=8)

        debugtext4 = "Hostile Army:  " + str(self.opponent_data['army_supply_scouted'])
        self._client.debug_text_screen(text=debugtext4, pos=Point2((0, 0.08)), color=None, size=8)


def main():
    import glob
    gls = glob.glob('E:\Battle.net\StarCraft II\Maps\*.SC2Map')
    available_maps = []
    for g in gls:
        map_path = g.split('\\')[-1:][0]
        map_name = map_path.split('.SC2Map')[0]
        available_maps.append(map_name)
    logger.info(f"Available Maps: {available_maps}")
    map_choice = random.choice(available_maps)
    # map_choice = 'OdysseyLE'
    logger.success(f'Starting Game on Random Map: {map_choice}')
    sc2.run_game(
        sc2.maps.get(f"{map_choice}"),
        [Bot(Race.Protoss, Nexus7()), Computer(Race.Zerg, Difficulty.CheatMoney)],
        realtime=False,
    )


if __name__ == "__main__":
    main()

