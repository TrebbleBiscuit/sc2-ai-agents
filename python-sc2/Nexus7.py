import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.player import Bot, Computer
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2, Point3

from s2clientprotocol import raw_pb2 as raw_pb
from s2clientprotocol import sc2api_pb2 as sc_pb

###############################
### Nexus-7 by Erik Nielsen ###
###    A Starcraft II AI    ###
###############################

class Nexus7(sc2.BotAI):
    async def on_start(self):
        print("Nexus-7 Online")

    async def on_step(self, iteration):
        if iteration == 0:
            self.sorted_expo_locations = self.start_location.sort_by_distance(self.expansion_locations_list)
            for w in self.workers:  # split workers
                w.gather(self.mineral_field.closest_to(w))
        
        if iteration == 7: await self.chat_send("Nexus-7. GLHF.")
        
        self.showdebuginfo()

        # Actions
        await self.distribute_workers()
        await self.army_movement(iteration)
        await self.ability_bilnk()
        await self.ability_chronoboost()
        await self.morph_arcons()

        # Macro
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
    
    async def army_movement(self, iteration):
        forces: Units = self.units.of_type({STALKER, ZEALOT, IMMORTAL, ARCHON, HIGHTEMPLAR})
        #if self.already_pending_upgrade(UpgradeId.BLINKTECH) == 1:
        if self.time > 510 and self.time < 600 or self.time > 780:  # 510 sec = 8:30, 780 sec = 13:00
            for unit in forces.idle: unit.attack(self.enemy_start_locations[0].position)
        elif iteration % 6 == 0:
            if self.enemy_units:
                for unit in forces.idle: unit.attack(self.enemy_units.random.position)
            else:
                for unit in forces: unit.attack(self.get_rally_point())

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
        cybers = self.structures(UnitTypeId.CYBERNETICSCORE).ready
        twilights = self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
        forges = self.structures(UnitTypeId.FORGE).ready
        for nexus in self.townhalls:
            if nexus.energy >= 50:
                if twilights and not twilights.first.is_idle and not twilights.first.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                    nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, twilights.first)
                elif cybers and not cybers.first.is_idle and not cybers.first.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                    nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, cybers.first)
                elif forges and not forges.first.is_idle and not forges.first.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                    nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, forges.first)

                #elif not nexus.is_idle and not nexus.has_buff(BuffId.CHRONOBOOSTENERGYCOST):
                #    nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, nexus)  # will only chrono itself, not another nexus

    async def train_workers(self):
        for nexus in self.townhalls:
            if (
                self.can_afford(UnitTypeId.PROBE)
                and self.supply_workers < self.get_ideal_worker_count()
                and nexus.is_idle
            ):
                nexus.train(UnitTypeId.PROBE)
    
    async def warp_in_gateway_units(self):
        for warpgate in self.structures(UnitTypeId.WARPGATE).ready:
            abilities = await self.get_available_abilities(warpgate)
            if self.units.of_type({STALKER}):  # avoid division by zero
                if (
                    self.already_pending_upgrade(UpgradeId.CHARGE) > .8  # Charge almost done
                    and len(self.units.of_type({ZEALOT})) / len(self.units.of_type({STALKER})) < 1
                    and AbilityId.WARPGATETRAIN_ZEALOT in abilities
                ):
                    target = self.structures(UnitTypeId.PYLON).ready.random.position.towards(self.game_info.map_center, 4)
                    placement = await self.find_placement(AbilityId.WARPGATETRAIN_ZEALOT, target, placement_step=1)
                    if placement is None:
                        # return ActionResult.CantFindPlacementLocation
                        print("can't place zealot")
                        return
                    warpgate.warp_in(UnitTypeId.ZEALOT, placement)
            if (
                AbilityId.WARPGATETRAIN_HIGHTEMPLAR in abilities
                and self.vespene > 400
            ):
                target = self.structures(UnitTypeId.PYLON).ready.random.position.towards(self.game_info.map_center, 4)
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_HIGHTEMPLAR, target, placement_step=1)
                if placement: warpgate.warp_in(UnitTypeId.HIGHTEMPLAR, placement)
            if AbilityId.WARPGATETRAIN_STALKER in abilities:
                target = self.structures(UnitTypeId.PYLON).ready.random.position.towards(self.game_info.map_center, 4)
                placement = await self.find_placement(AbilityId.WARPGATETRAIN_STALKER, target, placement_step=1)
                if placement is None:
                    # return ActionResult.CantFindPlacementLocation
                    print("can't place stalker")
                    return
                warpgate.warp_in(UnitTypeId.STALKER, placement)
    
    async def warp_in_robo_units(self):
        for robo in self.structures(UnitTypeId.ROBOTICSFACILITY).ready.idle:
            if (
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
                await self.build(UnitTypeId.PYLON, near=self.townhalls.ready.random.position.towards(self.game_info.map_center, 8))

    async def build_assimilators(self):
        if (
            self.structures(UnitTypeId.GATEWAY) or self.structures(UnitTypeId.WARPGATE)
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
                await self.build(UnitTypeId.CYBERNETICSCORE, near=pylon)
            elif (  # Gateways
                self.can_afford(UnitTypeId.GATEWAY)
                and self.already_pending(UnitTypeId.GATEWAY) + self.structures.of_type({UnitTypeId.GATEWAY, UnitTypeId.WARPGATE}).ready.amount < self.get_ideal_building_count("GATEWAY")
            ):
                await self.build(UnitTypeId.GATEWAY, near=pylon)
            elif (  # Twilight Council
                self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready.amount + self.already_pending(UnitTypeId.TWILIGHTCOUNCIL) == 0
                and self.structures(UnitTypeId.CYBERNETICSCORE).ready
                and self.can_afford(UnitTypeId.TWILIGHTCOUNCIL)
            ):
                await self.build(UnitTypeId.TWILIGHTCOUNCIL, near=pylon)
            elif ( # Forge
                self.structures(UnitTypeId.FORGE).ready.amount + self.already_pending(UnitTypeId.FORGE) < self.get_ideal_building_count("FORGE")
                and self.can_afford(UnitTypeId.FORGE)
            ):
                await self.build(UnitTypeId.FORGE, near=pylon)
            elif (  # Robotics Facility
                self.structures(UnitTypeId.ROBOTICSFACILITY).ready.amount + self.already_pending(UnitTypeId.ROBOTICSFACILITY) < self.get_ideal_building_count("ROBOTICS FACILITY")
                and self.structures(UnitTypeId.CYBERNETICSCORE).ready
                and self.can_afford(UnitTypeId.ROBOTICSFACILITY)
            ):
                await self.build(UnitTypeId.ROBOTICSFACILITY, near=pylon)
            elif (
                self.structures(UnitTypeId.TEMPLARARCHIVE).ready.amount + self.already_pending(UnitTypeId.TEMPLARARCHIVE) < 1
                and self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
                and self.can_afford(UnitTypeId.TEMPLARARCHIVE)
                and self.townhalls.amount >= 3
            ):  # Templar Archives
                await self.build(UnitTypeId.TEMPLARARCHIVE, near=pylon)

    async def expand(self):
        if (
            self.townhalls.amount < self.get_ideal_building_count("NEXUS")
            and self.can_afford(UnitTypeId.NEXUS)
            and not self.already_pending(UnitTypeId.NEXUS)
        ):
            if not self.enemy_units.closer_than(40, self.start_location) or self.townhalls.amount > 1:
                await self.expand_now()

    async def upgrade_warp_gate(self):
        if (
            self.structures(UnitTypeId.CYBERNETICSCORE).ready
            and self.can_afford(AbilityId.RESEARCH_WARPGATE)
            and self.already_pending_upgrade(UpgradeId.WARPGATERESEARCH) == 0
        ):
            self.structures(UnitTypeId.CYBERNETICSCORE).ready.first.research(UpgradeId.WARPGATERESEARCH)

    async def twilight_upgrades(self):
        if (
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
            and self.can_afford(AbilityId.RESEARCH_BLINK)
            and self.already_pending_upgrade(UpgradeId.BLINKTECH) == 0
        ):
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready.first.research(UpgradeId.BLINKTECH)
        if (
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready
            and self.can_afford(AbilityId.RESEARCH_CHARGE)
            and self.already_pending_upgrade(UpgradeId.BLINKTECH) == 1
            and self.already_pending_upgrade(UpgradeId.CHARGE) == 0
        ):
            self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready.first.research(UpgradeId.CHARGE)

    async def forge_upgrades(self):
        for forge in self.structures(UnitTypeId.FORGE).ready.idle:
            abilities = await self.get_available_abilities(forge)
            if (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL1 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL1)
            ):
                forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL2 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL2)
            ):
                forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL2)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL3 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL3)
            ):
                forge.research(UpgradeId.PROTOSSGROUNDWEAPONSLEVEL3)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL1 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL1)
            ):
                forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL1)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL2 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL2)
            ):
                forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL2)
            elif (
                AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL3 in abilities
                and self.can_afford(AbilityId.FORGERESEARCH_PROTOSSGROUNDARMORLEVEL3)
            ):
                forge.research(UpgradeId.PROTOSSGROUNDARMORSLEVEL3)
    
    async def morph_arcons(self):
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


    def on_end(self, result):
        print("Game ended.")
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
            elif self.townhalls.ready.amount == 2: return 3
            elif th == 3: return 5
            elif th == 4: return 7
            elif th == 5: return 10
            elif th > 5 and self.minerals > 1500: return 15
            else: return 12
        elif building == "FORGE":
            if th >= 3 and self.townhalls.ready.amount >= 3: return 2
            else: return 0
        elif building == "ASSIMILATOR":
            if th < 2: return th
            elif th == 2 and self.townhalls.ready.amount == 2: return 3
            elif th == 2: return 2
            elif self.minerals > 1000 and self.vespene < 400: return th*2
            else: return th + 1
        elif building == "ROBOTICS FACILITY":
            if not self.structures(UnitTypeId.TWILIGHTCOUNCIL).ready: return 0
            elif th == 2 and self.townhalls.ready.amount == 2: return 1
            elif th == 3 and self.townhalls.ready.amount == 3: return 2
            elif th >= 4: return 3
            else: return 0
        else: raise(Exception)
    
    def get_ideal_worker_count(self):
        idealworkers = (16 * self.townhalls.amount) + (3 * self.get_ideal_building_count("ASSIMILATOR"))
        if idealworkers < 76: return idealworkers
        else: return 76

    def showdebuginfo(self):
        self._client.debug_text_simple(text="Nexus-7 v0.1")

        debugtext1 = "Gateway Count: " + str(self.already_pending(UnitTypeId.GATEWAY) + self.structures.of_type({UnitTypeId.GATEWAY, UnitTypeId.WARPGATE}).ready.amount) + "/" + str(self.get_ideal_building_count("GATEWAY"))
        self._client.debug_text_screen(text=debugtext1, pos=Point2((0, 0.05)), color=None, size=8)

        debugtext11 = "Robo Count:    " + str(self.already_pending(UnitTypeId.ROBOTICSFACILITY) + self.structures.of_type({UnitTypeId.ROBOTICSFACILITY}).ready.amount) + "/" + str(self.get_ideal_building_count("ROBOTICS FACILITY"))
        self._client.debug_text_screen(text=debugtext11, pos=Point2((0, 0.06)), color=None, size=8)


def main():
    sc2.run_game(
        sc2.maps.get("CatalystLE"),
        [Bot(Race.Protoss, Nexus7()), Computer(Race.Zerg, Difficulty.CheatMoney)],
        realtime=False,
    )


if __name__ == "__main__":
    main()

