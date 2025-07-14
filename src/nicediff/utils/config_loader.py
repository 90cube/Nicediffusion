"""
설정 로더 유틸리티
"""

import toml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """설정 파일 로더"""
    
    def __init__(self):
        self.config_path = Path("config.toml")
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        if self.config_path.exists():
            try:
                return toml.load(self.config_path)
            except Exception as e:
                print(f"설정 파일 로드 실패: {e}")
                return {}
        else:
            print("설정 파일이 없습니다. 기본 설정을 사용합니다.")
            return {}
    
    def get_paths_config(self) -> Dict[str, str]:
        """경로 설정 반환"""
        paths = self.config.get('paths', {})
        
        # 기본 경로 설정
        default_paths = {
            'models': 'models',
            'loras': 'models/loras',
            'vae': 'models/vae',
            'outputs': 'outputs',
            'temp': 'temp'
        }
        
        # 설정 파일의 경로와 기본 경로 병합
        for key, default_value in default_paths.items():
            if key not in paths:
                paths[key] = default_value
        
        return paths
    
    def get_config(self) -> Dict[str, Any]:
        """전체 설정 반환"""
        return self.config
