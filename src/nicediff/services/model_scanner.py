# 파일 경로: src/nicediff/services/model_scanner.py
# VAE 스캔 및 PNG 메타데이터 우선순위 수정

import asyncio
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from .metadata_parser import MetadataParser
from ..core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)

class ModelScanner:
    """모델 파일 스캐너 (VAE 지원 및 PNG 메타데이터 우선순위 수정)"""

    def __init__(self, paths_config: Dict[str, str]):
        # config.toml의 [paths] 섹션을 통째로 받아 경로 Path 객체로 저장
        self.paths_config = {key: Path(value) for key, value in paths_config.items()}
        self.model_extensions = {'.safetensors', '.ckpt', '.pt'}
        self.vae_extensions = {'.safetensors', '.ckpt', '.pt', '.vae.pt'}  # VAE 확장자 추가
        self.metadata_parser = MetadataParser()

    async def scan_all_models(self) -> Dict[str, Any]:
        """모든 모델 타입을 병렬로 스캔하고 결과를 반환하는 유일한 공개 메서드."""
        info(r">>> 통합 모델 스캔 시작 (VAE 지원 포함)...")
        debug_emoji(f"스캔 대상 경로: {self.paths_config}")
        tasks = {}
        
        # 설정된 스캔 대상 타입에 대해서만 작업을 생성합니다.
        for model_type, path in self.paths_config.items():
            info(f"📁 {model_type} 스캔 준비: {path}")
            if model_type == 'outputs': # 출력 폴더는 스캔에서 제외
                info(f"⏭️ {model_type} 스캔 제외 (출력 폴더)")
                continue
            
            if model_type == 'vae':
                tasks[model_type] = self._scan_vae_directory(path)
            else:
                tasks[model_type] = self._scan_directory(path, model_type)
            
        info(f"🚀 스캔 작업 시작: {list(tasks.keys())}")
        list_of_results = await asyncio.gather(*tasks.values())
        result = dict(zip(tasks.keys(), list_of_results))
        
        info(f"<<< 모든 모델 스캔 완료. VAE 발견: {len(result.get('vae', {}))}")
        info(r"📊 스캔 결과 요약:")
        for model_type, data in result.items():
            total_items = sum(len(items) for items in data.values())
            info(f"   {model_type}: {total_items}개")
        return result

    async def _scan_vae_directory(self, base_path: Path) -> Dict[str, List[Dict[str, Any]]]:
        """VAE 디렉토리 전용 스캔 함수 (하위 폴더 포함)"""
        if not await asyncio.to_thread(base_path.exists):
            await asyncio.to_thread(base_path.mkdir, parents=True, exist_ok=True)
            return {}

        def scan_sync():
            """VAE 파일 스캔 (재귀적으로 모든 하위 폴더 탐색)"""
            result = defaultdict(list)
            
            info(f"  -> VAE 스캔 시작: {base_path}")
            vae_count = 0
            
            # 모든 파일을 재귀적으로 탐색
            for file_path in base_path.rglob('*'):
                if file_path.is_file():
                    # VAE 파일 확인 (더 관대한 조건)
                    file_lower = file_path.name.lower()
                    suffix_lower = file_path.suffix.lower()
                    
                    is_vae_file = (
                        # 확장자 기반 체크
                        suffix_lower in {'.safetensors', '.ckpt', '.pt', '.bin'} and
                        (
                            # 파일명에 'vae' 포함
                            'vae' in file_lower or
                            # 또는 vae 전용 확장자
                            file_lower.endswith('.vae.pt') or
                            file_lower.endswith('.vae.safetensors') or
                            # 또는 VAE 폴더 내의 모든 모델 파일
                            'vae' in str(file_path.parent).lower()
                        )
                    )
                    
                    if is_vae_file:
                        relative_path = file_path.relative_to(base_path)
                        folder = str(relative_path.parent) if relative_path.parent != Path('.') else 'Root'
                        
                        file_info = {
                            'name': file_path.stem,
                            'filename': file_path.name,
                            'path': str(file_path),
                            'folder': folder,
                            'size_mb': file_path.stat().st_size / (1024 * 1024),
                            'type': 'vae',
                        }
                        
                        # VAE 메타데이터 추출 (safetensors인 경우만)
                        if file_path.suffix.lower() == '.safetensors':
                            try:
                                vae_meta = self.metadata_parser.extract_from_safetensors(file_path)
                                if vae_meta:
                                    file_info['metadata'] = vae_meta
                            except Exception as e:
                                info(f"VAE 메타데이터 추출 실패 ({file_path.name}): {e}")
                        
                        result[folder].append(file_info)
                        vae_count += 1
                        info(f"    VAE 발견: {file_path.relative_to(base_path)}")

            info(f"  -> VAE 스캔 완료: 총 {vae_count}개")

            # 폴더별 정렬
            for folder_items in result.values():
                folder_items.sort(key=lambda x: x['name'].lower())
            
            return dict(result)
        
        return await asyncio.to_thread(scan_sync)

    async def _scan_directory(self, base_path: Path, model_type: str) -> Dict[str, List[Dict[str, Any]]]:
        """지정된 디렉토리 하나를 스캔하는 비공개 헬퍼 함수."""
        debug_emoji(f"{model_type} 스캔 시작: {base_path}")
        if not await asyncio.to_thread(base_path.exists):
            warning_emoji(f"{model_type} 경로가 존재하지 않음: {base_path}")
            await asyncio.to_thread(base_path.mkdir, parents=True, exist_ok=True)
            return {}

        def scan_sync():
            """실제 파일 시스템 I/O를 수행하는 동기 함수"""
            result = defaultdict(list)
            info(f"📂 {model_type} 파일 스캔 중: {base_path}")
            
            for file_path in base_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in self.model_extensions:
                    relative_path = file_path.relative_to(base_path)
                    folder = str(relative_path.parent) if relative_path.parent != Path('.') else 'Root'
                    
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
                        # --- [수정된 로직 시작] ---
                        # 1. 모델 타입 정보는 항상 safetensors 파일에서 직접 추출
                        model_specific_info = self.metadata_parser.get_model_info(file_path)
                        file_info.update(model_specific_info)

                        # 2. 생성 파라미터 메타데이터는 오직 이름이 같은 .png 파일에서만 가져옴
                        png_path = file_path.with_suffix('.png')
                        if png_path.exists():
                            # info(f"📷 PNG 메타데이터 발견: {png_path.name}") # 디버깅용
                            png_metadata = self.metadata_parser.extract_from_png(png_path)
                            # PNG에서 추출한 메타데이터를 file_info의 'metadata'에 덮어씀
                            file_info['metadata'] = png_metadata
                        else:
                            # PNG 파일이 없으면 메타데이터는 비워둠
                            file_info['metadata'] = {}
                            
                    elif model_type == 'loras':
                        # --- [LoRA 스캔 로직 개선] ---
                        info(f"🎯 LoRA 발견: {file_path.relative_to(base_path)}")
                        # 1. LoRA 메타데이터는 safetensors 파일에서 직접 추출
                        lora_specific_info = self.metadata_parser.get_lora_info(file_path)
                        file_info.update(lora_specific_info)
                        
                        # 2. 생성 파라미터 메타데이터는 오직 이름이 같은 .png 파일에서만 가져옴
                        png_path = file_path.with_suffix('.png')
                        if png_path.exists():
                            # info(f"📷 LoRA PNG 메타데이터 발견: {png_path.name}") # 디버깅용
                            png_metadata = self.metadata_parser.extract_from_png(png_path)
                            # PNG에서 추출한 메타데이터를 file_info의 'metadata'에 덮어씀
                            file_info['metadata'] = png_metadata
                        else:
                            # PNG 파일이 없으면 safetensors 메타데이터 사용
                            if file_path.suffix.lower() == '.safetensors':
                                lora_meta = self.metadata_parser.extract_from_safetensors(file_path)
                                file_info['metadata'] = lora_meta
                            else:
                                file_info['metadata'] = {}
                    
                    result[folder].append(file_info)

            # 폴더별 정렬
            for folder_items in result.values():
                folder_items.sort(key=lambda x: x['name'].lower())
            
            return dict(result)
        
        return await asyncio.to_thread(scan_sync)