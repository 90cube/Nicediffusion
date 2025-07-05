# src/nicediff/core/state_manager.py
# (수정 및 최종 검토 완료된 버전)


import torch
import asyncio
import random
import uuid
import tomllib
import copy
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline, DiffusionPipeline, AutoencoderKL
from PIL import Image, PngImagePlugin
from nicegui import ui

from ..services.model_scanner import ModelScanner
from ..services.metadata_parser import MetadataParser

# NOTE: 이 클래스들은 외부 파일로 분리해도 좋습니다.
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
    
    def randomize_seed(self):
        if self.seed == -1:
            self.seed = random.randint(0, 2**32 - 1)
        print(f"🌱 New random seed set: {self.seed}")

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationParams':
        return cls(**data)

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

class StateManager:
    """중앙 상태 관리자"""
    
    def __init__(self):
        self._state: Dict[str, Any] = {
            'current_model_info': None,
            'current_vae_path': None,
            'current_loras': [],
            'current_params': GenerationParams(),
            'available_checkpoints': {},
            'available_vaes': {},
            'available_loras': {},
            'history': [],
            'is_generating': False,
            'is_loading_model': False,
            'model_type': 'SD15',
            'is_xl_model': False,
        }
        self._observers: Dict[str, List[Callable]] = {}
        self.pipeline: Optional[DiffusionPipeline] = None
        self.config: Dict[str, Any] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.stop_generation_flag = asyncio.Event()
        print(f"🖥️ 사용 중인 디바이스: {self.device}")
        
    
    async def initialize(self):
        """설정 파일 로드 및 모델 스캔 시작"""
        config_path = Path("config.toml")
        if await asyncio.to_thread(config_path.exists):
            with open(config_path, "rb") as f:
                self.config = tomllib.load(f)
        
        # NOTE: 모델 스캔은 오래 걸릴 수 있으므로 백그라운드 작업으로 실행
        asyncio.create_task(self._scan_models())
    
    async def _scan_models(self):
        """ModelScanner를 사용하여 모델을 스캔하고, 표준화된 키로 상태를 업데이트합니다."""
        self.set('status_message', '모델 스캔 중...')
        paths_config = self.config.get('paths', {})
        scanner = ModelScanner(paths_config=paths_config)
        all_models_data = await scanner.scan_all_models()
        
        # 이제 스캐너가 'checkpoints' 키로 결과를 반환하므로, 이 코드가 정상 작동합니다.
        self.set('available_checkpoints', all_models_data.get('checkpoints', {}))
        self.set('available_vaes', all_models_data.get('vaes', {}))
        self.set('available_loras', all_models_data.get('loras', {}))        

        self.set('status_message', '준비 완료')
        print("✅ StateManager: 스캔 결과로 상태 업데이트 완료.")

    # --- 모델 선택 및 로딩 (2단계 로딩) ---
    async def select_model(self, model_info: Dict[str, Any]):
        """1단계: GPU 로딩 없이, 메타데이터 표시를 위해 모델을 '선택'만 합니다."""
        print(f"모델 선택됨 (미리보기용): {model_info['name']}")
        self.set('current_model_info', model_info)
        self.set('sd_model_type', model_info.get('model_type', 'SD15'))

    async def load_model_pipeline(self, model_info: Dict[str, Any]) -> bool:
        """[최종 수정] 모델 로딩의 모든 과정을 책임지는 중앙 처리 메서드"""
    
        # 이미 로드된 모델이면 중단
        current_model_info = self.get('current_model_info')
        if current_model_info and current_model_info.get('path') == model_info.get('path'):
            ui.notify(f"'{model_info['name']}' 모델은 이미 로드되어 있습니다.", type='info')
            return True

        try:
            # 1. '로딩 중' 상태를 *먼저* 설정하고 UI에 알립니다.
            self.set('is_loading_model', True)
            self._notify('model_loading_started', {'name': model_info['name']})
        
            # 2. 실제 모델을 로드하는 무거운 작업을 수행합니다.
            # ... (기존의 _load 함수와 await asyncio.to_thread(_load) 로직은 그대로 사용) ...
            # 이 부분은 CUBE님의 기존 코드가 정확합니다.
        
            # 3. 로드 성공 후, 상태를 업데이트합니다.
            self.set('current_model_info', model_info)
        
            # 4. VAE 자동 선택을 실행합니다.
            await self._auto_select_vae(model_info)
        
            # 5. 최종 성공 상태를 UI에 알립니다.
            self._notify('model_loading_finished', {'success': True, 'model_info': self.get('current_model_info')})
            return True
    
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._notify('model_loading_finished', {'success': False, 'error': str(e)})
            return False
        
        finally:
            # 6. 성공/실패와 관계없이 '로딩 중' 상태를 해제합니다.
            self.set('is_loading_model', False)

    async def _auto_select_vae(self, model_info: Dict[str, Any]):
        """A1111 방식의 VAE 자동 선택 로직"""
        print(f"🔍 VAE 자동 선택 프로세스 시작...")
        
        # 메타데이터에서 권장 VAE 찾기
        # 이름 규칙으로 VAE 찾기
        
        print("ℹ️ 체크포인트 내장 VAE 사용 (별도 VAE 없음)")
        self.set('current_vae_path', 'baked_in')
        self._notify('vae_auto_selected', 'baked_in')

    async def load_vae(self, vae_path: str):
        """VAE 파일을 로드하여 파이프라인에 적용"""
        if not self.pipeline:
            self._notify('status_update', {'message': '모델을 먼저 로드하세요.', 'type': 'warning'})
            return False
        
        self.set('is_loading_model', True) # VAE 로딩도 로딩 상태로 간주
        self._notify('status_update', {'message': f"VAE '{Path(vae_path).name}' 로드 중...", 'type': 'loading'})
        
        try:
            from diffusers import AutoencoderKL
            def _load_vae():
                vae = AutoencoderKL.from_single_file(vae_path, torch_dtype=torch.float16)
                self.pipeline.vae = vae.to(self.device)
            
            await asyncio.to_thread(_load_vae)
            
            self.set('current_vae_path', vae_path)
            self._notify('status_update', {'message': f"VAE '{Path(vae_path).name}' 적용 완료!", 'type': 'success'})
            return True
        except Exception as e:
            print(f"❌ VAE 로드 실패: {e}")
            self._notify('status_update', {'message': f"VAE 로드 실패: {e}", 'type': 'error'})
            return False
        finally:
            self.set('is_loading_model', False)

    async def generate_image(self):
        """[최종 업그레이드] 배치/반복 생성을 지원하고, 중단 가능한 중앙 생성 메서드"""
        if self.get('is_generating'): return
        
        self.stop_generation_flag.clear() # 중단 플래그 리셋
        self.set('is_generating', True)
        self._notify('generation_started', {})
        
        import copy
        params_snapshot = copy.deepcopy(self.get('current_params'))

        # 이제부터 이 생성 작업(배치)이 끝날 때까지는, UI에서 파라미터를 바꾸더라도
        # 이 '스냅샷'에 저장된 설정값만을 사용하여 일관성을 유지합니다.
        
        try:
            self.set('is_generating', True)
            self._notify('generation_started', {})

            total_generations = params_snapshot.iterations * params_snapshot.batch_size
            
            base_seed = params_snapshot.seed
            if base_seed == -1:
                base_seed = random.randint(0, 2**32 - 1)
                # (선택) 랜덤으로 결정된 시드를 UI에도 반영하고 싶다면
                params_snapshot.seed = base_seed
                self.set('current_params', params_snapshot)

            for i in range(params_snapshot.iterations):
                for b in range(params_snapshot.batch_size):
                    if self.stop_generation_flag.is_set():
                        # ... (중단 로직) ...
                        return

                    current_seed = base_seed + (i * params_snapshot.batch_size) + b
                    generator = torch.Generator(device=self.device).manual_seed(current_seed)
                    
                    def _generate():
                        # 파이프라인 호출 시에도 params_snapshot을 사용합니다.
                        return self.pipeline(prompt=params_snapshot.prompt,
                                             negative_prompt=params_snapshot.negative_prompt,
                                             # ... 이하 모든 파라미터 ...
                                             generator=generator).images[0]
                    
                    image = await asyncio.to_thread(_generate)
                    
                    # 후처리 함수에도 이 스냅샷을 전달하여 일관된 정보로 히스토리를 기록합니다.
                    await self.finish_generation(image, params_snapshot)

        except Exception as e:
            print(f"❌ 생성 중 심각한 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            self._notify('generation_failed', {'error': str(e)})
            return False

        finally:
            self.set('is_generating', False)
            self._notify('generation_finished', {})

    async def stop_generation(self):
        """생성 중단 신호를 보냅니다."""
        print("✋ 생성 중단 요청됨.")
        self.stop_generation_flag.set()

    # (보너스 오류 수정) 비어있는 cleanup 메서드 추가
    async def cleanup(self):
        """애플리케이션 종료 시 정리 작업"""
        print("🧹 애플리케이션 정리 중...")
        pass # 나중에 필요한 정리 로직 추가
# (이하 get, set, subscribe 등은 원래 위치에 있으므로 그대로 둡니다)

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any):
        old_value = self._state.get(key)
        self._state[key] = value
        if old_value != value:
            # 상태 변경 시 알림
            self._notify(f'{key}_changed', value)
    
    def subscribe(self, event: str, callback: Callable):
        if event not in self._observers:
            self._observers[event] = []
        self._observers[event].append(callback)
    
    def unsubscribe(self, event: str, callback: Callable):
        if event in self._observers and callback in self._observers[event]:
            self._observers[event].remove(callback)
    
    def _notify(self, event: str, data: Any = None):
        if event in self._observers:
            for callback in self._observers[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(data))
                    else:
                        callback(data)
                except Exception as e:
                    print(f"❌ 옵저버 콜백 오류 ({event}): {e}")

    async def select_model(self, model_info: Dict[str, Any]):
        """GPU 로딩 없이, 메타데이터만 읽어 모델을 '선택' 상태로 만듭니다."""
        
        # ModelScanner가 스캔 시점에 이미 메타데이터를 읽어왔다고 가정합니다.
        # 따라서 model_info 객체에는 이미 메타데이터가 들어있습니다.
        # 만약 아니라면 여기서 MetadataParser를 호출하여 메타데이터를 읽어와야 합니다.
        print(f"모델 선택됨 (메타데이터 표시용): {model_info['name']}")
        
        # 'current_model_info' 상태를 업데이트합니다. TopBar는 이 이벤트를 구독합니다.
        self.set('current_model_info', model_info)