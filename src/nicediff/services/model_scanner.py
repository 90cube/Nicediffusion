# 파일 경로: src/nicediff/services/model_scanner.py (단순화 버전)

from pathlib import Path
from typing import Dict, List, Any
import asyncio
from collections import defaultdict

class ModelScanner:
    """단순화된 모델 파일 스캐너 (경로 탐색에만 집중)"""
    
    def __init__(self, paths_config: Dict[str, str]):
        self.paths = {
            'checkpoints': Path(paths_config.get('models', 'models/checkpoints')),
            'vaes': Path(paths_config.get('vaes', 'models/vae')),
            'loras': Path(paths_config.get('loras', 'models/loras')),
        }
        self.model_extensions = {'.safetensors', '.ckpt'}

    async def scan_checkpoints(self) -> Dict[str, List[Dict[str, Any]]]:
        return await self._scan_directory(self.paths['checkpoints'])
    
    async def scan_vaes(self) -> Dict[str, List[Dict[str, Any]]]:
        return await self._scan_directory(self.paths['vaes'])
    
    async def scan_loras(self) -> Dict[str, List[Dict[str, Any]]]:
        return await self._scan_directory(self.paths['loras'])
    
    async def _scan_directory(self, base_path: Path) -> Dict[str, List[Dict[str, Any]]]:
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
                        
                        # 오직 파일의 기본 정보만 수집
                        file_info = {
                            'name': file_path.stem,
                            'filename': file_path.name,
                            'path': str(file_path),
                            'folder': folder,
                        }
                        result[folder].append(file_info)
            
            for folder_items in result.values():
                folder_items.sort(key=lambda x: x['name'].lower())
            return dict(result)
        
        return await asyncio.to_thread(scan_sync)