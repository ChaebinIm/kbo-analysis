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

## 투구 단위 데이터 (네이버 스포츠 문자중계)

출처: 네이버 스포츠 → 야구 → KBO리그 → 경기 → '문자중계' 탭.
화면이 쓰는 API(`api-gw.sports.naver.com`)에서 이닝별 중계를 받아
`data/raw/naver/relay/{시즌}/{경기ID}.json.gz` 로 저장한다.

```bash
python scripts/collect_naver_relay.py --start 2008 --end 2026   # 수집 (재실행 시 이어받기)
python scripts/build_naver_tables.py                            # data/processed/naver/*.parquet 생성
```

| 기간 | 들어 있는 것 |
|---|---|
| 2008~ | 투수·타자, 구종, 구속, 투구 결과(볼/스트라이크/파울/헛스윙/타격), 타석 결과 문장 |
| 2016~ | + 아웃·주자·점수 상황, 타석별 승리확률 변화(WPA) |
| 2016 후반~ | + 투구 추적(PTS): 홈플레이트 통과 위치, 궤적(초기 위치·속도·가속도), 타자별 스트라이크존 |

- 볼카운트는 투구 결과를 순서대로 따라가며 직접 계산한다 (피치클락 위반 포함, 2026 시즌 기준 공식 값과 100% 일치).
- 2008~2015년의 아웃·주자·점수는 원본에 비어 있어 빈 값(NaN)으로 둔다.
- `pitch_result` 코드: B 볼, T 스트라이크(루킹), S 헛스윙, F 파울, W 번트파울, H 타격(인플레이)

## 로드맵

1. 데이터 수집: KBO 공식 기록 → 경기 결과/박스스코어 → 문자중계(play-by-play)
2. EDA: 리그 환경 변화, 피타고리안 승률, 에이징 커브
3. 세이버메트릭스: KBO용 wOBA 가중치, FIP 상수, 파크팩터, RE24, WAR 근사
4. 모델링 / 대시보드
