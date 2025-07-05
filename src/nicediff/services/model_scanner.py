# 파일 경로: src/nicediff/services/model_scanner.py
# 최종 리팩토링 완료 버전

import asyncio
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from .metadata_parser import MetadataParser

class ModelScanner:
    """모델 파일 스캐너 (최종 완성본)"""

    def __init__(self, paths_config: Dict[str, str]):
        # config.toml의 [paths] 섹션을 통째로 받아 경로 Path 객체로 저장
        self.paths_config = {key: Path(value) for key, value in paths_config.items()}
        self.model_extensions = {'.safetensors', '.ckpt', '.pt'}
        self.metadata_parser = MetadataParser()
        self.scannable_types = ['checkpoints', 'vaes', 'loras', 'embeddings', 'controlnet', 'upscaler']

    async def scan_all_models(self) -> Dict[str, Any]:
        """모든 모델 타입을 병렬로 스캔하고 결과를 반환하는 유일한 공개 메서드."""
        print(">>> 통합 모델 스캔 시작 (최종 아키텍처 적용)...")
        tasks = {}
        
        # 설정된 스캔 대상 타입에 대해서만 작업을 생성합니다.
        for model_type, path in self.paths_config.items():
            if model_type == 'outputs': # 출력 폴더는 스캔에서 제외
                continue
            tasks[model_type] = self._scan_directory(path, model_type)
            
        list_of_results = await asyncio.gather(*tasks.values())
        print("<<< 모든 모델 스캔 완료.")
        return dict(zip(tasks.keys(), list_of_results))

    async def _scan_directory(self, base_path: Path, model_type: str) -> Dict[str, List[Dict[str, Any]]]:
        """지정된 디렉토리 하나를 스캔하는 비공개 헬퍼 함수."""
        if not await asyncio.to_thread(base_path.exists):
            await asyncio.to_thread(base_path.mkdir, parents=True, exist_ok=True)
            return {}


        def scan_sync():
            """실제 파일 시스템 I/O를 수행하는 동기 함수"""
            result = defaultdict(list)
            
            for file_path in base_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in self.model_extensions:
                    relative_path = file_path.relative_to(base_path)
                    folder = str(relative_path.parent) if relative_path.parent != Path('.') else 'Root'
                    
                    # CUBE님의 상세하고 훌륭한 정보 추출 로직을 여기에 적용합니다.
                    file_info = {
                        'name': file_path.stem,
                        'filename': file_path.name,
                        'path': str(file_path),
                        'folder': folder,
                        'size_mb': file_path.stat().st_size / (1024 * 1024),
                        'type': model_type,
                    }
                    
                    # model_type에 따라 필요한 메타데이터만 추출하도록 분기
                    if model_type == 'checkpoints':
                        model_meta = self.metadata_parser.get_model_info(file_path)
                        file_info.update(model_meta)
                    elif model_type == 'loras':
                        lora_meta = self.metadata_parser.extract_from_safetensors(file_path)
                        # 예시: ss_base_model_version 키가 있다면 추가
                        if 'ss_base_model_version' in lora_meta:
                            file_info['base_model'] = lora_meta['ss_base_model_version']
                        # 다른 필요한 LoRA 관련 메타데이터 추출 로직...
                    
                    result[folder].append(file_info)

            # 폴더별 정렬
            for folder_items in result.values():
                folder_items.sort(key=lambda x: x['name'].lower())
            
            return dict(result)
        
        # 동기 함수를 별도 스레드에서 실행하여 UI 멈춤 방지
        #print(f"  -> '{model_type}' 타입 스캔 중: {base_path}")
        return await asyncio.to_thread(scan_sync)