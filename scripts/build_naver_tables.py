"""수집된 네이버 문자중계 원본을 분석용 Parquet 표로 변환.

출력 (data/processed/naver/):
    pitches.parquet  한 줄 = 공 하나
    pas.parquet      한 줄 = 타석 하나
    players.parquet  선수 정보 (시즌·팀별)

투수-타자 '몇 번째 만남'은 타석 기준으로 세 가지를 붙인다:
    matchup_no_game    그 경기에서 몇 번째 대결
    matchup_no_season  그 시즌에서 몇 번째 대결 (시범경기·포스트시즌 포함, 경기 순서대로)
    matchup_no_career  수집 기간(2008~) 통산 몇 번째 대결

예)
    python scripts/build_naver_tables.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kbo.parsers.naver_relay import load_game, parse_game  # noqa: E402

RAW = ROOT / "data" / "raw" / "naver" / "relay"
OUT = ROOT / "data" / "processed" / "naver"


def main():
    P, A, PL = [], [], []
    files = sorted(RAW.glob("*/*.json.gz"))
    for i, f in enumerate(files, 1):
        try:
            p, a, pl = parse_game(load_game(f))
        except Exception as e:
            print(f"[fail] {f.name}: {e!r}")
            continue
        if p.empty:
            continue
        P.append(p), A.append(a), PL.append(pl)
        if i % 500 == 0:
            print(f"{i}/{len(files)}", flush=True)

    pitches = pd.concat(P, ignore_index=True)
    pas = pd.concat(A, ignore_index=True)
    players = pd.concat(PL, ignore_index=True).drop_duplicates(["player_id", "season", "team"])

    # 타석 순서 = 경기일 -> 경기ID -> 이닝 -> 초/말 -> 중계 순번
    pas["_half"] = (pas["half"] == "bot").astype(int)
    pas = pas.sort_values(["game_date", "game_id", "inning", "_half", "relay_no"]).drop(columns="_half")
    pair = ["pitcher_id", "batter_id"]
    pas["matchup_no_game"] = pas.groupby(["game_id", *pair]).cumcount() + 1
    pas["matchup_no_season"] = pas.groupby(["season", *pair]).cumcount() + 1
    pas["matchup_no_career"] = pas.groupby(pair).cumcount() + 1

    key = ["game_id", "inning", "half", "relay_no"]
    pitches = pitches.drop(columns=["_ball_after", "_strike_after"]).merge(
        pas[key + ["matchup_no_game", "matchup_no_season", "matchup_no_career"]],
        on=key, how="left",
    )

    OUT.mkdir(parents=True, exist_ok=True)
    pitches.to_parquet(OUT / "pitches.parquet", index=False)
    pas.to_parquet(OUT / "pas.parquet", index=False)
    players.to_parquet(OUT / "players.parquet", index=False)
    print(f"games {len(files)}, pitches {len(pitches):,}, PAs {len(pas):,}, players {len(players):,}")


if __name__ == "__main__":
    main()
