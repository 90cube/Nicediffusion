"""
Hires Fix 전략
저해상도 생성 후 고해상도로 업스케일하는 고급 전략
"""

import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from PIL import Image
from ..modes.txt2img import Txt2ImgMode, Txt2ImgParams
from ..modes.img2img import Img2ImgMode, Img2ImgParams
from ..processors.pre_processor import PreProcessor, PreProcessResult
from ..processors.post_processor import PostProcessor, PostProcessResult
from .basic_strategy import GenerationStrategyResult


@dataclass
class HiresFixParams:
    """Hires Fix 파라미터"""
    # 1단계: 저해상도 생성
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
    hires_width: int
    hires_height: int
    hires_steps: int
    hires_cfg_scale: float
    model_type: str = 'SD15'
    denoising_strength: float = 0.7  # 0.0 ~ 1.0
    upscaler: str = 'latent'  # 'latent', 'latent_antialiased', ...


class HiresFixStrategy:
    """Hires Fix 전략"""
    
    def __init__(self, pipeline, device: str, output_dir: str = "outputs"):
        self.pipeline = pipeline
        self.device = device
        self.output_dir = output_dir
        
        # 도메인 컴포넌트들 초기화
        self.txt2img_mode = Txt2ImgMode(pipeline, device)
        self.img2img_mode = Img2ImgMode(pipeline, device)
        self.pre_processor = PreProcessor()
        self.post_processor = PostProcessor(output_dir)
    
    def _calculate_low_res_dimensions(self, target_width: int, target_height: int, model_type: str) -> tuple[int, int]:
        """저해상도 크기 계산"""
        if model_type == 'SD15':
            # SD15: 최소 512, 8의 배수
            base_size = 512
        else:  # SDXL
            # SDXL: 최소 1024, 8의 배수
            base_size = 1024
        
        # 비율 유지하면서 저해상도 계산
        ratio = min(target_width / base_size, target_height / base_size)
        low_width = int(target_width / ratio)
        low_height = int(target_height / ratio)
        
        # 8의 배수로 조정
        low_width = low_width - (low_width % 8)
        low_height = low_height - (low_height % 8)
        
        # 최소 크기 보장
        low_width = max(base_size, low_width)
        low_height = max(base_size, low_height)
        
        return low_width, low_height
    
    async def execute(self, params: Dict[str, Any], model_info: Dict[str, Any]) -> GenerationStrategyResult:
        """Hires Fix 전략 실행"""
        result = GenerationStrategyResult(success=False)
        
        try:
            # 파라미터 추출
            hires_params = HiresFixParams(
                prompt=params.get('prompt', ''),
                negative_prompt=params.get('negative_prompt', ''),
                width=params.get('width', 512),
                height=params.get('height', 512),
                steps=params.get('steps', 20),
                cfg_scale=params.get('cfg_scale', 7.0),
                seed=params.get('seed', -1),
                sampler=params.get('sampler', 'dpmpp_2m'),
                scheduler=params.get('scheduler', 'karras'),
                batch_size=params.get('batch_size', 1),
                hires_width=params.get('hires_width', params.get('width', 512)),
                hires_height=params.get('hires_height', params.get('height', 512)),
                hires_steps=params.get('hires_steps', params.get('steps', 20)),
                hires_cfg_scale=params.get('hires_cfg_scale', params.get('cfg_scale', 7.0)),
                denoising_strength=params.get('denoising_strength', 0.7),
                upscaler=params.get('upscaler', 'latent')
            )
            
            print(f"🎯 Hires Fix 전략 시작")
            print(f"📐 목표 해상도: {hires_params.hires_width}x{hires_params.hires_height}")
            
            # 1단계: 저해상도 크기 계산
            low_width, low_height = self._calculate_low_res_dimensions(
                hires_params.hires_width, 
                hires_params.hires_height, 
                hires_params.model_type
            )
            print(f"📐 저해상도 생성: {low_width}x{low_height}")
            
            # 2단계: 전처리
            print("🔧 전처리 시작...")
            pre_result = self.pre_processor.preprocess(
                {
                    'prompt': hires_params.prompt,
                    'negative_prompt': hires_params.negative_prompt,
                    'width': low_width,
                    'height': low_height,
                    'steps': hires_params.steps,
                    'cfg_scale': hires_params.cfg_scale,
                    'seed': hires_params.seed
                },
                hires_params.model_type,
                getattr(self.pipeline, 'tokenizer', None)
            )
            
            if not pre_result.is_valid:
                result.errors = pre_result.errors
                print(f"❌ 전처리 실패: {pre_result.errors}")
                return result
            
            print("✅ 전처리 완료")
            
            # 3단계: 저해상도 생성
            print("🎨 1단계: 저해상도 생성 시작...")
            
            txt2img_params = Txt2ImgParams(
                prompt=pre_result.prompt,
                negative_prompt=pre_result.negative_prompt,
                width=low_width,
                height=low_height,
                steps=hires_params.steps,
                cfg_scale=hires_params.cfg_scale,
                seed=hires_params.seed,
                sampler=hires_params.sampler,
                scheduler=hires_params.scheduler,
                batch_size=hires_params.batch_size,
                model_type=hires_params.model_type
            )
            
            low_res_images = await self.txt2img_mode.generate(txt2img_params)
            
            if not low_res_images:
                result.errors = ["저해상도 이미지 생성에 실패했습니다."]
                print("❌ 저해상도 이미지 생성 실패")
                return result
            
            print(f"✅ 저해상도 생성 완료: {len(low_res_images)}개 이미지")
            
            # 4단계: 고해상도 업스케일
            print("🔄 2단계: 고해상도 업스케일 시작...")
            
            high_res_images = []
            for i, low_res_image in enumerate(low_res_images):
                print(f"🔄 이미지 {i+1} 업스케일 중...")
                
                # 이미지 크기 조정
                if low_res_image.size != (hires_params.hires_width, hires_params.hires_height):
                    low_res_image = low_res_image.resize(
                        (hires_params.hires_width, hires_params.hires_height), 
                        Image.Resampling.LANCZOS
                    )
                
                # img2img로 고해상도 개선
                img2img_params = Img2ImgParams(
                    prompt=hires_params.prompt,
                    negative_prompt=hires_params.negative_prompt,
                    init_image=low_res_image,
                    strength=hires_params.denoising_strength,
                    width=hires_params.hires_width,
                    height=hires_params.hires_height,
                    steps=hires_params.hires_steps,
                    cfg_scale=hires_params.hires_cfg_scale,
                    seed=hires_params.seed + i,  # 각 이미지마다 다른 시드
                    sampler=hires_params.sampler,
                    scheduler=hires_params.scheduler,
                    batch_size=1,  # 업스케일은 1개씩
                    model_type=hires_params.model_type
                )
                
                upscaled_images = await self.img2img_mode.generate(img2img_params)
                if upscaled_images:
                    high_res_images.extend(upscaled_images)
            
            if not high_res_images:
                result.errors = ["고해상도 업스케일 실패"]
                print("❌ 고해상도 업스케일 실패")
                return result
            
            result.images = high_res_images
            print(f"✅ 고해상도 업스케일 완료: {len(high_res_images)}개 이미지")
            
            # 5단계: 후처리
            print("💾 후처리 시작...")
            
            # 후처리용 파라미터 준비
            post_params = {
                'prompt': pre_result.prompt,
                'negative_prompt': pre_result.negative_prompt,
                'width': hires_params.hires_width,
                'height': hires_params.hires_height,
                'steps': hires_params.hires_steps,
                'cfg_scale': hires_params.hires_cfg_scale,
                'seed': hires_params.seed,
                'sampler': hires_params.sampler,
                'scheduler': hires_params.scheduler,
                'vae': params.get('vae', 'baked_in'),
                'loras': params.get('loras', []),
                'hires_fix': True,
                'denoising_strength': hires_params.denoising_strength,
                'upscaler': hires_params.upscaler
            }
            
            # 이미지 저장 및 메타데이터 추가
            post_results = self.post_processor.postprocess(
                high_res_images, 
                post_params, 
                model_info, 
                hires_params.seed
            )
            
            result.post_results = post_results
            
            # 성공 여부 확인
            success_count = sum(1 for r in post_results if r.success)
            if success_count == len(post_results):
                result.success = True
                print(f"✅ Hires Fix 완료: {success_count}개 이미지 저장")
            else:
                failed_count = len(post_results) - success_count
                result.errors = [f"{failed_count}개 이미지 저장에 실패했습니다."]
                print(f"⚠️ 후처리 부분 실패: {success_count}개 성공, {failed_count}개 실패")
            
        except Exception as e:
            result.errors = [f"Hires Fix 전략 실행 중 오류: {str(e)}"]
            print(f"❌ Hires Fix 전략 실행 중 오류: {e}")
        
        return result
    
    def cleanup(self):
        """정리 작업"""
        try:
            self.post_processor.cleanup_old_files()
        except Exception as e:
            print(f"⚠️ 정리 작업 중 오류: {e}")
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """생성 히스토리 조회"""
        return self.post_processor.get_generation_history(limit) 