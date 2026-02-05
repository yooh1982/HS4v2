"""
DP 파일 생성 모듈
IOLIST 데이터를 기반으로 DP XML 파일 생성
"""
import logging
import json
from datetime import datetime
from typing import List, Dict, Any
from xml.etree import ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger("dp-manager")


def prettify_xml(elem):
    """XML을 보기 좋게 포맷팅"""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def create_dp_xml(
    imo: str,
    items: List[Dict[str, Any]],
    devices: List[Dict[str, Any]]
) -> str:
    """
    IOLIST 데이터를 기반으로 DP XML 파일 생성
    
    Args:
        imo: IMO Number
        items: IOLIST 항목 리스트
        devices: Device 리스트
    
    Returns:
        XML 문자열
    """
    # 현재 시간 (UTC)
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    date_created = timestamp
    
    # 루트 요소 생성
    root = ET.Element(
        "sdd:Package",
        {
            "xmlns:device": "urn:BLUEONE:DEVICE_DATA_MAP",
            "xmlns:dmd": "urn:BLUEONE:DATA_MODEL_DEFINITION",
            "xmlns:sdd": "urn:ISO19848:SHIP_DATA_DEFINITION",
            "xmlns:tn": "urn:BLUEONE_TAGNATIVE_NAME_OBJECT",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns:jm": "urn:BLUEONE_JSMEA_NAME_OBJECT",
            "xsi:schemaLocation": "urn:BLUEONE_JSMEA_NAME_OBJECT jsmea_name_object.xsd urn:ISO19848:SHIP_DATA_DEFINITION ship_data_definition.xsd urn:BLUEONE:DATA_MODEL_DEFINITION blueone_data_model_definition.xsd urn:BLUEONE:DEVICE_DATA_MAP blueone_device_data_map.xsd urn:BLUEONE_JSMEA_NAME_OBJECT jsmea_name_object.xsd urn:BLUEONE_TAGNATIVE_NAME_OBJECT tagnative_name_object.xsd"
        }
    )
    
    # Header 섹션
    header = ET.SubElement(root, "sdd:Header")
    ET.SubElement(header, "sdd:ShipID").text = imo
    data_channel_list_id = ET.SubElement(header, "sdd:DataChannelListID")
    ET.SubElement(data_channel_list_id, "sdd:ID").text = imo
    ET.SubElement(data_channel_list_id, "sdd:TimeStamp").text = timestamp
    ET.SubElement(header, "sdd:Author").text = "Uangel"
    ET.SubElement(header, "sdd:DateCreated").text = date_created
    ET.SubElement(header, "dmd:Name").text = "hs4_profile"
    ET.SubElement(header, "dmd:Version").text = "1.0"
    
    # DataChannelList 섹션
    data_channel_list = ET.SubElement(root, "sdd:DataChannelList")
    
    # Device 맵 생성 (빠른 조회를 위해)
    device_map = {d.get("device_name"): d for d in devices}
    
    # 각 IOLIST 항목을 DataChannel로 변환
    for item in items:
        try:
            # raw_data 파싱
            raw_data = json.loads(item.get("raw_data", "{}")) if item.get("raw_data") else {}
            
            resource = raw_data.get("Resource", "")
            if not resource:
                continue
            
            # Device 정보 확인
            device_info = device_map.get(resource, {})
            protocol = device_info.get("protocol", "MQTT").upper()
            
            # 프로토콜별 처리
            if protocol not in ["MQTT", "NMEA"]:
                logger.warning(f"프로토콜 {protocol}은 아직 지원하지 않습니다. 항목 건너뜀: {item.get('id')}")
                continue
            
            # DataChannel 생성
            data_channel = ET.SubElement(data_channel_list, "sdd:DataChannel")
            
            # DataChannelID
            data_channel_id = ET.SubElement(data_channel, "sdd:DataChannelID")
            
            # 프로토콜별 LocalID 및 NamingRule 처리
            if protocol == "NMEA":
                # NMEA: /blueone_tagnative/{Device}/{InterfaceID}/{OriginTag} 형식
                interface_id = raw_data.get("InterfaceID", resource)  # InterfaceID가 없으면 Resource 사용
                origin_tag = raw_data.get("OriginTag", raw_data.get("NMEA Tag", ""))
                if not origin_tag:
                    logger.warning(f"NMEA OriginTag가 없습니다. 항목 건너뜀: {item.get('id')}")
                    continue
                local_id = f"/blueone_tagnative/{resource}/{interface_id}/{origin_tag}"
                naming_rule = "blueone_tagnative"
            else:  # MQTT
                # MQTT: 기존 로직 사용
                local_id = item.get("data_channel_id", "")
                if not local_id:
                    from .excel_parser import generate_data_channel_id
                    local_id = generate_data_channel_id(raw_data)
                naming_rule = raw_data.get("RuleNaming", "hs4sd_v1")
            
            ET.SubElement(data_channel_id, "sdd:LocalID").text = local_id
            
            # NameObject (NMEA의 경우에만 추가)
            if protocol == "NMEA" or naming_rule != "hs4sd_v1":
                name_object = ET.SubElement(data_channel_id, "sdd:NameObject")
                ET.SubElement(name_object, "sdd:NamingRule").text = naming_rule
            
            # Property
            property_elem = ET.SubElement(data_channel, "sdd:Property")
            
            # Measure에 따라 타입 결정 (기존 코드 로직 반영)
            measure = raw_data.get("Measure", "").lower() if raw_data.get("Measure") else ""
            is_alarm = measure.startswith("alarm")  # "alarm"으로 시작하는 경우
            is_status = measure in ["status", "run", "use"]  # status, run, use인 경우
            
            # DataChannelType
            data_channel_type = ET.SubElement(property_elem, "sdd:DataChannelType")
            if is_alarm:
                # Alarm인 경우: Type만 "Alert", UpdateCycle과 CalculationPeriod 없음
                ET.SubElement(data_channel_type, "sdd:Type").text = "Alert"
            elif is_status:
                # Status인 경우: Type만 "Status", UpdateCycle과 CalculationPeriod 없음
                ET.SubElement(data_channel_type, "sdd:Type").text = "Status"
            else:
                # 일반 Data인 경우: Type은 "Inst", UpdateCycle과 CalculationPeriod 포함
                ET.SubElement(data_channel_type, "sdd:Type").text = "Inst"
                ET.SubElement(data_channel_type, "sdd:UpdateCycle").text = "15"
                ET.SubElement(data_channel_type, "sdd:CalculationPeriod").text = "3600"
            
            # Format
            format_elem = ET.SubElement(property_elem, "sdd:Format")
            if is_alarm:
                # Alarm인 경우: Type은 "Alert"
                ET.SubElement(format_elem, "sdd:Type").text = "Alert"
            elif is_status:
                # Status인 경우: Type은 "Status" (기존 코드 로직)
                ET.SubElement(format_elem, "sdd:Type").text = "Status"
            else:
                # 일반 Data인 경우: Data type에 따라 결정 (기존 코드 로직 반영)
                format_type_str = raw_data.get("Data type", raw_data.get("format_type", "DECIMAL"))
                format_type_upper = format_type_str.upper() if format_type_str else "DECIMAL"
                
                # 기존 코드의 format_type 매핑 로직 반영
                if format_type_upper in ["FLOAT", "FLOAT"]:
                    format_type = "Decimal"
                elif format_type_upper in ["INT"]:
                    format_type = "Integer"  # 기존 코드는 "Integer" 사용
                elif format_type_upper in ["STRING"]:
                    format_type = "String"
                elif format_type_upper in ["BOOL", "DIG", "BOOLEAN", "BOOLEAN"]:
                    format_type = "Boolean"  # 기존 코드는 "Boolean" 사용
                else:
                    format_type = "Decimal"
                
                # NMEA의 경우 예시에서 "Inst"로 되어 있지만, 일반적으로는 Data type에 따라 결정
                if protocol == "NMEA" and format_type == "String":
                    # NMEA String의 경우 예시에서 "String"으로 되어 있음
                    ET.SubElement(format_elem, "sdd:Type").text = "String"
                else:
                    ET.SubElement(format_elem, "sdd:Type").text = format_type
            
            # Range
            range_elem = ET.SubElement(property_elem, "sdd:Range")
            ET.SubElement(range_elem, "sdd:High")
            ET.SubElement(range_elem, "sdd:Low")
            
            # Unit
            unit_elem = ET.SubElement(property_elem, "sdd:Unit")
            ET.SubElement(unit_elem, "sdd:UnitSymbol")
            # Unit은 필요시 추가 (MQTT의 경우 Description에서 추출 가능)
            quantity_name = ""
            if protocol == "MQTT":
                # MQTT의 경우 Description에서 단위 추출 시도 (예: "millibar")
                description = raw_data.get("Description", "") or item.get("description", "")
                # 간단한 추출 로직 (필요시 개선)
                if "millibar" in description.lower():
                    quantity_name = "millibar"
            ET.SubElement(unit_elem, "sdd:QuantityName").text = quantity_name
            
            # AlarmThreshold
            alarm_threshold = ET.SubElement(property_elem, "dmd:AlarmThreshold")
            ET.SubElement(alarm_threshold, "dmd:LowMinor")
            ET.SubElement(alarm_threshold, "dmd:LowMajor")
            ET.SubElement(alarm_threshold, "dmd:HighMinor")
            ET.SubElement(alarm_threshold, "dmd:HighMajor")
            
            # ChannelType
            channel_type = ET.SubElement(property_elem, "dmd:ChannelType")
            if is_alarm:
                # Alarm인 경우: "Alarm"
                channel_type.text = "Alarm"
            elif protocol == "MQTT":
                # 일반 MQTT Data인 경우: "Data"
                channel_type.text = "Data"
            else:  # NMEA
                # NMEA 예시에서는 빈 값
                pass
            
            # Direction
            direction_elem = ET.SubElement(property_elem, "dmd:Direction")
            direction_elem.text = "RO"
            
            # InoutType (기존 코드 로직 반영: Alarm이고 DO가 아니면 DI)
            inout_type_elem = ET.SubElement(property_elem, "dmd:InoutType")
            if is_alarm:
                # Alarm인 경우: DO가 아니면 "DI" (기존 코드 로직)
                iotype = raw_data.get("IOType", raw_data.get("iotype", "DI"))
                if iotype.upper() != "DO":
                    inout_type_elem.text = "DI"
                else:
                    inout_type_elem.text = "DO"
            elif protocol == "MQTT":
                # 일반 MQTT Data인 경우: Excel의 IOType 또는 기본값 "AI"
                inout_type_elem.text = raw_data.get("IOType", raw_data.get("iotype", "AI"))
            else:  # NMEA
                # NMEA 예시에서는 빈 값
                pass
            
            # Scale
            scale_elem = ET.SubElement(property_elem, "dmd:Scale")
            scale = raw_data.get("Scale", raw_data.get("Calculation", "1"))
            try:
                scale_float = float(scale) if scale else 1.0
            except:
                scale_float = 1.0
            scale_elem.text = str(scale_float)
            
            # InstCode (NMEA의 경우 빈 값일 수 있음)
            if protocol == "MQTT":
                inst_code_elem = ET.SubElement(property_elem, "dmd:InstCode")
                inst_code_elem.text = raw_data.get("Inst Code", "Inst")
            else:  # NMEA
                inst_code_elem = ET.SubElement(property_elem, "dmd:InstCode")
                # NMEA 예시에서는 빈 값
            
            # Description
            description_elem = ET.SubElement(property_elem, "dmd:Description")
            description = raw_data.get("Description", "") or item.get("description", "")
            description_elem.text = description
            
            # DeviceProperty
            device_property = ET.SubElement(property_elem, "device:DeviceProperty")
            ET.SubElement(device_property, "device:ID").text = resource
            
            # InterfaceID
            interface_id = raw_data.get("InterfaceID", resource)
            ET.SubElement(device_property, "device:InterfaceID").text = interface_id
            
            # OriginTag
            if protocol == "MQTT":
                origin_tag = raw_data.get("MQTT Tag", "") or item.get("io_no", "")
            else:  # NMEA
                origin_tag = raw_data.get("OriginTag", raw_data.get("NMEA Tag", ""))
            ET.SubElement(device_property, "device:OriginTag").text = origin_tag
            ET.SubElement(device_property, "device:Tag")
            
            # DataSet (프로토콜별)
            data_set = ET.SubElement(device_property, "device:DataSet")
            if protocol == "MQTT":
                # MQTT
                mqtt_elem = ET.SubElement(data_set, "device:MQTT")
                mqtt_elem.set("name", origin_tag)
                mqtt_elem.set("maximumLength", raw_data.get("Maximum Length", ""))
                mqtt_elem.set("description", description)
            elif protocol == "NMEA":
                # NMEA0183
                nmea_elem = ET.SubElement(data_set, "device:NMEA0183")
                # OriginTag에서 talker와 sentence 추출 (예: "FAFIR/alarm_status" -> talker="FA", sentence="FIR")
                # 또는 Excel에서 별도 컬럼으로 제공
                talker = raw_data.get("NMEA Talker", "")
                sentence = raw_data.get("NMEA Sentence", "")
                pos = raw_data.get("NMEA Position", raw_data.get("NMEA Pos", "1"))
                
                # OriginTag에서 파싱 시도 (형식: "FAFIR/alarm_status" 또는 "FA/FIR/alarm_status")
                if not talker or not sentence:
                    parts = origin_tag.split("/")
                    if len(parts) >= 2:
                        # "FAFIR" 형식인 경우
                        if len(parts[0]) >= 2:
                            talker = parts[0][:2]  # "FA"
                            sentence = parts[0][2:] if len(parts[0]) > 2 else parts[1] if len(parts) > 1 else ""
                        # "FA/FIR" 형식인 경우
                        elif len(parts) >= 2:
                            talker = parts[0]
                            sentence = parts[1]
                
                nmea_elem.set("talker", talker)
                nmea_elem.set("sentence", sentence)
                nmea_elem.set("pos", str(pos))
                nmea_elem.set("parsingFormat", raw_data.get("NMEA ParsingFormat", ""))
                nmea_elem.set("directionPos", raw_data.get("NMEA DirectionPos", ""))
                nmea_elem.set("isRepeatStart", raw_data.get("NMEA IsRepeatStart", ""))
                nmea_elem.set("isRepeatEnd", raw_data.get("NMEA IsRepeatEnd", ""))
                nmea_elem.set("description", description)
            
        except Exception as e:
            logger.error(f"DataChannel 생성 중 오류 (item_id={item.get('id')}): {e}", exc_info=True)
            continue
    
    # XML 문자열 생성
    xml_string = prettify_xml(root)
    return xml_string
