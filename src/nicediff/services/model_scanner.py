# 파일 경로: src/nicediff/services/model_scanner.py

from pathlib import Path
from typing import Dict, List, Any
import asyncio
from collections import defaultdict
from .metadata_parser import MetadataParser

class ModelScanner:
    """모델 파일 스캐너 - 모델 타입 자동 감지 포함"""
    
    def __init__(self, paths_config: Dict[str, str]):
        self.paths = {
            'checkpoints': Path(paths_config.get('models', 'models/checkpoints')),
            'vaes': Path(paths_config.get('vaes', 'models/vae')),
            'loras': Path(paths_config.get('loras', 'models/loras')),
        }
        self.model_extensions = {'.safetensors', '.ckpt'}

    async def scan_checkpoints(self) -> Dict[str, List[Dict[str, Any]]]:
        return await self._scan_directory(self.paths['checkpoints'], extract_model_info=True)
    
    async def scan_vaes(self) -> Dict[str, List[Dict[str, Any]]]:
        return await self._scan_directory(self.paths['vaes'])
    
    async def scan_loras(self) -> Dict[str, List[Dict[str, Any]]]:
        return await self._scan_directory(self.paths['loras'], extract_lora_info=True)
    
    async def _scan_directory(self, base_path: Path, extract_model_info: bool = False, extract_lora_info: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        if not base_path.exists():
            base_path.mkdir(parents=True, exist_ok=True)
            return {}
        
        def scan_sync():
            result = defaultdict(list)
            for ext in self.model_extensions:
                for file_path in base_path.rglob(f'*{ext}'):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(base_path)
                        folder = str(relative_path.parent) if relative_path.parent != Path('.') else 'Root'
                        
                        # 기본 파일 정보
                        file_info = {
                            'name': file_path.stem,
                            'filename': file_path.name,
                            'path': str(file_path),
                            'folder': folder,
                            'size_mb': file_path.stat().st_size / (1024 * 1024),  # MB 단위
                        }
                        
                        # 체크포인트 모델 정보 추출
                        if extract_model_info:
                            try:
                                print(f"📂 모델 스캔: {file_path.name}")
                                model_info = MetadataParser.get_model_info(file_path)
                                file_info.update(model_info)
                                print(f"   ✅ 타입: {model_info['model_type']}, 기본 크기: {model_info['default_size']}")
                            except Exception as e:
                                print(f"   ❌ 모델 정보 추출 실패: {e}")
                                # 파일명으로 추측
                                model_type, _ = MetadataParser.detect_model_type(file_path)
                                file_info['model_type'] = model_type
                                file_info['is_xl'] = model_type == 'SDXL'
                                file_info['default_size'] = (1024, 1024) if model_type == 'SDXL' else (512, 512)
                        
                        # LoRA 정보 추출
                        if extract_lora_info:
                            try:
                                # LoRA도 비슷하게 처리 가능
                                metadata = MetadataParser.extract_from_safetensors(file_path)
                                if 'ss_base_model_version' in metadata:
                                    file_info['base_model'] = metadata['ss_base_model_version']
                                    file_info['is_xl_lora'] = 'xl' in metadata['ss_base_model_version'].lower()
                                
                                # 트리거 워드 추출
                                if 'ss_tag_frequency' in metadata:
                                    try:
                                        import json
                                        tag_freq = json.loads(metadata['ss_tag_frequency'])
                                        all_tags = {}
                                        for dataset_tags in tag_freq.values():
                                            if isinstance(dataset_tags, dict):
                                                for tag, freq in dataset_tags.items():
                                                    all_tags[tag] = all_tags.get(tag, 0) + freq
                                        
                                        # 상위 5개 트리거 워드
                                        if all_tags:
                                            top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:5]
                                            file_info['trigger_words'] = [tag for tag, _ in top_tags]
                                    except:
                                        pass
                            except Exception as e:
                                print(f"   ⚠️ LoRA 정보 추출 실패: {e}")
                        
                        # 미리보기 이미지 확인
                        preview_path = file_path.with_suffix('.png')
                        if preview_path.exists():
                            file_info['has_preview'] = True
                            file_info['preview_path'] = str(preview_path)
                        else:
                            file_info['has_preview'] = False
                        
                        result[folder].append(file_info)
            
            # 폴더별로 정렬
            for folder_items in result.values():
                folder_items.sort(key=lambda x: x['name'].lower())
            
            return dict(result)
        
        return await asyncio.to_thread(scan_sync)