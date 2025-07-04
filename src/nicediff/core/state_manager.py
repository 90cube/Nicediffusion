"""
중앙 상태 관리자
모든 UI 컴포넌트와 파이프라인의 상태를 관리
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
from pathlib import Path
import torch

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
    
    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationParams':
        return cls(**data)

@dataclass
class HistoryItem:
    """히스토리 아이템"""
    id: str
    timestamp: datetime
    image_path: str
    thumbnail_path: str
    params: GenerationParams
    model: str
    vae: Optional[str] = None
    loras: List[Dict[str, Any]] = field(default_factory=list)

class StateManager:
    """중앙 상태 관리자"""
    
    def __init__(self):
        # 현재 상태
        self._state: Dict[str, Any] = {
            'current_model': None,
            'current_vae': None,
            'current_loras': [],
            'current_params': GenerationParams(),
            'available_models': {},
            'available_vaes': {},
            'available_loras': {},
            'history': [],
            'is_generating': False,
            'generation_progress': 0.0,
            'ui_mode': 'setup',  # 'setup' or 'generate'
            'sidebar_expanded': False,
            'sd_model': 'SD15',
        }
        
        # 옵저버 패턴을 위한 콜백 리스트
        self._observers: Dict[str, List[Callable]] = {}
        
        # 파이프라인
        self.pipeline = None
        
        # 디바이스 설정
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🖥️ 사용 중인 디바이스: {self.device}")
        
        if self.device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.backends.cudnn.benchmark = True
    
    async def initialize(self):
        """초기화 작업"""
        # 설정 파일 로드
        await self._load_config()
        
        # 모델 스캔 (별도 태스크로 실행)
        asyncio.create_task(self._scan_models())
    
    async def _load_config(self):
        """설정 파일 로드"""
        import tomllib
        
        config_path = Path("config.toml")
        if config_path.exists():
            with open(config_path, "rb") as f:
                self.config = tomllib.load(f)
        else:
            self.config = {}
    
    async def _scan_models(self):
        """모델 파일 스캔 (비동기)"""
        from ..services.model_scanner import ModelScanner
        
        scanner = ModelScanner(self.config.get('paths', {}))
        
        # 체크포인트 스캔
        self._state['available_models'] = await scanner.scan_checkpoints()
        self._notify('models_updated', self._state['available_models'])
        
        # VAE 스캔
        self._state['available_vaes'] = await scanner.scan_vaes()
        self._notify('vaes_updated', self._state['available_vaes'])
        
        # LoRA 스캔
        self._state['available_loras'] = await scanner.scan_loras()
        self._notify('loras_updated', self._state['available_loras'])
    
    def get(self, key: str, default: Any = None) -> Any:
        """상태 값 가져오기"""
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any):
        """상태 값 설정"""
        old_value = self._state.get(key)
        self._state[key] = value
        
        print(f"✅ StateManager SET: '{key}' changed to '{value}' (was: '{old_value}')")

        # 변경 알림
        if old_value != value:
            self._notify(f'{key}_changed', value)
    
    def update_batch(self, updates: Dict[str, Any]):
        """여러 상태 값을 한번에 업데이트"""
        for key, value in updates.items():
            self.set(key, value)
    
    def subscribe(self, event: str, callback: Callable):
        """이벤트 구독"""
        if event not in self._observers:
            self._observers[event] = []
        self._observers[event].append(callback)
    
    def unsubscribe(self, event: str, callback: Callable):
        """이벤트 구독 해제"""
        if event in self._observers:
            self._observers[event].remove(callback)
    
    def _notify(self, event: str, data: Any = None):
        """이벤트 발생 알림"""
        if event in self._observers:
            for callback in self._observers[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(data))
                    else:
                        callback(data)
                except Exception as e:
                    print(f"❌ 옵저버 콜백 오류: {e}")
    
    def add_to_history(self, image_path: str, thumbnail_path: str):
        """히스토리에 추가"""
        from uuid import uuid4
        
        history_item = HistoryItem(
            id=str(uuid4()),
            timestamp=datetime.now(),
            image_path=image_path,
            thumbnail_path=thumbnail_path,
            params=GenerationParams(**self._state['current_params'].to_dict()),
            model=self._state['current_model'],
            vae=self._state['current_vae'],
            loras=self._state['current_loras'].copy()
        )
        
        self._state['history'].insert(0, history_item)
        
        # 히스토리 제한
        limit = self.config.get('ui', {}).get('history_limit', 50)
        if len(self._state['history']) > limit:
            self._state['history'] = self._state['history'][:limit]
        
        self._notify('history_updated', self._state['history'])
    
    def restore_from_history(self, history_id: str):
        """히스토리에서 복원"""
        for item in self._state['history']:
            if item.id == history_id:
                # 파라미터 복원
                self._state['current_params'] = GenerationParams.from_dict(item.params.to_dict())
                self._state['current_model'] = item.model
                self._state['current_vae'] = item.vae
                self._state['current_loras'] = item.loras.copy()
                
                # 복원 이벤트 발생
                self._notify('state_restored', item)
                break
    
    async def cleanup(self):
        """정리 작업"""
        # 파이프라인 정리
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
        
        # GPU 메모리 정리
        if self.device == "cuda":
            torch.cuda.empty_cache()