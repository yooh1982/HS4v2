import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger("dp-manager")


def parse_filename(filename: str) -> Optional[Tuple[str, str]]:
    """
    파일명에서 Hull NO와 IMO NO를 추출
    
    형식: H2567_IMO9991862_IOList_20260125.xlsx
    또는: H2567_IMO9991862_IOList.xlsx
    
    Returns:
        (hull_no, imo) 튜플 또는 None
    """
    if not filename:
        return None
    
    # 확장자 제거
    name_without_ext = filename.rsplit('.', 1)[0] if '.' in filename else filename
    
    # 패턴: H로 시작하는 숫자, IMO로 시작하는 숫자
    # 예: H2567_IMO9991862 또는 H2567_IMO9991862_IOList_20260125
    pattern = r'H(\d+).*?IMO(\d+)'
    match = re.search(pattern, name_without_ext, re.IGNORECASE)
    
    if match:
        hull_no = f"H{match.group(1)}"
        imo = f"IMO{match.group(2)}"
        logger.info(f"파일명에서 추출: hull_no={hull_no}, imo={imo}")
        return (hull_no, imo)
    
    logger.warning(f"파일명에서 Hull NO와 IMO NO를 추출할 수 없습니다: {filename}")
    return None
