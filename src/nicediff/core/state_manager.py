# src/nicediff/core/state_manager.py
# 완전히 새로 생성할 파일 - 기존 파일을 삭제하고 이 내용으로 새로 만드세요

import torch
import asyncio
import random
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from diffusers import StableDiffusionPipeline, DiffusionPipeline
from PIL import Image, PngImagePlugin

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
    """중앙 상태 관리자"""
    
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
            print(f"'{model_info['name']}' 모델은 이미 로드되어 있습니다.")
            return False

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
            
            self.set('current_model', model_info.get('filename'))
            self.set('is_generating', False)
            self._notify('status_update', {'message': '로드 완료!', 'type': 'success', 'icon': 'check_circle'})
            self._notify('model_loaded', model_info)
            return True
        except Exception as e:
            print(f"❌ 파이프라인 로드 오류: {e}")
            self.pipeline = None
            self.set('current_model', None)
            self.set('is_generating', False)
            self._notify('status_update', {'message': f'로드 실패: {e}', 'type': 'error', 'icon': 'error'})
            self._notify('model_load_failed', str(e))
            return False

    async def generate_image(self) -> bool:
        """이미지 생성 실행"""
        if not self.pipeline:
            print("❌ 파이프라인이 로드되지 않음")
            self._notify('generation_failed', {'error': '모델이 로드되지 않았습니다'})
            return False
        
        if self.get('is_generating'):
            print("⚠️ 이미 생성 중")
            self._notify('generation_failed', {'error': '이미 생성 중입니다'})
            return False
        
        try:
            self.set('is_generating', True)
            self._notify('generation_started', {})
            print("🚀 이미지 생성 시작")
            
            params = self.get('current_params')
            
            # 샘플러/스케줄러 설정 적용
            from ..services.sampler_mapper import SamplerMapper
            scheduler = SamplerMapper.get_scheduler(params.sampler, params.scheduler, self.pipeline)
            self.pipeline.scheduler = scheduler
            print(f"📅 스케줄러 설정: {params.sampler} with {params.scheduler}")
            
            if params.seed < 0:
                params.seed = random.randint(0, 2**32 - 1)
                print(f"🎲 랜덤 시드 생성: {params.seed}")
            
            generator = torch.Generator(device=self.device).manual_seed(params.seed)
            
            step_count = 0
            def progress_callback(step, timestep, latents):
                nonlocal step_count
                step_count = step
                progress = step / params.steps
                print(f"📈 생성 진행: {step}/{params.steps} ({progress*100:.1f}%)")
                self._notify('generation_progress', {
                    'progress': progress,
                    'step': step,
                    'total_steps': params.steps
                })
            
            print(f"🎨 생성 파라미터:")
            print(f"   프롬프트: {params.prompt[:100]}...")
            print(f"   크기: {params.width}x{params.height}")
            print(f"   스텝: {params.steps}, CFG: {params.cfg_scale}")
            print(f"   샘플러: {params.sampler}, 스케줄러: {params.scheduler}")
            
            def _generate():
                return self.pipeline(
                    prompt=params.prompt,
                    negative_prompt=params.negative_prompt if params.negative_prompt else "",
                    width=params.width,
                    height=params.height,
                    num_inference_steps=params.steps,
                    guidance_scale=params.cfg_scale,
                    generator=generator,
                    callback=progress_callback,
                    callback_steps=1
                ).images[0]
            
            image = await asyncio.to_thread(_generate)
            
            output_path = await self.save_generated_image(image, params)
            
            self.set('is_generating', False)
            print(f"✅ 이미지 생성 완료: {output_path}")
            self._notify('image_generated', {'path': str(output_path)})
            
            return True
            
        except Exception as e:
            print(f"❌ 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            
            self.set('is_generating', False)
            self._notify('generation_failed', {'error': str(e)})
            return False

    async def save_generated_image(self, image: Image.Image, params: GenerationParams) -> Path:
        """생성된 이미지를 메타데이터와 함께 저장"""
        
        output_dir = Path(self.config.get('paths', {}).get('outputs', 'outputs'))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"nicediff_{timestamp}_{params.seed}.png"
        image_path = output_dir / filename
        
        metadata = self.create_png_metadata(params)
        
        def _save():
            image.save(image_path, "PNG", pnginfo=metadata)
        
        await asyncio.to_thread(_save)
        
        return image_path

    def create_png_metadata(self, params: GenerationParams) -> PngImagePlugin.PngInfo:
        """AUTOMATIC1111 호환 PNG 메타데이터 생성"""
        metadata = PngImagePlugin.PngInfo()
        
        param_string = (
            f"{params.prompt}\n"
            f"Negative prompt: {params.negative_prompt}\n"
            f"Steps: {params.steps}, Sampler: {params.sampler}, "
            f"Scheduler: {params.scheduler}, CFG scale: {params.cfg_scale}, "
            f"Seed: {params.seed}, Size: {params.width}x{params.height}, "
            f"Model: {self.get('current_model', 'Unknown')}"
        )
        
        metadata.add_text("parameters", param_string)
        metadata.add_text("Software", "Nicediff")
        metadata.add_text("Generator", "Nicediff v1.0")
        
        return metadata
            
    def get(self, key: str, default: Any = None) -> Any:
        """상태 값 가져오기"""
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any):
        """상태 값 설정"""
        old_value = self._state.get(key)
        self._state[key] = value
        
        if old_value != value:
            self._notify(f'{key}_changed', value)
    
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