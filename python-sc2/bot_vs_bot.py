import sc2
from sc2 import Race
from sc2.player import Bot

from deckard import DeckardBot
from Nexus7 import Nexus7
from Model2E import Model2E
from androidHunter import androidHunter


def main():
    sc2.run_game(
        sc2.maps.get("CatalystLE"),
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Protoss, Nexus7())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Zerg, androidHunter())],
        [Bot(Race.Terran, Model2E()), Bot(Race.Zerg, androidHunter())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Zerg, ZergRushBot())],
        #[Bot(Race.Terran, Model2E()), Bot(Race.Protoss, Nexus7())],
        realtime=True,
        #save_replay_as="DeckardvsandroidHunter.SC2Replay",
    )


if __name__ == "__main__":
    main()
