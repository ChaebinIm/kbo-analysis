"""네이버 문자중계 원본(json.gz) -> 분석용 표 변환.

- pitches: 한 줄 = 공 하나 (구종·구속·결과, 투구 직전 상황, PTS 위치/궤적)
- pas:     한 줄 = 타석 하나 (투수·타자, 타석 시작 상황, 결과 문장)
- players: 경기 라인업에 나온 선수 정보 (이름, 투타, 생년월일, 신장/체중)

문자중계 이벤트의 currentGameState 는 '그 이벤트 직후' 상태이므로
투구 직전 상황은 바로 앞 이벤트의 상태를 쓴다.
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pandas as pd

# 이벤트 type 코드 (문자중계에서 관찰한 값)
T_PITCH = 1        # n구 볼/스트라이크/파울/타격 ...
T_BATTER = 8       # "n번타자 OOO" 타석 시작
T_RESULT = (13, 23)  # 타석 결과 (13: 일반, 23: 안타·장타 등)
T_OTHER = 7        # 투수판 이탈, 피치클락 위반 등

PTS_FIELDS = ["crossPlateX", "crossPlateY", "topSz", "bottomSz",
              "x0", "y0", "z0", "vx0", "vy0", "vz0", "ax", "ay", "az", "stance"]


def _i(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


STATE_KEYS = ("ball", "strike", "out", "base1", "base2", "base3", "homeScore", "awayScore")
NA_STATE = {"outs": None, "on_1b": None, "on_2b": None, "on_3b": None,
            "home_score": None, "away_score": None}


def _state(s: dict) -> dict:
    return {
        "outs": _i(s.get("out")),
        "on_1b": _i(s.get("base1")) > 0, "on_2b": _i(s.get("base2")) > 0,
        "on_3b": _i(s.get("base3")) > 0,
        "home_score": _i(s.get("homeScore")), "away_score": _i(s.get("awayScore")),
    }


def _has_state(events: list[dict]) -> bool:
    """2015년 이전 중계는 currentGameState 의 상황값이 전부 0으로 비어 있다."""
    return any(
        (e.get("currentGameState") or {}).get(k) not in (None, "", "0")
        for e in events for k in STATE_KEYS
    )


def _next_count(balls: int, strikes: int, result: str | None) -> tuple[int, int]:
    """투구 결과 코드로 볼카운트 갱신. B=볼, F=파울, H=타격(인플레이), 그 외=스트라이크."""
    if result == "B":
        return balls + 1, strikes
    if result == "F":
        return balls, min(strikes + 1, 2)
    if result == "H":
        return balls, strikes
    return balls, strikes + 1


def parse_game(data: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    gid = data["gameId"]
    g = data.get("game", {})
    # 포스트시즌 경기ID는 앞 4자리가 연도가 아니다 (3333=준PO, 4444=WC, 5555=PO, 6666=5위결정전, 7777=KS)
    game_date = g.get("gameDate") or f"{gid[:4]}-{gid[4:6]}-{gid[6:8]}"
    meta = {
        "game_id": gid,
        "game_date": game_date,
        "season": _i(game_date[:4]),
        "round_code": g.get("roundCode"),
        "stadium": g.get("stadium"),
        "home_team": g.get("homeTeamCode"),
        "away_team": g.get("awayTeamCode"),
    }

    # 모든 이벤트를 게임 진행 순서(seqno)로 펼치기
    events, pts = [], {}
    for inn, relays in data["innings"].items():
        for r in relays:
            for p in r.get("ptsOptions") or []:
                pts[p.get("pitchId")] = p
            for o in r.get("textOptions", []):
                events.append({
                    "inning": _i(inn), "relay_no": r.get("no"),
                    "wpa": (r.get("metricOption") or {}).get("wpaByPlate"),
                    **o,
                })
    events.sort(key=lambda e: e["seqno"])
    has_state = _has_state(events)
    meta["has_state"] = has_state

    pitches, pas = [], {}
    prev = {}
    half = "top"
    count = (0, 0)
    for e in events:
        cur = e.get("currentGameState") or {}
        text = e.get("text") or ""
        if e["type"] == 0 and "회" in text:  # "1회초 KIA 공격"
            half = "top" if "회초" in text else "bot"
        key = (e["inning"], half, e["relay_no"])
        if e["type"] == T_BATTER:
            count = (0, 0)
            pas[key] = {
                **meta, "inning": e["inning"], "half": half, "relay_no": e["relay_no"],
                "pitcher_id": cur.get("pitcher"), "batter_id": cur.get("batter"),
                **{f"start_{k}": v for k, v in (_state(prev) if has_state else NA_STATE).items()},
                "result": None, "n_pitches": 0, "wpa": e["wpa"],
            }
        elif e["type"] == T_PITCH:
            pa = pas.get(key)
            p = pts.get(e.get("ptsPitchId"), {})
            balls, strikes = count
            count = _next_count(balls, strikes, e.get("pitchResult"))
            pitches.append({
                **meta, "inning": e["inning"], "half": half, "relay_no": e["relay_no"],
                "pitcher_id": cur.get("pitcher"), "batter_id": cur.get("batter"),
                "pitch_num": e.get("pitchNum"),
                "balls": balls, "strikes": strikes,
                **(_state(prev) if has_state else NA_STATE),
                # 검증용: 중계가 기록한 투구 직후 볼카운트 (2016~)
                "_ball_after": _i(cur.get("ball"), None) if has_state else None,
                "_strike_after": _i(cur.get("strike"), None) if has_state else None,
                "pitch_type": e.get("stuff") or None,
                "speed_kmh": _i(e.get("speed"), None),
                "pitch_result": e.get("pitchResult"),
                "text": e.get("text"),
                **{f"pts_{k}": p.get(k) for k in PTS_FIELDS},
            })
            if pa is not None:
                pa["n_pitches"] += 1
        elif e["type"] == T_OTHER and re.match(r"^\d+구 ", text):
            # 투구 없이 카운트만 바뀌는 경우: "3구 피치클락 투수위반 볼" (2025~)
            balls, strikes = count
            if text.endswith("볼"):
                count = (balls + 1, strikes)
            elif text.endswith("스트라이크"):
                count = (balls, strikes + 1)
        elif e["type"] in T_RESULT:
            pa = pas.get(key)
            if pa is not None and pa["result"] is None:
                pa["result"] = e.get("text", "").split(" : ", 1)[-1]
                pa["end_outs"] = _i(cur.get("out"))
        if cur:
            prev = cur

    pitches = pd.DataFrame(pitches)
    pas = pd.DataFrame(list(pas.values()))
    if not pas.empty:
        res = pas.set_index(["inning", "half", "relay_no"])["result"]
        pitches["pa_result"] = pitches.set_index(["inning", "half", "relay_no"]).index.map(res)

    players = []
    for side in ("home", "away"):
        lu = (data.get("lineup") or {}).get(f"{side}Lineup") or {}
        for role in ("batter", "pitcher"):
            for p in lu.get(role) or []:
                players.append({
                    "player_id": p.get("pcode"), "name": p.get("name"),
                    "hit_type": p.get("hitType"), "birth": p.get("birth"),
                    "height": p.get("height"), "weight": p.get("weight"),
                    "team": meta[f"{side}_team"], "season": meta["season"],
                })
    return pitches, pas, pd.DataFrame(players)


def load_game(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
