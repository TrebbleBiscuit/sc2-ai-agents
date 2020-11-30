import sc2
from sc2 import Race
from sc2.player import Human, Bot

from Model2E import Model2E

def main():
    sc2.run_game(sc2.maps.get("Catalyst LE"), [Human(Race.Terran), Bot(Race.Terran, Model2E())], realtime=True)


if __name__ == "__main__":
    main()
