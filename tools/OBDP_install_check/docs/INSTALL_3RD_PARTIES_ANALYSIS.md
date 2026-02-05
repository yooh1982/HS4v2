# install_3rd_parties.sh 분석

Installer 1/2. 서버에 설치되는 3rd party 구성요소를 정리한 문서입니다.

## 개요

- **로그 파일**: 스크립트 실행 시 `install_3rd_parties.log`에 stdout/stderr 공통 기록
- **실행 옵션**: `set -e` (오류 시 즉시 종료), `exec > >(tee -a install_3rd_parties.log) 2>&1`

## 설치 버전

| 항목 | 버전 |
|------|------|
| PostgreSQL (TimescaleDB) | 16 |
| Node.js | 20 (major) |
| OpenJDK | BellSoft Java 21 |
| EMQ-X | 5.6.1 (ubuntu22.04-amd64) |

## 설치 순서 및 검증 포인트

### 1. TimescaleDB (PostgreSQL 16)

- **설치**: `timescaledb-2-oss-postgresql-16`, `timescaledb-tune`
- **설정**: `postgresql.conf` (listen_addresses='*', max_connections=300, wal_level=minimal, max_wal_size=2GB), `/data` 존재 시 데이터 디렉터리 `/data/postgresql/16/main`로 변경
- **인증**: pg_hba.conf에 192.16.0.208/32 md5 추가, postgres 비밀번호 'postgres'
- **검증**: `systemctl postgresql`, `pg_isready`, 설정 파일/디렉터리 존재

### 2. Valkey

- **설치**: Percona repo, `valkey` 패키지
- **설정**: pidfile `/var/run/valkey/valkey_6379.pid`, dir `/var/lib/valkey`, sentinel.conf에 myprimary 127.0.0.1 6379
- **검증**: `systemctl valkey`, `valkey-cli ping`

### 3. RabbitMQ

- **설치**: Erlang 26.x, rabbitmq-server
- **설정**: 사용자 tapp / 비밀번호 (tapp.123), 권한 및 administrator 태그, rabbitmq_management 플러그인
- **검증**: `systemctl rabbitmq-server`, `rabbitmqctl list_users` 또는 status

### 4. EMQ-X

- **설치**: emqx-5.6.1-ubuntu22.04-amd64.deb
- **설정**: emqx.conf에 listeners.ssl.default 0.0.0.0:8885, acl.conf 수정
- **검증**: `systemctl emqx`, 포트 8885 리스닝 또는 emqx API

### 5. NGINX

- **설치**: apt install nginx, `/etc/nginx/ssl` 생성
- **검증**: `systemctl nginx`, `nginx -t`

### 6. fluent-bit

- **설치**: install.sh (공식), `/var/log/fluent-bit`, `/var/log/fluent-bit/old`
- **검증**: `systemctl fluent-bit`, `which fluent-bit`

### 7. Supervisor

- **설치**: apt supervisor
- **설정**: systemd After에 postgresql, valkey-server, rabbitmq-server 추가
- **검증**: `systemctl supervisor`

### 8. Zip

- **설치**: apt install zip
- **검증**: `which zip`, `zip --version` 또는 동등

### 9. OpenJDK (BellSoft Java 21)

- **설치**: bellsoft-java21
- **검증**: `java -version` (21)

### 10. Node.js

- **설치**: NodeSource node_20.x
- **검증**: `node -v` (v20.x), `npm -v`

### 11. Python3

- **설치**: python3-pip, virtualenv, `~/.venv`, pip 패키지: psycopg, requests, pycryptodome, PyYAML, pexpect
- **검증**: `python3 --version`, `~/.venv` 존재, `~/.venv/bin/python -c "import psycopg, requests, yaml, pexpect"`

### 12. VSFTP

- **설치**: vsftpd, 사용자별 설정 `/etc/vsftpd_user_conf/${USER}`, local_root `${HOME}/var/data/ftp`
- **검증**: `systemctl vsftpd`, `/etc/vsftpd.conf` 존재

### 13. Cleanup

- **동작**: `apt autoremove -y`
- **검증**: 별도 검증 없음 (설치 완료 후 정리)

---

## 두 번째 Installer

설치 툴은 2개로 구성된다고 하였으며, 현재 문서는 **install_3rd_parties.sh** 기준입니다.  
두 번째 installer 스크립트가 제공되면 동일 형식으로 분석을 추가할 예정입니다.
