import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.player import Bot, Computer
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2, Point3

###############################
### SN_10-L by Erik Nielsen ###
###    A Starcraft II AI    ###
###############################

class SN_10L(sc2.BotAI):
    async def on_start(self):
        print("SN_10-L Initialized")
        
        self.game_stage = "Opening"
        self.opening_step = 0
        self.queen_assignments = {}  # {queen tag: hatch tag}
        self.value_killed_minerals = 0
        self.value_killed_vespene = 0
        self.value_lost_minerals = 0
        self.value_lost_vespene = 0

    async def on_step(self, iteration):
        if iteration == 0:
            self.sorted_expo_locations = self.start_location.sort_by_distance(self.expansion_locations_list)
            for w in self.workers:  # split workers
                w.gather(self.mineral_field.closest_to(w))
        
        if iteration == 10: await self.chat_send("SN_10-L Initialized. GLHF.")
        
        self.total_worker_supply = self.supply_workers + self.already_pending(UnitTypeId.DRONE)

        await self.distribute_workers()
        await self.ability_inject()
        await self.army_movement(iteration)
        await self.pair_queens_to_hatches()
        
        if self.game_stage == "Opening":
            await self.opening_build()
        elif self.game_stage == "Early":
            await self.expand()
            await self.spawn_drones()
            await self.birth_queen()
            await self.spawn_zerglings()
            await self.morph_extractor()
            await self.spawn_overlords()
        else:
            print("undefined game stage, oof")

    async def on_unit_created(self, unit):
        pass  # note that larva spawning calls this function

    async def on_unit_destroyed(self, tag):
        """
        Note that losing eggs calls this function.
        """
        lost = self._units_previous_map.get(tag) or self._structures_previous_map.get(tag)
        if lost:
            if lost.type_id in {EGG, LARVA, BROODLING}:
                return  # we want to ignore units like this
            self.value_lost_minerals += self.calculate_unit_value(lost.type_id).minerals
            self.value_lost_vespene += self.calculate_unit_value(lost.type_id).vespene
            if lost.type_id in {HATCHERY, LAIR, HIVE}:
                for q, h in self.queen_assignments.items():
                    if tag == h:
                        self.queen_assignments.pop(q)  # if hatch dies, remove from queen_assignments
                        return
            elif lost.type_id in {DRONE}:
                pass  # TODO: keep track of number of workers lost - does this get called when drones make buildings?
            elif lost.tag in self.queen_assignments:  # this could be one line, self.queen_assignments.pop(lost.tag, None)
                self.queen_assignments.pop(lost.tag)

        enemylost = self._enemy_units_previous_map.get(tag) or self._enemy_structures_previous_map.get(tag)
        if enemylost and enemylost.type_id not in {EGG, LARVA, BROODLING, MULE}:
            self.value_killed_minerals += self.calculate_unit_value(enemylost.type_id).minerals
            self.value_killed_vespene += self.calculate_unit_value(enemylost.type_id).vespene
            # UNDER CONSTRUCTION
            if enemylost.type_id in {HATCHERY, LAIR, HIVE, COMMANDCENTER, PLANETARYFORTRESS, ORBITALCOMMAND, NEXUS}:
                print("Enemy lost townhall!")

    async def pair_queens_to_hatches(self):
        if len(self.queen_assignments) < self.townhalls.ready.amount:  # at least 1 hatch without a paired queen
            for q in [x for x in self.units(QUEEN) if x.tag not in self.queen_assignments]:  # unassigned queens
                for h in self.townhalls.sorted_by_distance_to(q.position):  # closest townhalls first
                    if h.tag not in list(self.queen_assignments.values()):  # if hatch doesn't have paired queen
                        self.queen_assignments[q.tag] = h.tag  # pair this queen with it
                        print("New queen paired!")
                        print(f"Queen assignments is: {self.queen_assignments}")
                        return
        """
        if len(self.queen_assignments) < self.townhalls.ready.amount:  # at least 1 hatch without a paired queen
            for h in self.townhalls.sorted_by_distance_to(unit.position, reverse=True):  # closest townhalls first
                if h.tag not in list(self.queen_assignments.values()):  # if hatch doesn't have paired queen
                    self.queen_assignments[unit.tag] = h.tag  # pair this queen with it
                    print("New queen paired!")
                    print(f"Queen assignments is: {self.queen_assignments}")
                    break  # break out of for loop
        """

    async def opening_build(self):
        # 17 hatch 18 gas 17 pool
        # 20 overlord, 2x queen
        if self.opening_step == 0:
            if (
                self.larva 
                and self.can_afford(UnitTypeId.DRONE)
                and self.total_worker_supply < 13
            ):
                self.train(UnitTypeId.DRONE)
            if self.total_worker_supply == 13: self.opening_step += 1
        elif self.opening_step == 1:
            if self.can_afford(UnitTypeId.OVERLORD):
                self.train(UnitTypeId.OVERLORD)
                self.opening_step += 1
        elif self.opening_step == 2:
            if (
                self.larva 
                and self.can_afford(UnitTypeId.DRONE)
                and self.total_worker_supply < 17
            ):
                self.train(UnitTypeId.DRONE)
            if self.total_worker_supply == 17: self.opening_step += 1
        elif self.opening_step == 3:
            if self.can_afford(UnitTypeId.HATCHERY):
                await self.expand_now()
                self.opening_step += 1
        elif self.opening_step == 4:
            if (
                self.larva 
                and self.can_afford(UnitTypeId.DRONE)
                and self.total_worker_supply < 18
            ):
                self.train(UnitTypeId.DRONE)
            if self.total_worker_supply == 18: self.opening_step += 1
        elif self.opening_step == 5:
            if self.can_afford(UnitTypeId.EXTRACTOR):
                geysers = self.vespene_geyser.closer_than(10, self.townhalls.random.position)
                for geyser in geysers:
                    if self.gas_buildings.filter(lambda unit: unit.distance_to(geyser) < 1):
                        continue
                    worker: Unit = self.select_build_worker(geyser)
                    if worker is None:
                        continue
                    worker.build_gas(geyser)
                    break  # so that it doesn't queue two refineries at once
                self.opening_step += 1
        elif self.opening_step == 6:
            if self.can_afford(UnitTypeId.SPAWNINGPOOL):
                await self.build(UnitTypeId.SPAWNINGPOOL, near=self.townhalls.first.position.towards(self.game_info.map_center, -10))
                self.opening_step += 1
        elif self.opening_step == 7:
            if (
                self.larva 
                and self.can_afford(UnitTypeId.DRONE)
                and self.total_worker_supply < 20
            ):
                self.train(UnitTypeId.DRONE)
            if self.total_worker_supply == 20: self.opening_step += 1
        elif self.opening_step == 8:
            if self.can_afford(UnitTypeId.OVERLORD):
                self.train(UnitTypeId.OVERLORD)
                self.opening_step += 1
        elif self.opening_step == 9:
            self.game_stage = "Early"
            print("opening done")
        else:
            print("opening step exceeds expected limits")
            
    async def army_movement(self, iteration):
        queens: Units = [q for q in self.units(UnitTypeId.QUEEN) if q.tag not in self.queen_assignments]  # non-paired queens
        if iteration % 4 == 0:
            for queen in queens: queen.attack(self.get_rally_point())
        
        forces: Units = self.units(UnitTypeId.ZERGLING)
        if self.time > 360:  # 360 sec = 6:00
            for unit in forces.idle: unit.attack(self.enemy_start_locations[0].position)
        elif iteration % 4 == 0:
            if self.enemy_units:
                for unit in forces.idle: unit.attack(self.enemy_units.random.position)
            else:
                for unit in forces: unit.attack(self.get_rally_point())

    async def spawn_drones(self):
        if self.larva and self.can_afford(UnitTypeId.DRONE) and self.total_worker_supply < self.get_ideal_worker_count():
            if (
                not (self.total_worker_supply == 13 and self.already_pending(UnitTypeId.OVERLORD) + self.units(UnitTypeId.OVERLORD).amount < 2)
                and not (self.total_worker_supply == 16 and self.townhalls.amount < 2)
                and not (self.total_worker_supply == 18 and self.gas_buildings.amount  < 1)
                and not (self.total_worker_supply == 17 and self.gas_buildings.amount >= 1 and self.structures(UnitTypeId.SPAWNINGPOOL).amount == 0)
            ):
                self.train(UnitTypeId.DRONE)

    async def spawn_overlords(self):
        if (
            (self.supply_left < 2 and self.already_pending(UnitTypeId.OVERLORD) < 2 and self.supply_workers > 25)
            or (self.supply_left < 4 and self.already_pending(UnitTypeId.OVERLORD) < 1)
        ):
            self.train(UnitTypeId.OVERLORD)

    async def spawn_zerglings(self):
        if (
            self.structures(UnitTypeId.SPAWNINGPOOL).ready and self.larva and self.can_afford(UnitTypeId.ZERGLING)
            and not self.townhalls.amount < self.get_ideal_building_count("HATCHERY")
        ):
            self.train(UnitTypeId.ZERGLING)

    async def birth_queen(self):
        for hatch in self.townhalls:
            if (
                hatch.is_idle
                and self.structures(UnitTypeId.SPAWNINGPOOL).ready
                and self.units(UnitTypeId.QUEEN).amount + self.already_pending(UnitTypeId.QUEEN) < self.get_ideal_unit_count("QUEEN")
            ):
                    if self.can_afford(UnitTypeId.QUEEN): hatch.train(UnitTypeId.QUEEN)
                    
    async def morph_spawning_pool(self):
        """
        if (
            self.structures(UnitTypeId.SPAWNINGPOOL).amount + self.already_pending(UnitTypeId.SPAWNINGPOOL) == 0
            and self.townhalls.amount > 1
            and self.can_afford(UnitTypeId.SPAWNINGPOOL)
        ):
        """
        if self.can_afford(UnitTypeId.SPAWNINGPOOL):
            await self.build(UnitTypeId.SPAWNINGPOOL, near=self.townhalls.first.position.towards(self.game_info.map_center, -10))
            return True

    async def morph_extractor(self):
        if (
            self.gas_buildings.amount + self.already_pending(UnitTypeId.EXTRACTOR) < self.get_ideal_building_count("EXTRACTOR")
            and self.can_afford(UnitTypeId.EXTRACTOR)
        ):
            geysers = self.vespene_geyser.closer_than(10, self.townhalls.random.position)
            for geyser in geysers:
                if self.gas_buildings.filter(lambda unit: unit.distance_to(geyser) < 1):
                    continue
                worker: Unit = self.select_build_worker(geyser)
                if worker is None:
                    continue
                worker.build_gas(geyser)
                break  # so that it doesn't queue two refineries at once
    
    async def ability_inject(self):    # TODO: rn all the queens get told to inject the same hatch 
        for q, h in self.queen_assignments.items():  # this syntax is nice
            queen = self.units(QUEEN).find_by_tag(q)
            hatch = self.townhalls.find_by_tag(h)
            if queen.energy >= 25 and hatch.is_ready and not hatch.has_buff(QUEENSPAWNLARVATIMER):
                queen(AbilityId.EFFECT_INJECTLARVA, hatch)
            elif queen.is_idle and queen.position.distance_to(hatch.position) > 10:
                queen.move(hatch.position)


        """
        inject_queens = self.units.filter(lambda unit: unit.type_id == UnitTypeId.QUEEN and unit.energy >= 25).idle
        if self.townhalls and inject_queens:
            for hatch in self.townhalls:
                queen = inject_queens.closest_to(hatch)
                if queen and queen.energy >= 25 and not hatch.has_buff(BuffId.QUEENSPAWNLARVATIMER):
                    queen(AbilityId.EFFECT_INJECTLARVA, hatch)
        """

    async def expand(self):
        if (
            self.townhalls.amount < self.get_ideal_building_count("HATCHERY")
            and self.can_afford(UnitTypeId.HATCHERY)
            and not self.already_pending(UnitTypeId.HATCHERY)
        ):
            if not self.enemy_units.closer_than(40, self.start_location) or self.townhalls.amount > 1:
                await self.expand_now()

    def on_end(self, result):
        print("Game ended.")

    def get_rally_point(self):
        return self.sorted_expo_locations[1].towards(self.game_info.map_center, 16)
    
    def get_ideal_building_count(self, building):
        th = self.townhalls.amount
        if building == "HATCHERY":
            if self.supply_cap - self.supply_left < 16: return 1
            elif self.supply_cap - self.supply_left < 28: return 2
            elif self.time < 330: return 3  # 5:30
            elif self.time < 560: return 4  # 9:20
            elif self.time < 690: return 5  # 11:30
            elif self.time < 840: return 6  # 14:00
            else: return 6
        elif building == "EXTRACTOR":
            if self.total_worker_supply < 18: return 0
            elif th <= 2: return 1
            else: return th
        else: raise(Exception)

    def get_ideal_unit_count(self, unit):
        th = self.townhalls.amount
        if unit == "QUEEN":
            return th

    def get_ideal_worker_count(self):
        idealworkers = (16 * self.townhalls.amount) + (3 * self.structures(UnitTypeId.EXTRACTOR).amount)
        if idealworkers < 80: return idealworkers
        else: return 80



def main():
    sc2.run_game(
        sc2.maps.get("CatalystLE"),
        [Bot(Race.Zerg, SN_10L()), Computer(Race.Zerg, Difficulty.Medium)],
        realtime=False,
    )


if __name__ == "__main__":
    main()
