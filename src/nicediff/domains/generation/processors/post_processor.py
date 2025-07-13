"""
후처리기 도메인 로직
이미지 저장, 메타데이터 추가, 품질 개선 등을 담당
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from PIL import Image, PngImagePlugin


@dataclass
class PostProcessResult:
    """후처리 결과"""
    image_path: str
    thumbnail_path: str
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class PostProcessor:
    """후처리기"""
    
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def _generate_filename(self, seed: int, timestamp: datetime = None) -> str:
        """파일명 생성"""
        if timestamp is None:
            timestamp = datetime.now()
        
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        return f"generated_{timestamp_str}_{seed}.png"
    
    def _create_thumbnail(self, image: Image.Image, max_size: int = 256) -> Image.Image:
        """썸네일 생성"""
        # 원본 비율 유지하면서 리사이즈
        ratio = min(max_size / image.width, max_size / image.height)
        new_width = int(image.width * ratio)
        new_height = int(image.height * ratio)
        
        thumbnail = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        return thumbnail
    
    def _add_metadata(self, image: Image.Image, params: Dict[str, Any], model_info: Dict[str, Any]) -> Image.Image:
        """PNG 메타데이터 추가"""
        # 메타데이터 준비
        metadata = {
            'prompt': params.get('prompt', ''),
            'negative_prompt': params.get('negative_prompt', ''),
            'width': params.get('width', 512),
            'height': params.get('height', 512),
            'steps': params.get('steps', 20),
            'cfg_scale': params.get('cfg_scale', 7.0),
            'seed': params.get('seed', -1),
            'sampler': params.get('sampler', 'dpmpp_2m'),
            'scheduler': params.get('scheduler', 'karras'),
            'model_name': model_info.get('name', ''),
            'model_type': model_info.get('model_type', ''),
            'vae': params.get('vae', 'baked_in'),
            'generator': 'NiceDiffusion',
            'generation_time': datetime.now().isoformat(),
        }
        
        # LoRA 정보 추가
        loras = params.get('loras', [])
        if loras:
            metadata['loras'] = loras
        
        # PNG 메타데이터로 추가
        meta = PngImagePlugin.PngInfo()
        for key, value in metadata.items():
            if isinstance(value, (list, dict)):
                import json
                meta.add_text(key, json.dumps(value))
            else:
                meta.add_text(key, str(value))
        
        return image, meta
    
    def _save_image(self, image: Image.Image, filename: str, metadata: PngImagePlugin.PngInfo = None) -> str:
        """이미지 저장"""
        filepath = self.output_dir / filename
        
        # 메타데이터와 함께 저장
        if metadata:
            image.save(filepath, 'PNG', pnginfo=metadata)
        else:
            image.save(filepath, 'PNG')
        
        return str(filepath)
    
    def _save_thumbnail(self, thumbnail: Image.Image, filename: str) -> str:
        """썸네일 저장"""
        # 썸네일용 디렉토리
        thumb_dir = self.output_dir / "thumbnails"
        thumb_dir.mkdir(exist_ok=True)
        
        # 파일명에 _thumb 접미사 추가
        name, ext = os.path.splitext(filename)
        thumb_filename = f"{name}_thumb{ext}"
        thumb_path = thumb_dir / thumb_filename
        
        thumbnail.save(thumb_path, 'PNG')
        return str(thumb_path)
    
    def postprocess(self, images: List[Image.Image], params: Dict[str, Any], 
                   model_info: Dict[str, Any], seed: int) -> List[PostProcessResult]:
        """후처리 실행"""
        results = []
        timestamp = datetime.now()
        
        for i, image in enumerate(images):
            try:
                # 배치 내 각 이미지에 대한 시드는 구별할 수 있도록 임시로 i를 더함
                image_seed = seed if len(images) == 1 else f"{seed}_{i+1}"
                
                # 파일명 생성
                filename = self._generate_filename(image_seed, timestamp)
                
                # 썸네일 생성
                thumbnail = self._create_thumbnail(image)
                
                # 메타데이터 추가
                image_with_meta, metadata = self._add_metadata(image, params, model_info)
                
                # 이미지 저장
                image_path = self._save_image(image_with_meta, filename, metadata)
                
                # 썸네일 저장
                thumbnail_path = self._save_thumbnail(thumbnail, filename)
                
                print(f"✅ 이미지 저장 완료: {image_path}")
                
                # 결과 생성
                result = PostProcessResult(
                    image_path=image_path,
                    thumbnail_path=thumbnail_path,
                    metadata=params,
                    success=True
                )
                results.append(result)
                
            except Exception as e:
                print(f"❌ 이미지 저장 실패: {e}")
                result = PostProcessResult(
                    image_path="",
                    thumbnail_path="",
                    metadata=params,
                    success=False,
                    error=str(e)
                )
                results.append(result)
        
        return results
    
    def cleanup_old_files(self, max_files: int = 100):
        """오래된 파일 정리"""
        try:
            # PNG 파일들 수집
            png_files = list(self.output_dir.glob("*.png"))
            
            if len(png_files) <= max_files:
                return
            
            # 생성 시간순으로 정렬
            png_files.sort(key=lambda x: x.stat().st_mtime)
            
            # 오래된 파일들 삭제
            files_to_delete = png_files[:-max_files]
            for file_path in files_to_delete:
                file_path.unlink()
                
                # 해당 썸네일도 삭제
                thumb_dir = self.output_dir / "thumbnails"
                name, ext = os.path.splitext(file_path.name)
                thumb_path = thumb_dir / f"{name}_thumb{ext}"
                if thumb_path.exists():
                    thumb_path.unlink()
            
            print(f"🧹 {len(files_to_delete)}개의 오래된 파일을 정리했습니다.")
            
        except Exception as e:
            print(f"⚠️ 파일 정리 중 오류: {e}")
    
    def get_generation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """생성 히스토리 조회"""
        history = []
        
        try:
            # PNG 파일들 수집
            png_files = list(self.output_dir.glob("*.png"))
            
            # 생성 시간순으로 정렬 (최신순)
            png_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for file_path in png_files[:limit]:
                try:
                    # 이미지에서 메타데이터 읽기
                    with Image.open(file_path) as img:
                        metadata = {}
                        if 'prompt' in img.info:
                            metadata['prompt'] = img.info['prompt']
                        if 'seed' in img.info:
                            metadata['seed'] = int(img.info['seed'])
                        if 'model_name' in img.info:
                            metadata['model_name'] = img.info['model_name']
                        
                        # 썸네일 경로 확인
                        name, ext = os.path.splitext(file_path.name)
                        thumb_path = self.output_dir / "thumbnails" / f"{name}_thumb{ext}"
                        
                        history.append({
                            'image_path': str(file_path),
                            'thumbnail_path': str(thumb_path) if thumb_path.exists() else str(file_path),
                            'metadata': metadata,
                            'timestamp': datetime.fromtimestamp(file_path.stat().st_mtime)
                        })
                        
                except Exception as e:
                    print(f"⚠️ 메타데이터 읽기 실패 {file_path}: {e}")
                    continue
            
        except Exception as e:
            print(f"⚠️ 히스토리 조회 중 오류: {e}")
        
        return history
