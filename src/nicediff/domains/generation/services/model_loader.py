"""
모델 로딩 도메인 서비스
UI나 StateManager에 의존하지 않는 순수한 비즈니스 로직
"""

import asyncio
from typing import Dict, Any, Optional, Union, List
from pathlib import Path

import torch
from diffusers import AutoencoderKL
from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import StableDiffusionPipeline
from diffusers.pipelines.stable_diffusion_xl.pipeline_stable_diffusion_xl import StableDiffusionXLPipeline


class ModelLoader:
    """모델 로딩 서비스"""
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.current_pipeline: Optional[Union[StableDiffusionPipeline, StableDiffusionXLPipeline]] = None
        self.loaded_loras: List[Dict[str, Any]] = []  # 로드된 LoRA 목록
    
    async def load_model(self, model_info: Dict[str, Any]) -> Union[StableDiffusionPipeline, StableDiffusionXLPipeline]:
        """모델을 로드하고 최적화 설정을 적용"""
        
        def _load():
            model_path = model_info['path']
            model_type = model_info.get('model_type', 'SD15')
            
            print(f"🔍 모델 타입: {model_type}, 경로: {model_path}")
            
            if model_type == 'SDXL':
                pipeline = StableDiffusionXLPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True
                )
            else:
                pipeline = StableDiffusionPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16,
                    use_safetensors=True
                )
            
            # GPU로 이동
            pipeline = pipeline.to(self.device)
            
            # 최적화 설정 적용
            self._apply_optimizations(pipeline, model_type)
            
            return pipeline
        
        self.current_pipeline = await asyncio.to_thread(_load)
        # 모델 로드 시 기존 LoRA 목록 초기화
        self.loaded_loras = []
        return self.current_pipeline
    
    def _apply_optimizations(self, pipeline: Union[StableDiffusionPipeline, StableDiffusionXLPipeline], model_type: str):
        """모델 최적화 설정 적용"""
        
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
            print(f"ℹ️ xformers 미사용: {e}")
        
        # SD15 전용 최적화
        if model_type == 'SD15':
            self._apply_sd15_optimizations(pipeline)
    
    def _apply_sd15_optimizations(self, pipeline: StableDiffusionPipeline):
        """SD15 모델 전용 최적화"""
        # Text Encoder를 float16으로 변환
        if hasattr(pipeline, 'text_encoder') and pipeline.text_encoder is not None:
            pipeline.text_encoder = pipeline.text_encoder.to(torch.float16)
        
        # VAE를 float16으로 변환
        if hasattr(pipeline, 'vae') and pipeline.vae is not None:
            pipeline.vae = pipeline.vae.to(torch.float16)
        
        # SD15에서 더 나은 품질을 위한 스케줄러 설정
        if hasattr(pipeline.scheduler, 'config'):
            pipeline.scheduler.config.use_karras_sigmas = True
            pipeline.scheduler.config.karras_rho = 7.0
        
        print("🔧 SD15 최적화 설정 적용 완료")
    
    async def load_vae(self, vae_path: str) -> bool:
        """VAE 로드"""
        if not self.current_pipeline:
            return False
        
        def _load_vae():
            vae = AutoencoderKL.from_single_file(
                vae_path,
                torch_dtype=torch.float16
            )
            self.current_pipeline.vae = vae.to(self.device)
            return True
        
        return await asyncio.to_thread(_load_vae)
    
    async def load_lora(self, lora_info: Dict[str, Any], weight: float = 1.0) -> bool:
        """LoRA 로드"""
        if not self.current_pipeline:
            print("❌ 모델이 로드되지 않았습니다.")
            return False
        
        try:
            lora_path = lora_info['path']
            lora_name = Path(lora_path).stem
            
            def _load_lora():
                # LoRA 로드
                self.current_pipeline.load_lora_weights(
                    lora_path,
                    adapter_name=lora_name,
                    weight=weight
                )
                return True
            
            success = await asyncio.to_thread(_load_lora)
            
            if success:
                # 로드된 LoRA 정보 저장
                loaded_lora = {
                    'name': lora_name,
                    'path': lora_path,
                    'weight': weight,
                    'info': lora_info
                }
                self.loaded_loras.append(loaded_lora)
                print(f"✅ LoRA 로드 완료: {lora_name} (weight: {weight})")
                return True
            else:
                print(f"❌ LoRA 로드 실패: {lora_name}")
                return False
                
        except Exception as e:
            print(f"❌ LoRA 로드 오류: {e}")
            return False
    
    async def unload_lora(self, lora_name: str) -> bool:
        """특정 LoRA 언로드"""
        if not self.current_pipeline:
            return False
        
        try:
            def _unload_lora():
                # LoRA 언로드
                self.current_pipeline.unload_lora_weights()
                return True
            
            success = await asyncio.to_thread(_unload_lora)
            
            if success:
                # 로드된 LoRA 목록에서 제거
                self.loaded_loras = [lora for lora in self.loaded_loras if lora['name'] != lora_name]
                print(f"✅ LoRA 언로드 완료: {lora_name}")
                return True
            else:
                print(f"❌ LoRA 언로드 실패: {lora_name}")
                return False
                
        except Exception as e:
            print(f"❌ LoRA 언로드 오류: {e}")
            return False
    
    async def unload_all_loras(self) -> bool:
        """모든 LoRA 언로드"""
        if not self.current_pipeline:
            return False
        
        try:
            def _unload_all_loras():
                # 모든 LoRA 언로드
                self.current_pipeline.unload_lora_weights()
                return True
            
            success = await asyncio.to_thread(_unload_all_loras)
            
            if success:
                self.loaded_loras = []
                print("✅ 모든 LoRA 언로드 완료")
                return True
            else:
                print("❌ 모든 LoRA 언로드 실패")
                return False
                
        except Exception as e:
            print(f"❌ 모든 LoRA 언로드 오류: {e}")
            return False
    
    def get_loaded_loras(self) -> List[Dict[str, Any]]:
        """로드된 LoRA 목록 반환"""
        return self.loaded_loras.copy()
    
    def unload_model(self):
        """모델 언로드"""
        if self.current_pipeline:
            # GPU 메모리에서 제거
            del self.current_pipeline
            self.current_pipeline = None
            
            # LoRA 목록 초기화
            self.loaded_loras = []
            
            # CUDA 캐시 정리
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            print("✅ 기존 모델 언로드 완료")
    
    def get_current_pipeline(self) -> Optional[Union[StableDiffusionPipeline, StableDiffusionXLPipeline]]:
        """현재 로드된 파이프라인 반환"""
        return self.current_pipeline 