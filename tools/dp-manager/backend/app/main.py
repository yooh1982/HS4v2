import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .db import db_ping, init_db, SessionLocal
from .schemas import (
    IOListHeaderResponse,
    IOListHeaderListResponse,
    IOListItemResponse,
    IOListItemCreate,
    IOListItemUpdate,
    DeviceResponse,
    DeviceCreate,
    DeviceUpdate
)
from .services import (
    create_iolist_from_excel,
    get_iolist_headers,
    get_iolist_header,
    get_iolist_items,
    create_iolist_item,
    update_iolist_item,
    delete_iolist_item,
    delete_iolist_header,
    get_available_filters,
    check_duplicates_and_missing,
    generate_dp_file,
    create_device,
    update_device,
    delete_device
)
from .file_parser import parse_filename


def setup_logging() -> None:
    log_file = os.getenv("LOG_FILE", "/data/logs/backend/backend.log")
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 중복 핸들러 방지(uvicorn reload 환경)
    if root.handlers:
        return

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)


setup_logging()
logger = logging.getLogger("dp-manager")

app = FastAPI(title="DP Manager API", version="0.1.0")

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:15173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# DB 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 앱 시작 시 DB 초기화
@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("Database initialized")


@app.get("/health")
def health():
    ok = db_ping()
    logger.info("health check db=%s", ok)
    return {"ok": True, "db": ok}


