# src/nicediff/core/state_manager.py
# (오류 수정 및 중복 제거 완료된 버전)

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
    """중앙 상태 관리자 (오류 수정 완료)"""
    
    def __init__(self):
        self._state: Dict[str, Any] = {
            'current_model_info': None,
            'current_vae_path': None,
            'current_loras': [],
            'current_params': GenerationParams(),
            'available_checkpoints': {},
            'available_vae': {},
            'available_loras': {},
            'history': [],
            'is_generating': False,
            'is_loading_model': False,
            'model_type': 'SD15',
            'is_xl_model': False,
            'sd_model': 'SD15',  # 추가: UI에서 사용하는 모델 타입
            'status_message': '준비 중...',
            'infinite_mode': False,  # 무한 생성 모드
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
        self.set('available_vae', all_models_data.get('vae', {}))
        self.set('available_loras', all_models_data.get('loras', {}))        

        self.set('status_message', '준비 완료')
        print("✅ StateManager: 스캔 결과로 상태 업데이트 완료.")

    # --- 모델 선택 및 로딩 ---
    async def select_model(self, model_info: Dict[str, Any]):
        """1단계: GPU 로딩 없이, 메타데이터 표시를 위해 모델을 '선택'만 합니다."""
        print(f"모델 선택됨 (미리보기용): {model_info['name']}")
        self.set('current_model_info', model_info)
        self.set('sd_model_type', model_info.get('model_type', 'SD15'))
        
        # 선택 이벤트 발생
        self._notify('model_selection_changed', model_info)

    async def load_model_pipeline(self, model_info: Dict[str, Any]) -> bool:
        """[최종 수정] 모델 로딩의 모든 과정을 책임지는 중앙 처리 메서드"""
    
        # 이미 로드된 모델이면 중단
        current_model_info = self.get('current_model_info')
        if (current_model_info and 
            current_model_info.get('path') == model_info.get('path') and 
            self.pipeline is not None):
            ui.notify(f"'{model_info['name']}' 모델은 이미 로드되어 있습니다.", type='info')
            return True

        try:
            self.set('is_loading_model', True)
            self._notify('model_loading_started', {'name': model_info['name']})
            await self._load_model_heavy_work(model_info)
            self.set('current_model_info', model_info)
            await self._auto_select_vae(model_info)
            
            # --- [확인 및 추가] ---
            # 모델 로딩 후 메타데이터를 적용하는 로직 호출
            self.apply_params_from_metadata(model_info)
            
            self._notify('model_loading_finished', {'success': True, 'model_info': model_info})
            ui.notify(f"'{model_info['name']}' 모델이 로드되었습니다.", type='success')
            return True
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"모델 로드 실패: {str(e)}"
            ui.notify(error_msg, type='negative')
            self._notify('model_loading_finished', {'success': False, 'error': str(e)})
            return False
        
        finally:
            # 6. 성공/실패와 관계없이 '로딩 중' 상태를 해제합니다.
            self.set('is_loading_model', False)

    async def _load_model_heavy_work(self, model_info: Dict[str, Any]):
        """실제 모델 로딩 작업 (Heavy I/O)"""
        def _load():
            model_path = model_info['path']
            model_type = model_info.get('model_type', 'SD15')
            
            # 모델 타입에 따라 적절한 파이프라인 선택
            if model_type == 'SDXL':
                from diffusers import StableDiffusionXLPipeline
                pipeline = StableDiffusionXLPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True
                )
            else:
                from diffusers import StableDiffusionPipeline
                pipeline = StableDiffusionPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True
                )
            
            # GPU로 이동
            pipeline = pipeline.to(self.device)
            
            # 메모리 효율성을 위한 설정
            if hasattr(pipeline, 'enable_model_cpu_offload'):
                pipeline.enable_model_cpu_offload()
            if hasattr(pipeline, 'enable_attention_slicing'):
                pipeline.enable_attention_slicing()
            
            return pipeline
        
        # 별도 스레드에서 로딩 수행
        self.pipeline = await asyncio.to_thread(_load)
        print(f"✅ 모델 로딩 완료: {model_info['name']}")

    async def _auto_select_vae(self, model_info: Dict[str, Any]):
        """A1111 방식의 VAE 자동 선택 로직"""
        print(f"🔍 VAE 자동 선택 프로세스 시작...")
        
        # 메타데이터에서 권장 VAE 찾기
        metadata = model_info.get('metadata', {})
        recommended_vae = metadata.get('recommended_vae')
        
        if recommended_vae:
            # 추천 VAE가 있으면 로드 시도
            available_vae = self.get('available_vae', {})
            for folder_vae in available_vae.values():
                for vae_info in folder_vae:
                    if recommended_vae.lower() in vae_info['name'].lower():
                        print(f"✅ 추천 VAE 발견: {vae_info['name']}")
                        await self.load_vae(vae_info['path'])
                        return
        
        # 기본적으로 내장 VAE 사용
        print("ℹ️ 체크포인트 내장 VAE 사용 (별도 VAE 없음)")
        self.set('current_vae_path', 'baked_in')
        self._notify('vae_auto_selected', 'baked_in')

    async def load_vae(self, vae_path: str):
        """VAE 파일을 로드하여 파이프라인에 적용"""
        if not self.pipeline:
            ui.notify('모델을 먼저 로드하세요.', type='warning')
            return False
        
        self.set('is_loading_model', True) # VAE 로딩도 로딩 상태로 간주
        ui.notify(f"VAE '{Path(vae_path).name}' 로드 중...", type='info')
        
        try:
            def _load_vae():
                vae = AutoencoderKL.from_single_file(vae_path, torch_dtype=torch.float16)
                self.pipeline.vae = vae.to(self.device)
            
            await asyncio.to_thread(_load_vae)
            
            self.set('current_vae_path', vae_path)
            ui.notify(f"VAE '{Path(vae_path).name}' 적용 완료!", type='success')
            return True
        except Exception as e:
            print(f"❌ VAE 로드 실패: {e}")
            ui.notify(f"VAE 로드 실패: {e}", type='negative')
            return False
        finally:
            self.set('is_loading_model', False)

    async def generate_image(self):
        """[최종 업그레이드] 배치/반복 생성을 지원하고, 중단 가능한 중앙 생성 메서드"""
        if self.get('is_generating'): 
            ui.notify('이미 생성 중입니다.', type='warning')
            return
        
        if not self.pipeline:
            ui.notify('모델을 먼저 로드해주세요.', type='warning')
            return
        
        self.stop_generation_flag.clear() # 중단 플래그 리셋
        self.set('is_generating', True)
        self._notify('generation_started', {})
        
        params_snapshot = copy.deepcopy(self.get('current_params'))
        try:
            # UI로부터 받은 값이 문자열일 수 있으므로, 정수로 강제 변환합니다.
            batch_size = int(params_snapshot.batch_size)
            iterations = int(params_snapshot.iterations)
        except (ValueError, TypeError):
            # 만약 값이 이상해서 정수로 변환할 수 없다면, 오류를 알리고 기본값으로 설정합니다.
            ui.notify('배치 사이즈와 반복 횟수는 숫자여야 합니다.', type='negative')
            batch_size = 1
            iterations = 1

        try:
            total_generations = params_snapshot.iterations * params_snapshot.batch_size
            
            base_seed = params_snapshot.seed
            if base_seed == -1:
                base_seed = random.randint(0, 2**32 - 1)
                params_snapshot.seed = base_seed
                self.set('current_params', params_snapshot)

            for i in range(params_snapshot.iterations):
                for b in range(params_snapshot.batch_size):
                    if self.stop_generation_flag.is_set():
                        ui.notify('생성이 중단되었습니다.', type='info')
                        return

                    current_seed = base_seed + (i * params_snapshot.batch_size) + b
                    generator = torch.Generator(device=self.device).manual_seed(current_seed)
                    
                    def _generate():
                        return self.pipeline(
                            prompt=params_snapshot.prompt,
                            negative_prompt=params_snapshot.negative_prompt,
                            width=params_snapshot.width,
                            height=params_snapshot.height,
                            num_inference_steps=params_snapshot.steps,
                            guidance_scale=params_snapshot.cfg_scale,
                            generator=generator
                        ).images[0]
                    
                    image = await asyncio.to_thread(_generate)
                    
                    # 후처리 및 저장
                    await self.finish_generation(image, params_snapshot, current_seed)

        except Exception as e:
            print(f"❌ 생성 중 심각한 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            self._notify('generation_failed', {'error': str(e)})
            ui.notify(f'생성 실패: {str(e)}', type='negative')
            return False

        finally:
            self.set('is_generating', False)
            self._notify('generation_finished', {})

    async def finish_generation(self, image: Image.Image, params: GenerationParams, seed: int):
        """생성 완료 후 후처리"""
        try:
            # 출력 폴더 생성
            output_dir = Path(self.config.get('paths', {}).get('outputs', 'outputs'))
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{seed}.png"
            image_path = output_dir / filename
            
            # 메타데이터와 함께 저장
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("parameters", self._build_metadata_string(params, seed))
            
            def _save():
                image.save(image_path, pnginfo=metadata)
            
            await asyncio.to_thread(_save)
            
            # 썸네일 생성
            thumbnail_path = output_dir / f"thumb_{filename}"
            def _save_thumbnail():
                thumbnail = image.copy()
                thumbnail.thumbnail((256, 256), Image.Resampling.LANCZOS)
                thumbnail.save(thumbnail_path)
            
            await asyncio.to_thread(_save_thumbnail)
            
            # 히스토리에 추가
            history_item = HistoryItem(
                image_path=str(image_path),
                thumbnail_path=str(thumbnail_path),
                params=params,
                model=self.get('current_model_info', {}).get('name', 'Unknown')
            )
            
            history = self.get('history', [])
            history.insert(0, history_item)  # 최신이 앞에
            history = history[:50]  # 최대 50개만 유지
            self.set('history', history)
            
            # UI 알림
            self._notify('image_generated', {'path': str(image_path)})
            ui.notify('이미지 생성 완료!', type='success')
            
        except Exception as e:
            print(f"❌ 후처리 실패: {e}")
            ui.notify(f'후처리 실패: {str(e)}', type='negative')

    def _build_metadata_string(self, params: GenerationParams, seed: int) -> str:
        """A1111 형식의 메타데이터 문자열 생성"""
        model_name = self.get('current_model_info', {}).get('name', 'Unknown')
        
        return f"""{params.prompt}
Negative prompt: {params.negative_prompt}
Steps: {params.steps}, Sampler: {params.sampler}, Scheduler: {params.scheduler}, CFG scale: {params.cfg_scale}, Seed: {seed}, Size: {params.width}x{params.height}, Model: {model_name}"""

    async def start_infinite_generation(self):
        """무한 생성 모드 시작"""
        if self.get('is_generating') and not self.get('infinite_mode'):
            # 일반 생성 중이면 중지하고 무한 모드로 전환
            await self.stop_generation()
            await asyncio.sleep(0.5)  # 잠깐 대기
        
        if not self.pipeline:
            ui.notify('모델을 먼저 로드해주세요.', type='warning')
            return
        
        self.set('infinite_mode', True)
        ui.notify('무한 생성 모드 시작됨', type='info')
        
        try:
            while self.get('infinite_mode', False):
                print("🔄 무한 생성 - 새로운 이미지 생성 시작")
                
                # 중단 플래그 리셋
                self.stop_generation_flag.clear()
                
                # 단일 이미지 생성 (배치/반복 무시)
                await self._generate_single_image()
                
                # 중단 신호 확인
                if self.stop_generation_flag.is_set() or not self.get('infinite_mode', False):
                    break
                
                # 다음 생성 전 잠깐 대기 (UI 업데이트 시간)
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ 무한 생성 중 오류: {e}")
            ui.notify(f'무한 생성 오류: {str(e)}', type='negative')
        
        finally:
            # 무한 모드 상태 정리
            self.set('infinite_mode', False)
            
            # 생성 상태 정리 (무한 모드가 아닌 경우에만)
            if not self.get('infinite_mode', False):
                self.set('is_generating', False)
                self._notify('generation_finished', {})
                
            print("🏁 무한 생성 모드 완전 종료")
            ui.notify('무한 생성 모드 중지됨', type='info')

    async def _generate_single_image(self):
        """단일 이미지 생성 (무한 모드용)"""
        try:
            self.set('is_generating', True)
            self._notify('generation_started', {})
            
            params = self.get('current_params')
            
            # 시드 처리
            seed = params.seed
            if seed == -1:
                seed = random.randint(0, 2**32 - 1)
            
            generator = torch.Generator(device=self.device).manual_seed(seed)
            
            def _generate():
                return self.pipeline(
                    prompt=params.prompt,
                    negative_prompt=params.negative_prompt,
                    width=params.width,
                    height=params.height,
                    num_inference_steps=params.steps,
                    guidance_scale=params.cfg_scale,
                    generator=generator
                ).images[0]
            
            image = await asyncio.to_thread(_generate)
            
            # 후처리 및 저장
            await self.finish_generation(image, params, seed)
            
        except Exception as e:
            print(f"❌ 단일 이미지 생성 실패: {e}")
            self._notify('generation_failed', {'error': str(e)})
        
        finally:
            # 무한 모드가 비활성화된 경우에만 상태 정리
            if not self.get('infinite_mode', False):
                self.set('is_generating', False)
                self._notify('generation_finished', {})

    async def stop_infinite_generation(self):
        """무한 생성 모드 중지"""
        print("⏹️ 무한 생성 모드 중지 요청")
        self.set('infinite_mode', False)
        self.stop_generation_flag.set()
        
        # 잠깐 대기 후 상태 정리
        await asyncio.sleep(0.1)
        if not self.get('is_generating', False):
            self._notify('generation_finished', {})

    async def stop_generation(self):
        """생성 중단 신호를 보냅니다."""
        print("✋ 생성 중단 요청됨.")
        self.stop_generation_flag.set()
        
        # 무한 모드도 함께 중지
        if self.get('infinite_mode', False):
            self.set('infinite_mode', False)

    def apply_params_from_metadata(self, model_info: Dict[str, Any]):
        """메타데이터에서 파라미터를 현재 설정에 적용"""
        metadata = model_info.get('metadata', {})
        params = metadata.get('parameters', {})
        
        if not params:
            return
        
        current_params = self.get('current_params')
        
        # 파라미터 적용 (너비, 높이는 여기서 직접 제어)
        if 'steps' in params:
            current_params.steps = int(params['steps'])
        if 'cfg_scale' in params:
            current_params.cfg_scale = float(params['cfg_scale'])
        if 'sampler' in params:
            # NOTE: ComfyUI 샘플러 목록에 있는 것만 적용
            comfyui_samplers = ["euler", "dpmpp_2m", "dpmpp_sde_gpu", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde_gpu"]
            if params['sampler'] in comfyui_samplers:
                current_params.sampler = params['sampler']
        if 'scheduler' in params:
            # NOTE: ComfyUI 스케줄러 목록에 있는 것만 적용
            comfyui_schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
            if params['scheduler'] in comfyui_schedulers:
                current_params.scheduler = params['scheduler']
        #if 'width' in params:
        #    current_params.width = int(params['width'])
        #if 'height' in params:
        #    current_params.height = int(params['height'])
        if 'seed' in params:
            current_params.seed = int(params['seed'])
        
        # --- [수정된 부분] ---
        # 사용자 요청에 따라 프롬프트 자동 적용 로직은 주석 처리합니다.
        # if 'prompt' in metadata:
        #     current_params.prompt = metadata['prompt']
        # if 'negative_prompt' in metadata:
        #     current_params.negative_prompt = metadata['negative_prompt']
        
        # 'current_params_changed' 이벤트를 통해 UI에 변경사항을 알립니다.
        self.set('current_params', current_params)
        print("✅ 메타데이터에서 파라미터가 적용되었습니다.")
        
        # 기존 MetadataPanel 등을 위한 알림은 유지합니다.
        self._notify('state_restored', {'params': current_params})

    def restore_from_history(self, history_id: str):
        """히스토리에서 설정 복원"""
        history = self.get('history', [])
        for item in history:
            if item.id == history_id:
                self.set('current_params', item.params)
                if item.vae:
                    asyncio.create_task(self.load_vae(item.vae))
                self._notify('state_restored', {'params': item.params})
                break

    async def get_vae_options_list(self) -> List[str]:
        """VAE 선택 옵션 리스트 생성"""
        options = ['Automatic', 'None']
        
        available_vae = self.get('available_vae', {})
        for folder_name, folder_vae in available_vae.items():
            for vae_info in folder_vae:
                display_name = vae_info['name']
                if folder_name != 'Root':
                    display_name = f"{folder_name}/{vae_info['name']}"
                options.append(display_name)
        
        return options

    def find_vae_by_name(self, vae_name: str) -> Optional[str]:
        """VAE 이름으로 경로 찾기"""
        available_vae = self.get('available_vae', {})
        
        for folder_name, folder_vae in available_vae.items():
            for vae_info in folder_vae:
                display_name = vae_info['name']
                if folder_name != 'Root':
                    display_name = f"{folder_name}/{vae_info['name']}"
                
                if display_name == vae_name or vae_info['name'] == vae_name:
                    return vae_info['path']
        
        return None

    async def cleanup(self):
        """애플리케이션 종료 시 정리 작업"""
        print("🧹 애플리케이션 정리 중...")
        if self.pipeline:
            # GPU 메모리 정리
            del self.pipeline
            torch.cuda.empty_cache()
        """애플리케이션 종료 시 정리 작업"""
        print("🧹 애플리케이션 정리 중...")
        if self.pipeline:
            # GPU 메모리 정리
            del self.pipeline
            torch.cuda.empty_cache()

    # === 기본 상태 관리 메서드 ===
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