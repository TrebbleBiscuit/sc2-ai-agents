import sc2
from sc2 import Race
from sc2.player import Bot

from deckard import DeckardBot
from Nexus7 import Nexus7
from Model2E import Model2E
from SN_10L import SN_10L
from expand_everywhere import ExpandEverywhere
#from androidHunterV2 import androidHunter


def main():
    import glob
    from loguru import logger
    import random
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
        sc2.maps.get(map_choice),
        [Bot(Race.Terran, DeckardBot()), Bot(Race.Protoss, Nexus7())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Zerg, androidHunter())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Zerg, SN_10L())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Zerg, ExpandEverywhere())],
        #[Bot(Race.Terran, DeckardBot()), Bot(Race.Terran, Model2E())],
        #[Bot(Race.Terran, Model2E()), Bot(Race.Zerg, androidHunter())],
        #[Bot(Race.Terran, Model2E()), Bot(Race.Protoss, Nexus7())],
        #[Bot(Race.Terran, Model2E()), Bot(Race.Terran, Model2E())],
        realtime=True,
        #save_replay_as="BotReplay.SC2Replay",
    )


if __name__ == "__main__":
    main()
