import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, text, Table, MetaData

from .models import IOListHeader
from .schemas import IOListItemCreate, IOListItemUpdate
from .excel_parser import parse_iolist_excel, parse_device_sheet, extract_iolist_fields, generate_data_channel_id, REQUIRED_VALUE_COLUMNS
from .schema_manager import (
    create_schema, create_device_table, create_iolist_table,
    get_table, sanitize_schema_name
)
from .db import engine

logger = logging.getLogger("dp-manager")


def save_uploaded_file(file_content: bytes, filename: str, file_uuid: str) -> str:
    """업로드된 파일을 저장하고 경로 반환"""
    # 저장 디렉토리: ./data/uploads/{uuid}/
    base_dir = Path("/data/uploads") / file_uuid
    base_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = base_dir / filename
    file_path.write_bytes(file_content)
    
    logger.info(f"파일 저장 완료: {file_path}")
    return str(file_path)


def create_iolist_from_excel(
    db: Session,
    file_content: bytes,
    filename: str,
    hull_no: str,
    imo: str,
    date_key: str
) -> IOListHeader:
    """엑셀 파일을 파싱하여 DB에 저장 (파일 구조 그대로 저장)"""
    # UUID 생성
    file_uuid = str(uuid.uuid4())
    
    # 임시 파일로 저장
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
        tmp_file.write(file_content)
        tmp_path = tmp_file.name
    
    try:
        # Device 시트 파싱 (Protocol 정보 확인)
        device_protocol_map = parse_device_sheet(tmp_path)
        
        # 기본 Protocol 결정 (Device 시트가 없거나 비어있으면 MQTT 사용)
        default_protocol = "MQTT"
        if device_protocol_map:
            # 가장 많이 사용되는 Protocol을 기본값으로 사용
            from collections import Counter
            protocol_counts = Counter(device_protocol_map.values())
            if protocol_counts:
                default_protocol = protocol_counts.most_common(1)[0][0]
        
        # 엑셀 파싱 (파일 구조 그대로, Protocol 정보 사용)
        parsed_items = parse_iolist_excel(tmp_path, protocol=default_protocol)
        
        if not parsed_items:
            raise ValueError("엑셀 파일에 데이터가 없습니다.")
        
        # 파일 저장 (UUID 기준)
        file_path = save_uploaded_file(file_content, filename, file_uuid)
        
        # 헤더 생성 (전역 테이블)
        header = IOListHeader(
            uuid=file_uuid,
            hull_no=hull_no,
            imo=imo,
            date_key=date_key,
            file_name=filename,
            file_path=file_path
        )
        db.add(header)
        db.flush()  # ID를 얻기 위해 flush
        
        # Hull No 스키마 생성
        create_schema(engine, hull_no)
        
        # Device 테이블 생성 및 데이터 저장
        device_table = create_device_table(engine, hull_no)
        schema_name = sanitize_schema_name(hull_no)
        for device_name, protocol in device_protocol_map.items():
            with engine.connect() as conn:
                # 중복 체크: 같은 device_name이 이미 존재하는지 확인
                result = conn.execute(
                    text(f'SELECT * FROM "{schema_name}".device WHERE device_name = :device_name'),
                    {"device_name": device_name}
                )
                if result.first():
                    # 이미 존재하면 건너뛰기 (또는 프로토콜 업데이트 가능)
                    logger.info(f"Device '{device_name}'가 이미 존재합니다. 건너뜁니다.")
                    continue
                
                # 존재하지 않으면 새로 추가
                conn.execute(
                    device_table.insert().values(
                        device_name=device_name,
                        protocol=protocol.upper(),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
                conn.commit()
        
        # IOLIST 테이블 생성 및 데이터 저장
        iolist_table = create_iolist_table(engine, hull_no, date_key)
        for item_data in parsed_items:
            # 원본 데이터를 JSON으로 저장
            raw_data_json = json.dumps(item_data, ensure_ascii=False)
            
            # 호환성을 위한 필드 추출
            mqtt_tag = item_data.get("MQTT Tag", "")
            description = item_data.get("Description", "")
            data_type = item_data.get("Data type", "")
            remark = item_data.get("Remark", "")
            
            with engine.connect() as conn:
                conn.execute(
                    iolist_table.insert().values(
                        raw_data=raw_data_json,
                        io_no=mqtt_tag,
                        io_name=description or item_data.get("Measure", ""),
                        io_type=data_type,
                        description=description,
                        remarks=remark,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
                conn.commit()
        
        db.commit()
        db.refresh(header)
        
        logger.info(f"IOLIST 생성 완료: uuid={file_uuid}, hull_no={hull_no}, imo={imo}, date_key={date_key}, items={len(parsed_items)}, devices={len(device_protocol_map)}")
        return header
        
    finally:
        # 임시 파일 삭제
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def get_iolist_headers(
    db: Session,
    hull_no: Optional[str] = None,
    imo: Optional[str] = None,
    date_key: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[IOListHeader]:
    """IOLIST 헤더 목록 조회 (필터링 지원)"""
    query = db.query(IOListHeader)
    
    if hull_no:
        query = query.filter(IOListHeader.hull_no == hull_no)
    if imo:
        query = query.filter(IOListHeader.imo == imo)
    if date_key:
        query = query.filter(IOListHeader.date_key == date_key)
    
    return query.order_by(IOListHeader.created_at.desc()).offset(skip).limit(limit).all()


def get_iolist_header(db: Session, header_id: int) -> Optional[IOListHeader]:
    """IOLIST 헤더 조회"""
    return db.query(IOListHeader).filter(IOListHeader.id == header_id).first()


def get_iolist_items(
    db: Session, 
    header_id: int,
    show_duplicates: bool = False,
    show_missing_required: bool = False
) -> List[Dict[str, Any]]:
    """IOLIST 항목 목록 조회 (스키마 기반, 필터링 지원)"""
    # 헤더 정보 조회
    header = get_iolist_header(db, header_id)
    if not header:
        return []
    
    # 스키마 및 테이블 이름
    schema_name = sanitize_schema_name(header.hull_no)
    table_name = f"iolist_{header.date_key}"
    
    # 테이블 가져오기
    iolist_table = get_table(engine, header.hull_no, table_name)
    if iolist_table is None:
        return []
    
    # 데이터 조회
    with engine.connect() as conn:
        result = conn.execute(
            text(f'SELECT * FROM "{schema_name}"."{table_name}" ORDER BY id')
        )
        items = []
        for row in result:
            item_dict = dict(row._mapping)
            items.append(item_dict)
    
    if not show_duplicates and not show_missing_required:
        return items
    
    # 중복 및 필수 값 누락 체크
    from .excel_parser import generate_data_channel_id
    filtered_items = []
    data_channel_ids = {}
    descriptions = {}
    mqtt_tags = {}
    
    for item in items:
        # raw_data에서 원본 데이터 가져오기
        raw_data = json.loads(item.get("raw_data", "{}")) if item.get("raw_data") else {}
        data_channel_id = generate_data_channel_id(raw_data)
        description = raw_data.get("Description", "") or item.get("description", "") or ""
        mqtt_tag = raw_data.get("MQTT Tag", "") or item.get("io_no", "") or ""
        
        # 중복 체크
        is_duplicate = False
        if data_channel_id:
            if data_channel_id in data_channel_ids:
                is_duplicate = True
            else:
                data_channel_ids[data_channel_id] = []
            data_channel_ids[data_channel_id].append(item.get("id"))
        
        if description:
            if description in descriptions:
                is_duplicate = True
            else:
                descriptions[description] = []
            descriptions[description].append(item.get("id"))
        
        if mqtt_tag:
            if mqtt_tag in mqtt_tags:
                is_duplicate = True
            else:
                mqtt_tags[mqtt_tag] = []
            mqtt_tags[mqtt_tag].append(item.get("id"))
        
        # 필수 값 누락 체크
        has_missing_required = False
        for col in REQUIRED_VALUE_COLUMNS:
            value = raw_data.get(col)
            if not value or (isinstance(value, str) and not value.strip()):
                has_missing_required = True
                break
        
        # 필터링
        should_include = True
        if show_duplicates and not is_duplicate:
            should_include = False
        if show_missing_required and not has_missing_required:
            should_include = False
        
        if should_include:
            filtered_items.append(item)
    
    return filtered_items


def check_duplicates_and_missing(db: Session, header_id: int) -> Dict[str, Any]:
    """중복 및 필수 값 누락 체크 결과 반환 (스키마 기반)"""
    from .excel_parser import generate_data_channel_id
    
    # 헤더 정보 조회
    header = get_iolist_header(db, header_id)
    if not header:
        return {
            "duplicate_data_channel_ids": {},
            "duplicate_descriptions": {},
            "duplicate_mqtt_tags": {},
            "missing_required_values": []
        }
    
    # 스키마 및 테이블 이름
    schema_name = sanitize_schema_name(header.hull_no)
    table_name = f"iolist_{header.date_key}"
    
    # 데이터 조회
    items = get_iolist_items(db, header_id, show_duplicates=False, show_missing_required=False)
    
    data_channel_ids = {}
    descriptions = {}
    mqtt_tags = {}
    missing_required = []
    
    for item in items:
        # raw_data에서 원본 데이터 가져오기
        raw_data = json.loads(item.get("raw_data", "{}")) if item.get("raw_data") else {}
        
        # DataChannelId 생성
        data_channel_id = generate_data_channel_id(raw_data)
        
        description = raw_data.get("Description", "") or item.get("description", "") or ""
        mqtt_tag = raw_data.get("MQTT Tag", "") or item.get("io_no", "") or ""
        
        item_id = item.get("id")
        
        # DataChannelId 중복
        if data_channel_id:
            if data_channel_id not in data_channel_ids:
                data_channel_ids[data_channel_id] = []
            data_channel_ids[data_channel_id].append(item_id)
        
        # Description 중복
        if description:
            if description not in descriptions:
                descriptions[description] = []
            descriptions[description].append(item_id)
        
        # MQTT Tag 중복
        if mqtt_tag:
            if mqtt_tag not in mqtt_tags:
                mqtt_tags[mqtt_tag] = []
            mqtt_tags[mqtt_tag].append(item_id)
        
        # 필수 값 누락
        for col in REQUIRED_VALUE_COLUMNS:
            value = raw_data.get(col)
            if not value or (isinstance(value, str) and not value.strip()):
                missing_required.append({
                    "item_id": item_id,
                    "column": col,
                    "value": value
                })
                break
    
    # 중복만 필터링
    duplicate_data_channel_ids = {k: v for k, v in data_channel_ids.items() if len(v) > 1}
    duplicate_descriptions = {k: v for k, v in descriptions.items() if len(v) > 1}
    duplicate_mqtt_tags = {k: v for k, v in mqtt_tags.items() if len(v) > 1}
    
    return {
        "duplicate_data_channel_ids": duplicate_data_channel_ids,
        "duplicate_descriptions": duplicate_descriptions,
        "duplicate_mqtt_tags": duplicate_mqtt_tags,
        "missing_required_values": missing_required
    }


def create_iolist_item(db: Session, header_id: int, item: IOListItemCreate) -> Dict[str, Any]:
    """IOLIST 항목 생성 (스키마 기반)"""
    header = get_iolist_header(db, header_id)
    if not header:
        raise ValueError("헤더를 찾을 수 없습니다.")
    
    schema_name = sanitize_schema_name(header.hull_no)
    table_name = f"iolist_{header.date_key}"
    
    iolist_table = get_table(engine, header.hull_no, table_name)
    if iolist_table is None:
        raise ValueError(f"테이블을 찾을 수 없습니다: {schema_name}.{table_name}")
    
    item_data = item.model_dump(exclude_unset=True)
    item_data["created_at"] = datetime.utcnow()
    item_data["updated_at"] = datetime.utcnow()
    
    with engine.connect() as conn:
        result = conn.execute(iolist_table.insert().values(**item_data))
        conn.commit()
        # 생성된 ID 가져오기
        new_id = result.inserted_primary_key[0]
        item_data["id"] = new_id
    
    return item_data


def update_iolist_item(db: Session, item_id: int, item: IOListItemUpdate) -> Optional[Dict[str, Any]]:
    """IOLIST 항목 수정 (스키마 기반, raw_data 포함)"""
    # 헤더 정보는 item_id로 찾을 수 없으므로, header_id를 파라미터로 받아야 함
    # 일단 모든 헤더를 조회하여 해당 item_id를 가진 항목 찾기
    # 실제로는 프론트엔드에서 header_id를 함께 전달해야 함
    # 임시로 모든 스키마를 검색 (성능상 좋지 않지만 동작은 함)
    
    # 더 나은 방법: header_id를 파라미터로 추가
    # 지금은 간단하게 구현
    update_data = item.model_dump(exclude_unset=True)
    
    # raw_data가 업데이트되면 호환성 필드도 업데이트
    if "raw_data" in update_data and update_data["raw_data"]:
        try:
            raw_data = json.loads(update_data["raw_data"])
            # 호환성 필드 업데이트
            if "MQTT Tag" in raw_data:
                update_data["io_no"] = raw_data["MQTT Tag"]
            if "Description" in raw_data:
                update_data["description"] = raw_data["Description"]
                update_data["io_name"] = raw_data["Description"] or raw_data.get("Measure", "")
            if "Data type" in raw_data:
                update_data["io_type"] = raw_data["Data type"]
            if "Remark" in raw_data:
                update_data["remarks"] = raw_data["Remark"]
        except Exception as e:
            logger.warning(f"raw_data 파싱 실패: {e}")
    
    update_data["updated_at"] = datetime.utcnow()
    
    # 모든 헤더를 조회하여 해당 item_id가 있는 테이블 찾기
    headers = db.query(IOListHeader).all()
    for header in headers:
        schema_name = sanitize_schema_name(header.hull_no)
        table_name = f"iolist_{header.date_key}"
        
        iolist_table = get_table(engine, header.hull_no, table_name)
        if iolist_table is None:
            continue
        
        with engine.connect() as conn:
            result = conn.execute(
                iolist_table.update().where(iolist_table.c.id == item_id).values(**update_data)
            )
            conn.commit()
            if result.rowcount > 0:
                # 업데이트된 데이터 조회
                result = conn.execute(
                    iolist_table.select().where(iolist_table.c.id == item_id)
                )
                row = result.first()
                if row:
                    return dict(row._mapping)
    
    return None


def delete_iolist_item(db: Session, item_id: int) -> bool:
    """IOLIST 항목 삭제 (스키마 기반)"""
    # 모든 헤더를 조회하여 해당 item_id가 있는 테이블 찾기
    headers = db.query(IOListHeader).all()
    for header in headers:
        schema_name = sanitize_schema_name(header.hull_no)
        table_name = f"iolist_{header.date_key}"
        
        iolist_table = get_table(engine, header.hull_no, table_name)
        if iolist_table is None:
            continue
        
        with engine.connect() as conn:
            result = conn.execute(
                iolist_table.delete().where(iolist_table.c.id == item_id)
            )
            conn.commit()
            if result.rowcount > 0:
                return True
    
    return False


def delete_iolist_header(db: Session, header_id: int) -> bool:
    """IOLIST 헤더 및 모든 항목 삭제 (스키마 기반, 테이블 삭제 포함)"""
    from .schema_manager import drop_table
    
    header = db.query(IOListHeader).filter(IOListHeader.id == header_id).first()
    if not header:
        return False
    
    # 스키마 내 테이블 삭제
    table_name = f"iolist_{header.date_key}"
    try:
        drop_table(engine, header.hull_no, table_name)
        logger.info(f"테이블 삭제 완료: {header.hull_no}.{table_name}")
    except Exception as e:
        logger.warning(f"테이블 삭제 실패: {header.hull_no}.{table_name}, {e}")
    
    # UUID 기준 디렉토리 삭제
    if header.uuid:
        uuid_dir = Path("/data/uploads") / header.uuid
        if uuid_dir.exists():
            try:
                import shutil
                shutil.rmtree(uuid_dir)
                logger.info(f"UUID 디렉토리 삭제 완료: {uuid_dir}")
            except Exception as e:
                logger.warning(f"UUID 디렉토리 삭제 실패: {uuid_dir}, {e}")
    
    # 파일도 삭제 (이전 방식 호환)
    if os.path.exists(header.file_path):
        try:
            os.remove(header.file_path)
        except Exception as e:
            logger.warning(f"파일 삭제 실패: {header.file_path}, {e}")
    
    db.delete(header)
    db.commit()
    return True


def get_available_filters(db: Session) -> dict:
    """사용 가능한 필터 옵션 조회 (HullNO, IMO, 날짜 목록)"""
    hull_nos = db.query(IOListHeader.hull_no).distinct().order_by(IOListHeader.hull_no).all()
    imos = db.query(IOListHeader.imo).distinct().order_by(IOListHeader.imo).all()
    date_keys = db.query(IOListHeader.date_key).distinct().order_by(IOListHeader.date_key.desc()).all()
    
    return {
        "hull_nos": [row[0] for row in hull_nos],
        "imos": [row[0] for row in imos],
        "date_keys": [row[0] for row in date_keys]
    }


def generate_dp_file(db: Session, header_id: int) -> tuple[str, str]:
    """
    DP XML 파일 생성
    
    Args:
        db: Database session
        header_id: IOLIST 헤더 ID
    
    Returns:
        (xml_content, filename) 튜플
    """
    from .dp_generator import create_dp_xml
    from .schema_manager import get_table, sanitize_schema_name
    from sqlalchemy import text
    
    # 헤더 정보 조회
    header = get_iolist_header(db, header_id)
    if not header:
        raise ValueError("IOLIST를 찾을 수 없습니다.")
    
    # IOLIST 항목 조회
    items = get_iolist_items(db, header_id, show_duplicates=False, show_missing_required=False)
    
    # Device 정보 조회
    schema_name = sanitize_schema_name(header.hull_no)
    device_table = get_table(engine, header.hull_no, "device")
    devices = []
    if device_table is not None:
        with engine.connect() as conn:
            result = conn.execute(text(f'SELECT * FROM "{schema_name}".device ORDER BY id'))
            for row in result:
                devices.append(dict(row._mapping))
    
    # XML 생성
    xml_content = create_dp_xml(header.imo, items, devices)
    
    # 파일명 생성: DP_IMO9991862_20260126235247.xml
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"DP_{header.imo}_{timestamp}.xml"
    
    return xml_content, filename


def create_device(db: Session, header_id: int, device_name: str, protocol: str = "MQTT") -> Dict[str, Any]:
    """Device 생성 (스키마 기반)"""
    header = get_iolist_header(db, header_id)
    if not header:
        raise ValueError("IOLIST를 찾을 수 없습니다.")
    
    schema_name = sanitize_schema_name(header.hull_no)
    device_table = get_table(engine, header.hull_no, "device")
    if device_table is None:
        # Device 테이블이 없으면 생성
        device_table = create_device_table(engine, header.hull_no)
    
    # 중복 체크
    with engine.connect() as conn:
        result = conn.execute(
            text(f'SELECT * FROM "{schema_name}".device WHERE device_name = :device_name'),
            {"device_name": device_name}
        )
        if result.first():
            raise ValueError(f"Device '{device_name}'가 이미 존재합니다.")
    
    # Device 생성
    with engine.connect() as conn:
        result = conn.execute(
            device_table.insert().values(
                device_name=device_name,
                protocol=protocol.upper(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        conn.commit()
        new_id = result.inserted_primary_key[0]
    
    return {
        "id": new_id,
        "device_name": device_name,
        "protocol": protocol.upper(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


def update_device(db: Session, header_id: int, device_id: int, device_name: Optional[str] = None, protocol: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Device 수정 (스키마 기반)"""
    header = get_iolist_header(db, header_id)
    if not header:
        raise ValueError("IOLIST를 찾을 수 없습니다.")
    
    schema_name = sanitize_schema_name(header.hull_no)
    device_table = get_table(engine, header.hull_no, "device")
    if device_table is None:
        raise ValueError("Device 테이블을 찾을 수 없습니다.")
    
    update_data = {}
    if device_name is not None:
        # 중복 체크 (자기 자신 제외)
        with engine.connect() as conn:
            result = conn.execute(
                text(f'SELECT * FROM "{schema_name}".device WHERE device_name = :device_name AND id != :device_id'),
                {"device_name": device_name, "device_id": device_id}
            )
            if result.first():
                raise ValueError(f"Device '{device_name}'가 이미 존재합니다.")
        update_data["device_name"] = device_name
    
    if protocol is not None:
        update_data["protocol"] = protocol.upper()
    
    if not update_data:
        return None
    
    update_data["updated_at"] = datetime.utcnow()
    
    with engine.connect() as conn:
        result = conn.execute(
            device_table.update().where(device_table.c.id == device_id).values(**update_data)
        )
        conn.commit()
        if result.rowcount > 0:
            # 업데이트된 데이터 조회
            result = conn.execute(
                device_table.select().where(device_table.c.id == device_id)
            )
            row = result.first()
            if row:
                return dict(row._mapping)
    
    return None


def delete_device(db: Session, header_id: int, device_id: int) -> bool:
    """Device 삭제 (스키마 기반)"""
    header = get_iolist_header(db, header_id)
    if not header:
        return False
    
    schema_name = sanitize_schema_name(header.hull_no)
    device_table = get_table(engine, header.hull_no, "device")
    if device_table is None:
        return False
    
    with engine.connect() as conn:
        result = conn.execute(
            device_table.delete().where(device_table.c.id == device_id)
        )
        conn.commit()
        return result.rowcount > 0
