"""KBO 공식 사이트(koreabaseball.com) 선수 기록 수집기.

기록 페이지는 ASP.NET WebForms 포스트백으로 시즌/팀/페이지를 바꾼다.
기본 화면은 규정타석(이닝) 충족 선수만 보여주므로, 팀별로 조회해서
해당 시즌 등록 선수 전체를 모은다.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://www.koreabaseball.com"
PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"

# 페이지 키 -> 경로
PAGES = {
    "hitter_basic1": "/Record/Player/HitterBasic/Basic1.aspx",
    "hitter_basic2": "/Record/Player/HitterBasic/Basic2.aspx",
    "hitter_detail1": "/Record/Player/HitterBasic/Detail1.aspx",
    "pitcher_basic1": "/Record/Player/PitcherBasic/Basic1.aspx",
    "pitcher_basic2": "/Record/Player/PitcherBasic/Basic2.aspx",
    "pitcher_detail1": "/Record/Player/PitcherBasic/Detail1.aspx",
    "defense": "/Record/Player/Defense/Basic.aspx",
    "runner": "/Record/Player/Runner/Basic.aspx",
}

# ddlSeries 값
SERIES = {"regular": "0", "exhibition": "1", "wildcard": "4",
          "semi_po": "3", "po": "5", "ks": "7"}

SELECTS = ["ddlSeason", "ddlSeries", "ddlTeam", "ddlPos"]


class KboRecordScraper:
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

    # ---- low-level -------------------------------------------------------
    def _get(self, url: str) -> BeautifulSoup:
        time.sleep(self.delay)
        r = self.session.get(url, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")

    def _post(self, url: str, soup: BeautifulSoup, target: str, **values) -> BeautifulSoup:
        data = {
            i["name"]: i.get("value", "")
            for i in soup.select("input[type=hidden]")
            if i.get("name")
        }
        for key in SELECTS:
            sel = soup.find("select", attrs={"name": f"{PREFIX}{key}${key}"})
            if sel is None:
                continue
            opt = sel.find("option", selected=True) or sel.find("option")
            data[f"{PREFIX}{key}${key}"] = values.get(key, opt["value"])
        data["__EVENTTARGET"] = target
        data["__EVENTARGUMENT"] = ""
        time.sleep(self.delay)
        r = self.session.post(url, data=data, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")

    @staticmethod
    def _options(soup: BeautifulSoup, key: str) -> list[tuple[str, str]]:
        sel = soup.find("select", attrs={"name": f"{PREFIX}{key}${key}"})
        if sel is None:
            return []
        return [(o["value"], o.text.strip()) for o in sel.find_all("option") if o["value"]]

    @staticmethod
    def _page_numbers(soup: BeautifulSoup) -> list[int]:
        return [int(a.text) for a in soup.select(".paging a") if a.text.strip().isdigit()]

    @staticmethod
    def _parse_table(soup: BeautifulSoup) -> pd.DataFrame:
        table = soup.select_one("table.tData01") or soup.find("table")
        if table is None:
            return pd.DataFrame()
        headers = [th.text.strip() for th in table.select("thead th")]
        rows = []
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td")
            if len(tds) != len(headers):  # "기록이 없습니다" 등
                continue
            row = [td.text.strip() for td in tds]
            link = tr.find("a", href=re.compile("playerId="))
            pid = re.search(r"playerId=(\d+)", link["href"]).group(1) if link else None
            rows.append(row + [pid])
        return pd.DataFrame(rows, columns=headers + ["playerId"])

    # ---- public ----------------------------------------------------------
    def fetch(self, page: str, season: int, series: str = "regular") -> pd.DataFrame:
        """한 시즌의 특정 기록 페이지를 팀별로 모두 긁어서 반환."""
        url = BASE + PAGES[page]
        soup = self._get(url)
        vals = {"ddlSeason": str(season), "ddlSeries": SERIES[series]}
        soup = self._post(url, soup, f"{PREFIX}ddlSeason$ddlSeason", **vals)
        soup = self._post(url, soup, f"{PREFIX}ddlSeries$ddlSeries", **vals)

        frames = []
        for team_code, team_name in self._options(soup, "ddlTeam"):
            tvals = {**vals, "ddlTeam": team_code}
            tsoup = self._post(url, soup, f"{PREFIX}ddlTeam$ddlTeam", **tvals)
            frames.append(self._parse_table(tsoup))
            for n in self._page_numbers(tsoup)[1:]:
                psoup = self._post(url, tsoup, f"{PREFIX}ucPager$btnNo{n}", **tvals)
                frames.append(self._parse_table(psoup))

        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if df.empty:
            return df
        df = df.drop(columns=["순위"], errors="ignore").drop_duplicates()
        df.insert(0, "season", season)
        df.insert(1, "series", series)
        return df

    def fetch_to_csv(self, page: str, season: int, out_dir: Path,
                     series: str = "regular", overwrite: bool = False) -> Path:
        """결과를 data/raw/kbo_record/{page}/{series}_{season}.csv 로 저장 (캐시)."""
        path = Path(out_dir) / "kbo_record" / page / f"{series}_{season}.csv"
        if path.exists() and not overwrite:
            return path
        df = self.fetch(page, season, series)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
