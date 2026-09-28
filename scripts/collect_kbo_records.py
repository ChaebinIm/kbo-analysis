"""KBO 공식 선수 기록을 시즌 범위만큼 수집해 data/raw 에 CSV로 저장.

예)
    python scripts/collect_kbo_records.py --start 2010 --end 2026
    python scripts/collect_kbo_records.py --start 2025 --end 2025 --pages hitter_basic1 pitcher_basic1
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kbo.scrapers.kbo_record import PAGES, KboRecordScraper  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2010)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--pages", nargs="*", default=list(PAGES))
    ap.add_argument("--series", default="regular")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    scraper = KboRecordScraper(delay=args.delay)
    out_dir = ROOT / "data" / "raw"
    for season in range(args.start, args.end + 1):
        for page in args.pages:
            try:
                path = scraper.fetch_to_csv(page, season, out_dir, args.series, args.overwrite)
                print(f"[ok] {season} {page} -> {path.relative_to(ROOT)}", flush=True)
            except Exception as e:  # 한 페이지 실패가 전체를 멈추지 않도록
                print(f"[fail] {season} {page}: {e!r}", flush=True)


if __name__ == "__main__":
    main()
