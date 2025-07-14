"""
이미지-이미지 생성 모드 도메인 로직
UI나 Services에 의존하지 않는 순수한 비즈니스 로직
"""

import torch
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from PIL import Image


@dataclass
class Img2ImgParams:
    """이미지-이미지 생성 파라미터"""
    prompt: str
    negative_prompt: str
    init_image: Image.Image
    strength: float  # 0.0 ~ 1.0 (0.0: 원본 유지, 1.0: 완전히 새로 생성)
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


class Img2ImgMode:
    """이미지-이미지 생성 모드 (A1111 스타일)"""
    
    def __init__(self, pipeline: Any, device: str):
        self.pipeline = pipeline
        self.device = device
    
    def _encode_image(self, image: Image.Image) -> torch.Tensor:
        """이미지를 latent space로 인코딩 (A1111 스타일)"""
        print(f"🔍 이미지 인코딩 시작: 크기={image.size}, 모드={image.mode}")
        
        with torch.no_grad():
            # 이미지 전처리
            if hasattr(self.pipeline, 'image_processor'):
                # StableDiffusionImg2ImgPipeline의 경우
                image_tensor = self.pipeline.image_processor.preprocess(image)
            else:
                # 일반 StableDiffusionPipeline의 경우
                from diffusers.utils import PIL_INTERPOLATION
                image_tensor = self.pipeline.feature_extractor(
                    image, 
                    return_tensors="pt"
                ).pixel_values
            
            image_tensor = image_tensor.to(self.device)
            
            # VAE 인코딩
            latent = self.pipeline.vae.encode(image_tensor).latent_dist.sample()
            latent = latent * self.pipeline.vae.config.scaling_factor
            
            print(f"✅ 이미지 인코딩 완료: latent shape={latent.shape}")
            return latent
    
    def _validate_init_image(self, init_image: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """초기 이미지 검증 및 리사이즈 (img2img에서는 원본 크기 우선)"""
        if init_image is None:
            raise ValueError("초기 이미지가 필요합니다.")
        
        # img2img 모드에서는 원본 이미지 크기를 우선적으로 사용
        # 파라미터의 width/height는 참고용으로만 사용
        original_size = init_image.size
        print(f"🔍 원본 이미지 크기: {original_size}")
        print(f"🔍 파라미터 크기: ({target_width}, {target_height})")
        
        # 원본 크기를 그대로 사용 (리사이즈하지 않음)
        print(f"✅ 원본 이미지 크기 유지: {original_size}")
        return init_image
    
    def _validate_strength(self, strength: float) -> float:
        """강도 값 검증"""
        if strength < 0.0 or strength > 1.0:
            raise ValueError("강도 값은 0.0 ~ 1.0 사이여야 합니다.")
        return strength
    
    def _apply_sd15_optimizations(self, params: Img2ImgParams):
        """SD15 모델 최적화 설정 적용"""
        if params.model_type != 'SD15':
            return
            
        # SD15에서 더 정확한 결과를 위한 설정
        if hasattr(self.pipeline.scheduler, 'config'):
            self.pipeline.scheduler.config.use_karras_sigmas = True
            self.pipeline.scheduler.config.karras_rho = 7.0
        
        # SD15에서 더 나은 노이즈 스케줄링
        if hasattr(self.pipeline.scheduler, 'set_timesteps'):
            self.pipeline.scheduler.set_timesteps(params.steps, device=self.device)
        
        # SD15에서 더 안정적인 생성
        if hasattr(self.pipeline.scheduler, 'beta_start'):
            self.pipeline.scheduler.beta_start = 0.00085
        if hasattr(self.pipeline.scheduler, 'beta_end'):
            self.pipeline.scheduler.beta_end = 0.012
        
        # SD15에서 더 선명한 결과를 위한 설정
        if hasattr(self.pipeline, 'enable_attention_slicing'):
            self.pipeline.enable_attention_slicing(1)
        if hasattr(self.pipeline, 'enable_vae_slicing'):
            self.pipeline.enable_vae_slicing()
        
        # xformers는 선택적 기능이므로 안전하게 처리
        try:
            if hasattr(self.pipeline, 'enable_xformers_memory_efficient_attention'):
                self.pipeline.enable_xformers_memory_efficient_attention()
        except ModuleNotFoundError:
            pass  # 조용히 무시
    
    async def generate(self, params: Img2ImgParams) -> List[Any]:
        """이미지-이미지 생성 실행 (A1111 스타일)"""
        print(f"🎨 Img2Img 생성 시작 - Seed: {params.seed}, Strength: {params.strength}")
        print(f"🔧 파이프라인 호출 - Size: {params.width}x{params.height}, Batch: {params.batch_size}")
        
        # 디버그: 초기 이미지 확인
        print(f"🔍 Img2Img 모드에서 init_image 확인: {params.init_image}")
        if params.init_image:
            print(f"🔍 Img2Img 모드에서 이미지 크기: {params.init_image.size}, 모드: {params.init_image.mode}")
        else:
            print(f"❌ Img2Img 모드에서 init_image가 None!")
            return []
        
        # 파라미터 검증
        init_image = self._validate_init_image(params.init_image, params.width, params.height)
        strength = self._validate_strength(params.strength)
        
        print(f"📝 프롬프트: {params.prompt[:100]}...")
        print(f"🚫 부정 프롬프트: {params.negative_prompt[:100]}...")
        print(f"⚙️ Steps: {params.steps}, CFG: {params.cfg_scale}, Strength: {strength}")
        
        # SD15 최적화 적용
        self._apply_sd15_optimizations(params)
        
        if params.model_type == 'SD15':
            print(f"🔧 SD15 생성 최적화 적용: Steps={params.steps}, CFG={params.cfg_scale}")
        
        # 생성기 설정
        generator = torch.Generator(device=self.device)
        if params.seed > 0:
            generator.manual_seed(params.seed)
        
        def _generate():
            """실제 생성 로직 (단순화된 방식)"""
            print(f"🔍 파이프라인 타입: {type(self.pipeline)}")
            print(f"🔍 Strength 값 확인: {strength} (0.0=원본 유지, 1.0=완전 새로 생성)")
            print(f"🔍 전달할 이미지 크기: {init_image.size}")
            
            # SDXL 모델의 경우 직접 image 파라미터 사용 (더 안전)
            try:
                result = self.pipeline(
                    prompt=params.prompt,
                    negative_prompt=params.negative_prompt,
                    image=init_image,  # 직접 이미지 전달
                    strength=strength,
                    width=init_image.size[0],  # 원본 이미지 크기 사용
                    height=init_image.size[1],  # 원본 이미지 크기 사용
                    num_inference_steps=params.steps,
                    guidance_scale=params.cfg_scale,
                    generator=generator,
                    num_images_per_prompt=params.batch_size
                )
                
                # 파이프라인 결과에서 images 반환
                if hasattr(result, 'images'):
                    return result.images
                else:
                    # result 자체가 이미지 리스트인 경우
                    return result if isinstance(result, list) else [result]
                    
            except Exception as e:
                print(f"❌ 파이프라인 호출 실패: {e}")
                # 폴백: 더 간단한 방식으로 재시도
                try:
                    result = self.pipeline(
                        prompt=params.prompt,
                        negative_prompt=params.negative_prompt,
                        image=init_image,
                        strength=strength,
                        width=init_image.size[0],  # 원본 이미지 크기 사용
                        height=init_image.size[1],  # 원본 이미지 크기 사용
                        num_inference_steps=params.steps,
                        guidance_scale=params.cfg_scale,
                        generator=generator
                    )
                    
                    if hasattr(result, 'images'):
                        return result.images
                    else:
                        return result if isinstance(result, list) else [result]
                        
                except Exception as e2:
                    print(f"❌ 폴백 방식도 실패: {e2}")
                    return []
        
        # 별도 스레드에서 생성 수행
        generated_images = await asyncio.to_thread(_generate)
        
        print(f"✅ 생성된 이미지 개수: {len(generated_images)}")
        for i, image in enumerate(generated_images):
            print(f"✅ 생성된 이미지 {i+1} 크기: {image.size}")
        
        return generated_images
    
    async def upscale(self, image: Image.Image, scale_factor: float = 2.0) -> Image.Image:
        """이미지 업스케일 (간단한 구현)"""
        if scale_factor <= 1.0:
            return image
        
        new_width = int(image.width * scale_factor)
        new_height = int(image.height * scale_factor)
        
        print(f"🔄 업스케일: {image.size} -> ({new_width}, {new_height})")
        
        # 고품질 리사이즈
        upscaled_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return upscaled_image
    
    async def inpaint(self, image: Image.Image, mask: Image.Image, prompt: str, 
                     negative_prompt: str = "", strength: float = 0.8) -> List[Any]:
        """인페인팅 (마스크 기반 이미지 수정)"""
        print(f"🎨 인페인팅 시작 - Strength: {strength}")
        
        # 마스크 검증
        if mask.size != image.size:
            print(f"🔄 마스크 크기 조정: {mask.size} -> {image.size}")
            mask = mask.resize(image.size, Image.Resampling.LANCZOS)
        
        # 생성기 설정
        generator = torch.Generator(device=self.device)
        generator.manual_seed(int(torch.randint(0, 2**32 - 1, (1,)).item()))
        
        def _inpaint():
            """인페인팅 생성 로직"""
            # 인페인팅 파이프라인 호출 (파이프라인이 지원하는 경우)
            if hasattr(self.pipeline, 'inpaint'):
                result = self.pipeline.inpaint(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    image=image,
                    mask_image=mask,
                    strength=strength,
                    generator=generator,
                    num_inference_steps=20,
                    guidance_scale=7.0
                )
                return result.images if hasattr(result, 'images') else [result]
            else:
                # 인페인팅을 지원하지 않는 경우 일반 img2img로 대체
                print("⚠️ 인페인팅을 지원하지 않는 파이프라인입니다. 일반 img2img로 대체합니다.")
                return self.pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    image=image,
                    strength=strength,
                    generator=generator,
                    num_inference_steps=20,
                    guidance_scale=7.0
                ).images
        
        # 별도 스레드에서 생성 수행
        generated_images = await asyncio.to_thread(_inpaint)
        
        print(f"✅ 인페인팅 완료: {len(generated_images)}개 이미지")
        return generated_images