@app.post("/upload/iolist", response_model=IOListHeaderResponse)
async def upload_iolist(
    file: UploadFile = File(...),
    hull_no: Optional[str] = Query(None, description="Hull Number (예: H369, 파일명에서 자동 추출 가능)"),
    imo: Optional[str] = Query(None, description="IMO Number (예: IMO1234567, 파일명에서 자동 추출 가능)"),
    date_key: Optional[str] = Query(None, description="날짜 키 (YYYYMMDD_HHMMSS, 미지정 시 현재 시간 UTC)"),
    db: Session = Depends(get_db)
):
    """IOLIST 엑셀 파일 업로드 및 저장"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.")
    
    # 파일명에서 Hull NO와 IMO NO 추출 시도
    parsed = parse_filename(file.filename)
    if parsed:
        file_hull_no, file_imo = parsed
        # 쿼리 파라미터가 없으면 파일명에서 추출한 값 사용
        if not hull_no:
            hull_no = file_hull_no
        if not imo:
            imo = file_imo
    
    # Hull NO와 IMO NO가 여전히 없으면 에러
    if not hull_no:
        raise HTTPException(status_code=400, detail="Hull Number를 입력하거나 파일명에서 추출할 수 있어야 합니다. (예: H2567_IMO9991862_IOList.xlsx)")
    if not imo:
        raise HTTPException(status_code=400, detail="IMO Number를 입력하거나 파일명에서 추출할 수 있어야 합니다. (예: H2567_IMO9991862_IOList.xlsx)")
    
    # 날짜 키가 없으면 현재 시간(UTC)으로 생성
    if not date_key:
        date_key = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    content = await file.read()
    logger.info("uploaded file=%s hull_no=%s imo=%s date_key=%s size=%d", 
                file.filename, hull_no, imo, date_key, len(content))
    
    try:
        header = create_iolist_from_excel(db, content, file.filename, hull_no, imo, date_key)
        return header
    except Exception as e:
        logger.error(f"업로드 처리 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"업로드 처리 실패: {str(e)}")


@app.get("/iolist/headers", response_model=list[IOListHeaderListResponse])
def list_iolist_headers(
    hull_no: Optional[str] = Query(None, description="Hull Number 필터"),
    imo: Optional[str] = Query(None, description="IMO Number 필터"),
    date_key: Optional[str] = Query(None, description="날짜 키 필터"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """IOLIST 헤더 목록 조회 (필터링 지원)"""
    headers = get_iolist_headers(db, hull_no=hull_no, imo=imo, date_key=date_key, skip=skip, limit=limit)
    
    result = []
    for header in headers:
        item_count = len(header.items)
        result.append(IOListHeaderListResponse(
            id=header.id,
            uuid=header.uuid,
            hull_no=header.hull_no,
            imo=header.imo,
            date_key=header.date_key,
            file_name=header.file_name,
            created_at=header.created_at,
            updated_at=header.updated_at,
            item_count=item_count
        ))
    
    return result


@app.get("/iolist/headers/{header_id}", response_model=IOListHeaderResponse)
def get_iolist_header_detail(header_id: int, db: Session = Depends(get_db)):
    """IOLIST 헤더 상세 조회"""
    header = get_iolist_header(db, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="IOLIST를 찾을 수 없습니다.")
    return header


@app.get("/iolist/headers/{header_id}/items", response_model=list[IOListItemResponse])
def list_iolist_items(
    header_id: int,
    show_duplicates: bool = Query(False, description="중복 항목만 표시"),
    show_missing_required: bool = Query(False, description="필수 값 없는 항목만 표시"),
    db: Session = Depends(get_db)
):
    """IOLIST 항목 목록 조회 (필터링 및 중복 정보 포함)"""
    import json
    
    header = get_iolist_header(db, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="IOLIST를 찾을 수 없습니다.")
    
    items = get_iolist_items(db, header_id, show_duplicates, show_missing_required)
    
    # 중복 및 필수 값 누락 정보 조회
    duplicate_info = check_duplicates_and_missing(db, header_id)
    
    # 응답 생성
    result = []
    for item in items:
        # raw_data에서 원본 데이터 가져오기
        raw_data = json.loads(item.get("raw_data", "{}")) if item.get("raw_data") else {}
        
        # DataChannelId 생성
        from .excel_parser import generate_data_channel_id
        data_channel_id = generate_data_channel_id(raw_data)
        
        # 중복 체크
        is_dup_dc = data_channel_id in duplicate_info["duplicate_data_channel_ids"]
        is_dup_desc = (item.get("description", "") or "") in duplicate_info["duplicate_descriptions"]
        is_dup_mqtt = (item.get("io_no", "") or "") in duplicate_info["duplicate_mqtt_tags"]
        
        # 필수 값 누락 체크
        has_missing = any(
            d["item_id"] == item.get("id")
            for d in duplicate_info["missing_required_values"]
        )
        
        result.append(IOListItemResponse(
            id=item.get("id"),
            header_id=header_id,
            io_no=item.get("io_no"),
            io_name=item.get("io_name"),
            io_type=item.get("io_type"),
            description=item.get("description"),
            remarks=item.get("remarks"),
            raw_data=item.get("raw_data"),  # 원본 데이터 반환
            created_at=item.get("created_at"),
            updated_at=item.get("updated_at"),
            data_channel_id=data_channel_id,
            is_duplicate_data_channel_id=is_dup_dc,
            is_duplicate_description=is_dup_desc,
            is_duplicate_mqtt_tag=is_dup_mqtt,
            has_missing_required=has_missing
        ))
    
    return result


@app.get("/iolist/headers/{header_id}/validation")
def get_validation_info(header_id: int, db: Session = Depends(get_db)):
    """중복 및 필수 값 누락 검증 정보 조회"""
    header = get_iolist_header(db, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="IOLIST를 찾을 수 없습니다.")
    
    return check_duplicates_and_missing(db, header_id)


@app.get("/iolist/headers/{header_id}/devices", response_model=list[DeviceResponse])
def list_devices(header_id: int, db: Session = Depends(get_db)):
    """IOLIST 헤더의 Device 목록 조회 (스키마 기반)"""
    from .schema_manager import get_table, sanitize_schema_name
    from .db import engine
    from sqlalchemy import text
    
    header = get_iolist_header(db, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="IOLIST를 찾을 수 없습니다.")
    
    schema_name = sanitize_schema_name(header.hull_no)
    table_name = "device"
    
    device_table = get_table(engine, header.hull_no, table_name)
    if device_table is None:
        return []
    
    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT * FROM "{schema_name}"."{table_name}" ORDER BY id'))
        devices = []
        for row in result:
            device_dict = dict(row._mapping)
            devices.append(DeviceResponse(
                id=device_dict.get("id"),
                header_id=header_id,
                device_name=device_dict.get("device_name"),
                protocol=device_dict.get("protocol"),
                created_at=device_dict.get("created_at"),
                updated_at=device_dict.get("updated_at")
            ))
    
    return devices


@app.post("/iolist/headers/{header_id}/devices", response_model=DeviceResponse)
def create_device_endpoint(header_id: int, device: DeviceCreate, db: Session = Depends(get_db)):
    """Device 생성"""
    try:
        device_dict = create_device(db, header_id, device.device_name, device.protocol)
        return DeviceResponse(
            id=device_dict.get("id"),
            header_id=header_id,
            device_name=device_dict.get("device_name"),
            protocol=device_dict.get("protocol"),
            created_at=device_dict.get("created_at"),
            updated_at=device_dict.get("updated_at")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Device 생성 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Device 생성 실패: {str(e)}")


@app.put("/iolist/headers/{header_id}/devices/{device_id}", response_model=DeviceResponse)
def update_device_endpoint(header_id: int, device_id: int, device: DeviceUpdate, db: Session = Depends(get_db)):
    """Device 수정"""
    try:
        device_dict = update_device(db, header_id, device_id, device.device_name, device.protocol)
        if not device_dict:
            raise HTTPException(status_code=404, detail="Device를 찾을 수 없습니다.")
        return DeviceResponse(
            id=device_dict.get("id"),
            header_id=header_id,
            device_name=device_dict.get("device_name"),
            protocol=device_dict.get("protocol"),
            created_at=device_dict.get("created_at"),
            updated_at=device_dict.get("updated_at")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Device 수정 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Device 수정 실패: {str(e)}")


@app.delete("/iolist/headers/{header_id}/devices/{device_id}")
def delete_device_endpoint(header_id: int, device_id: int, db: Session = Depends(get_db)):
    """Device 삭제"""
    success = delete_device(db, header_id, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device를 찾을 수 없습니다.")
    return {"message": "Device가 삭제되었습니다."}


@app.post("/iolist/headers/{header_id}/items", response_model=IOListItemResponse)
def create_iolist_item_endpoint(
    header_id: int,
    item: IOListItemCreate,
    db: Session = Depends(get_db)
):
    """IOLIST 항목 생성"""
    header = get_iolist_header(db, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="IOLIST를 찾을 수 없습니다.")
    
    item_dict = create_iolist_item(db, header_id, item)
    
    # IOListItemResponse로 변환
    raw_data = json.loads(item_dict.get("raw_data", "{}")) if item_dict.get("raw_data") else {}
    from .excel_parser import generate_data_channel_id
    data_channel_id = generate_data_channel_id(raw_data)
    
    return IOListItemResponse(
        id=item_dict.get("id"),
        header_id=header_id,
        io_no=item_dict.get("io_no"),
        io_name=item_dict.get("io_name"),
        io_type=item_dict.get("io_type"),
        description=item_dict.get("description"),
        remarks=item_dict.get("remarks"),
        raw_data=item_dict.get("raw_data"),
        created_at=item_dict.get("created_at"),
        updated_at=item_dict.get("updated_at"),
        data_channel_id=data_channel_id,
        is_duplicate_data_channel_id=False,
        is_duplicate_description=False,
        is_duplicate_mqtt_tag=False,
        has_missing_required=False
    )


@app.put("/iolist/items/{item_id}", response_model=IOListItemResponse)
def update_iolist_item_endpoint(
    item_id: int,
    item: IOListItemUpdate,
    db: Session = Depends(get_db)
):
    """IOLIST 항목 수정"""
    updated_item = update_iolist_item(db, item_id, item)
    if not updated_item:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    
    # IOListItemResponse로 변환
    raw_data = json.loads(updated_item.get("raw_data", "{}")) if updated_item.get("raw_data") else {}
    from .excel_parser import generate_data_channel_id
    data_channel_id = generate_data_channel_id(raw_data)
    
    # header_id 찾기 (모든 헤더 검색)
    from .services import get_iolist_headers
    from .schema_manager import sanitize_schema_name
    headers = get_iolist_headers(db)
    header_id = None
    for h in headers:
        schema_name = sanitize_schema_name(h.hull_no)
        table_name = f"iolist_{h.date_key}"
        from .schema_manager import get_table
        from .db import engine
        iolist_table = get_table(engine, h.hull_no, table_name)
        if iolist_table is not None:
            with engine.connect() as conn:
                from sqlalchemy import text
                result = conn.execute(
                    text(f'SELECT id FROM "{schema_name}"."{table_name}" WHERE id = :item_id'),
                    {"item_id": item_id}
                )
                if result.first():
                    header_id = h.id
                    break
    
    return IOListItemResponse(
        id=updated_item.get("id"),
        header_id=header_id or 0,
        io_no=updated_item.get("io_no"),
        io_name=updated_item.get("io_name"),
        io_type=updated_item.get("io_type"),
        description=updated_item.get("description"),
        remarks=updated_item.get("remarks"),
        raw_data=updated_item.get("raw_data"),
        created_at=updated_item.get("created_at"),
        updated_at=updated_item.get("updated_at"),
        data_channel_id=data_channel_id,
        is_duplicate_data_channel_id=False,
        is_duplicate_description=False,
        is_duplicate_mqtt_tag=False,
        has_missing_required=False
    )


@app.delete("/iolist/items/{item_id}")
def delete_iolist_item_endpoint(item_id: int, db: Session = Depends(get_db)):
    """IOLIST 항목 삭제"""
    success = delete_iolist_item(db, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    return {"message": "항목이 삭제되었습니다."}


@app.delete("/iolist/headers/{header_id}")
def delete_iolist_header_endpoint(header_id: int, db: Session = Depends(get_db)):
    """IOLIST 헤더 및 모든 항목 삭제"""
    success = delete_iolist_header(db, header_id)
    if not success:
        raise HTTPException(status_code=404, detail="IOLIST를 찾을 수 없습니다.")
    return {"message": "IOLIST가 삭제되었습니다."}


@app.get("/iolist/filters")
def get_filters(db: Session = Depends(get_db)):
    """사용 가능한 필터 옵션 조회"""
    return get_available_filters(db)


@app.get("/iolist/headers/{header_id}/download-dp")
def download_dp_file(header_id: int, db: Session = Depends(get_db)):
    """DP XML 파일 다운로드"""
    try:
        xml_content, filename = generate_dp_file(db, header_id)
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"DP 파일 생성 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DP 파일 생성 실패: {str(e)}")
