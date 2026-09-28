"""네이버 문자중계(투구 단위)를 시즌 범위만큼 수집.

최신 시즌부터 거꾸로 받는다 (투구 추적 데이터가 있는 최근 시즌 우선).
중간에 끊겨도 다시 실행하면 이미 받은 경기는 건너뛴다.

예)
    python scripts/collect_naver_relay.py --start 2008 --end 2026
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kbo.scrapers.naver_relay import NaverRelayScraper  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2008)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=0.25)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    scraper = NaverRelayScraper(delay=args.delay)
    out_dir = ROOT / "data" / "raw"
    for season in range(args.end, args.start - 1, -1):
        sched = scraper.schedule(season)
        sched_path = out_dir / "naver" / "schedule" / f"{season}.csv"
        sched_path.parent.mkdir(parents=True, exist_ok=True)
        sched.to_csv(sched_path, index=False, encoding="utf-8-sig")

        # 종료 경기만 (포스트시즌 일부는 ENDED로 표기됨), 올스타전 제외
        done = sched[sched["statusCode"].isin(["RESULT", "ENDED"])
                     & ~sched["cancel"].astype(bool)
                     & (sched["roundCode"] != "kbo_as")]
        print(f"=== {season}: 일정 {len(sched)}경기, 종료 {len(done)}경기", flush=True)
        ok = skip = fail = 0
        for i, gid in enumerate(done["gameId"], 1):
            try:
                path = scraper.game_to_file(gid, season, out_dir, args.overwrite)
                if path is None:
                    skip += 1
                else:
                    ok += 1
            except Exception as e:
                fail += 1
                print(f"[fail] {gid}: {e!r}", flush=True)
            if i % 50 == 0:
                print(f"  {season} {i}/{len(done)} (ok {ok}, 중계없음 {skip}, 실패 {fail})", flush=True)
        print(f"=== {season} 완료: ok {ok}, 중계없음 {skip}, 실패 {fail}", flush=True)


if __name__ == "__main__":
    main()
