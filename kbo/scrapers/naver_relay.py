"""네이버 스포츠 KBO 문자중계 수집기.

네이버 스포츠(m.sports.naver.com) 경기 화면의 '문자중계'가 쓰는 API를 호출한다.
- 경기 일정: /schedule/games
- 경기 정보: /schedule/games/{gameId}
- 문자중계: /schedule/games/{gameId}/relay?inning=N  (N회 초·말 전체)

문자중계에는 투구마다 구종·구속·결과, 볼카운트·주자·아웃 상황,
그리고 2016년 후반부터는 투구 추적(PTS: 투구 위치·궤적) 수치가 들어 있다.
데이터는 2008년 시즌부터 존재한다.
"""
from __future__ import annotations

import calendar
import gzip
import json
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api-gw.sports.naver.com"
MAX_INNING = 18  # 연장 대비 상한. 빈 이닝이 나오면 그 전에 멈춘다.


class NaverRelayScraper:
    def __init__(self, delay: float = 0.25):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://m.sports.naver.com/",
        })

    def _get(self, path: str, params: dict | None = None, retries: int = 3) -> dict:
        for attempt in range(retries):
            time.sleep(self.delay)
            try:
                r = self.session.get(API + path, params=params, timeout=30)
                if r.status_code == 404:
                    return {}
                r.raise_for_status()
                return r.json().get("result", {})
            except (requests.RequestException, ValueError):
                if attempt == retries - 1:
                    raise
                time.sleep(5 * (attempt + 1))
        return {}

    # ---- 일정 -----------------------------------------------------------
    def schedule(self, season: int) -> pd.DataFrame:
        """시즌 전체 경기 목록 (월 단위로 조회)."""
        games = []
        for month in range(2, 12):  # 시범경기(3월)~한국시리즈(11월) 여유 있게
            last = calendar.monthrange(season, month)[1]
            res = self._get("/schedule/games", {
                "fields": "basic,stadium,roundCode",
                "upperCategoryId": "kbaseball", "categoryId": "kbo",
                "fromDate": f"{season}-{month:02d}-01",
                "toDate": f"{season}-{month:02d}-{last}",
                "size": 1000,
            })
            games += res.get("games", [])
        return pd.DataFrame(games).drop_duplicates("gameId") if games else pd.DataFrame()

    # ---- 한 경기 ----------------------------------------------------------
    def game(self, game_id: str) -> dict:
        """경기 정보 + 이닝별 문자중계를 하나의 dict로 반환."""
        info = self._get(f"/schedule/games/{game_id}").get("game", {})
        innings, lineup = {}, {}
        for inn in range(1, MAX_INNING + 1):
            data = self._get(f"/schedule/games/{game_id}/relay", {"inning": inn})
            relay = data.get("textRelayData", {})
            relays = relay.get("textRelays", [])
            if not relays:
                break
            if not lineup:
                lineup = {k: relay.get(k) for k in
                          ("homeLineup", "awayLineup", "homeEntry", "awayEntry")}
            # 매 투구마다 반복되는 선수 누적성적 블록은 용량만 차지하므로 제거
            for r in relays:
                for o in r.get("textOptions", []):
                    o.pop("currentPlayersInfo", None)
            innings[inn] = relays
        return {"gameId": game_id, "game": info, "lineup": lineup, "innings": innings}

    def game_to_file(self, game_id: str, out_dir: Path, overwrite: bool = False) -> Path | None:
        """data/raw/naver/relay/{season}/{gameId}.json.gz 로 저장 (이미 있으면 건너뜀)."""
        season = game_id[:4]
        path = Path(out_dir) / "naver" / "relay" / season / f"{game_id}.json.gz"
        if path.exists() and not overwrite:
            return path
        data = self.game(game_id)
        if not data["innings"]:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        tmp.rename(path)
        return path
