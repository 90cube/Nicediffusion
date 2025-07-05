# 파일 경로: src/nicediff/services/metadata_parser.py

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image
import json
import re
import struct

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
        """AUTOMATIC1111 형식 파싱"""
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
                    'sampler': r'Sampler:\s*([^,]+)',
                    'scheduler': r'Scheduler:\s*([^,]+)',
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
                # 헤더 크기 읽기
                header_size_bytes = f.read(8)
                header_size = struct.unpack('<Q', header_size_bytes)[0]
                
                if header_size > 0:
                    # JSON 헤더 읽기
                    json_data = f.read(header_size)
                    header_dict = json.loads(json_data)
                    
                    # 메타데이터 추출
                    if '__metadata__' in header_dict:
                        metadata = header_dict['__metadata__']
                        
                        # 상세 디버깅
                        print("📋 Safetensors 메타데이터 발견:")
                        for key, value in list(metadata.items())[:10]:  # 처음 10개만 출력
                            print(f"   - {key}: {str(value)[:100]}...")
                        
                        return metadata
                    else:
                        print("⚠️ __metadata__ 블록이 없습니다.")
                        
        except Exception as e:
            print(f"Safetensors 메타데이터 추출 오류 ({model_path.name}): {e}")
        return {}
    
    @staticmethod
    def detect_model_type(model_path: Path) -> Tuple[str, Optional[str]]:
        """
        모델 타입을 자동으로 감지합니다.
        Returns: (model_type, base_model) - 예: ('SDXL', 'sdxl_1_0')
        """
        print(f"🔍 모델 타입 감지 중: {model_path.name}")
        
        # 1. Safetensors 메타데이터에서 확인
        if model_path.suffix == '.safetensors':
            metadata = MetadataParser.extract_from_safetensors(model_path)
            
            # Civitai 형식 메타데이터
            if 'ss_base_model_version' in metadata:
                base_version = metadata['ss_base_model_version']
                print(f"✅ ss_base_model_version 발견: {base_version}")
                
                if 'xl' in base_version.lower() or 'sdxl' in base_version.lower():
                    return 'SDXL', base_version
                elif 'sd3' in base_version.lower():
                    return 'SD3', base_version
                else:
                    return 'SD15', base_version
            
            # ComfyUI/A1111 형식
            if 'modelspec.architecture' in metadata:
                arch = metadata['modelspec.architecture']
                print(f"✅ modelspec.architecture 발견: {arch}")
                
                if 'xl' in arch.lower():
                    return 'SDXL', arch
                elif 'sd3' in arch.lower():
                    return 'SD3', arch
                else:
                    return 'SD15', arch
            
            # 기타 메타데이터 키 확인
            for key, value in metadata.items():
                if isinstance(value, str):
                    value_lower = value.lower()
                    if 'sdxl' in value_lower or 'xl' in value_lower:
                        print(f"✅ SDXL 힌트 발견: {key}={value[:50]}...")
                        return 'SDXL', value
                    elif 'sd3' in value_lower:
                        print(f"✅ SD3 힌트 발견: {key}={value[:50]}...")
                        return 'SD3', value
        
        # 2. 파일명에서 추측
        filename_lower = model_path.name.lower()
        
        # SDXL 키워드
        sdxl_keywords = ['sdxl', 'xl', 'illustrious', 'pony', 'animagine', 'juggernaut']
        for keyword in sdxl_keywords:
            if keyword in filename_lower:
                print(f"📝 파일명에서 SDXL 키워드 발견: {keyword}")
                return 'SDXL', None
        
        # SD3 키워드
        sd3_keywords = ['sd3', 'stable-diffusion-3']
        for keyword in sd3_keywords:
            if keyword in filename_lower:
                print(f"📝 파일명에서 SD3 키워드 발견: {keyword}")
                return 'SD3', None
        
        # 기본값은 SD1.5
        print("ℹ️ 특별한 표시가 없어 SD1.5로 간주합니다.")
        return 'SD15', None
    
    @staticmethod
    def get_model_info(model_path: Path) -> Dict[str, Any]:
        """
        모델의 전체 정보를 추출합니다.
        """
        model_type, base_model = MetadataParser.detect_model_type(model_path)
        
        info = {
            'model_type': model_type,
            'base_model': base_model,
            'is_xl': model_type == 'SDXL',
            'is_sd3': model_type == 'SD3',
            'default_size': (1024, 1024) if model_type in ['SDXL', 'SD3'] else (512, 512),
        }
        
        # 추가 메타데이터 병합
        if model_path.suffix == '.safetensors':
            metadata = MetadataParser.extract_from_safetensors(model_path)
            
            # 학습 정보 추출
            if 'ss_training_comment' in metadata:
                info['training_comment'] = metadata['ss_training_comment']
            if 'ss_num_train_images' in metadata:
                info['num_train_images'] = metadata['ss_num_train_images']
            if 'ss_learning_rate' in metadata:
                info['learning_rate'] = metadata['ss_learning_rate']
            if 'ss_unet_lr' in metadata:
                info['unet_lr'] = metadata['ss_unet_lr']
            if 'ss_text_encoder_lr' in metadata:
                info['text_encoder_lr'] = metadata['ss_text_encoder_lr']
            
            # 트리거 워드
            if 'ss_tag_frequency' in metadata:
                try:
                    tag_freq = json.loads(metadata['ss_tag_frequency'])
                    # 가장 빈번한 태그 추출
                    all_tags = {}
                    for dataset_tags in tag_freq.values():
                        for tag, freq in dataset_tags.items():
                            all_tags[tag] = all_tags.get(tag, 0) + freq
                    
                    # 상위 10개 태그
                    top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:10]
                    info['suggested_tags'] = [tag for tag, _ in top_tags]
                except:
                    pass
        
        return info