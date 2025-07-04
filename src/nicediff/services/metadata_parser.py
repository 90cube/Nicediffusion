"""
메타데이터 파서
PNG 이미지와 safetensors 파일에서 메타데이터 추출
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from PIL import Image
import json
import re

class MetadataParser:
    """메타데이터 파서"""
    
    @staticmethod
    def extract_from_png(image_path: Path) -> Dict[str, Any]:
        """PNG 이미지에서 메타데이터 추출"""
        metadata = {
            'prompt': '',
            'negative_prompt': '',
            'parameters': {},
            'raw': ''
        }
        
        try:
            with Image.open(image_path) as img:
                # PNG 메타데이터에서 parameters 추출
                png_info = img.info.get('parameters', '')
                if png_info:
                    metadata['raw'] = png_info
                    metadata.update(MetadataParser._parse_automatic1111_format(png_info))
        except Exception as e:
            print(f"PNG 메타데이터 추출 오류: {e}")
        
        return metadata
    
    @staticmethod
    def _parse_automatic1111_format(text: str) -> Dict[str, Any]:
        """AUTOMATIC1111 형식 파싱"""
        result = {
            'prompt': '',
            'negative_prompt': '',
            'parameters': {}
        }
        
        # 프롬프트 추출
        parts = text.split('Negative prompt:', 1)
        if parts:
            result['prompt'] = parts[0].strip()
        
        # 네거티브 프롬프트 추출
        if len(parts) > 1:
            neg_parts = parts[1].split('\n', 1)
            if neg_parts:
                result['negative_prompt'] = neg_parts[0].strip()
                
                # 파라미터 추출
                if len(neg_parts) > 1:
                    param_text = neg_parts[1]
                    
                    # 각 파라미터 파싱
                    patterns = {
                        'steps': r'Steps:\s*(\d+)',
                        'sampler': r'Sampler:\s*([^,]+)',
                        'cfg_scale': r'CFG scale:\s*([\d.]+)',
                        'seed': r'Seed:\s*(\d+)',
                        'size': r'Size:\s*(\d+x\d+)',
                        'model_hash': r'Model hash:\s*([a-fA-F0-9]+)',
                        'model': r'Model:\s*([^,]+)',
                        'scheduler': r'Schedule[r]?:\s*([^,]+)',
                    }
                    
                    for key, pattern in patterns.items():
                        match = re.search(pattern, param_text, re.IGNORECASE)
                        if match:
                            value = match.group(1).strip()
                            if key in ['steps', 'seed']:
                                value = int(value)
                            elif key == 'cfg_scale':
                                value = float(value)
                            elif key == 'size':
                                w, h = value.split('x')
                                result['parameters']['width'] = int(w)
                                result['parameters']['height'] = int(h)
                                continue
                            result['parameters'][key] = value
        
        return result
    
    @staticmethod
    def extract_lora_trigger_words(metadata: Dict[str, Any]) -> List[str]:
        """LoRA 트리거 워드 추출"""
        trigger_words = []
        
        # 다양한 형식의 트리거 워드 찾기
        if 'trigger_words' in metadata:
            words = metadata['trigger_words']
            if isinstance(words, list):
                trigger_words.extend(words)
            elif isinstance(words, str):
                # 쉼표로 구분된 경우
                trigger_words.extend([w.strip() for w in words.split(',')])
        
        # activation_text 필드 확인
        if 'activation_text' in metadata:
            trigger_words.append(metadata['activation_text'])
        
        # 중복 제거
        return list(dict.fromkeys(trigger_words))
    
    @staticmethod
    def extract_from_safetensors(model_path: Path) -> Dict[str, Any]:
        """Safetensors 파일에서 메타데이터 추출"""
        metadata = {}
        
        try:
            # safetensors는 파일 끝에 JSON 메타데이터를 저장
            # 여기서는 간단한 구현만 제공
            pass
        except Exception as e:
            print(f"Safetensors 메타데이터 추출 오류: {e}")
        
        return metadata