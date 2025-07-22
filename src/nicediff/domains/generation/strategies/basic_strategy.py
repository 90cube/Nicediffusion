from ....core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji, canvas_emoji
)
"""
기본 생성 전략
전처리, 생성, 후처리를 조율하는 전략 패턴
"""

import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..modes.txt2img import Txt2ImgMode, Txt2ImgParams
from ..modes.img2img import Img2ImgMode, Img2ImgParams
from ..processors.pre_processor import PreProcessor, PreProcessResult
from ..processors.post_processor import PostProcessor, PostProcessResult


@dataclass
class GenerationStrategyResult:
    """생성 전략 결과"""
    success: bool
    images: List[Any] = field(default_factory=list)
    post_results: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.post_results is None:
            self.post_results = []
        if self.errors is None:
            self.errors = []


class BasicGenerationStrategy:
    """기본 생성 전략"""
    
    def __init__(self, pipeline, device: str, output_dir: str = "outputs", state=None):
        self.pipeline = pipeline
        self.device = device
        self.output_dir = output_dir
        self.state = state  # StateManager 참조 추가
        
        # 도메인 컴포넌트들 초기화
        self.txt2img_mode = Txt2ImgMode(pipeline, device)
        self.img2img_mode = Img2ImgMode(pipeline, device)  # i2i 모드 추가
        self.pre_processor = PreProcessor()
        self.post_processor = PostProcessor(output_dir)
    
    async def execute(self, params: Dict[str, Any], model_info: Dict[str, Any]) -> GenerationStrategyResult:
        """전략 실행"""
        result = GenerationStrategyResult(success=False)
        
        try:
            # 1. 전처리 단계
            info(r"🔧 전처리 시작...")
            pre_result = self.pre_processor.preprocess(
                params, 
                model_info.get('model_type', 'SD15'),
                getattr(self.pipeline, 'tokenizer', None)
            )
            
            if not pre_result.is_valid:
                result.errors = pre_result.errors
                failure(f"전처리 실패: {pre_result.errors}")
                return result
            
            success(r"전처리 완료")
            
            # 2. 생성 단계
            canvas_emoji(r"생성 시작...")
            
            # i2i 모드인지 확인
            is_img2img = params.get('img2img_mode', False)
            
            if is_img2img:
                # i2i 모드: Img2Img 파라미터 변환
                init_image = params.get('init_image')
                debug_emoji(f"생성 전략에서 init_image 확인: {init_image}")
                if init_image is None:
                    failure(r"img2img 모드인데 init_image가 없습니다!")
                    # StateManager에서 다시 가져오기
                    if self.state and hasattr(self.state, 'get'):
                        init_image = self.state.get('init_image')
                        params['init_image'] = init_image
                        if init_image is not None:
                            if hasattr(init_image, 'shape'):
                                process_emoji(f"StateManager에서 init_image 복구: 크기={init_image.shape[1]}×{init_image.shape[0]}")
                            elif hasattr(init_image, 'size'):
                                process_emoji(f"StateManager에서 init_image 복구: {init_image.size}")
                            else:
                                process_emoji(f"StateManager에서 init_image 복구: {type(init_image)}")
                        else:
                            process_emoji(r"StateManager에서 init_image 복구: None")
                
                if init_image is not None:
                    if hasattr(init_image, 'shape'):
                        debug_emoji(f"생성 전략에서 이미지 크기: {init_image.shape[1]}×{init_image.shape[0]}")
                    elif hasattr(init_image, 'size'):
                        debug_emoji(f"생성 전략에서 이미지 크기: {init_image.size}, 모드: {init_image.mode}")
                    else:
                        debug_emoji(f"생성 전략에서 이미지: {type(init_image)}")
                else:
                    failure(r"생성 전략에서 init_image가 None!")
                    result.errors = ["img2img 모드에서 초기 이미지를 찾을 수 없습니다."]
                    return result
                
                img2img_params = Img2ImgParams(
                    prompt=pre_result.prompt,
                    negative_prompt=pre_result.negative_prompt,
                    init_image=init_image,  # 초기 이미지 필요
                    strength=params.get('strength', 0.8),  # Strength 값
                    width=pre_result.width,
                    height=pre_result.height,
                    steps=pre_result.steps,
                    cfg_scale=pre_result.cfg_scale,
                    seed=pre_result.seed,
                    sampler=params.get('sampler', 'dpmpp_2m'),
                    scheduler=params.get('scheduler', 'karras'),
                    batch_size=params.get('batch_size', 1),
                    model_type=model_info.get('model_type', 'SD15'),
                    clip_skip=params.get('clip_skip', 1),
                    size_match_enabled=params.get('size_match_enabled', False)  # 크기 일치 모드 추가
                )
                
                # 이미지 생성 (i2i)
                generated_images = await self.img2img_mode.generate(img2img_params)
            else:
                # txt2img 모드: Txt2Img 파라미터 변환
                txt2img_params = Txt2ImgParams(
                    prompt=pre_result.prompt,
                    negative_prompt=pre_result.negative_prompt,
                    width=pre_result.width,
                    height=pre_result.height,
                    steps=pre_result.steps,
                    cfg_scale=pre_result.cfg_scale,
                    seed=pre_result.seed,
                    sampler=params.get('sampler', 'dpmpp_2m'),
                    scheduler=params.get('scheduler', 'karras'),
                    batch_size=params.get('batch_size', 1),
                    model_type=model_info.get('model_type', 'SD15'),
                    clip_skip=params.get('clip_skip', 1)  # CLIP Skip 추가
                )
                
                # 이미지 생성 (txt2img)
                generated_images = await self.txt2img_mode.generate(txt2img_params)
            
            if generated_images is None or len(generated_images) == 0:
                result.errors = ["이미지 생성에 실패했습니다."]
                failure(r"이미지 생성 실패")
                return result
            
            result.images = generated_images
            success(f"생성 완료: {len(generated_images)}개 이미지")
            
            # 3. 후처리 단계
            info(r"💾 후처리 시작...")
            
            # 후처리용 파라미터 준비
            post_params = {
                'prompt': pre_result.prompt,
                'negative_prompt': pre_result.negative_prompt,
                'width': pre_result.width,
                'height': pre_result.height,
                'steps': pre_result.steps,
                'cfg_scale': pre_result.cfg_scale,
                'seed': pre_result.seed,
                'sampler': params.get('sampler', 'dpmpp_2m'),
                'scheduler': params.get('scheduler', 'karras'),
                'vae': params.get('vae', 'baked_in'),
                'loras': params.get('loras', [])
            }
            
            # 이미지 저장 및 메타데이터 추가
            post_results = self.post_processor.postprocess(
                generated_images, 
                post_params, 
                model_info, 
                pre_result.seed
            )
            
            result.post_results = post_results
            
            # 성공 여부 확인
            success_count = sum(1 for r in post_results if r.success)
            if success_count == len(post_results):
                result.success = True
                success(f"후처리 완료: {success_count}개 이미지 저장")
            else:
                failed_count = len(post_results) - success_count
                result.errors = [f"{failed_count}개 이미지 저장에 실패했습니다."]
                warning_emoji(f"후처리 부분 실패: {success_count}개 성공, {failed_count}개 실패")
            
        except Exception as e:
            result.errors = [f"생성 전략 실행 중 오류: {str(e)}"]
            failure(f"생성 전략 실행 중 오류: {e}")
        
        return result
    
    def cleanup(self):
        """정리 작업"""
        try:
            self.post_processor.cleanup_old_files()
        except Exception as e:
            warning_emoji(f"정리 작업 중 오류: {e}")
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """생성 히스토리 조회"""
        return self.post_processor.get_generation_history(limit)
