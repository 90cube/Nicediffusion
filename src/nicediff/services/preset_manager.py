from ..core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)
"""
프롬프트 프리셋 관리 시스템
JSON 기반 프리셋 시스템으로 편리한 프롬프트 관리
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any


class PresetManager:
    """프롬프트 프리셋 관리"""
    
    def __init__(self):
        self.preset_dir = Path("models/preset")
        self.pos_dir = self.preset_dir / "pos_prompt"
        self.neg_dir = self.preset_dir / "neg_prompt"
        
        # 디렉토리 생성
        self.pos_dir.mkdir(parents=True, exist_ok=True)
        self.neg_dir.mkdir(parents=True, exist_ok=True)
        
        # 기본 프리셋 생성
        self._create_default_presets()
    
    def _create_default_presets(self):
        """기본 프리셋 파일 생성"""
        
        # 긍정 프롬프트 프리셋들
        positive_presets = {
            "Quality": {
                "prompt": "masterpiece, best quality, highly detailed, sharp focus, professional",
                "description": "기본 품질 향상 태그"
            },
            "Photorealistic": {
                "prompt": "photorealistic, realistic, photo, 8k uhd, high resolution, professional photography",
                "description": "사실적인 사진 스타일"
            },
            "Anime": {
                "prompt": "anime style, manga style, illustration, detailed anime art, vibrant colors",
                "description": "애니메이션 스타일"
            },
            "Portrait": {
                "prompt": "beautiful face, detailed eyes, detailed skin, perfect anatomy, beautiful lighting",
                "description": "인물화 전용 태그"
            },
            "Landscape": {
                "prompt": "beautiful landscape, scenic view, natural lighting, atmospheric perspective, depth of field",
                "description": "풍경화 전용 태그"
            },
            "Fantasy": {
                "prompt": "fantasy art, magical, mystical, ethereal, enchanting, otherworldly",
                "description": "판타지 아트 스타일"
            },
            "Cinematic": {
                "prompt": "cinematic lighting, dramatic lighting, film grain, movie poster style",
                "description": "영화적 분위기"
            },
            "Artistic": {
                "prompt": "artistic, creative, imaginative, unique style, artistic composition",
                "description": "예술적 스타일"
            },
            "Detailed": {
                "prompt": "ultra detailed, intricate details, fine details, high detail, detailed texture",
                "description": "고해상도 상세 태그"
            },
            "Professional": {
                "prompt": "professional, studio quality, commercial quality, premium quality",
                "description": "전문가급 품질"
            }
        }
        
        # 부정 프롬프트 프리셋들
        negative_presets = {
            "Basic": {
                "prompt": "worst quality, low quality, normal quality, lowres, bad anatomy, bad hands",
                "description": "기본 품질 제외 태그"
            },
            "People": {
                "prompt": "bad anatomy, bad hands, bad fingers, missing fingers, extra fingers, bad proportions, deformed, ugly face",
                "description": "인물 그릴 때 제외할 것들"
            },
            "Artifacts": {
                "prompt": "blurry, noisy, jpeg artifacts, compression artifacts, oversaturated, duplicate",
                "description": "이미지 아티팩트 제거"
            },
            "NSFW": {
                "prompt": "nsfw, nude, explicit, sexual content, inappropriate",
                "description": "성인 콘텐츠 제외"
            },
            "Text": {
                "prompt": "text, watermark, signature, logo, username, artist name, copyright",
                "description": "텍스트 및 워터마크 제거"
            },
            "Deformed": {
                "prompt": "deformed, disfigured, mutation, mutated, extra limbs, missing limbs, poorly drawn",
                "description": "변형된 형태 제외"
            },
            "LowQuality": {
                "prompt": "low quality, worst quality, bad quality, poor quality, low resolution",
                "description": "저품질 제외"
            },
            "Unwanted": {
                "prompt": "unwanted, unnecessary, redundant, excessive, overdone",
                "description": "불필요한 요소 제외"
            }
        }
        
        # JSON 파일로 저장
        for name, data in positive_presets.items():
            preset_file = self.pos_dir / f"{name}.json"
            if not preset_file.exists():
                with open(preset_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                success(f"긍정 프리셋 생성: {name}")
        
        for name, data in negative_presets.items():
            preset_file = self.neg_dir / f"{name}.json"
            if not preset_file.exists():
                with open(preset_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                success(f"부정 프리셋 생성: {name}")
    
    def get_positive_presets(self) -> List[Dict[str, str]]:
        """긍정 프롬프트 프리셋 목록 반환"""
        presets = []
        
        for preset_file in self.pos_dir.glob("*.json"):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    presets.append({
                        'name': preset_file.stem,
                        'prompt': data.get('prompt', ''),
                        'description': data.get('description', '')
                    })
            except Exception as e:
                info(f"프리셋 로드 실패 {preset_file}: {e}")
        
        return sorted(presets, key=lambda x: x['name'])
    
    def get_negative_presets(self) -> List[Dict[str, str]]:
        """부정 프롬프트 프리셋 목록 반환"""
        presets = []
        
        for preset_file in self.neg_dir.glob("*.json"):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    presets.append({
                        'name': preset_file.stem,
                        'prompt': data.get('prompt', ''),
                        'description': data.get('description', '')
                    })
            except Exception as e:
                info(f"프리셋 로드 실패 {preset_file}: {e}")
        
        return sorted(presets, key=lambda x: x['name'])
    
    def add_preset(self, name: str, prompt: str, description: str, is_negative: bool = False):
        """새 프리셋 추가"""
        preset_data = {
            'prompt': prompt,
            'description': description
        }
        
        target_dir = self.neg_dir if is_negative else self.pos_dir
        preset_file = target_dir / f"{name}.json"
        
        with open(preset_file, 'w', encoding='utf-8') as f:
            json.dump(preset_data, f, ensure_ascii=False, indent=2)
        
        success(f"프리셋 추가: {name} ({'부정' if is_negative else '긍정'})")
    
    def delete_preset(self, name: str, is_negative: bool = False):
        """프리셋 삭제"""
        target_dir = self.neg_dir if is_negative else self.pos_dir
        preset_file = target_dir / f"{name}.json"
        
        if preset_file.exists():
            preset_file.unlink()
            success(f"프리셋 삭제: {name} ({'부정' if is_negative else '긍정'})")
        else:
            warning_emoji(f"프리셋을 찾을 수 없음: {name}")
    
    def get_preset(self, name: str, is_negative: bool = False) -> Dict[str, str]:
        """특정 프리셋 조회"""
        target_dir = self.neg_dir if is_negative else self.pos_dir
        preset_file = target_dir / f"{name}.json"
        
        if preset_file.exists():
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {
                        'name': name,
                        'prompt': data.get('prompt', ''),
                        'description': data.get('description', '')
                    }
            except Exception as e:
                info(f"프리셋 로드 실패 {preset_file}: {e}")
        
        return {'name': name, 'prompt': '', 'description': ''}
    
    def list_all_presets(self) -> Dict[str, List[Dict[str, str]]]:
        """모든 프리셋 목록 반환"""
        return {
            'positive': self.get_positive_presets(),
            'negative': self.get_negative_presets()
        } 