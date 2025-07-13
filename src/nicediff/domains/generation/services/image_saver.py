"""
이미지 저장 도메인 서비스
UI나 StateManager에 의존하지 않는 순수한 비즈니스 로직
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, PngImagePlugin

from ..models.generation_params import GenerationParams


class ImageSaver:
    """이미지 저장 서비스"""
    
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    async def save_generated_image(self, image: Image.Image, params: GenerationParams, seed: int, model_name: str) -> dict:
        """생성된 이미지를 저장하고 메타데이터를 포함한 결과를 반환"""
        
        def _save():
            # 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_{timestamp}_{seed}.png"
            filepath = self.output_dir / filename
            
            # 메타데이터 생성
            metadata = self._build_metadata_string(params, seed, model_name)
            pnginfo = self._create_pnginfo(metadata)
            
            # 이미지 저장
            image.save(filepath, "PNG", pnginfo=pnginfo)
            
            # 썸네일 생성 및 저장
            thumbnail_path = self._save_thumbnail(image, filename)
            
            return {
                'image_path': str(filepath),
                'thumbnail_path': str(thumbnail_path),
                'metadata': metadata
            }
        
        return await asyncio.to_thread(_save)
    
    def _build_metadata_string(self, params: GenerationParams, seed: int, model_name: str) -> str:
        """메타데이터 문자열 생성"""
        metadata_parts = [
            f"Model: {model_name}",
            f"Seed: {seed}",
            f"Steps: {params.steps}",
            f"CFG Scale: {params.cfg_scale}",
            f"Sampler: {params.sampler}",
            f"Scheduler: {params.scheduler}",
            f"CLIP Skip: {getattr(params, 'clip_skip', 1)}",  # CLIP Skip 추가
            f"Size: {params.width}x{params.height}",
            f"Prompt: {params.prompt}",
            f"Negative prompt: {params.negative_prompt}"
        ]
        return ", ".join(metadata_parts)
    
    def _create_pnginfo(self, metadata: str) -> PngImagePlugin.PngInfo:
        """PNG 메타데이터 생성"""
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("parameters", metadata)
        return pnginfo
    
    def _save_thumbnail(self, image: Image.Image, original_filename: str) -> Path:
        """썸네일 생성 및 저장"""
        # 썸네일 크기 (150x150)
        thumbnail_size = (150, 150)
        
        # 원본 비율 유지하면서 썸네일 생성
        image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        
        # 썸네일 파일명
        thumbnail_filename = f"thumb_{original_filename}"
        thumbnail_path = self.output_dir / thumbnail_filename
        
        # 썸네일 저장
        image.save(thumbnail_path, "PNG")
        
        return thumbnail_path 