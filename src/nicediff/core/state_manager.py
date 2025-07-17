# src/nicediff/core/state_manager.py
# (도메인 주도 설계 원칙에 따라 정리된 버전)

import asyncio
import json
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import torch

from ..services.model_scanner import ModelScanner
from ..services.metadata_parser import MetadataParser
from ..services.tokenizer_manager import TokenizerManager
from ..domains.generation.model_definitions.generation_params import GenerationParams
from ..domains.generation.model_definitions.history_item import HistoryItem
from ..domains.generation.services.model_loader import ModelLoader
from ..domains.generation.services.image_saver import ImageSaver
from ..domains.generation.strategies.basic_strategy import BasicGenerationStrategy
from ..domains.generation.processors.prompt_processor import PromptProcessor
from ..services.long_prompt_handler import LongPromptHandler


class StateManager:
    """중앙 상태 관리자 (도메인 주도 설계 원칙 적용)"""
    
    def __init__(self):
        self._state: Dict[str, Any] = {
            'current_model_info': None,
            'current_vae_path': 'baked_in',  # 기본값으로 내장 VAE 사용
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
            'current_mode': 'txt2img',  # 현재 생성 모드 (txt2img, img2img, inpaint, upscale)
            
            # 이미지 상태 분리 (개선안 5 적용)
            'init_image': None,  # 업로드된 원본 이미지 (영구 보존)
            'generated_images': [],  # 생성된 결과 이미지들 (독립 관리)
            'current_display_image': None,  # 현재 표시 중인 이미지
        }
        
        # 크기 일치 토글 기본값 설정
        self._state['current_params'].size_match_enabled = False
        self._observers: Dict[str, List[Callable]] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.stop_generation_flag = asyncio.Event()
        
        # 도메인 서비스 초기화
        self.model_loader = ModelLoader(self.device)
        self.image_saver = ImageSaver()
        self.tokenizer_manager = None  # initialize에서 설정
        self.prompt_processor = PromptProcessor('SD15')  # 기본값으로 SD15
        self.long_prompt_handler = None  # initialize에서 설정
        
        print(f"🖥️ 사용 중인 디바이스: {self.device}")
    
    async def initialize(self):
        """설정 파일 로드 및 모델 스캔 시작"""
        config_path = Path("config.toml")
        if await asyncio.to_thread(config_path.exists):
            with open(config_path, "rb") as f:
                self.config = tomllib.load(f)
        else:
            # config.toml이 없으면 기본 경로 사용
            self.config = {
                'paths': {
                    'checkpoints': 'models/checkpoints',
                    'vae': 'models/vae',
                    'loras': 'models/loras'
                }
            }
            print("⚠️ config.toml이 없어 기본 경로를 사용합니다.")
        
        # 토크나이저 매니저 초기화
        self.tokenizer_manager = TokenizerManager(self.config.get('paths', {}).get('tokenizers', 'models/tokenizers'))
        
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

        # 토크나이저 스캔
        if self.tokenizer_manager:
            self.tokenizer_manager.scan_tokenizers()
        
        self.set('status_message', '준비 완료')
        print("✅ StateManager: 스캔 결과로 상태 업데이트 완료.")
        
        # LoRA 목록 업데이트 이벤트 발생
        loras_data = all_models_data.get('loras', {})
        self._notify('loras_updated', loras_data)
        print(f"📢 LoRA 업데이트 이벤트 발생: {sum(len(items) for items in loras_data.values())}개 LoRA")

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
            self.model_loader.get_current_pipeline() is not None):
            self._notify_user(f"'{model_info['name']}' 모델은 이미 로드되어 있습니다.", 'info')
            return True

        try:
            self.set('is_loading_model', True)
            self._notify('model_loading_started', {'name': model_info['name']})
            
            # 기존 모델 언로드
            self.model_loader.unload_model()
            
            # 도메인 서비스를 사용하여 모델 로드
            await self.model_loader.load_model(model_info)
            self.set('current_model_info', model_info)
            
            # VAE 자동 선택은 사용자가 'Automatic'을 선택했을 때만 실행
            current_vae_path = self.get('current_vae_path')
            if current_vae_path is None:
                await self._auto_select_vae(model_info)
            
            # Top_bar에서는 파라미터 자동 적용 금지 - 프롬프트 패널과 파라미터 패널에서만 설정
            print(f"ℹ️ 파라미터 자동 적용 비활성화 (Top_bar에서는 체크포인트와 VAE만 선택)")
            
            # 모델 타입에 따라 PromptProcessor와 LongPromptHandler 업데이트
            model_type = model_info.get('model_type', 'SD15')
            self.prompt_processor = PromptProcessor(model_type)
            
            # LongPromptHandler 초기화 (토크나이저가 로드된 후)
            pipeline = self.model_loader.get_current_pipeline()
            if pipeline and hasattr(pipeline, 'tokenizer'):
                max_tokens = 225 if model_type == 'SDXL' else 77
                self.long_prompt_handler = LongPromptHandler(pipeline.tokenizer, max_tokens)
                print(f"✅ LongPromptHandler 초기화: {model_type} 모드 (최대 {max_tokens} 토큰)")
            
            print(f"✅ PromptProcessor 업데이트: {model_type} 모드 (최대 {self.prompt_processor.max_tokens} 토큰)")
            
            # 모델 로딩 완료 알림 (선택 알림은 이미 select_model에서 발생했으므로 생략)
            self._notify('model_loaded', model_info)
            
            self._notify('model_loading_finished', {'success': True, 'model_info': model_info})
            self._notify_user(f"'{model_info['name']}' 모델이 로드되었습니다.", 'positive')
            return True
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"모델 로드 실패: {str(e)}"
            self._notify_user(error_msg, 'negative')
            self._notify('model_loading_finished', {'success': False, 'error': str(e)})
            return False
        
        finally:
            self.set('is_loading_model', False)

    async def _load_model_heavy_work(self, model_info: Dict[str, Any]):
        """실제 모델 로딩 작업 (Heavy I/O)"""
        def _load():
            model_path = model_info['path']
            model_type = model_info.get('model_type', 'SD15')
            
            print(f"🔍 모델 타입: {model_type}, 경로: {model_path}")
            
            # 모델 타입에 따라 적절한 파이프라인 선택
            if model_type == 'SDXL':
                from diffusers.pipelines.stable_diffusion_xl.pipeline_stable_diffusion_xl import StableDiffusionXLPipeline
                pipeline = StableDiffusionXLPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                    safety_checker=None
                )
            else:
                # SD15 모델
                from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import StableDiffusionPipeline
                pipeline = StableDiffusionPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                    safety_checker=None,
                    requires_safety_checker=False
                )
            
            # GPU로 이동
            pipeline = pipeline.to(self.device)
            
            # SD15 특화 설정
            if model_type == 'SD15':
                # SD15에서 더 나은 품질을 위한 설정
                if hasattr(pipeline, 'enable_attention_slicing'):
                    pipeline.enable_attention_slicing(1)
                if hasattr(pipeline, 'enable_vae_slicing'):
                    pipeline.enable_vae_slicing()
                
                # PyTorch 2.0+ SDPA 최적화 (xformers 대신 사용)
                if hasattr(pipeline, 'enable_model_cpu_offload'):
                    pipeline.enable_model_cpu_offload()
                
                # xformers는 선택적 기능이므로 안전하게 처리
                try:
                    if hasattr(pipeline, 'enable_xformers_memory_efficient_attention'):
                        pipeline.enable_xformers_memory_efficient_attention()
                        print("✅ xformers 메모리 효율적 어텐션 활성화")
                except (ModuleNotFoundError, AttributeError) as e:
                    print(f"⚠️ xformers 미사용: {e}")
                    print("✅ PyTorch 2.0+ SDPA 사용 중")
                
                # SD15 품질 개선을 위한 추가 설정
                if hasattr(pipeline, 'scheduler') and hasattr(pipeline.scheduler, 'config'):
                    # Karras 스케줄러 최적화
                    pipeline.scheduler.config.use_karras_sigmas = True
                    pipeline.scheduler.config.karras_rho = 7.0
                    
                    # SD15에서 더 안정적인 생성
                    if hasattr(pipeline.scheduler.config, 'beta_start'):
                        pipeline.scheduler.config.beta_start = 0.00085
                    if hasattr(pipeline.scheduler.config, 'beta_end'):
                        pipeline.scheduler.config.beta_end = 0.012
                
                # 모델 정밀도 최적화
                if hasattr(pipeline, 'text_encoder'):
                    pipeline.text_encoder = pipeline.text_encoder.to(torch.float16)
                if hasattr(pipeline, 'vae'):
                    pipeline.vae = pipeline.vae.to(torch.float16)
                if hasattr(pipeline, 'unet'):
                    pipeline.unet = pipeline.unet.to(torch.float16)
                
                print("✅ SD15 품질 최적화 설정 적용 완료")
            else:
                # SDXL 설정
                if hasattr(pipeline, 'enable_attention_slicing'):
                    pipeline.enable_attention_slicing()
                if hasattr(pipeline, 'enable_vae_slicing'):
                    pipeline.enable_vae_slicing()
            
            return pipeline
        
        # 별도 스레드에서 로딩 수행
        self.pipeline = await asyncio.to_thread(_load)
        print(f"✅ 모델 로딩 완료: {model_info['name']}")

    async def _unload_current_model(self):
        """기존 모델을 메모리에서 해제"""
        if self.pipeline is not None:
            print(f"🗑️ 기존 모델 언로드 중...")
            try:
                # float16 모델은 CPU로 이동하지 않고 직접 삭제
                del self.pipeline
                self.pipeline = None
                
                # CUDA 캐시 정리
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                print(f"✅ 기존 모델 언로드 완료")
            except Exception as e:
                print(f"⚠️ 기존 모델 언로드 중 오류 (무시됨): {e}")
                # 오류가 발생해도 계속 진행
                self.pipeline = None

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
        
        # SD15 모델의 경우 일반적으로 사용되는 VAE들을 자동으로 찾아서 적용
        model_type = model_info.get('model_type', 'SD15')
        if model_type == 'SD15':
            available_vae = self.get('available_vae', {})
            preferred_vae_names = [
                'vaeFtMse840000EmaPruned',  # 가장 일반적인 SD15 VAE
                'vae-ft-mse-840000-ema-pruned',
                'vaeFtMse840k',
                'vae-ft-mse-840k',
                'vaeRealanimark',
                'vaeRealanimark_vaeRealanimark'
            ]
            
            for preferred_name in preferred_vae_names:
                for folder_vae in available_vae.values():
                    for vae_info in folder_vae:
                        if preferred_name.lower() in vae_info['name'].lower():
                            print(f"✅ SD15 권장 VAE 발견: {vae_info['name']}")
                            await self.load_vae(vae_info['path'])
                            return
        
        # 기본적으로 내장 VAE 사용
        print("ℹ️ 체크포인트 내장 VAE 사용 (별도 VAE 없음)")
        self.set('current_vae_path', 'baked_in')
        self._notify('vae_auto_selected', 'baked_in')

    async def load_vae(self, vae_path: str):
        """VAE 파일을 로드하여 파이프라인에 적용"""
        if not self.model_loader.get_current_pipeline():
            self._notify_user('모델을 먼저 로드하세요.', 'warning')
            return False
        
        self.set('is_loading_model', True) # VAE 로딩도 로딩 상태로 간주
        self._notify_user(f"VAE '{Path(vae_path).name}' 로드 중...", 'info')
        
        try:
            # 도메인 서비스를 사용하여 VAE 로드
            success = await self.model_loader.load_vae(vae_path)
            
            if success:
                self.set('current_vae_path', vae_path)
                self._notify_user(f"VAE '{Path(vae_path).name}' 적용 완료!", 'positive')
                return True
            else:
                self._notify_user(f"VAE 로드 실패", 'negative')
                return False
        except Exception as e:
            print(f"❌ VAE 로드 실패: {e}")
            self._notify_user(f"VAE 로드 실패: {e}", 'negative')
            return False
        finally:
            self.set('is_loading_model', False)

    async def generate_image(self):
        """
        이미지 생성 실행 (중복 생성 방지 강화 + UI 동기화 강화)
        - 생성 파라미터는 반드시 current_params(파라미터/프롬프트 패널)에서만 수집
        - 모델/LoRA/프리뷰 등 외부 상태는 생성 파라미터에 직접 포함하지 않음
        - 혹시라도 외부 값이 params_dict에 들어가면 경고 로그 출력 및 무시
        """
        # 중복 생성 방지 강화
        if self.get('is_generating'):
            print(f"⚠️ 이미 생성 중입니다 - 중복 요청 무시")
            self._notify_user('이미 생성 중입니다.', 'warning')
            return
        
        # 생성 상태 체크 (추가 안전장치)
        if hasattr(self, '_generation_in_progress') and self._generation_in_progress:
            print(f"⚠️ 생성 진행 중 - 중복 요청 무시")
            self._notify_user('이미 생성 중입니다.', 'warning')
            return
        
        if not self.model_loader.get_current_pipeline():
            self._notify_user('모델을 먼저 로드해주세요.', 'warning')
            return
        
        # 생성 상태 설정 (중복 방지 강화)
        self.stop_generation_flag.clear()
        self.set('is_generating', True)
        self._generation_in_progress = True
        print(f"🔄 이미지 생성 시작...")
        
        try:
            pipeline = self.model_loader.get_current_pipeline()
            current_mode = self.get('current_mode', 'txt2img')
            
            # 파라미터 수집 (current_params에서만)
            params = self.get('current_params')
            if not params:
                print(f"❌ 파라미터가 없습니다")
                return
            
            # img2img 모드에서 원본 이미지 보존 강화
            if current_mode in ['img2img', 'inpaint', 'upscale']:
                init_image = self.get('init_image')
                if not init_image:
                    print(f"❌ img2img 모드에서 원본 이미지가 없습니다")
                    self._notify_user('이미지를 먼저 업로드해주세요.', 'warning')
                    return
                
                print(f"✅ 원본 이미지 보존 확인: {init_image.size}")
                # 원본 이미지를 파라미터에 추가
                params.init_image = init_image
            
            # 생성 실행
            result = await self._execute_generation(pipeline, params, current_mode)
            
            if result and result.images:
                print(f"✅ 생성 완료: {len(result.images)}개 이미지")
                
                # 생성된 이미지 저장 (원본 이미지 보존)
                # self.set_generated_images(result.images)  # 중복 저장 제거 - _execute_generation에서 이미 저장됨
                
                # 이벤트 발생
                self._notify('generation_completed', {'images': result.images})
                
                # 히스토리 업데이트 (메서드명 수정)
                # self._update_history(result.images)  # 이 메서드는 존재하지 않음
                
            else:
                print(f"❌ 생성 실패")
                self._notify_user('이미지 생성에 실패했습니다.', 'negative')
                
        except Exception as e:
            print(f"❌ 이미지 생성 중 오류: {e}")
            import traceback
            traceback.print_exc()
            self._notify_user(f'생성 중 오류가 발생했습니다: {str(e)}', 'negative')
            
        finally:
            # 생성 상태 해제
            self.set('is_generating', False)
            self._generation_in_progress = False
            print(f"✅ 이미지 생성 완료")

    async def _execute_generation(self, pipeline, params: GenerationParams, current_mode: str):
        """실제 생성 로직을 수행하는 내부 메서드"""
        strategy = BasicGenerationStrategy(pipeline, self.device, state=self)
        
        # [정책] 오직 current_params에서만 생성 파라미터 수집
        params_dict = {
            'prompt': params.prompt,
            'negative_prompt': params.negative_prompt,
            'width': params.width,
            'height': params.height,
            'steps': params.steps,
            'cfg_scale': params.cfg_scale,
            'seed': params.seed,  # 처리된 시드 사용
            'sampler': params.sampler,
            'scheduler': params.scheduler,
            'batch_size': params.batch_size,
            'clip_skip': getattr(params, 'clip_skip', 1),
        }
        # [방어] 외부 상태가 params_dict에 섞이면 경고
        for forbidden in ['current_model_info', 'current_loras', 'current_vae_path', 'preview', 'preview_image']:
            if forbidden in params_dict:
                print(f"⚠️ 경고: 생성 파라미터에 외부 상태({forbidden})가 포함되어 있음. 무시합니다.")
                params_dict.pop(forbidden)
        
        # 모델 정보는 파이프라인에만 영향, 생성 파라미터에는 직접 포함하지 않음
        model_info = self.get('current_model_info', {})
        
        self._notify('generation_started', {
            'mode': current_mode,
            'params': params_dict
        })
        
        result = await strategy.execute(params_dict, model_info)
        
        # 1단계: 생성 완료 후 이미지가 StateManager에 저장되는지 확인
        print("=" * 80)
        print("🔍 [디버깅 1단계] 생성 완료 후 이미지 저장 확인")
        print("=" * 80)
        
        if result.success and result.images:
            print(f"✅ 생성 성공: {len(result.images)}개 이미지")
            print(f"   - result.images 타입: {type(result.images)}")
            print(f"   - result.images[0] 타입: {type(result.images[0])}")
            print(f"   - result.images[0] 크기: {result.images[0].size if hasattr(result.images[0], 'size') else 'N/A'}")
            
            # 생성된 이미지를 독립적으로 저장 (UI 동기화 강화)
            generated_images = result.images
            self.set_generated_images(generated_images)
            print(f"✅ StateManager에 generated_images 독립 저장 완료")
            print(f"   - 저장된 이미지 개수: {len(generated_images)}")
            
            # 원본 이미지 보존 확인 및 강화
            self.preserve_init_image()
            self.ensure_image_state_preservation()
            
            # 각 이미지별 후처리
            for i, image in enumerate(generated_images):
                print(f"   - 이미지 {i+1} 후처리 시작")
                await self.finish_generation(image, params, params_dict['seed'])
                print(f"   - 이미지 {i+1} 후처리 완료")
            
            self._notify_user(f'{len(result.images)}개 이미지 생성 완료!', 'positive')
            return result
        else:
            error_msg = ', '.join(result.errors) if result.errors else '알 수 없는 오류'
            print(f"❌ 생성 실패: {error_msg}")
            self._notify_user(f'생성 실패: {error_msg}', 'negative')
            generated_images = []
            return result

    async def finish_generation(self, image, params: GenerationParams, seed: int):
        """이미지 생성 완료 후처리 (도메인 서비스 사용)"""
        try:
            # 도메인 서비스를 사용하여 이미지 저장
            model_name = self.get('current_model_info')['name']
            save_result = await self.image_saver.save_generated_image(image, params, seed, model_name)
            
            # 이벤트 발생
            self._notify('image_generated', {
                'image_path': save_result['image_path'],
                'thumbnail_path': save_result['thumbnail_path'],
                'params': params,
                'seed': seed
            })
            
            # 히스토리에 추가
            history_item = HistoryItem(
                image_path=save_result['image_path'],
                thumbnail_path=save_result['thumbnail_path'],
                params=params,
                model=model_name,
                vae=self.get('current_vae_path'),
                loras=self.get('current_loras', [])
            )
            self._add_to_history(history_item.to_dict())
            
            print(f"✅ 후처리 완료: 1개 이미지 저장")
            
        except Exception as e:
            print(f"❌ 후처리 실패: {e}")
            import traceback
            traceback.print_exc()

    def _build_metadata_string(self, params: GenerationParams, seed: int) -> str:
        """PNG 메타데이터 문자열 생성"""
        model_name = self.get('current_model_info', {}).get('name', 'Unknown')
        vae_path = self.get('current_vae_path')
        
        # VAE 정보 추가
        vae_info = ""
        if vae_path and vae_path != 'baked_in':
            vae_name = Path(vae_path).name
            vae_info = f", VAE: {vae_name}"
        
        return f"{params.prompt}\n\nNegative prompt: {params.negative_prompt}\nSteps: {params.steps}, Sampler: {params.sampler}, CFG scale: {params.cfg_scale}, Seed: {seed}, Size: {params.width}x{params.height}, Model: {model_name}{vae_info}"

    def _create_pnginfo(self, metadata: str) -> Any:
        """PNG 메타데이터 객체 생성"""
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("parameters", metadata)
        return pnginfo

    async def start_infinite_generation(self):
        """무한 생성 모드 시작"""
        if not self.model_loader.get_current_pipeline():
            self._notify_user('모델을 먼저 로드해주세요.', 'warning')
            return
        
        self.set('infinite_mode', True)
        self._notify_user('무한 생성 모드가 시작되었습니다.', 'info')
        asyncio.create_task(self._infinite_generation_loop())

    async def _infinite_generation_loop(self):
        """무한 생성 루프"""
        while self.get('infinite_mode') and not self.stop_generation_flag.is_set():
            try:
                await self._generate_single_image()
                await asyncio.sleep(2)  # 2초 대기
            except Exception as e:
                print(f"❌ 무한 생성 중 오류: {e}")
                await asyncio.sleep(5)  # 오류 시 5초 대기

    async def _generate_single_image(self):
        """단일 이미지 생성 (무한 모드용)"""
        if not self.model_loader.get_current_pipeline():
            return
        
        params = self.get('current_params')
        
        def _generate():
            return self.model_loader.get_current_pipeline()(
                prompt=params.prompt,
                negative_prompt=params.negative_prompt,
                width=params.width,
                height=params.height,
                num_inference_steps=params.steps,
                guidance_scale=params.cfg_scale,
                generator=torch.Generator(device=self.device).manual_seed(params.seed)
            )
        
        try:
            result = await asyncio.to_thread(_generate)
            if result.images:
                await self.finish_generation(result.images[0], params, params.seed)
        except Exception as e:
            print(f"❌ 단일 이미지 생성 실패: {e}")

    async def stop_infinite_generation(self):
        """무한 생성 모드 중지"""
        self.set('infinite_mode', False)
        self._notify_user('무한 생성 모드가 중지되었습니다.', 'info')

    async def stop_generation(self):
        """생성 중지"""
        self.stop_generation_flag.set()
        self.set('is_generating', False)
        self._notify_user('생성이 중지되었습니다.', 'info')

    def apply_params_from_metadata(self, model_info: Dict[str, Any], include_prompts: bool = False):
        """메타데이터에서 파라미터 적용 (더 이상 자동으로 호출되지 않음)"""
        def get_first(*keys, default=None):
            # 최상위 → parameters 내부 순서로 값 반환
            for key in keys:
                if key in model_info:
                    return model_info[key]
                if 'parameters' in model_info and key in model_info['parameters']:
                    return model_info['parameters'][key]
            return default
        
        # 파라미터 추출
        width = get_first('width', 'Width', default=512)
        height = get_first('height', 'Height', default=512)
        steps = get_first('steps', 'Steps', default=20)
        cfg_scale = get_first('cfg_scale', 'CFG Scale', default=7.0)
        sampler = get_first('sampler', 'Sampler', default='dpmpp_2m')
        scheduler = get_first('scheduler', 'Scheduler', default='karras')
        seed = get_first('seed', 'Seed', default=-1)
        
        # 현재 파라미터 업데이트
        current_params = self.get('current_params')
        
        # 프롬프트 포함 여부에 따라 처리
        if include_prompts:
            prompt = get_first('prompt', 'Prompt', default='')
            negative_prompt = get_first('negative_prompt', 'Negative prompt', default='')
            current_params.prompt = prompt
            current_params.negative_prompt = negative_prompt
            print(f"ℹ️ 프롬프트는 제외하고 파라미터만 적용합니다.")
        
        # 각 파라미터를 개별적으로 업데이트하여 이벤트 발생
        if width is not None:
            self.update_param('width', int(width))
        if height is not None:
            self.update_param('height', int(height))
        if steps is not None:
            self.update_param('steps', int(steps))
        if cfg_scale is not None:
            self.update_param('cfg_scale', float(cfg_scale))
        if sampler:
            self.update_param('sampler', str(sampler))
        if scheduler:
            self.update_param('scheduler', str(scheduler))
        
        # 시드 처리
        if seed is not None and seed != -1:
            self.update_param('seed', int(seed))
            print(f"✅ Seed {seed} 발견, 랜덤 시드로 설정: -1")
        else:
            self.update_param('seed', -1)
        
        print(f"✅ 메타데이터에서 파라미터가 적용되었습니다.")

    def restore_from_history(self, history_id: str):
        """히스토리에서 파라미터 복원"""
        history = self.get('history', [])
        for item in history:
            if item.get('id') == history_id:
                # 파라미터 복원
                params = item.get('params', {})
                current_params = self.get('current_params')
                
                # GenerationParams 객체로 변환
                if isinstance(params, dict):
                    for key, value in params.items():
                        if hasattr(current_params, key):
                            setattr(current_params, key, value)
                elif hasattr(params, '__dict__'):
                    # 이미 GenerationParams 객체인 경우
                    for key, value in params.__dict__.items():
                        if hasattr(current_params, key):
                            setattr(current_params, key, value)
                
                # VAE 복원
                vae = item.get('vae')
                if vae and vae != 'baked_in':
                    self.set('current_vae_path', vae)
                
                # LoRA 복원
                loras = item.get('loras', [])
                if loras:
                    self.set('current_loras', loras)
                
                # 모델 복원 (가능한 경우)
                model_name = item.get('model')
                if model_name:
                    available_checkpoints = self.get('available_checkpoints', {})
                    for folder_models in available_checkpoints.values():
                        for model_info in folder_models:
                            if model_info['name'] == model_name:
                                asyncio.create_task(self.select_model(model_info))
                                break
                
                self._notify('params_restored', params)
                self._notify_user('히스토리에서 파라미터가 복원되었습니다.', 'positive')
                return
        
        self._notify_user('히스토리 항목을 찾을 수 없습니다.', 'negative')

    async def get_vae_options_list(self) -> List[str]:
        """VAE 옵션 목록 반환"""
        available_vae = self.get('available_vae', {})
        options = ['baked_in']  # 기본값
        
        for folder_vae in available_vae.values():
            for vae_info in folder_vae:
                options.append(vae_info['name'])
        
        return options

    def find_vae_by_name(self, vae_name: str) -> Optional[str]:
        """VAE 이름으로 경로 찾기"""
        if vae_name == 'baked_in':
            return 'baked_in'
        
        available_vae = self.get('available_vae', {})
        for folder_vae in available_vae.values():
            for vae_info in folder_vae:
                if vae_info['name'] == vae_name:
                    return vae_info['path']
        
        return None

    async def cleanup(self):
        """리소스 정리"""
        try:
            # 모델 언로드
            self.model_loader.unload_model()
            
            # CUDA 캐시 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            print("✅ 리소스 정리 완료")
        except Exception as e:
            print(f"⚠️ 리소스 정리 중 오류: {e}")

    # --- 상태 관리 메서드들 ---
    def get(self, key: str, default: Any = None) -> Any:
        """상태 값 조회"""
        return self._state.get(key, default)

    def set(self, key: str, value: Any):
        """상태 값 설정"""
        self._state[key] = value
        self._notify(f'{key}_changed', value)
    
    def set_init_image(self, image):
        """img2img용 원본 이미지 설정 (영구 보존) - 이미지 프리뷰 강화"""
        print(f"🔍 set_init_image 호출: 이미지 타입={type(image)}")
        
        # 무한 재귀 방지 플래그 확인 (완화 - 이미지가 실제로 다른 경우에는 허용)
        if hasattr(self, '_setting_init_image') and self._setting_init_image:
            current_image = self._state.get('init_image')
            if current_image is not None and image is not None:
                if hasattr(current_image, 'size') and hasattr(image, 'size'):
                    if current_image.size == image.size:
                        print(f"⚠️ set_init_image 중복 호출 방지됨 (동일한 크기)")
                        return
            # 다른 이미지인 경우에는 허용
            print(f"ℹ️ 다른 이미지로 업데이트 허용")
        
        try:
            self._setting_init_image = True
            
            if image is not None:
                print(f"🔍 이미지 정보: 크기={image.size}, 모드={image.mode}")
                # 원본 이미지를 영구 보존
                self._state['init_image'] = image
                print(f"✅ init_image 영구 보존 완료: {image.size}")
                
                # 저장 후 확인
                saved_image = self._state.get('init_image')
                print(f"🔍 저장 후 확인: 타입={type(saved_image)}, 크기={saved_image.size if saved_image else 'None'}")
                
                # 이벤트 발생 (이미지 프리뷰 강화)
                self._notify('init_image_changed', {'status': 'success', 'size': image.size})
                print(f"✅ init_image_changed 이벤트 발생")
            else:
                print(f"⚠️ init_image가 None으로 설정됨")
                self._state['init_image'] = None
                
                # 이벤트 발생
                self._notify('init_image_changed', {'status': 'cleared'})
                print(f"✅ init_image_changed 이벤트 발생 (cleared)")
                    
        except Exception as e:
            print(f"❌ set_init_image 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 플래그 해제 (이미지 프리뷰 강화)
            self._setting_init_image = False
    
    def set_generated_images(self, images):
        """
        생성된 이미지들 설정 (독립 관리) - UI 동기화 강화
        
        ⚠️ 중요: StateManager에는 오직 원본 이미지만 저장합니다!
        - 썸네일은 절대 저장하지 않음
        - 썸네일은 히스토리 표시용으로만 사용됨
        - UI 프리뷰에는 원본 이미지를 사용
        
        Args:
            images: 원본 이미지 리스트 (썸네일이 아님)
        """
        print(f"🔍 set_generated_images 호출: 이미지 개수={len(images) if images else 0}")
        
        # 무한 재귀 방지 플래그 확인
        if hasattr(self, '_setting_generated_images') and self._setting_generated_images:
            print(f"⚠️ set_generated_images 중복 호출 방지됨")
            return
        
        try:
            self._setting_generated_images = True
            
            if images:
                # 각 이미지의 크기 확인 (원본인지 확인)
                for i, img in enumerate(images):
                    print(f"🔍 생성된 이미지 {i+1}: 크기={img.size}, 타입={type(img)}")
                    # 썸네일 크기인지 확인 (150x150)
                    if img.size == (150, 150):
                        print(f"⚠️ 경고: 썸네일 크기(150x150)가 StateManager에 저장됨 - 원본 이미지가 필요함")
                
                self._state['generated_images'] = images
                print(f"✅ generated_images 독립 저장 완료: {len(images)}개")
                
                # 이벤트 발생 (UI 동기화 강화)
                self._notify('generated_images_changed', {'count': len(images)})
                print(f"✅ generated_images_changed 이벤트 발생")
            else:
                self._state['generated_images'] = []
                
                # 이벤트 발생
                self._notify('generated_images_changed', {'count': 0})
                print(f"✅ generated_images_changed 이벤트 발생 (cleared)")
                    
        except Exception as e:
            print(f"❌ set_generated_images 오류: {e}")
        finally:
            self._setting_generated_images = False
    
    def get_init_image(self):
        """업로드된 원본 이미지 조회"""
        return self._state.get('init_image')
    
    def get_generated_images(self):
        """생성된 결과 이미지들 조회"""
        return self._state.get('generated_images', [])
    
    def clear_generated_images(self):
        """생성된 이미지들 초기화 - UI 동기화 강화"""
        if not hasattr(self, '_clearing_generated_images') or not self._clearing_generated_images:
            try:
                self._clearing_generated_images = True
                self._state['generated_images'] = []
                
                # 이벤트 발생 (UI 동기화 강화)
                self._notify('generated_images_changed', {'count': 0})
                print(f"✅ generated_images 초기화 완료")
            except Exception as e:
                print(f"❌ clear_generated_images 오류: {e}")
            finally:
                self._clearing_generated_images = False
    
    def preserve_init_image(self):
        """원본 이미지 보존 확인 - 생성 과정에서 호출"""
        init_image = self.get('init_image')
        if init_image:
            print(f"✅ 원본 이미지 보존 확인: {init_image.size}")
            return True
        else:
            print(f"⚠️ 원본 이미지가 없음 - 보존할 이미지 없음")
            return False
    
    def ensure_image_state_preservation(self):
        """이미지 상태 보존 강화 - 생성 전후 호출"""
        try:
            print(f"🔄 이미지 상태 보존 강화 시작")
            
            # 원본 이미지 보존 확인
            init_image = self.get('init_image')
            if init_image:
                print(f"✅ 원본 이미지 보존됨: {init_image.size}")
            else:
                print(f"ℹ️ 원본 이미지 없음")
            
            # 생성된 이미지 확인
            generated_images = self.get('generated_images', [])
            if generated_images:
                print(f"✅ 생성된 이미지 보존됨: {len(generated_images)}개")
            else:
                print(f"ℹ️ 생성된 이미지 없음")
            
            print(f"✅ 이미지 상태 보존 강화 완료")
            
        except Exception as e:
            print(f"❌ 이미지 상태 보존 강화 중 오류: {e}")

    def update_param(self, param_name: str, value: Any):
        """파라미터 업데이트"""
        current_params = self.get('current_params')
        if hasattr(current_params, param_name):
            setattr(current_params, param_name, value)
            print(f"✅ {param_name} 적용: {value}")
            self._notify('params_updated', {param_name: value})

    def update_prompt(self, positive_prompt: str, negative_prompt: str):
        """프롬프트 업데이트"""
        current_params = self.get('current_params')
        current_params.prompt = positive_prompt
        current_params.negative_prompt = negative_prompt
        self._notify('prompt_updated', {'positive': positive_prompt, 'negative': negative_prompt})

    # --- 이벤트 시스템 ---
    def subscribe(self, event: str, callback: Callable):
        """이벤트 구독"""
        if event not in self._observers:
            self._observers[event] = []
        self._observers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable):
        """이벤트 구독 해제 (안전한 제거)"""
        if event in self._observers:
            try:
                if callback in self._observers[event]:
                    self._observers[event].remove(callback)
                    print(f"✅ 이벤트 '{event}' 구독 해제 완료")
                else:
                    print(f"⚠️ 이벤트 '{event}'에서 콜백을 찾을 수 없음 (이미 해제됨)")
            except ValueError:
                print(f"⚠️ 이벤트 '{event}' 구독 해제 중 오류 (콜백이 리스트에 없음)")
            except Exception as e:
                print(f"❌ 이벤트 '{event}' 구독 해제 중 예상치 못한 오류: {e}")

    def _notify(self, event: str, data: Any = None):
        """이벤트 발생"""
        if event in self._observers:
            for callback in self._observers[event]:
                try:
                    # async 함수인지 확인하고 적절히 처리
                    if asyncio.iscoroutinefunction(callback):
                        # async 함수는 별도 태스크로 실행
                        asyncio.create_task(callback(data))
                    else:
                        # 동기 함수는 직접 호출
                        callback(data)
                except Exception as e:
                    print(f"⚠️ 이벤트 콜백 오류 ({event}): {e}")

    def _notify_user(self, message: str, notification_type: str = 'info', duration: int = 5):
        """사용자 알림"""
        self._notify('user_notification', {
            'message': message,
            'type': notification_type,
            'duration': duration
        })

    # --- 프롬프트 처리 (도메인 서비스 위임) ---
    def copy_prompt_to_clipboard(self, positive_prompt: str = "", negative_prompt: str = ""):
        """프롬프트를 클립보드에 복사"""
        import pyperclip
        
        if positive_prompt and negative_prompt:
            full_prompt = f"{positive_prompt}\n\nNegative prompt: {negative_prompt}"
        elif positive_prompt:
            full_prompt = positive_prompt
        elif negative_prompt:
            full_prompt = f"Negative prompt: {negative_prompt}"
        else:
            return
        
        try:
            pyperclip.copy(full_prompt)
            print(f"📋 클립보드에 복사됨: {full_prompt[:50]}...")
            self._notify_user("프롬프트가 클립보드에 복사되었습니다.", 'positive')
        except Exception as e:
            print(f"❌ 클립보드 복사 실패: {e}")
            self._notify_user("클립보드 복사에 실패했습니다.", 'negative')

    def calculate_token_count(self, text: str) -> int:
        """실제 CLIP 토크나이저를 사용하여 토큰 수 계산"""
        pipeline = self.model_loader.get_current_pipeline()
        if not text.strip() or not pipeline or not hasattr(pipeline, 'tokenizer'):
            return 0
        
        try:
            # 토크나이저로 정확한 토큰 수 계산
            text_inputs = pipeline.tokenizer(
                text,
                padding="longest",
                truncation=False,
                return_tensors="pt"
            )
            return len(text_inputs.input_ids[0])
        except Exception as e:
            print(f"⚠️ 토큰 계산 오류: {e}")
            return len(text.split())  # 폴백: 단어 수로 추정

    def analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """프롬프트 분석 및 최적화 제안"""
        pipeline = self.model_loader.get_current_pipeline()
        tokenizer = getattr(pipeline, 'tokenizer', None) if pipeline else None
        analysis = self.prompt_processor.analyze_prompt(prompt, tokenizer)
        
        # PromptAnalysis 객체를 딕셔너리로 변환
        return {
            'token_count': analysis.token_count,
            'segments': analysis.segments,
            'weights': analysis.weights,
            'suggestions': analysis.suggestions,
            'is_optimized': analysis.is_optimized,
            'truncated_parts': analysis.truncated_parts
        }

    def add_break_keyword(self, prompt: str, position: int = None) -> str:
        """BREAK 키워드 추가"""
        if self.long_prompt_handler:
            return self.long_prompt_handler.add_break_keywords(prompt)
        return self.prompt_processor.add_break_keyword(prompt, position)
    
    def get_prompt_stats(self, prompt: str) -> Dict:
        """프롬프트 통계 정보 (LongPromptHandler 사용)"""
        if self.long_prompt_handler:
            return self.long_prompt_handler.get_prompt_stats(prompt)
        
        # 기본 통계 (LongPromptHandler가 없는 경우)
        total_tokens = self.calculate_token_count(prompt)
        return {
            'total_tokens': total_tokens,
            'max_tokens': self.prompt_processor.max_tokens,
            'chunks_count': 1,
            'is_truncated': total_tokens > self.prompt_processor.max_tokens,
            'truncation_ratio': total_tokens / self.prompt_processor.max_tokens if self.prompt_processor.max_tokens > 0 else 0,
            'chunks': [{'text': prompt, 'tokens': total_tokens, 'importance': 1.0}]
        }
    
    def optimize_long_prompt(self, prompt: str) -> str:
        """긴 프롬프트 최적화"""
        if self.long_prompt_handler:
            return self.long_prompt_handler.optimize_prompt(prompt)
        return self.optimize_prompt(prompt)
    
    def split_long_prompt(self, prompt: str) -> List[Dict]:
        """긴 프롬프트 분할"""
        if self.long_prompt_handler:
            chunks = self.long_prompt_handler.smart_split(prompt)
            return [
                {
                    'text': chunk.text,
                    'tokens': len(chunk.tokens),
                    'importance': chunk.importance,
                    'start_pos': chunk.start_pos,
                    'end_pos': chunk.end_pos
                }
                for chunk in chunks
            ]
        return [{'text': prompt, 'tokens': self.calculate_token_count(prompt), 'importance': 1.0}]

    def apply_weight(self, keyword: str, weight: float = 1.1) -> str:
        """가중치 적용"""
        return self.prompt_processor.apply_weight(keyword, weight)

    def optimize_prompt(self, prompt: str, target_tokens: int = 70) -> str:
        """프롬프트 최적화"""
        return self.prompt_processor.optimize_prompt(prompt, target_tokens)

    def _add_to_history(self, history_item: Dict[str, Any]):
        """히스토리에 아이템 추가"""
        history = self.get('history', [])
        history.insert(0, history_item)  # 최신 항목을 맨 앞에 추가
        
        # 설정에서 히스토리 제한 가져오기
        history_limit = self.config.get('ui', {}).get('history_limit', 50)
        history = history[:history_limit]  # 제한된 개수만 유지
        
        self.set('history', history)
        
        # 히스토리 업데이트 이벤트 발생
        self._notify('history_updated', history)
        
        print(f"📋 히스토리에 추가됨: {history_item.get('model', 'Unknown')}")
    
    async def _notify_async(self, event: str, data: Any = None):
        """비동기 이벤트 발생"""
        self._notify(event, data)

    def get_history(self) -> List[Dict[str, Any]]:
        """히스토리 목록 반환"""
        return self.get('history', [])
    
    def clear_history(self):
        """히스토리 전체 삭제"""
        self.set('history', [])
        self._notify('history_updated', [])
        self._notify_user('히스토리가 삭제되었습니다.', 'info')
    
    def clear_all_history(self):
        """전체 히스토리 삭제 (별칭)"""
        self.clear_history()
    
    def delete_history_item(self, history_id: str):
        """히스토리 아이템 삭제"""
        history = self.get('history', [])
        history = [item for item in history if item.get('id') != history_id]
        self.set('history', history)
        self._notify('history_updated', history)
        self._notify_user('히스토리 아이템이 삭제되었습니다.', 'info')
    
    # --- LoRA 관련 메서드들 ---
    async def load_lora(self, lora_info: Dict[str, Any], weight: float = 1.0) -> bool:
        """LoRA 로드"""
        try:
            success = await self.model_loader.load_lora(lora_info, weight)
            if success:
                # 로드된 LoRA 목록 업데이트
                loaded_loras = self.model_loader.get_loaded_loras()
                self.set('loaded_loras', loaded_loras)
                self._notify('loras_updated', loaded_loras)
                self._notify_user(f"LoRA '{lora_info['name']}' 로드 완료", 'positive')
                return True
            else:
                self._notify_user(f"LoRA '{lora_info['name']}' 로드 실패", 'negative')
                return False
        except Exception as e:
            print(f"❌ LoRA 로드 오류: {e}")
            self._notify_user(f"LoRA 로드 오류: {str(e)}", 'negative')
            return False
    
    async def unload_lora(self, lora_name: str) -> bool:
        """특정 LoRA 언로드"""
        try:
            success = await self.model_loader.unload_lora(lora_name)
            if success:
                # 로드된 LoRA 목록 업데이트
                loaded_loras = self.model_loader.get_loaded_loras()
                self.set('loaded_loras', loaded_loras)
                self._notify('loras_updated', loaded_loras)
                self._notify_user(f"LoRA '{lora_name}' 언로드 완료", 'positive')
                return True
            else:
                self._notify_user(f"LoRA '{lora_name}' 언로드 실패", 'negative')
                return False
        except Exception as e:
            print(f"❌ LoRA 언로드 오류: {e}")
            self._notify_user(f"LoRA 언로드 오류: {str(e)}", 'negative')
            return False
    
    async def unload_all_loras(self) -> bool:
        """모든 LoRA 언로드"""
        try:
            success = await self.model_loader.unload_all_loras()
            if success:
                # 로드된 LoRA 목록 업데이트
                loaded_loras = self.model_loader.get_loaded_loras()
                self.set('loaded_loras', loaded_loras)
                self._notify('loras_updated', loaded_loras)
                self._notify_user("모든 LoRA 언로드 완료", 'positive')
                return True
            else:
                self._notify_user("모든 LoRA 언로드 실패", 'negative')
                return False
        except Exception as e:
            print(f"❌ 모든 LoRA 언로드 오류: {e}")
            self._notify_user(f"모든 LoRA 언로드 오류: {str(e)}", 'negative')
            return False
    
    def get_loaded_loras(self) -> List[Dict[str, Any]]:
        """로드된 LoRA 목록 반환"""
        return self.model_loader.get_loaded_loras()