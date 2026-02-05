# MQTT 프로토콜 테스트 결과

## ✅ 테스트 완료

### 테스트 파일
- 파일명: `H2567_IMO9991862_ChannelID_20260127.xlsx`
- 위치: `data/test/H2567_IMO9991862_ChannelID_20260127.xlsx`

### 구현된 기능

1. **필수 컬럼 검증**
   - 헤더에 필수 컬럼이 모두 있는지 검증
   - 필수 컬럼: Resource, Data type, RuleNaming, Level 1-4, Miscellaneous, Measure, Description, Calculation, MQTT Tag, Remark
   - 필수 컬럼이 없으면 에러 발생

2. **MQTT Tag 필수 값 검증**
   - MQTT Tag 컬럼은 반드시 값이 있어야 함
   - 값이 없으면 에러 발생

3. **데이터 저장**
   - 모든 필드를 `extra_data`에 JSON으로 저장
   - 주요 필드는 별도 컬럼에도 저장 (호환성)
     - `io_no`: MQTT Tag 값
     - `io_name`: Description 또는 Measure
     - `io_type`: Data type
     - `description`: Description
     - `remarks`: Remark

### 테스트 결과

**업로드 성공:**
- 총 16개 항목 파싱 및 저장 완료
- 파일명에서 Hull NO (H2567), IMO (IMO9991862) 자동 추출
- 날짜 키 자동 생성 (UTC 기준)

**저장된 데이터 예시:**
```json
{
  "io_no": "TX038.01/Meas1/PRIM",
  "io_name": "ME1 TC Speed",
  "io_type": "Decimal",
  "description": "ME1 TC Speed",
  "extra_data": "{\"Resource\": \"IAS\", \"Data type\": \"Decimal\", \"RuleNaming\": \"hs4sd_v1\", \"Level 1\": \"me01\", \"Level 2\": \"tc\", \"Miscellaneous\": \"rpm\", \"Measure\": \"speed\", \"Description\": \"ME1 TC Speed\", \"MQTT Tag\": \"TX038.01/Meas1/PRIM\"}"
}
```

### 에러 처리

1. **필수 컬럼 누락**
   - 에러 메시지: "필수 컬럼이 누락되었습니다: {컬럼명들}"
   - HTTP 상태 코드: 500

2. **MQTT Tag 값 누락**
   - 에러 메시지: "MQTT Tag는 필수 컬럼이며 값이 있어야 합니다."
   - HTTP 상태 코드: 500

3. **헤더 없음**
   - 에러 메시지: "엑셀 파일에 헤더가 없습니다."
   - HTTP 상태 코드: 500

## 📋 필수 컬럼 목록

1. Resource
2. Data type
3. RuleNaming
4. Level 1
5. Level 2
6. Level 3
7. Level 4
8. Miscellaneous
9. Measure
10. Description
11. Calculation
12. MQTT Tag ⚠️ (값 필수)
13. Remark

## 🧪 테스트 방법

### 1. 웹 브라우저 테스트
```
http://localhost:15173
```
- 파일 업로드
- IOLIST 목록 확인
- 항목 상세 확인

### 2. API 테스트
```bash
# 파일 업로드
curl -X POST "http://localhost:18000/upload/iolist" \
  -F "file=@data/test/H2567_IMO9991862_ChannelID_20260127.xlsx"

# IOLIST 목록 조회
curl "http://localhost:18000/iolist/headers"

# 항목 조회
curl "http://localhost:18000/iolist/headers/{header_id}/items"
```

## ✅ 검증 완료 사항

- [x] 필수 컬럼 헤더 검증
- [x] MQTT Tag 값 필수 검증
- [x] 엑셀 파일 파싱
- [x] 데이터베이스 저장
- [x] 파일 저장
- [x] 파일명 자동 파싱 (Hull NO, IMO)
- [x] 날짜 키 자동 생성 (UTC)
- [x] 에러 처리
