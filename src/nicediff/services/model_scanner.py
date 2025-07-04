"""
모델 파일 시스템 스캐너
"""

from pathlib import Path
from typing import Dict, List, Any
import asyncio
from collections import defaultdict

class ModelScanner:
    """모델 파일 스캐너"""
    
    def __init__(self, paths_config: Dict[str, str]):
        self.paths = {
            'checkpoints': Path(paths_config.get('models', 'models/checkpoints')),
            'vaes': Path(paths_config.get('vaes', 'models/vae')),
            'loras': Path(paths_config.get('loras', 'models/loras')),
            'embeddings': Path(paths_config.get('embeddings', 'models/embeddings'))
        }
        
        # 지원 확장자
        self.model_extensions = {'.safetensors', '.ckpt', '.pt', '.pth'}
    
    async def scan_checkpoints(self) -> Dict[str, List[Dict[str, Any]]]:
        """체크포인트 모델 스캔"""
        return await self._scan_directory(self.paths['checkpoints'])
    
    async def scan_vaes(self) -> Dict[str, List[Dict[str, Any]]]:
        """VAE 모델 스캔"""
        return await self._scan_directory(self.paths['vaes'])
    
    async def scan_loras(self) -> Dict[str, List[Dict[str, Any]]]:
        """LoRA 모델 스캔"""
        result = await self._scan_directory(self.paths['loras'])
        
        # LoRA는 SD1.5/SDXL 구분 추가
        for folder, items in result.items():
            for item in items:
                # 파일명이나 경로에서 버전 추측
                path_lower = item['path'].lower()
                if 'sdxl' in path_lower or 'xl' in path_lower:
                    item['base_model'] = 'SDXL'
                else:
                    item['base_model'] = 'SD1.5'
        
        return result
    
    async def _scan_directory(self, base_path: Path) -> Dict[str, List[Dict[str, Any]]]:
        """디렉토리 스캔 (비동기)"""
        result = defaultdict(list)
        
        if not base_path.exists():
            base_path.mkdir(parents=True, exist_ok=True)
            return dict(result)
        
        # 비동기로 파일 스캔
        def scan_sync():
            for ext in self.model_extensions:
                for file_path in base_path.rglob(f'*{ext}'):
                    if file_path.is_file():
                        # 상대 경로로 폴더 구조 파악
                        relative_path = file_path.relative_to(base_path)
                        folder = str(relative_path.parent) if relative_path.parent != Path('.') else 'Root'
                        
                        # 파일 정보 수집
                        file_info = {
                            'name': file_path.stem,
                            'filename': file_path.name,
                            'path': str(file_path),
                            'size': file_path.stat().st_size,
                            'folder': folder,
                            'has_preview': file_path.with_suffix('.png').exists()
                        }
                        
                        result[folder].append(file_info)
            
            # 폴더별 정렬
            for folder in result:
                result[folder].sort(key=lambda x: x['name'].lower())
            
            return dict(result)
        
        # 블로킹 작업을 별도 스레드에서 실행
        return await asyncio.to_thread(scan_sync)