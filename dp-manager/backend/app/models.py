from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class IOListHeader(Base):
    """IOLIST 헤더 정보 (HullNO, IMO, 날짜 기준, UUID 기준)"""
    __tablename__ = "iolist_headers"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), nullable=False, unique=True, index=True)  # 파일별 UUID
    hull_no = Column(String(50), nullable=False, index=True)
    imo = Column(String(20), nullable=False, index=True)
    date_key = Column(String(20), nullable=False, index=True)  # YYYYMMDD_HHMMSS
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 관계
    items = relationship("IOListItem", back_populates="header", cascade="all, delete-orphan")
    devices = relationship("Device", back_populates="header", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_hull_imo_date", "hull_no", "imo", "date_key"),
        Index("idx_uuid", "uuid"),
    )


class IOListItem(Base):
    """IOLIST 항목 데이터 (파일 구조 그대로 저장)"""
    __tablename__ = "iolist_items"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("iolist_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 파일의 원본 데이터를 JSON으로 저장 (파일 구조 그대로)
    raw_data = Column(Text, nullable=False)  # 엑셀 파일의 원본 행 데이터 (JSON)
    
    # 호환성을 위한 필드 (raw_data에서 추출)
    io_no = Column(String(50), nullable=True)  # MQTT Tag
    io_name = Column(String(255), nullable=True)  # Description 또는 Measure
    io_type = Column(String(50), nullable=True)  # Data type
    description = Column(Text, nullable=True)  # Description
    remarks = Column(Text, nullable=True)  # Remark
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 관계
    header = relationship("IOListHeader", back_populates="items")


class Device(Base):
    """Device별 Protocol 정보"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    header_id = Column(Integer, ForeignKey("iolist_headers.id", ondelete="CASCADE"), nullable=False, index=True)
    device_name = Column(String(100), nullable=False)  # Device 이름
    protocol = Column(String(20), nullable=False, default="MQTT")  # Protocol: MQTT, NMEA, OPCUA, OPCDA, MODBUS
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 관계
    header = relationship("IOListHeader", back_populates="devices")

    __table_args__ = (
        Index("idx_header_device", "header_id", "device_name"),
    )
