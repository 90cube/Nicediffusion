"""
Upscale 모드 구현
Stable Diffusion Upscale Pipeline을 사용한 이미지 업스케일링
"""

import torch
import torch.nn.functional as F
from PIL import Image
from typing import Dict, Any, Optional, Union, List
from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion_upscale import StableDiffusionUpscalePipeline

from ..model_definitions.generation_params import GenerationParams
from ..processors.prompt_processor import PromptProcessor
from ..processors.pre_processor import PreProcessor
from ..processors.post_processor import PostProcessor
from src.nicediff.core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)


class UpscaleMode:
    """이미지 업스케일링 모드"""
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.pipeline = None
        self.prompt_processor = PromptProcessor('SD15')
        self.pre_processor = PreProcessor()
        self.post_processor = PostProcessor()
        
    async def load_pipeline(self, model_path: str) -> bool:
        """업스케일 파이프라인 로드"""
        try:
            process_emoji("업스케일 파이프라인 로드 시작")
            
            # Stable Diffusion Upscale Pipeline 로드
            self.pipeline = StableDiffusionUpscalePipeline.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                safety_checker=None,
                requires_safety_checker=False
            )
            
            # 디바이스로 이동
            self.pipeline = self.pipeline.to(self.device)
            
            # 메모리 최적화
            if self.device == "cuda":
                self.pipeline.enable_attention_slicing()
                self.pipeline.enable_vae_slicing()
                
            success("업스케일 파이프라인 로드 완료")
            return True
            
        except Exception as e:
            failure(f"업스케일 파이프라인 로드 실패: {e}")
            return False
    
    async def generate(
        self, 
        params: GenerationParams, 
        init_image: Image.Image,
        prompt: str = "",
        negative_prompt: str = ""
    ) -> List[Image.Image]:
        """이미지 업스케일링 생성"""
        
        try:
            process_emoji("업스케일 생성 시작")
            
            if self.pipeline is None:
                raise ValueError("업스케일 파이프라인이 로드되지 않았습니다")
            
            # 이미지 전처리
            processed_image = self.pre_processor.process_image(init_image)
            
            # 프롬프트 처리
            if not prompt:
                prompt = "high quality, detailed, sharp"
            
            if not negative_prompt:
                negative_prompt = "blurry, low quality, pixelated"
            
            # 업스케일 파라미터 설정
            upscale_params = {
                'prompt': prompt,
                'image': processed_image,
                'num_inference_steps': params.steps,
                'guidance_scale': params.cfg_scale,
                'negative_prompt': negative_prompt,
                'num_images_per_prompt': params.batch_size,
                'output_type': 'pil'
            }
            
            # 시드 설정
            if params.seed != -1:
                generator = torch.Generator(device=self.device).manual_seed(params.seed)
                upscale_params['generator'] = generator
            
            # 업스케일링 실행
            result = self.pipeline(**upscale_params)
            
            # 결과 후처리
            upscaled_images = []
            for image in result.images:
                processed_image = self.post_processor.process_image(image)
                upscaled_images.append(processed_image)
            
            success(f"업스케일 생성 완료: {len(upscaled_images)}개 이미지")
            return upscaled_images
            
        except Exception as e:
            failure(f"업스케일 생성 실패: {e}")
            return []
    
    async def simple_upscale(
        self, 
        image: Image.Image, 
        scale_factor: float = 2.0,
        method: str = "bicubic"
    ) -> Image.Image:
        """간단한 업스케일링 (AI 없이)"""
        
        try:
            process_emoji("간단한 업스케일링 시작")
            
            # 원본 크기
            original_width, original_height = image.size
            
            # 새로운 크기 계산
            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)
            
            # 업스케일링
            upscaled_image = image.resize((new_width, new_height), Image.Resampling.BICUBIC)
            
            success(f"간단한 업스케일링 완료: {original_width}x{original_height} → {new_width}x{new_height}")
            return upscaled_image
            
        except Exception as e:
            failure(f"간단한 업스케일링 실패: {e}")
            return image
    
    async def ai_upscale(
        self, 
        image: Image.Image, 
        prompt: str = "",
        negative_prompt: str = "",
        strength: float = 0.8,
        steps: int = 20
    ) -> List[Image.Image]:
        """AI 기반 업스케일링"""
        
        try:
            process_emoji("AI 업스케일링 시작")
            
            if self.pipeline is None:
                raise ValueError("업스케일 파이프라인이 로드되지 않았습니다")
            
            # 기본 프롬프트 설정
            if not prompt:
                prompt = "high quality, detailed, sharp, 4k resolution"
            
            if not negative_prompt:
                negative_prompt = "blurry, low quality, pixelated, artifacts"
            
            # 파라미터 설정
            params = GenerationParams()
            params.steps = steps
            params.cfg_scale = 7.5
            params.batch_size = 1
            params.seed = -1  # 랜덤 시드
            
            # AI 업스케일링 실행
            result = await self.generate(params, image, prompt, negative_prompt)
            
            success("AI 업스케일링 완료")
            return result
            
        except Exception as e:
            failure(f"AI 업스케일링 실패: {e}")
            return []
    
    def get_supported_models(self) -> List[str]:
        """지원되는 업스케일 모델 목록"""
        return [
            "stabilityai/stable-diffusion-x4-upscaler",
            "stabilityai/stable-diffusion-2-1-base",
            "runwayml/stable-diffusion-v1-5"
        ]
    
    def cleanup(self):
        """리소스 정리"""
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        info("업스케일 모드 리소스 정리 완료") 