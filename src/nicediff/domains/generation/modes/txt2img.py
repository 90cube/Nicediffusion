"""
텍스트-이미지 생성 모드 도메인 로직
UI나 Services에 의존하지 않는 순수한 비즈니스 로직
"""

import torch
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from typing import Union, TYPE_CHECKING, Any
if TYPE_CHECKING:
    from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import StableDiffusionPipeline
    from diffusers.pipelines.stable_diffusion_xl.pipeline_stable_diffusion_xl import StableDiffusionXLPipeline

from ..services.scheduler_manager import SchedulerManager
from ..services.advanced_encoder import AdvancedTextEncoder


@dataclass
class Txt2ImgParams:
    """텍스트-이미지 생성 파라미터"""
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    cfg_scale: float
    seed: int
    sampler: str
    scheduler: str
    batch_size: int
    model_type: str = 'SD15'
    clip_skip: int = 1  # CLIP Skip 추가
    use_custom_tokenizer: bool = True  # 고급 인코딩 설정
    weight_interpretation: str = "A1111"  # 가중치 처리 방식
    
    def __post_init__(self):
        """SD15 모델의 경우 기본값 최적화"""
        if self.model_type == 'SD15':
            # SD15에서 더 나은 품질을 위한 기본값
            if self.steps < 20:
                self.steps = 20  # 최소 steps 보장
            if self.cfg_scale < 6.0:
                self.cfg_scale = 6.0  # 최소 CFG 보장
            if not self.scheduler or self.scheduler == "default":
                self.scheduler = "karras"  # SD15에서 더 나은 품질


