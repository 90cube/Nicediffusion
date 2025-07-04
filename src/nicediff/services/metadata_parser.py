# 파일 경로: src/nicediff/services/metadata_parser.py (디버깅 강화 및 파서 개선)

from pathlib import Path
from typing import Dict, Any
from PIL import Image
import json
import re

class MetadataParser:
    @staticmethod
    def extract_from_png(image_path: Path) -> Dict[str, Any]:
        try:
            with Image.open(image_path) as img:
                raw_metadata = ""
                if 'parameters' in img.info:
                    raw_metadata = img.info['parameters']
                else:
                    for value in img.info.values():
                        if isinstance(value, str) and 'Steps:' in value:
                            raw_metadata = value
                            break
                if raw_metadata:
                    return MetadataParser._parse_automatic1111_format(raw_metadata)
        except Exception as e:
            print(f"PNG 메타데이터 추출 오류: {e}")
        return {}

    @staticmethod
    def _parse_automatic1111_format(text: str) -> Dict[str, Any]:
        result = {'prompt': '', 'negative_prompt': '', 'parameters': {}}
        parts = text.split('Negative prompt:', 1)
        result['prompt'] = parts[0].strip()
        if len(parts) > 1:
            neg_parts = parts[1].split('\n', 1)
            result['negative_prompt'] = neg_parts[0].strip()
            if len(neg_parts) > 1:
                param_text = neg_parts[1]
                patterns = {
                    'steps': r'Steps:\s*(\d+)',
                    'sampler': r'Sampler:\s*([\w\s\+]+)',
                    'scheduler': r'Scheduler:\s*([\w\s]+)', # 스케줄러 패턴
                    'cfg_scale': r'CFG scale:\s*([\d\.]+)',
                    'seed': r'Seed:\s*(\d+)',
                    'width': r'Size:\s*(\d+)x\d+', # 너비만 추출
                    'height': r'Size:\s*\d+x(\d+)', # 높이만 추출
                }
                for key, pattern in patterns.items():
                    match = re.search(pattern, param_text)
                    if match:
                        value_str = match.group(1).strip()
                        try:
                            if key in ['steps', 'seed', 'width', 'height']:
                                result['parameters'][key] = int(value_str)
                            elif key == 'cfg_scale':
                                result['parameters'][key] = float(value_str)
                            else:
                                result['parameters'][key] = value_str
                        except ValueError:
                            result['parameters'][key] = value_str
        return result

    @staticmethod
    def _parse_automatic1111_format(text: str) -> Dict[str, Any]:
        """AUTOMATIC1111 형식 파싱"""
        result = {'prompt': '', 'negative_prompt': '', 'parameters': {}}
        
        parts = text.split('Negative prompt:', 1)
        result['prompt'] = parts[0].strip()
        
        if len(parts) > 1:
            neg_parts = parts[1].split('\n', 1)
            result['negative_prompt'] = neg_parts[0].strip()
            
            if len(neg_parts) > 1:
                param_text = neg_parts[1]
                
                # --- [수정] scheduler를 포함하여 파싱 패턴 강화 ---
                patterns = {
                    'steps': r'Steps:\s*(\d+)',
                    'sampler': r'Sampler:\s*([^,]+)',
                    'scheduler': r'Scheduler:\s*([^,]+)', # 스케줄러 패턴 추가
                    'cfg_scale': r'CFG scale:\s*([\d\.]+)',
                    'seed': r'Seed:\s*(\d+)',
                    'size': r'Size:\s*(\d+x\d+)',
                    'model': r'Model:\s*([^,]+)',
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, param_text, re.IGNORECASE)
                    if match:
                        value_str = match.group(1).strip()
                        try:
                            if key == 'size':
                                w, h = value_str.split('x')
                                result['parameters']['width'] = int(w)
                                result['parameters']['height'] = int(h)
                            elif key in ['steps', 'seed']:
                                result['parameters'][key] = int(value_str)
                            elif key == 'cfg_scale':
                                result['parameters'][key] = float(value_str)
                            else:
                                result['parameters'][key] = value_str
                        except (ValueError, IndexError):
                             print(f"경고: 파라미터 '{key}'의 값 '{value_str}'을 변환할 수 없습니다.")
                             result['parameters'][key] = value_str
        return result
    
    @staticmethod
    def extract_from_safetensors(model_path: Path) -> Dict[str, Any]:
        """Safetensors 파일에서 __metadata__ 블록 직접 추출"""
        try:
            with open(model_path, 'rb') as f:
                metadata_len_bytes = f.read(8)
                metadata_len = int.from_bytes(metadata_len_bytes, 'little')
                if metadata_len > 0:
                    json_data = f.read(metadata_len)
                    json_obj = json.loads(json_data)
                    if '__metadata__' in json_obj:
                        # safetensors에서 읽은 메타데이터도 A1111 형식으로 파싱 시도
                        if 'ss_text_encoder_lr' in json_obj['__metadata__']: # 학습 메타데이터로 추정
                            return json_obj['__metadata__']
                        elif 'prompt' in json_obj['__metadata__']:
                            return MetadataParser._parse_automatic1111_format(json_obj['__metadata__']['prompt'])
        except Exception as e:
            print(f"Safetensors 메타데이터 추출 오류 ({model_path.name}): {e}")
        return {}