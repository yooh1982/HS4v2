"""
스키마 및 동적 테이블 관리 모듈
Hull No별로 스키마를 분리하고, 파일별로 테이블을 생성
"""
import logging
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, DateTime, Text, Index
from sqlalchemy.orm import declarative_base
from typing import Optional

logger = logging.getLogger("dp-manager")


def sanitize_schema_name(name: str) -> str:
    """스키마/테이블 이름을 PostgreSQL에 안전한 형식으로 변환"""
    # Hull No에서 특수문자 제거 (예: H2567 -> H2567)
    return name.replace("-", "_").replace(".", "_").replace(" ", "_")


def create_schema(engine, hull_no: str) -> None:
    """Hull No별 스키마 생성"""
    schema_name = sanitize_schema_name(hull_no)
    
    with engine.begin() as conn:
        # IF NOT EXISTS를 사용하여 스키마 생성 (대소문자 구분을 위해 따옴표 사용)
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        logger.info(f"스키마 확인/생성 완료: {schema_name}")


def create_device_table(engine, hull_no: str) -> Table:
    """Device 테이블 생성 (Hull No 스키마 내)"""
    schema_name = sanitize_schema_name(hull_no)
    table_name = "device"
    
    # 스키마가 존재하는지 확인하고 없으면 생성 (IF NOT EXISTS 사용)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
    
    # 테이블이 이미 존재하는지 확인
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = '{schema_name}' 
                AND table_name = '{table_name}'
            )
        """))
        table_exists = result.scalar()
        
        if table_exists:
            logger.info(f"테이블이 이미 존재합니다: {schema_name}.{table_name}")
            # 기존 테이블 반환
            metadata = MetaData(schema=schema_name)
            table = Table(
                table_name,
                metadata,
                autoload_with=engine
            )
            return table
    
    metadata = MetaData(schema=schema_name)
    
    table = Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("device_name", String(100), nullable=False),
        Column("protocol", String(20), nullable=False, default="MQTT"),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    
    # 테이블 생성
    metadata.create_all(engine)
    
    # 인덱스 생성 (IF NOT EXISTS 사용)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_device_name ON "{schema_name}"."{table_name}" (device_name)'))
    
    logger.info(f"Device 테이블 생성 완료: {schema_name}.{table_name}")
    
    return table


def create_iolist_table(engine, hull_no: str, date_key: str) -> Table:
    """IOLIST 테이블 생성 (Hull No 스키마 내, 파일별)"""
    schema_name = sanitize_schema_name(hull_no)
    # 테이블 이름: iolist_20260127_025210 형식
    table_name = f"iolist_{date_key}"
    
    # 스키마가 존재하는지 확인하고 없으면 생성 (IF NOT EXISTS 사용)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
    
    # 테이블이 이미 존재하는지 확인
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = '{schema_name}' 
                AND table_name = '{table_name}'
            )
        """))
        table_exists = result.scalar()
        
        if table_exists:
            logger.info(f"테이블이 이미 존재합니다: {schema_name}.{table_name}")
            # 기존 테이블 반환
            metadata = MetaData(schema=schema_name)
            table = Table(
                table_name,
                metadata,
                autoload_with=engine
            )
            return table
    
    metadata = MetaData(schema=schema_name)
    
    table = Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("raw_data", Text, nullable=False),
        Column("io_no", String(50), nullable=True),
        Column("io_name", String(255), nullable=True),
        Column("io_type", String(50), nullable=True),
        Column("description", Text, nullable=True),
        Column("remarks", Text, nullable=True),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
    )
    
    # 테이블 생성
    metadata.create_all(engine)
    
    # 인덱스 생성 (IF NOT EXISTS 사용)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS idx_io_no ON "{schema_name}"."{table_name}" (io_no)'))
    
    logger.info(f"IOLIST 테이블 생성 완료: {schema_name}.{table_name}")
    
    return table


def get_table(engine, hull_no: str, table_name: str) -> Optional[Table]:
    """기존 테이블 가져오기"""
    schema_name = sanitize_schema_name(hull_no)
    metadata = MetaData()
    
    try:
        # 스키마를 명시적으로 지정하여 테이블 로드
        table = Table(
            table_name,
            metadata,
            autoload_with=engine,
            schema=schema_name
        )
        return table
    except Exception as e:
        logger.warning(f"테이블 로드 실패: {schema_name}.{table_name}, {e}")
        return None


def drop_table(engine, hull_no: str, table_name: str) -> None:
    """테이블 삭제"""
    schema_name = sanitize_schema_name(hull_no)
    
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {schema_name}.{table_name} CASCADE"))
        conn.commit()
    
    logger.info(f"테이블 삭제 완료: {schema_name}.{table_name}")
