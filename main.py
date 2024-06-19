import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from keepassxc_client import keepassxc
import requests
from bs4 import BeautifulSoup
import pandas as pd
from jinja2 import FileSystemLoader, Environment
from pydantic import BaseModel

import openai

logger = logging.getLogger()

import jinja2


class GameInfo(BaseModel):
    home_team: str
    guest_team: str
    group: str
    quota: str
    home_last_games_md_table: str
    guest_last_games_md_table: str
    group_md_table: str
    date: datetime


def get_credentials() -> tuple[str, str]:
    creds = keepassxc.get_credentials("https://www.kicktipp.de/info/profil/login")[0]
    return creds["login"], creds["password"]


def get_llm_token() -> str:
    return keepassxc.get_first_password("local-access://tng-ai-token.offline")

class KickTippGPT:
    _BASE_URL = "https://www.kicktipp.de/gaensheimer"
    _SEASON_ID = "2813920"

    def __init__(self):
        self._cookies = self._login()

    def _login(self):
        user, password = get_credentials()
        res = requests.post(f"https://www.kicktipp.de/info/profil/loginaction",
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                            data=urlencode({"kennung": user, "passwort": password}).encode("utf-8"),
                            allow_redirects=False)
        return res.cookies

    def fetch_html(self, url, ref=None):
        # Set up the headers with the cookie

        # Set up the headers with the cookies
        headers = {
            **({'Referer': ref} if ref else {}),
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
        }

        # Make the GET request
        response = requests.get(f"{self._BASE_URL}/{url}", headers=headers, allow_redirects=False,
                                cookies=self._cookies)

        # Check if the request was successful
        if response.status_code != 200:
            raise Exception(f"Failed to fetch the URL: {response.status_code}")

        # Parse the HTML content
        return BeautifulSoup(response.content, 'html.parser')

    def fetch_game_ids(self, game_day_index: str | int):
        body = self.fetch_html(f"tippabgabe?tippsaisonId={self._SEASON_ID}&spieltagIndex={game_day_index}")
        # Find the table with the given classes
        table = body.find('table', {"id": "tippabgabeSpiele"})
        tablebody = table.find('tbody')
        reg = re.compile("spieltippForms\[(?P<spielId>\d+)\]")
        game_ids = [next(reg.finditer(str(table_row)))["spielId"]
                    for table_row in tablebody.children if reg.findall(str(table_row))]
        return game_ids
        # if table is None:
        #     raise Exception("Table with the specified classes not found")
        #
        # # Use pandas to read the HTML table
        # df = pd.read_html(str(table))[0]
        #
        # # Print the table as markdown
        # print(df.to_markdown(index=False))

    @staticmethod
    def _html_table_to_df(table):
        f = io.StringIO(str(table))
        return pd.read_html(f)[0]

    @staticmethod
    def _adapt_last_games_table(table: pd.DataFrame):
        table = table.copy()
        table[0] = table[0].str.replace("EMQ", "EM 2024 Qualifikation")
        table[0] = table[0].str.replace("NL", "Nations League")
        table[0] = table[0].str.replace("WM", "WM 2022")
        table[0] = table[0].str.replace("WMQ", "WM 2022 Qualifikation")

        table.columns = ["Typ", "Heim", "Gast", "Ergebnis"]

        return table

    def extract_game_info(self, game_id: str):
        body = self.fetch_html(f"spielinfo?tippsaisonId={self._SEASON_ID}&tippspielId={game_id}")

        tip_table = body.find('table', {"id": "tippabgabeSpiele"}).find("tbody")
        assert len(list(tip_table.children)) == 1

        game_date, home_team, guest_team, quota = [t.text for t in tip_table.find_all("td", {"class": "nw"})]

        table_home_team_last_games = self._adapt_last_games_table(
            self._html_table_to_df(body.find("table", {"class": "spielinfoHeim"})))
        table_guest_team_last_games = self._adapt_last_games_table(
            self._html_table_to_df(body.find("table", {"class": "spielinfoGast"})))

        table_group = self._html_table_to_df(body.find("table", {"class": "sporttabelle drei_punkte_regel"}))
        group = table_group.columns[0]

        return GameInfo(home_team=home_team, guest_team=guest_team, date=datetime.strptime(game_date, "%d.%m.%y %H:%M"),
                        quota=quota,
                        home_last_games_md_table=table_home_team_last_games.to_markdown(index=False),
                        guest_last_games_md_table=table_guest_team_last_games.to_markdown(index=False),
                        group_md_table=table_group.to_markdown(index=False),
                        group=group
                        )

    def parse_prompt(self, info: GameInfo):
        file_loader = FileSystemLoader('.')
        env = Environment(loader=file_loader)

        # Load the template file
        template = env.get_template("prompt.txt.j2")

        # Render the template with the provided context
        output = template.render(data=info)

        return output


class OpenAiClient():

    def __init__(self):
        self._openai = openai
        self._openai.base_url = "https://taia.tngtech.com/proxy/openai/v1/"
        self._openai.api_key = get_llm_token()

    def request(self, prompt: str):
        res =  self._openai.chat.completions.create(
            model="gpt-4o",
            temperature=0.2,
            messages=[{
                "role": "system",
                "content": "Du bist ein deutscher Fußballexperte zur Europameisterschaft 2024"
            },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            stream=False,
            max_tokens=2000
        )

        return res.choices[0].message.content


logging.basicConfig()
# Example usage
ref = "https://www.kicktipp.de/gaensheimer/spielinfo?tippsaisonId=2813920&tippspielId=1238193335&ansicht=3"
kicktipp_gpt = KickTippGPT()
game_day = 3
game_ids = kicktipp_gpt.fetch_game_ids(game_day)
print(game_ids)

client = OpenAiClient()
games = {}
for game_id in game_ids:
    try:
        info = kicktipp_gpt.extract_game_info(game_id)
        print("*" * 80)
        print("*" * 80)
        print("*" * 80)
        # res = fetch_table_with_cookie(ref, url, cookie, )
        prompt = kicktipp_gpt.parse_prompt(info)
        print(kicktipp_gpt.parse_prompt(info))
        print("*" * 80)
        res = client.request(kicktipp_gpt.parse_prompt(info))
        print(res)
        games[game_id] = {"prompt": prompt, "res": res}
    except:
        logger.warning(f"skip game {game_id}")

with Path(f"game_day_{game_day}.json").open("w") as f:
    json.dump(games, f)