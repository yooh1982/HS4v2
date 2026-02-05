from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class IOListItemBase(BaseModel):
    io_no: Optional[str] = None
    io_name: Optional[str] = None
    io_type: Optional[str] = None
    description: Optional[str] = None
    remarks: Optional[str] = None
    raw_data: Optional[str] = None  # 파일 구조 그대로 저장된 원본 데이터


class IOListItemCreate(IOListItemBase):
    pass


class IOListItemUpdate(IOListItemBase):
    pass


class IOListItemResponse(IOListItemBase):
    id: int
    header_id: int
    created_at: datetime
    updated_at: datetime
    data_channel_id: Optional[str] = None
    is_duplicate_data_channel_id: bool = False
    is_duplicate_description: bool = False
    is_duplicate_mqtt_tag: bool = False
    has_missing_required: bool = False

    class Config:
        from_attributes = True


class IOListHeaderBase(BaseModel):
    uuid: str
    hull_no: str
    imo: str
    date_key: str
    file_name: str


class IOListHeaderCreate(IOListHeaderBase):
    pass


class IOListHeaderResponse(IOListHeaderBase):
    id: int
    file_path: str
    created_at: datetime
    updated_at: datetime
    items: List[IOListItemResponse] = []

    class Config:
        from_attributes = True


class IOListHeaderListResponse(BaseModel):
    id: int
    uuid: str
    hull_no: str
    imo: str
    date_key: str
    file_name: str
    created_at: datetime
    updated_at: datetime
    item_count: int = 0

    class Config:
        from_attributes = True


class DeviceCreate(BaseModel):
    device_name: str
    protocol: str = "MQTT"  # MQTT, NMEA, OPCUA, OPCDA, MODBUS


class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    protocol: Optional[str] = None


class DeviceResponse(BaseModel):
    id: int
    header_id: int
    device_name: str
    protocol: str  # MQTT, NMEA, OPCUA, OPCDA, MODBUS
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
