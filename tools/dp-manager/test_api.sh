#!/bin/bash

API_BASE="http://localhost:18000"

echo "=== 1. Health Check ==="
curl -s "${API_BASE}/health" | python3 -m json.tool
echo -e "\n"

echo "=== 2. 필터 옵션 조회 ==="
curl -s "${API_BASE}/iolist/filters" | python3 -m json.tool
echo -e "\n"

echo "=== 3. IOLIST 헤더 목록 조회 ==="
curl -s "${API_BASE}/iolist/headers" | python3 -m json.tool
echo -e "\n"

echo "=== 4. 특정 IOLIST 헤더 조회 (ID=1) ==="
curl -s "${API_BASE}/iolist/headers/1" | python3 -m json.tool
echo -e "\n"

echo "=== 5. IOLIST 항목 조회 (Header ID=1) ==="
curl -s "${API_BASE}/iolist/headers/1/items" | python3 -m json.tool
echo -e "\n"

echo "=== 6. 엑셀 파일 업로드 테스트 ==="
echo "파일이 있으면 업로드하세요:"
echo "curl -X POST \"${API_BASE}/upload/iolist?hull_no=H2567&imo=IMO9991862\" -F \"file=@test.xlsx\""
echo -e "\n"
