import io
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup
from jinja2 import FileSystemLoader, Environment
from pydantic import BaseModel

from gpt_kicktipp.settings import GlobalSettings


class GameInfo(BaseModel):
    home_team: str
    guest_team: str
    group: str
    quota: str
    home_last_games_md_table: str
    guest_last_games_md_table: str
    group_md_table: str
    date: datetime


class KickTippGPT:
    _LOGIN_URL = f"https://www.kicktipp.de/info/profil/loginaction"
    _BASE_URL = "https://www.kicktipp.de"
    _SEASON_ID = "2813920"  # em 2024

    def __init__(self, settings: GlobalSettings):
        self._settings = settings
        self._cookies = self._login()

    def _login(self):
        res = requests.post(self._LOGIN_URL,
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                            data=urlencode({"kennung": self._settings.kicktipp_user,
                                            "passwort": self._settings.kicktipp_password}).encode("utf-8"),
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
        response = requests.get(f"{self._BASE_URL}/{self._settings.kicktipp_group_name}/{url}", headers=headers,
                                allow_redirects=False,
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
        file_loader = FileSystemLoader(Path(__file__).parent)
        env = Environment(loader=file_loader)

        # Load the template file
        template = env.get_template("prompt.txt.j2")

        # Render the template with the provided context
        output = template.render(data=info)

        return output
