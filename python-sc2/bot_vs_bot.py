import sc2
from sc2 import Race
from sc2.player import Bot

from deckard import DeckardBot
from Nexus7 import Nexus7
from Model2E import Model2E
from SN_10L import SN_10L
#from androidHunterV2 import androidHunter


def main():
    sc2.run_game(
        sc2.maps.get("CatalystLE"),
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Protoss, Nexus7())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Zerg, androidHunter())],
        [Bot(Race.Terran, DeckardBot()), Bot(Race.Zerg, SN_10L())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Terran, Model2E())],
        #[Bot(Race.Terran, Model2E()), Bot(Race.Zerg, androidHunter())],
        #[Bot(Race.Terran, Model2E()), Bot(Race.Protoss, Nexus7())],
        #[Bot(Race.Terran, Model2E()), Bot(Race.Terran, Model2E())],
        realtime=False,
        #save_replay_as="BotReplay.SC2Replay",
    )


if __name__ == "__main__":
    main()
