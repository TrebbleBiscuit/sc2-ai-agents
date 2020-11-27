import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
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

    async def on_step(self, iteration):
        if iteration == 0:
            self.sorted_expo_locations = self.start_location.sort_by_distance(self.expansion_locations_list)
        
        if iteration == 10: await self.chat_send("2E Initialized. GLHF.")
        
        if self.game_stage == "Opening":
            await self.opening_build()
        else:
            await self.distribute_workers()  # do not do during opening (looks for idle SCVs)
            await self.army_movement(iteration)
            await self.build_depots()
        await self.train_marines()  # do even during opening
        await self.intel()
    

    async def opening_build(self):

        # TODO: deal with idle SCV that finishes 1st depot

        # Reassign workers if dead
        print(f"opening step: {self.opening_step}")
        try: self.placement_position
        except AttributeError:
            self.placement_position = self.townhalls.first.position
        self._client.debug_text_world("PLACEMENT_POSITION", Point3((self.placement_position.x, self.placement_position.y, self.get_terrain_z_height(self.placement_position))), size=12)

        if self.opening_step == 0:  # make SCV, send out SCV
            self.townhalls.first.train(UnitTypeId.SCV)
            self.worker1 = self.workers.gathering.closest_to(self.enemy_start_locations[0].position)
            self.worker1.move(self.enemy_start_locations[0].position)
            self.opening_step += 1
        elif self.opening_step == 1:  # send out 2nd SCV 
            if self.time > 5:
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
            if self.time > 15:
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
                worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv)
                this_worker = worker_canidates.closest_to(self.enemy_start_locations[0].position)
                newpp = await self.find_placement(UnitTypeId.BARRACKS, near=this_worker.position, placement_step=1)
                if newpp:
                    self.placement_position = newpp
                    if this_worker.build(UnitTypeId.BARRACKS, self.placement_position):
                        self.opening_step += 1
        elif self.opening_step == 9:  # Make second depot
            worker_canidates = self.workers.filter(lambda worker: not worker.is_constructing_scv)
            this_worker = worker_canidates.closest_to(self.enemy_start_locations[0].position)
            if self.can_afford(UnitTypeId.SUPPLYDEPOT):
                placement_position = await self.find_placement(UnitTypeId.BARRACKS, near=this_worker.position.towards(self.game_info.map_center, 3), placement_step=1)
                if placement_position:
                    self.worker2.build(UnitTypeId.SUPPLYDEPOT, placement_position)
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
            for unit in forces.idle: unit.attack(self.enemy_start_locations[0].position)
    
    async def build_depots(self):
        if not self.already_pending(UnitTypeId.SUPPLYDEPOT) and self.supply_left < 7 and self.supply_cap < 200:
            await self.build(UnitTypeId.SUPPLYDEPOT, near=self.townhalls.first.position.towards(self.game_info.map_center, 6))
    
    async def stutter_step(self):
        pass
        # away from ATTACKING units with less range (zealots, lings, workers)
        # towards units with more range (stalkers)
        #
        # marine.distance_to_weapon_ready
    
    async def intel(self):
        # for game_info: https://github.com/Dentosal/python-sc2/blob/master/sc2/game_info.py#L162
        # print(self.game_info.map_size)
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
        resized = cv2.resize(flipped, dsize=None, fx=3, fy=3)

        cv2.imshow('Intel', resized)
        cv2.waitKey(1)

    def on_end(self, result):
        print("Game ended.")




def main():
    sc2.run_game(
        sc2.maps.get("CatalystLE"),
        [Bot(Race.Terran, Model2E()), Computer(Race.Protoss, Difficulty.VeryHard)],
        realtime=False,
    )


if __name__ == "__main__":
    main()

