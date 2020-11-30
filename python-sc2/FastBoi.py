import sc2
from sc2 import Race, Difficulty
from sc2.constants import *
from sc2.ids.unit_typeid import *
from sc2.ids.ability_id import *
from sc2.player import Bot, Computer
from sc2.unit import Unit
from sc2.units import Units
from sc2.position import Point2, Point3
# i just copied over my import statements because you'll probably end up using all this stuff

def main():
    """
    Make sure whatever map you use is present in your "Username/Documents/Starcraft II/Maps" folder!
    replace Terran and CompetitiveBot() with whatever race and name your bot has
    replace Zerg and Medium with whatever race and difficulty you want to play against
    """
    sc2.run_game(
        sc2.maps.get("CatalystLE"),
        [Bot(Race.Terran, FastBoi()), Computer(Race.Zerg, Difficulty.Medium)],
        realtime=True,  # Set to True to watch in real time, False to play through as fast as possible
    )

###############################
### FastBoi by Erik Nielsen ###
###    A Starcraft II AI    ###
###############################


class FastBoi(sc2.BotAI):  # give it a cool name tho
    async def on_start(self):
        print("Game started")
        # Do things here JUST BEFORE the game starts 

    async def on_step(self, iteration):
        """
        Populate this function with whatever your bot should do!
        This function will run every iteration; multiple times for second
        note that the rate of iterations is not constant when playing non-realtime games
        use self.time to get a FLOAT of elapsed seconds in-game instead
        it's a float, so don't use `if self.time == 30`, instead do `if self.time > 30`
        """
        if iteration == 0:  # runs immediately after the game begins
            #await self.split_workers()
            for w in self.workers:
                w.attack(self.enemy_start_locations[0].position)
            
        if iteration == 10:  # runs exactly once
            await self.chat_send("(glhf)")
        
        if iteration % 10 == 0:  # run less frequently for performance reasons
            pass
            #await self.distribute_workers()  # automagically distribute workers between bases and send idle workers to mine

    async def split_workers(self):
        # order every worker to gather from the mineral field closest to them
        for w in self.workers:
            w.gather(self.mineral_field.closest_to(w))

    def on_end(self, result):
        print("Game ended.")
        # Do things here after the game ends




if __name__ == "__main__":
    main()
