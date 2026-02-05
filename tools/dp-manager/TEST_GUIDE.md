# DP Manager 테스트 가이드

## 🚀 빠른 시작

### 1. 서비스 확인
```bash
# 서비스 상태 확인
docker-compose ps

# Health Check
curl http://localhost:18000/health
```

### 2. 웹 브라우저 테스트 (권장)

**접속 URL**: http://localhost:15173

#### 테스트 시나리오:

1. **엑셀 파일 업로드**
   - 테스트 파일 생성: `python3 create_test_excel.py`
   - 파일 선택: `H2567_IMO9991862_IOList_20260125.xlsx`
   - 파일명에서 Hull NO와 IMO NO가 자동으로 채워지는지 확인
   - "업로드" 버튼 클릭
   - 성공 메시지 확인

2. **IOLIST 목록 확인**
   - 업로드한 IOLIST가 목록에 표시되는지 확인
   - Hull NO, IMO, 날짜 키, 파일명, 항목 수 확인

3. **필터링 테스트**
   - Hull Number 드롭다운에서 선택
   - IMO Number 드롭다운에서 선택
   - 날짜 키 드롭다운에서 선택
   - 필터링된 결과 확인

4. **IOLIST 항목 조회**
   - 목록에서 IOLIST 클릭
   - GRID에 항목들이 표시되는지 확인
   - IO 번호, IO 이름, IO 타입, 설명, 비고 확인

5. **항목 추가**
   - 하단 "새 항목 추가" 섹션에 입력
   - "추가" 버튼 클릭
   - GRID에 새 항목이 추가되는지 확인

6. **항목 수정**
   - 항목의 "수정" 버튼 클릭
   - 인라인 편집 모드로 변경되는지 확인
   - 값 수정 후 "저장" 버튼 클릭
   - 변경사항이 반영되는지 확인

7. **항목 삭제**
   - 항목의 "삭제" 버튼 클릭
   - 확인 대화상자에서 확인
   - 항목이 삭제되는지 확인

8. **IOLIST 삭제**
   - 목록에서 IOLIST의 "삭제" 버튼 클릭
   - 확인 대화상자에서 확인
   - IOLIST와 모든 항목이 삭제되는지 확인

### 3. API 직접 테스트

#### 테스트 스크립트 실행
```bash
./test_api.sh
```

#### 수동 API 테스트

**1. Health Check**
```bash
curl http://localhost:18000/health
```

**2. 필터 옵션 조회**
```bash
curl http://localhost:18000/iolist/filters
```

**3. IOLIST 헤더 목록 조회**
```bash
curl http://localhost:18000/iolist/headers
```

**4. 필터링된 목록 조회**
```bash
curl "http://localhost:18000/iolist/headers?hull_no=H2567&imo=IMO9991862"
```

**5. 특정 IOLIST 헤더 조회**
```bash
curl http://localhost:18000/iolist/headers/1
```

**6. IOLIST 항목 조회**
```bash
curl http://localhost:18000/iolist/headers/1/items
```

**7. 엑셀 파일 업로드**
```bash
curl -X POST "http://localhost:18000/upload/iolist?hull_no=H2567&imo=IMO9991862" \
  -F "file=@H2567_IMO9991862_IOList_20260125.xlsx"
```

**8. 항목 추가**
```bash
curl -X POST "http://localhost:18000/iolist/headers/1/items" \
  -H "Content-Type: application/json" \
  -d '{
    "io_no": "IO006",
    "io_name": "Test IO",
    "io_type": "Digital Input",
    "description": "Test description",
    "remarks": "Test"
  }'
```

**9. 항목 수정**
```bash
curl -X PUT "http://localhost:18000/iolist/items/1" \
  -H "Content-Type: application/json" \
  -d '{
    "io_name": "Updated IO Name",
    "remarks": "Updated"
  }'
```

**10. 항목 삭제**
```bash
curl -X DELETE "http://localhost:18000/iolist/items/1"
```

**11. IOLIST 삭제**
```bash
curl -X DELETE "http://localhost:18000/iolist/headers/1"
```

## 📝 테스트 체크리스트

### 기능 테스트
- [ ] 엑셀 파일 업로드 (파일명 자동 파싱)
- [ ] Hull NO, IMO NO 자동 추출
- [ ] 날짜 키 자동 생성 (UTC)
- [ ] 엑셀 파싱 및 DB 저장
- [ ] IOLIST 목록 조회
- [ ] 필터링 (Hull NO, IMO, 날짜)
- [ ] IOLIST 항목 조회
- [ ] 항목 추가
- [ ] 항목 수정
- [ ] 항목 삭제
- [ ] IOLIST 삭제

### UI 테스트
- [ ] 파일 선택 시 자동 입력
- [ ] GRID 표시
- [ ] 인라인 편집
- [ ] 필터 드롭다운
- [ ] 에러 메시지 표시
- [ ] 로딩 상태 표시

### 데이터 검증
- [ ] 파일 저장 경로 확인: `./data/uploads/{hull_no}/{imo}/{date_key}/`
- [ ] DB 데이터 확인
- [ ] 파일 삭제 시 물리적 파일도 삭제되는지 확인

## 🐛 문제 해결

### 백엔드가 시작되지 않는 경우
```bash
# 로그 확인
docker-compose logs backend

# 재시작
docker-compose restart backend

# 재빌드
docker-compose build --no-cache backend
docker-compose up -d
```

### 프론트엔드가 접속되지 않는 경우
```bash
# 로그 확인
docker-compose logs frontend

# 재시작
docker-compose restart frontend
```

### DB 연결 오류
```bash
# DB 상태 확인
docker-compose ps db

# DB 로그 확인
docker-compose logs db
```

## 📊 테스트 데이터

테스트용 엑셀 파일 생성:
```bash
python3 create_test_excel.py
```

생성된 파일: `H2567_IMO9991862_IOList_20260125.xlsx`

## 🔗 접속 정보

- **Frontend**: http://localhost:15173
- **Backend API**: http://localhost:18000
- **PostgreSQL**: localhost:15432
  - Database: iolist
  - User: iolist
  - Password: iolistpass