class Txt2ImgMode:
    """텍스트-이미지 생성 모드"""
    
    def __init__(self, pipeline: Any, device: str):
        self.pipeline = pipeline
        self.device = device
    
    def _truncate_prompt_with_tokenizer(self, text: str, max_tokens: int, tokenizer) -> str:
        """토크나이저를 사용하여 프롬프트 길이 제한"""
        if not text.strip():
            return text
            
        try:
            text_inputs = tokenizer(
                text,
                padding="longest",
                return_tensors="pt",
            )
            input_ids = text_inputs.input_ids[0]
            
            if len(input_ids) <= max_tokens:
                return text
            
            # 토큰 수를 제한하고 다시 디코딩
            truncated_ids = input_ids[:max_tokens]
            truncated_text = tokenizer.decode(truncated_ids, skip_special_tokens=True)
            
            # 잘린 부분 표시
            if len(input_ids) > max_tokens:
                print(f"⚠️ 프롬프트가 너무 깁니다 ({len(input_ids)} > {max_tokens} 토큰). 자동으로 잘립니다.")
                print(f"   잘린 부분: {text[len(truncated_text):].strip()}")
            
            return truncated_text
        except Exception as e:
            print(f"⚠️ 토큰 계산 중 오류: {e}")
            # 오류 시 간단한 추정
            words = text.split()
            if len(words) > max_tokens:
                return ' '.join(words[:max_tokens])
            return text
    
    def _apply_sd15_optimizations(self, params: Txt2ImgParams):
        """SD15 모델 최적화 설정 적용"""
        if params.model_type != 'SD15':
            return
            
        print("🔧 SD15 품질 최적화 적용 중...")
        
        # 1. 스케줄러 최적화
        if hasattr(self.pipeline.scheduler, 'config'):
            # Karras 스케줄러 최적화 (더 나은 노이즈 스케줄링)
            self.pipeline.scheduler.config.use_karras_sigmas = True
            self.pipeline.scheduler.config.karras_rho = 7.0
            
            # SD15에서 더 안정적인 생성
            if hasattr(self.pipeline.scheduler.config, 'beta_start'):
                self.pipeline.scheduler.config.beta_start = 0.00085
            if hasattr(self.pipeline.scheduler.config, 'beta_end'):
                self.pipeline.scheduler.config.beta_end = 0.012
        
        # 2. 스케줄러 타임스텝 설정
        if hasattr(self.pipeline.scheduler, 'set_timesteps'):
            self.pipeline.scheduler.set_timesteps(params.steps, device=self.device)
        
        # 3. 메모리 최적화 (더 나은 품질을 위해)
        if hasattr(self.pipeline, 'enable_attention_slicing'):
            self.pipeline.enable_attention_slicing(1)
        if hasattr(self.pipeline, 'enable_vae_slicing'):
            self.pipeline.enable_vae_slicing()
        
        # 4. PyTorch 2.0+ SDPA 최적화
        if hasattr(self.pipeline, 'enable_model_cpu_offload'):
            self.pipeline.enable_model_cpu_offload()
        
        # 5. xformers 메모리 효율적 어텐션 (선택적)
        try:
            if hasattr(self.pipeline, 'enable_xformers_memory_efficient_attention'):
                self.pipeline.enable_xformers_memory_efficient_attention()
                print("✅ xformers 메모리 효율적 어텐션 활성화")
        except (ModuleNotFoundError, AttributeError) as e:
            print(f"⚠️ xformers 미사용: {e}")
            print("✅ PyTorch 2.0+ SDPA 사용 중")
        
        # 6. 모델 정밀도 최적화
        if hasattr(self.pipeline, 'text_encoder'):
            self.pipeline.text_encoder = self.pipeline.text_encoder.to(torch.float16)
        
        if hasattr(self.pipeline, 'vae'):
            self.pipeline.vae = self.pipeline.vae.to(torch.float16)
        
        # 7. SD15 특화 품질 개선 설정
        if hasattr(self.pipeline, 'unet'):
            # UNet을 float16으로 변환하여 메모리 효율성과 속도 향상
            self.pipeline.unet = self.pipeline.unet.to(torch.float16)
        
        # 8. 추가 품질 개선 설정
        if hasattr(self.pipeline.scheduler, 'config'):
            # 더 정밀한 노이즈 스케줄링
            if hasattr(self.pipeline.scheduler.config, 'timestep_spacing'):
                self.pipeline.scheduler.config.timestep_spacing = 'trailing'
            
            # SD15에서 더 나은 품질을 위한 스케줄러 설정
            if hasattr(self.pipeline.scheduler.config, 'algorithm_type'):
                self.pipeline.scheduler.config.algorithm_type = 'dpmsolver++'
        
        print("✅ SD15 품질 최적화 완료")
    
    def _validate_scheduler_application(self, expected_sampler: str, expected_scheduler: str):
        """스케줄러 적용 검증"""
        try:
            current_scheduler = self.pipeline.scheduler.__class__.__name__
            print(f"🔍 현재 적용된 스케줄러: {current_scheduler}")
            
            # 설정 확인
            if hasattr(self.pipeline.scheduler, 'config'):
                config = self.pipeline.scheduler.config
                print(f"🔍 스케줄러 설정:")
                print(f"   - use_karras_sigmas: {getattr(config, 'use_karras_sigmas', 'N/A')}")
                print(f"   - algorithm_type: {getattr(config, 'algorithm_type', 'N/A')}")
                print(f"   - solver_order: {getattr(config, 'solver_order', 'N/A')}")
            
            return True
        except Exception as e:
            print(f"⚠️ 스케줄러 검증 실패: {e}")
            return False
    
    async def generate(self, params: Txt2ImgParams) -> List[Any]:
        """텍스트-이미지 생성 실행"""
        print(f"🎨 Txt2Img 생성 시작 - Seed: {params.seed}")
        print(f"🔧 파이프라인 호출 - Size: {params.width}x{params.height}, Batch: {params.batch_size}")
        
        # 1. 스케줄러/샘플러 실제 적용
        SchedulerManager.apply_scheduler_to_pipeline(
            self.pipeline, 
            params.sampler, 
            params.scheduler
        )
        
        # 2. CLIP Skip 실제 적용
        if params.clip_skip > 1:
            SchedulerManager.apply_clip_skip_to_pipeline(
                self.pipeline, 
                params.clip_skip
            )
        
        # 3. 스케줄러 적용 검증
        self._validate_scheduler_application(params.sampler, params.scheduler)
        
        # 고급 텍스트 인코더 사용 (77토큰 제한 해제)
        use_custom = getattr(params, 'use_custom_tokenizer', True)
        weight_mode = getattr(params, 'weight_interpretation', 'A1111')
        
        encoder = AdvancedTextEncoder(
            self.pipeline, 
            weight_mode=weight_mode,
            use_custom_tokenizer=use_custom
        )
        
        # 프롬프트 인코딩 (77토큰 제한 없음, SDXL 지원)
        print(f"📝 프롬프트 인코딩 - 모드: {weight_mode}, 커스텀: {use_custom}")
        prompt_embeds, negative_prompt_embeds, pooled_prompt_embeds, pooled_negative_prompt_embeds = encoder.encode_prompt_with_pooled(
            params.prompt, 
            params.negative_prompt
        )
        
        print(f"✅ 임베딩 생성 완료:")
        print(f"   - 긍정: {prompt_embeds.shape}")
        print(f"   - 부정: {negative_prompt_embeds.shape}")
        if pooled_prompt_embeds is not None:
            print(f"   - 긍정 pooled: {pooled_prompt_embeds.shape}")
            print(f"   - 부정 pooled: {pooled_negative_prompt_embeds.shape}")
        else:
            print(f"   - SD15 모델 (pooled 임베딩 없음)")
        
        print(f"📝 프롬프트: {params.prompt[:100]}...")
        print(f"🚫 부정 프롬프트: {params.negative_prompt[:100]}...")
        print(f"⚙️ Steps: {params.steps}, CFG: {params.cfg_scale}, Sampler: {params.sampler}, Scheduler: {params.scheduler}, CLIP Skip: {params.clip_skip}")
        
        # SD15 최적화 적용
        self._apply_sd15_optimizations(params)
        
        if params.model_type == 'SD15':
            print(f"🔧 SD15 생성 최적화 적용: Steps={params.steps}, CFG={params.cfg_scale}")
        
        def _generate():
            """실제 생성 로직"""
            import torch  # 함수 내부에서 torch import
            
            # 생성기 설정
            generator = torch.Generator(device=self.device)
            if params.seed > 0:
                generator.manual_seed(params.seed)
            
            # 기본 파라미터
            extra_params: dict = {
                'output_type': 'pil',  # PIL 이미지로 직접 반환
            }
            
            # SD15에서만 특별한 최적화 적용
            if params.model_type == 'SD15':
                extra_params['eta'] = 1.0  # DDIM 스케줄러에서 사용
                
                # guidance_rescale은 특정 스케줄러에서만 사용
                if params.scheduler in ['karras', 'exponential']:
                    extra_params['guidance_rescale'] = 0.7
            
            # 실제 파이프라인 호출 파라미터 로깅 (고급 인코더 사용, SDXL 지원)
            pipeline_params = {
                'prompt_embeds': prompt_embeds,
                'negative_prompt_embeds': negative_prompt_embeds,
                'height': params.height,
                'width': params.width,
                'num_inference_steps': params.steps,
                'guidance_scale': params.cfg_scale,
                'generator': generator,
                'num_images_per_prompt': params.batch_size,
                **extra_params
            }
            
            # SDXL 모델인 경우 pooled 임베딩 추가
            if pooled_prompt_embeds is not None:
                pipeline_params['pooled_prompt_embeds'] = pooled_prompt_embeds
                pipeline_params['negative_pooled_prompt_embeds'] = pooled_negative_prompt_embeds
                print(f"   - SDXL 모델: pooled 임베딩 추가됨")
            else:
                print(f"   - SD15 모델: 기본 임베딩만 사용")
            
            print(f"🚀 실제 파이프라인 호출 파라미터:")
            print(f"   - Steps: {pipeline_params['num_inference_steps']}")
            print(f"   - CFG: {pipeline_params['guidance_scale']}")
            print(f"   - Size: {pipeline_params['width']}x{pipeline_params['height']}")
            print(f"   - Batch: {pipeline_params['num_images_per_prompt']}")
            print(f"   - Extra: {extra_params}")
            
            try:
                result = self.pipeline(**pipeline_params)
                
                # 파이프라인 결과에서 images 반환
                if hasattr(result, 'images'):
                    return result.images
                else:
                    # result 자체가 이미지 리스트인 경우
                    return result if isinstance(result, list) else [result]
            except Exception as e:
                print(f"❌ 파이프라인 호출 중 오류: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        # 별도 스레드에서 생성 수행
        generated_images = await asyncio.to_thread(_generate)
        
        # 결과 검증
        if generated_images is None:
            print("❌ 파이프라인 호출 결과가 None입니다")
            return []
        
        if not isinstance(generated_images, list):
            generated_images = [generated_images]
        
        print(f"✅ 생성된 이미지 개수: {len(generated_images)}")
        for i, image in enumerate(generated_images):
            if hasattr(image, 'size'):
                print(f"✅ 생성된 이미지 {i+1} 크기: {image.size}")
            else:
                print(f"✅ 생성된 이미지 {i+1}: {type(image)}")
        
        return generated_images
