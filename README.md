# KBO Analysis

KBO 리그 데이터를 직접 수집해서 탐색 분석, 세이버메트릭스, 모델링까지 해보는 프로젝트.

## 구조

```
kbo/                 # 재사용 코드 (수집기, 지표 계산 등)
  scrapers/
    kbo_record.py    # KBO 공식 사이트 선수 기록 수집기
scripts/             # 실행용 스크립트
notebooks/           # 분석 노트북
data/raw/            # 원본 수집 데이터 (git 제외)
data/processed/      # 정제 데이터 (git 제외)
```

## 데이터 수집

```bash
conda activate system_trading
python scripts/collect_kbo_records.py --start 2010 --end 2026
```

수집 대상 페이지(시즌별, 팀별 전체 선수):

| 키 | 내용 |
|---|---|
| hitter_basic1 / basic2 / detail1 | 타자 기본·세부 기록 |
| pitcher_basic1 / basic2 / detail1 | 투수 기본·세부 기록 |
| defense | 수비 |
| runner | 주루 |

이미 받은 시즌은 CSV 캐시를 재사용한다 (`--overwrite`로 다시 받기).
요청 사이 기본 1초 간격을 둔다.

## 로드맵

1. 데이터 수집: KBO 공식 기록 → 경기 결과/박스스코어 → 문자중계(play-by-play)
2. EDA: 리그 환경 변화, 피타고리안 승률, 에이징 커브
3. 세이버메트릭스: KBO용 wOBA 가중치, FIP 상수, 파크팩터, RE24, WAR 근사
4. 모델링 / 대시보드
