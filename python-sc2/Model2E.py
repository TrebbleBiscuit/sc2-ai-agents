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
import time

###############################
### Model2E by Erik Nielsen ###
###    A Starcraft II AI    ###
###############################

class Model2E(sc2.BotAI):
    async def on_start(self):
        print("2E Initialized")
        
        self.game_stage = "Opening"
        self.opening_step = 0
        self.allin = False
        self.killed_main = False

    async def on_step(self, iteration):
        if iteration == 0:
            self.sorted_expo_locations = self.start_location.sort_by_distance(self.expansion_locations_list)
            for w in self.workers:  # split workers
                w.gather(self.mineral_field.closest_to(w))
        
        if iteration == 10: await self.chat_send("2E Initialized. GLHF.")
        
        if self.game_stage == "Opening":
            await self.opening_build()
            for w in self.workers.idle:
                if w.distance_to(self.townhalls.first) < 15:
                    w.gather(self.mineral_field.closest_to(w))
        else:
            # await self.distribute_workers()  # do not do during opening (looks for idle SCVs)
            await self.army_movement(iteration)
            await self.build_depots()
            await self.make_barracks()
        await self.train_marines()  # do even during opening
        await self.lower_depots()
        await self.intel()
    

    async def opening_build(self):

        # TODO: deal with idle SCV that finishes 1st depot

        if self.opening_step == 0:  # make SCV, send out SCV
            self.townhalls.first.train(UnitTypeId.SCV)
            self.worker1 = self.workers.gathering.closest_to(self.enemy_start_locations[0].position)
            self.worker1.move(self.enemy_start_locations[0].position)
            self.opening_step += 1
        elif self.opening_step == 1:  # send out 2nd SCV 
            if self.time > 7:
                self.worker2 = self.workers.gathering.closest_to(self.enemy_start_locations[0].position)
                self.worker2.move(self.enemy_start_locations[0].position)
                self.opening_step += 1
        elif self.opening_step == 2:  # finished SCV makes depot
            if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                this_worker = self.workers.closest_to(self.townhalls.first.position)
                self.placement_position = await self.find_placement(UnitTypeId.SUPPLYDEPOT, near=this_worker.position.towards(self.game_info.map_center, 3), placement_step=3)
                if self.placement_position:
                    if this_worker.build(UnitTypeId.SUPPLYDEPOT, self.placement_position): self.opening_step += 1
        elif self.opening_step == 3:  # send out 3nd SCV
            if self.time > 18:
                self.worker3 = self.workers.gathering.closest_to(self.enemy_start_locations[0].position)
                self.worker3.move(self.enemy_start_locations[0].position)
                self.opening_step += 1
        elif self.opening_step == 4:  # Make first rax
            if self.can_afford(UnitTypeId.BARRACKS) and self.tech_requirement_progress(UnitTypeId.BARRACKS) == 1:
                worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv)
                this_worker = worker_canidates.closest_to(self.enemy_start_locations[0].position)
                self.placement_position = await self.find_placement(UnitTypeId.BARRACKS, near=this_worker.position, placement_step=1)
                if self.placement_position:
                    if this_worker.build(UnitTypeId.BARRACKS, self.placement_position): self.opening_step += 1
                    self.worker2.move(self.placement_position)
                    self.worker3.move(self.placement_position)
        elif self.opening_step == 5:  # Make second rax
            if self.time > 45 and self.can_afford(UnitTypeId.BARRACKS):
                worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv)
                this_worker = worker_canidates.closest_to(self.enemy_start_locations[0].position)
                newpp = await self.find_placement(UnitTypeId.BARRACKS, near=this_worker.position, placement_step=1)
                if newpp:
                    self.placement_position = newpp
                    if this_worker.build(UnitTypeId.BARRACKS, self.placement_position):
                        self.opening_step += 1
        elif self.opening_step == 6:  # Make third rax
            if self.time > 60 and self.can_afford(UnitTypeId.BARRACKS):
                worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv)
                this_worker = worker_canidates.closest_to(self.enemy_start_locations[0].position)
                newpp = await self.find_placement(UnitTypeId.BARRACKS, near=this_worker.position, placement_step=1)
                if newpp:
                    self.placement_position = newpp
                    if this_worker.build(UnitTypeId.BARRACKS, self.placement_position):
                        self.opening_step += 1
        elif self.opening_step == 7:  # Train one worker
            if self.can_afford(UnitTypeId.SCV):
                self.townhalls.first.train(UnitTypeId.SCV)
                self.opening_step += 1
        # 1st barracks should finish now, one marine should start
        elif self.opening_step == 8:  # Make fourth rax
            if self.can_afford(UnitTypeId.BARRACKS):
                worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv and worker.distance_to(self.enemy_start_locations[0].position) < 50)
                if not worker_canidates:
                    return
                this_worker = worker_canidates.closest_to(self.enemy_start_locations[0].position)
                newpp = await self.find_placement(UnitTypeId.BARRACKS, near=this_worker.position, placement_step=1)
                if newpp:
                    self.placement_position = newpp
                    if this_worker.build(UnitTypeId.BARRACKS, self.placement_position):
                        self.opening_step += 1
        elif self.opening_step == 9:  # Make second depot
            if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv)
                this_worker = worker_canidates.closest_to(self.enemy_start_locations[0].position)
                place = await self.find_placement(UnitTypeId.SUPPLYDEPOT, near=this_worker.position.towards(self.game_info.map_center, 4), placement_step=1)
                if place:
                    this_worker.build(UnitTypeId.SUPPLYDEPOT, place)
                    self.opening_step += 1
        elif self.opening_step == 10:
            self.game_stage = "Brrr"
            print("opening done")
            
    async def train_marines(self):
        for rax in self.structures(UnitTypeId.BARRACKS).ready.idle:
            if self.can_afford(UnitTypeId.MARINE): rax.train(UnitTypeId.MARINE)

    async def army_movement(self, iteration):
        forces: Units = self.units(UnitTypeId.MARINE)
        if self.time > 150:  # 2:30
            if not self.allin:
                self.allin = True
                await self.chat_send("Sending kill signal to rogue process")
                worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv and worker.distance_to(self.enemy_start_locations[0].position) < 50)
                for w in worker_canidates:
                    if w != worker_canidates.furthest_to(self.enemy_start_locations[0].position):
                        w.attack(self.get_attack_target())
            for unit in forces.idle:
                unit.attack(self.get_attack_target())
            await self.stutter_step()
    
    async def build_depots(self):
        if not self.already_pending(UnitTypeId.SUPPLYDEPOT) and self.supply_left < 7 and self.supply_cap < 200:
            await self.build(UnitTypeId.SUPPLYDEPOT, near=self.townhalls.first.position.towards(self.game_info.map_center, 6))
    
    async def make_barracks(self):
        if self.minerals > 350 and self.supply_left > 0:
            worker_canidates = self.workers.filter(lambda worker: not worker.is_attacking and not worker.is_constructing_scv)
            if not worker_canidates: return
            this_worker = worker_canidates.closest_to(self.placement_position)
            place = await self.find_placement(UnitTypeId.BARRACKS, near=this_worker.position.towards(self.placement_position), placement_step=1)
            if place: this_worker.build(UnitTypeId.BARRACKS, place)

    async def lower_depots(self):
        for depot in self.structures(UnitTypeId.SUPPLYDEPOT).ready:
            depot(AbilityId.MORPH_SUPPLYDEPOT_LOWER)
    
    async def stutter_step(self):
        for u in self.units(UnitTypeId.MARINE):
            if self.enemy_units:
                closest_enemy = self.enemy_units.closest_to(u)
                if u.distance_to(closest_enemy) < 6 and u.weapon_cooldown > 0:
                    u.move(u.position.towards(closest_enemy.position, -u.distance_to_weapon_ready))
        # away from ATTACKING units with less range (zealots, lings, workers)
        # towards units with more range (stalkers)
        # 
        # marine.distance_to_weapon_ready
    
    async def intel(self):
        # for game_info: https://github.com/Dentosal/python-sc2/blob/master/sc2/game_info.py#L162
        # print(self.game_info.map_size)
        # flip around. It's y, x when you're dealing with an array.

        game_data = np.zeros((self.game_info.map_size[1], self.game_info.map_size[0], 3), np.uint8)
        """
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
        """

        for townhall in self.townhalls:
            cv2.circle(game_data, (int(townhall.position[0]), int(townhall.position[1])), 4, (255, 20, 0), -1)  # BGR
        for structure in self.structures:
            if structure not in self.townhalls:
                cv2.circle(game_data, (int(structure.position[0]), int(structure.position[1])), 3, (180, 0, 0), -1)  # BGR
        #for rax in self.units(BARRACKS):
        #    cv2.circle(game_data, (int(rax.position[0]), int(rax.position[1])), 6, (0, 255, 0), -1)  # BGR

        for w in self.workers:
            pos = w.position
            cv2.circle(game_data, (int(pos[0]), int(pos[1])), 1, (55, 100, 0), -1)
        for u in self.units:
            if u not in self.workers:
                pos = u.position
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), 1, (150, 100, 50), -1)

        main_base_names = ["nexus", "commandcenter", "hatchery"]
        for enemy_building in self.enemy_structures:
            pos = enemy_building.position
            if enemy_building.name.lower() not in main_base_names:
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), 3, (50, 50, 120), -1)
        for enemy_building in self.enemy_structures:
            pos = enemy_building.position
            if enemy_building.name.lower() in main_base_names:
                cv2.circle(game_data, (int(pos[0]), int(pos[1])), 4, (50, 50, 255), -1)
        for enemy_unit in self.enemy_units:
            pos = enemy_unit.position
            cv2.circle(game_data, (int(pos[0]), int(pos[1])), 1, (0, 0, 200), -1)

        # flip horizontally to make our final fix in visual representation:
        flipped = cv2.flip(game_data, 0)
        resized = cv2.resize(flipped, dsize=None, fx=3, fy=3)
        cv2.imshow('Intel', resized)
        cv2.waitKey(1)

    def on_end(self, result):
        print("Game ended.")

    def get_attack_target(self):
        """ Select an enemy target the units should attack. """
        if min([u.position.distance_to(self.enemy_start_locations[0]) for u in self.units]) < 5:
            self.killed_main = True
        if self.killed_main:
            if self.enemy_structures: return self.enemy_structures.random.position
            return self.mineral_field.random.position
        else:
            return self.enemy_start_locations[0].position


def main():
    sc2.run_game(
        sc2.maps.get("CatalystLE"),
        [Bot(Race.Terran, Model2E()), Computer(Race.Protoss, Difficulty.VeryHard)],
        realtime=False,
    )


if __name__ == "__main__":
    main()

