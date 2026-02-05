# OBDP Install Check

Installer를 통해 설치한 플랫폼이 정상적으로 설치되었는지 **초기 설치 상태**를 확인하는 도구입니다.

## 목적

- 설치 스크립트(installer) 실행 후 플랫폼의 초기 설치 상태 검증
- 필수 구성요소·서비스·경로·설정 등이 기대한 대로 존재하는지 확인
- **실행 내역은 로그로 저장**, **검증 결과는 보고서(HTML/MD)로 출력**

## 디렉터리 구조

```
OBDP_install_check/
├── README.md
├── config/
│   └── install_components.yaml   # install_3rd_parties 기준 검증 항목
├── scripts/
│   ├── run.sh             # 실행 진입점 (bash)
│   ├── run_check.py       # 검증 실행 + 로그 + 결과 JSON
│   └── report_generator.py # 결과 JSON → 보고서 생성
├── docs/
│   └── INSTALL_3RD_PARTIES_ANALYSIS.md  # install_3rd_parties.sh 분석
├── logs/                  # 실행 로그 (run_YYYYMMDD_HHMMSS.log)
├── results/               # 결과 JSON (result_YYYYMMDD_HHMMSS.json)
└── reports/               # 생성된 보고서 (report_YYYYMMDD_HHMMSS.html / .md)
```

## 요구 사항

- Python 3
- PyYAML: `pip install pyyaml`
- 검증은 **설치가 완료된 대상 호스트(Linux, systemd)**에서 실행해야 합니다. macOS/Windows에서는 서비스·경로 검증 대부분이 실패합니다.

## 사용법

### 1. 검증 실행 (로그 + 결과 JSON + 보고서 자동 생성)

```bash
cd tools/OBDP_install_check/scripts
./run.sh
```

또는

```bash
python3 run_check.py
```

- **로그**: `../logs/run_YYYYMMDD_HHMMSS.log` 에 실행 내역 전체 기록
- **결과**: `../results/result_YYYYMMDD_HHMMSS.json`
- **보고서**: `../reports/report_YYYYMMDD_HHMMSS.html`, `report_YYYYMMDD_HHMMSS.md` 자동 생성

### 2. 옵션

```bash
python3 run_check.py --config ../config/install_components.yaml \
  --logs-dir ../logs --results-dir ../results
python3 run_check.py --no-report   # 결과 JSON만 생성, 보고서 생략
```

### 3. 기존 결과 JSON으로만 보고서 생성

```bash
python3 report_generator.py --result ../results/result_20260101_120000.json
python3 report_generator.py --result ../results/result_20260101_120000.json --format html
```

## 검증 대상 (install_3rd_parties.sh 기준)

| 순서 | 컴포넌트 |
|------|----------|
| 1 | TimescaleDB (PostgreSQL 16) |
| 2 | Valkey |
| 3 | RabbitMQ |
| 4 | EMQ-X |
| 5 | NGINX |
| 6 | fluent-bit |
| 7 | Supervisor |
| 8 | Zip |
| 9 | OpenJDK (BellSoft Java 21) |
| 10 | Node.js 20 |
| 11 | Python3 + venv & 패키지 (psycopg, requests, PyYAML, pexpect 등) |
| 12 | VSFTP |

자세한 설치 단계·검증 포인트는 `docs/INSTALL_3RD_PARTIES_ANALYSIS.md` 참고.

## Installer 2

설치 툴은 2개로 구성 예정이며, 현재는 **install_3rd_parties.sh** 기준만 반영되어 있습니다. 두 번째 installer 스크립트가 정해지면 `config`에 검증 정의를 추가하고 동일 방식으로 실행·보고서를 사용할 수 있습니다.

## 관련

- HS4v2 `tools/` 하위 툴 중 하나입니다.
