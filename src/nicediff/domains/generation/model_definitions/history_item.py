"""
히스토리 아이템 도메인 모델
UI나 Services에 의존하지 않는 순수한 비즈니스 로직
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .generation_params import GenerationParams


@dataclass
class HistoryItem:
    """히스토리 아이템"""
    image_path: str
    thumbnail_path: str
    params: GenerationParams
    model: str

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    vae: Optional[str] = None
    loras: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'id': self.id,
            'image_path': self.image_path,
            'thumbnail_path': self.thumbnail_path,
            'params': self.params.to_dict(),
            'model': self.model,
            'timestamp': self.timestamp.isoformat(),
            'vae': self.vae,
            'loras': self.loras
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoryItem':
        """딕셔너리에서 생성"""
        # timestamp를 datetime으로 변환
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        
        # params를 GenerationParams로 변환
        if isinstance(data.get('params'), dict):
            data['params'] = GenerationParams.from_dict(data['params'])
        
        return cls(**data) 