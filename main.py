import json
import logging
from pathlib import Path

from gpt_kicktipp.gpt_client import OpenAiClient
from gpt_kicktipp.kicktipp_client import KickTippGPT
from gpt_kicktipp.settings import GlobalSettings

logger = logging.getLogger()
logging.basicConfig()

settings = GlobalSettings()
kicktipp_gpt = KickTippGPT(settings)
gpt_client = OpenAiClient(settings)


def process_game(game_id: str):
    info = kicktipp_gpt.extract_game_info(game_id)
    print("*" * 80)
    print("*" * 80)
    print("*" * 80)
    # res = fetch_table_with_cookie(ref, url, cookie, )
    prompt = kicktipp_gpt.parse_prompt(info)
    print(kicktipp_gpt.parse_prompt(info))
    print("*" * 80)
    res = gpt_client.request(kicktipp_gpt.parse_prompt(info))
    print(res)
    return {"prompt": prompt, "res": res}


def process_game_day(game_day: int):
    game_ids = kicktipp_gpt.fetch_game_ids(game_day)
    games = {}
    for game_id in game_ids:
        try:
            games[game_id] = process_game(game_id)
        except Exception as e:
            logger.warning(f"skip game {game_id}: {e}")

    with Path(f"game_day_{game_day}.json").open("w") as f:
        json.dump(games, f)


game_day = 4

process_game_day(game_day)