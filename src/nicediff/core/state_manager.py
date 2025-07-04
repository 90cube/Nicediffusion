# 파일 경로: src/nicediff/core/state_manager.py (진짜 최종 완성본)

import torch
import asyncio
import random
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from diffusers import StableDiffusionPipeline, DiffusionPipeline

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
    
    def randomize_seed(self):
        """seed 값을 새로운 난수로 설정합니다."""
        new_seed = self.seed
        while new_seed == self.seed:
            new_seed = random.randint(0, 2**32 - 1)
        self.seed = new_seed
        print(f"🌱 New random seed set: {self.seed}")

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
    """중앙 상태 관리자 (모든 기능 포함 최종 버전)"""
    
    def __init__(self):
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
            'sd_model': 'SD15',
        }
        self._observers: Dict[str, List[Callable]] = {}
        self.pipeline: Optional[DiffusionPipeline] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🖥️ 사용 중인 디바이스: {self.device}")
    
    async def initialize(self):
        """초기화 작업"""
        import tomllib
        config_path = Path("config.toml")
        if config_path.exists():
            with open(config_path, "rb") as f:
                self.config = tomllib.load(f)
        else:
            self.config = {}
        asyncio.create_task(self._scan_models())
    
    async def _scan_models(self):
        """모델 파일 스캔"""
        from ..services.model_scanner import ModelScanner
        
        scanner = ModelScanner(self.config.get('paths', {}))
        
        self.set('available_models', await scanner.scan_checkpoints())
        self._notify('models_updated', self.get('available_models'))
        
        self.set('available_vaes', await scanner.scan_vaes())
        self._notify('vaes_updated', self.get('available_vaes'))
        
        self.set('available_loras', await scanner.scan_loras())
        self._notify('loras_updated', self.get('available_loras'))
    
    async def load_model_pipeline(self, model_info: Dict[str, Any]) -> bool:
        """선택된 모델 파일을 GPU에 로드하고 성공 여부를 반환합니다."""
        
        if self.get('current_model') == model_info.get('filename'):
            ui.notify(f"'{model_info['name']}' 모델은 이미 로드되어 있습니다.", type='info')
            return False # 로드를 진행하지 않았으므로 False 반환

        self.set('is_generating', True)
        self._notify('status_update', {'message': f"'{model_info['name']}' 로드 중...", 'type': 'loading', 'icon': 'sync'})
        try:
            if self.pipeline is not None:
                print("- [Pipeline] 기존 모델을 메모리에서 제거합니다...")
                del self.pipeline
                self.pipeline = None
                if self.device == "cuda":
                    torch.cuda.empty_cache()

            model_path = model_info['path']
            
            def _load():
                pipe = StableDiffusionPipeline.from_single_file(
                    model_path, 
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                    safety_checker=None
                )
                return pipe.to(self.device)

            self.pipeline = await asyncio.to_thread(_load)
            
            self.set('is_generating', False)
            self._notify('status_update', {'message': '로드 완료!', 'type': 'success', 'icon': 'check_circle'})
            self._notify('model_loaded', model_info) # 성공 시 모델 정보 전달
            return True
        except Exception as e:
            print(f"❌ 파이프라인 로드 오류: {e}")
            self.pipeline = None
            self.set('is_generating', False)
            self._notify('status_update', {'message': f'로드 실패: {e}', 'type': 'error', 'icon': 'error'})
            self._notify('model_load_failed', str(e))
            return False
            
    def get(self, key: str, default: Any = None) -> Any:
        """상태 값 가져오기"""
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any):
        """상태 값 설정"""
        old_value = self._state.get(key)
        self._state[key] = value
        
        # print(f"✅ StateManager SET: '{key}' changed to '{value}' (was: '{old_value}')")
        
        if old_value != value:
            self._notify(f'{key}_changed', value)
    
    # --- [수정] 누락되었던 subscribe, unsubscribe, _notify 함수 추가 ---
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
                    print(f"❌ 옵저버 콜백 오류 ({event}): {e}")

    async def cleanup(self):
        """앱 종료 시 정리 작업"""
        if self.pipeline:
            del self.pipeline
            self.pipeline = None
        if self.device == "cuda":
            torch.cuda.empty_cache()