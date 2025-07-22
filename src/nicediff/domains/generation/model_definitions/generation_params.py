from ....core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)
"""
생성 파라미터 도메인 모델
UI나 Services에 의존하지 않는 순수한 비즈니스 로직
"""

import random
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class GenerationParams:
    """생성 파라미터 데이터 클래스"""
    prompt: str = ""
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    steps: int = 20
    cfg_scale: float = 7.0
    seed: int = -1
    sampler: str = "dpmpp_2m"
    scheduler: str = "karras"
    batch_size: int = 1
    iterations: int = 1
    clip_skip: int = 1  # CLIP Skip 추가
    strength: float = 0.8  # i2i 모드용 Strength (Denoise) 값
    size_match_enabled: bool = False  # 크기 일치 토글 (img2img 모드용)
    
    def reset_to_defaults(self, model_type: str = 'SD15'):
        """모델 타입에 따라 기본값으로 리셋"""
        if model_type == 'SDXL':
            self.width = 1024
            self.height = 1024
            self.steps = 28
            self.cfg_scale = 7.0
        else:
            # SD15 기본값 (사용자가 직접 조정)
            self.width = 512
            self.height = 512
            self.steps = 20
            self.cfg_scale = 7.0
            self.scheduler = "karras"
    
    def randomize_seed(self):
        """시드를 랜덤으로 설정"""
        if self.seed == -1:
            self.seed = random.randint(0, 2**32 - 1)
        info(f"🌱 New random seed set: {self.seed}")

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return self.__dict__.copy()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationParams':
        """딕셔너리에서 생성"""
        return cls(**data) 