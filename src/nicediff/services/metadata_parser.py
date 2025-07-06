# 파일 경로: src/nicediff/services/metadata_parser.py (수정 제안)

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image
import json
import re
import struct # struct는 내장 모듈이므로 pip 설치 불필요 (오류가 났던 부분)

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
        """[수정] AUTOMATIC1111 형식 파싱 로직 개선"""
        result = {'prompt': '', 'negative_prompt': '', 'parameters': {}}
        
        # 파라미터 블록의 시작점을 찾음 (Steps: 가 가장 일반적)
        param_match = re.search(r'Steps:\s*\d+', text)
        param_start_index = param_match.start() if param_match else -1
        
        # 파라미터 블록과 프롬프트 블록을 분리
        param_text = text[param_start_index:] if param_start_index != -1 else ""
        prompt_block = text[:param_start_index].strip() if param_start_index != -1 else text.strip()
        
        # 프롬프트 블록에서 긍정/부정 프롬프트 분리
        neg_prompt_match = re.search(r'Negative prompt:\s*', prompt_block, re.IGNORECASE)
        if neg_prompt_match:
            result['prompt'] = prompt_block[:neg_prompt_match.start()].strip()
            result['negative_prompt'] = prompt_block[neg_prompt_match.end():].strip()
        else:
            result['prompt'] = prompt_block

        # 파라미터 파싱 (기존 로직과 유사)
        if param_text:
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
                    # (파라미터 값 변환 로직은 기존과 동일하므로 생략)
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
        """Safetensors 파일에서 __metadata__ 블록 직접 추출 및 워크플로우 프롬프트 파싱"""
        try:
            with open(model_path, 'rb') as f:
                header_size_bytes = f.read(8)
                header_size = struct.unpack('<Q', header_size_bytes)[0]
                
                if header_size > 0:
                    json_data = f.read(header_size)
                    header_dict = json.loads(json_data)
                    
                    if '__metadata__' in header_dict:
                        metadata = header_dict['__metadata__']
                        
                        # 상세 디버깅
                        #print("📋 Safetensors 메타데이터 발견:")
                        #for key, value in list(metadata.items())[:10]:
                        #    print(f"   - {key}: {str(value)[:100]}...")
                        
                        # 'prompt' 키가 ComfyUI 워크플로우 JSON인지 확인하고 파싱
                        if 'prompt' in metadata and isinstance(metadata['prompt'], str):
                            try:
                                # JSON 문자열일 가능성 확인
                                prompt_content = json.loads(metadata['prompt'])
                                # ComfyUI 워크플로우 JSON으로 간주하고 파싱
                                parsed_prompts = MetadataParser._parse_comfyui_workflow_json(prompt_content)
                                if parsed_prompts['prompt']:
                                    metadata['prompt'] = parsed_prompts['prompt']
                                if parsed_prompts['negative_prompt']:
                                    metadata['negative_prompt'] = parsed_prompts['negative_prompt']
                                # 'parameters'도 워크플로우에서 추출 가능하면 추가
                                if parsed_prompts['parameters']:
                                    metadata['parameters'] = {**metadata.get('parameters', {}), **parsed_prompts['parameters']}
                                
                            except json.JSONDecodeError:
                                # JSON이 아니면 일반 문자열 프롬프트로 간주
                                pass
                            except Exception as e:
                                print(f"경고: ComfyUI 워크플로우 프롬프트 파싱 오류: {e}")
                                pass # 파싱 실패해도 원래 메타데이터 사용

                        return metadata
                    else:
                        print("없음")
                        
        except Exception as e:
            print(f"Safetensors 메타데이터 추출 오류 ({model_path.name}): {e}")
        return {}
    
    @staticmethod
    def _parse_comfyui_workflow_json(workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        ComfyUI 워크플로우 JSON 데이터에서 긍정/부정 프롬프트 및 파라미터를 추출합니다.
        가장 일반적인 "CLIPTextEncode" 노드를 기반으로 합니다.
        """
        extracted = {'prompt': '', 'negative_prompt': '', 'parameters': {}}
        nodes = workflow_data.get('nodes', [])

        # 긍정 및 부정 프롬프트 추출 시도
        # CLIPTextEncode 노드를 찾아 프롬프트 추출
        for node in nodes:
            if node.get('class_type') == 'CLIPTextEncode':
                node_id = str(node.get('id'))
                if 'inputs' in node and 'text' in node['inputs']:
                    # 긍정 프롬프트 (대부분의 경우 CLIPTextEncode 노드는 긍정 프롬프트에 사용됨)
                    if not extracted['prompt']: # 첫 번째 긍정 프롬프트만 가져옴
                        extracted['prompt'] = node['inputs']['text']
                        #print(f"🔎 ComfyUI 워크플로우에서 긍정 프롬프트 추출됨 (Node {node_id}): {extracted['prompt'][:50]}...")
                
                # 부정 프롬프트는 보통 별도의 CLIPTextEncode 노드나 다른 특정 노드에 연결될 수 있음
                # 명시적인 'negative' 키가 없으므로 heuristic이 필요함
                # 예를 들어, prompt가 비어있고 text_g/text_l이 있는 노드를 찾을 수 있음 (고급 케이스)
                
                # 워크플로우 메타데이터에서 파라미터 추출 시도 (예: KSampler 노드)
                if node.get('class_type') == 'KSampler':
                    if 'inputs' in node:
                        if 'steps' in node['inputs']:
                            extracted['parameters']['steps'] = node['inputs']['steps']
                        if 'cfg' in node['inputs']: # ComfyUI에서는 'cfg'로 표기될 수 있음
                            extracted['parameters']['cfg_scale'] = node['inputs']['cfg']
                        if 'sampler_name' in node['inputs']:
                            extracted['parameters']['sampler'] = node['inputs']['sampler_name']
                        if 'scheduler' in node['inputs']:
                            extracted['parameters']['scheduler'] = node['inputs']['scheduler']
                        if 'seed' in node['inputs']:
                            extracted['parameters']['seed'] = node['inputs']['seed']
                
                # 크기 정보 (EmptyLatentImage 노드)
                if node.get('class_type') == 'EmptyLatentImage':
                    if 'inputs' in node:
                        if 'width' in node['inputs']:
                            extracted['parameters']['width'] = node['inputs']['width']
                        if 'height' in node['inputs']:
                            extracted['parameters']['height'] = node['inputs']['height']
            
            # TODO: LoRA, ControlNet 등 다른 노드에서 추가 정보 추출 가능
            # (이 부분은 필요에 따라 확장)

        # 'prompt' 키가 없거나 비어 있다면, 'workflow' 최상위 키의 다른 프롬프트 필드를 찾을 수도 있음 (덜 일반적)
        if not extracted['prompt'] and 'prompt' in workflow_data and isinstance(workflow_data['prompt'], str):
            extracted['prompt'] = workflow_data['prompt']

        # 'workflow' 키에 직접 'extra_pnginfo'가 있는 경우
        if 'extra_pnginfo' in workflow_data and 'prompt' in workflow_data['extra_pnginfo']:
            extracted['prompt'] = workflow_data['extra_pnginfo']['prompt']
        if 'extra_pnginfo' in workflow_data and 'negative_prompt' in workflow_data['extra_pnginfo']:
            extracted['negative_prompt'] = workflow_data['extra_pnginfo']['negative_prompt']

        return extracted
    
    @staticmethod
    def detect_model_type(model_path: Path) -> Tuple[str, Optional[str]]:
        """
        모델 타입을 자동으로 감지합니다.
        Returns: (model_type, base_model) - 예: ('SDXL', 'sdxl_1_0')
        """
        print(f"🔍 모델 타입 감지 중: {model_path.name}")
        
        # 1. Safetensors 메타데이터에서 확인
        if model_path.suffix == '.safetensors':
            metadata = MetadataParser.extract_from_safetensors(model_path) # 수정된 extract_from_safetensors 호출
            
            # Civitai 형식 메타데이터
            if 'ss_base_model_version' in metadata:
                base_version = metadata['ss_base_model_version']
                #print(f"✅ ss_base_model_version 발견: {base_version}")
                
                if 'xl' in base_version.lower() or 'sdxl' in base_version.lower():
                    return 'SDXL', base_version
                elif 'sd3' in base_version.lower():
                    return 'SD3', base_version
                else:
                    return 'SD15', base_version
            
            # ComfyUI/A1111 형식
            if 'modelspec.architecture' in metadata:
                arch = metadata['modelspec.architecture']
                #print(f"✅ modelspec.architecture 발견: {arch}")
                
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
                        #print(f"✅ SDXL 힌트 발견: {key}={value[:50]}...")
                        return 'SDXL', value
                    elif 'sd3' in value_lower:
                        #print(f"✅ SD3 힌트 발견: {key}={value[:50]}...")
                        return 'SD3', value
        
        # 2. 파일명에서 추측
        filename_lower = model_path.name.lower()
        
        # SDXL 키워드
        sdxl_keywords = ['sdxl', 'xl', 'illustrious', 'pony', 'animagine', 'juggernaut']
        for keyword in sdxl_keywords:
            if keyword in filename_lower:
                #print(f"📝 파일명에서 SDXL 키워드 발견: {keyword}")
                return 'SDXL', None
        
        # SD3 키워드
        sd3_keywords = ['sd3', 'stable-diffusion-3']
        for keyword in sd3_keywords:
            if keyword in filename_lower:
                #print(f"📝 파일명에서 SD3 키워드 발견: {keyword}")
                return 'SD3', None
        
        # 기본값은 SD1.5
        #print("ℹ️ 특별한 표시가 없어 SD1.5로 간주합니다.")
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
            'metadata': {}  # 빈 메타데이터 딕셔너리 초기화
        }
        
        # 추가 메타데이터 병합
        if model_path.suffix == '.safetensors':
            metadata = MetadataParser.extract_from_safetensors(model_path)
            
            # 전체 메타데이터 저장
            info['metadata'] = metadata
            
            # VAE 정보 추출
            if 'ss_vae_name' in metadata:
                info['recommended_vae'] = metadata['ss_vae_name']
            if 'vae' in metadata:
                info['recommended_vae'] = metadata['vae']
            if 'sd_vae' in metadata:
                info['recommended_vae'] = metadata['sd_vae']
            
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