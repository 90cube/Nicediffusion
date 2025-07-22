from ..core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)
"""
토크나이저 관리 서비스
커스텀 토크나이저 파일들을 스캔하고 로드하는 기능
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from transformers import CLIPTokenizer, CLIPTokenizerFast


class TokenizerManager:
    """토크나이저 관리자"""
    
    def __init__(self, tokenizers_path: str):
        self.tokenizers_path = Path(tokenizers_path)
        self.available_tokenizers: Dict[str, Dict[str, Any]] = {}
        self.loaded_tokenizers: Dict[str, CLIPTokenizer] = {}
        self.current_tokenizer: Optional[CLIPTokenizer] = None
        
    def scan_tokenizers(self) -> Dict[str, Dict[str, Any]]:
        """토크나이저 디렉토리 스캔"""
        if not self.tokenizers_path.exists():
            warning_emoji(f"토크나이저 경로가 존재하지 않습니다: {self.tokenizers_path}")
            return {}
        
        self.available_tokenizers.clear()
        
        for tokenizer_dir in self.tokenizers_path.iterdir():
            if not tokenizer_dir.is_dir():
                continue
                
            tokenizer_name = tokenizer_dir.name
            tokenizer_info = self._validate_tokenizer_directory(tokenizer_dir)
            
            if tokenizer_info:
                self.available_tokenizers[tokenizer_name] = tokenizer_info
                success(f"토크나이저 발견: {tokenizer_name}")
            else:
                warning_emoji(f"유효하지 않은 토크나이저: {tokenizer_name}")
        
        info(f"📋 총 {len(self.available_tokenizers)}개의 토크나이저 발견")
        return self.available_tokenizers
    
    def _validate_tokenizer_directory(self, tokenizer_dir: Path) -> Optional[Dict[str, Any]]:
        """토크나이저 디렉토리 유효성 검사"""
        required_files = ['tokenizer_config.json', 'vocab.json']
        optional_files = ['special_tokens_map.json', 'merges.txt']
        
        # 필수 파일 확인
        for required_file in required_files:
            if not (tokenizer_dir / required_file).exists():
                return None
        
        # 파일 정보 수집
        tokenizer_info = {
            'name': tokenizer_dir.name,
            'path': str(tokenizer_dir),
            'files': {},
            'has_merges': False,
            'has_special_tokens': False
        }
        
        # 파일 존재 여부 확인
        for file_name in required_files + optional_files:
            file_path = tokenizer_dir / file_name
            if file_path.exists():
                tokenizer_info['files'][file_name] = {
                    'path': str(file_path),
                    'size': file_path.stat().st_size
                }
                
                if file_name == 'merges.txt':
                    tokenizer_info['has_merges'] = True
                elif file_name == 'special_tokens_map.json':
                    tokenizer_info['has_special_tokens'] = True
        
        return tokenizer_info
    
    def load_tokenizer(self, tokenizer_name: str) -> Optional[CLIPTokenizer]:
        """토크나이저 로드"""
        if tokenizer_name in self.loaded_tokenizers:
            success(f"이미 로드된 토크나이저 사용: {tokenizer_name}")
            return self.loaded_tokenizers[tokenizer_name]
        
        if tokenizer_name not in self.available_tokenizers:
            failure(f"토크나이저를 찾을 수 없습니다: {tokenizer_name}")
            return None
        
        tokenizer_info = self.available_tokenizers[tokenizer_name]
        tokenizer_path = Path(tokenizer_info['path'])
        
        try:
            process_emoji(f"토크나이저 로드 중: {tokenizer_name}")
            
            # CLIPTokenizer 로드
            tokenizer = CLIPTokenizer.from_pretrained(
                tokenizer_path,
                local_files_only=True
            )
            
            # 토크나이저 설정
            tokenizer.padding_side = "right"
            tokenizer.truncation_side = "right"
            
            self.loaded_tokenizers[tokenizer_name] = tokenizer
            self.current_tokenizer = tokenizer
            
            success(f"토크나이저 로드 완료: {tokenizer_name}")
            info(f"   - 모델 최대 길이: {tokenizer.model_max_length}")
            info(f"   - 어휘 크기: {tokenizer.vocab_size}")
            
            return tokenizer
            
        except Exception as e:
            failure(f"토크나이저 로드 실패: {tokenizer_name}")
            info(f"   오류: {e}")
            return None
    
    def get_current_tokenizer(self) -> Optional[CLIPTokenizer]:
        """현재 로드된 토크나이저 반환"""
        return self.current_tokenizer
    
    def get_tokenizer_info(self, tokenizer_name: str) -> Optional[Dict[str, Any]]:
        """토크나이저 정보 반환"""
        return self.available_tokenizers.get(tokenizer_name)
    
    def list_available_tokenizers(self) -> List[str]:
        """사용 가능한 토크나이저 목록 반환"""
        return list(self.available_tokenizers.keys())
    
    def unload_tokenizer(self, tokenizer_name: str):
        """토크나이저 언로드"""
        if tokenizer_name in self.loaded_tokenizers:
            del self.loaded_tokenizers[tokenizer_name]
            if self.current_tokenizer and tokenizer_name in str(self.current_tokenizer):
                self.current_tokenizer = None
            success(f"토크나이저 언로드: {tokenizer_name}")
    
    def unload_all_tokenizers(self):
        """모든 토크나이저 언로드"""
        self.loaded_tokenizers.clear()
        self.current_tokenizer = None
        success(r"모든 토크나이저 언로드 완료")
    
    def get_tokenizer_stats(self, tokenizer_name: str) -> Optional[Dict[str, Any]]:
        """토크나이저 통계 정보"""
        tokenizer = self.loaded_tokenizers.get(tokenizer_name)
        if not tokenizer:
            return None
        
        return {
            'name': tokenizer_name,
            'model_max_length': tokenizer.model_max_length,
            'vocab_size': tokenizer.vocab_size,
            'pad_token': tokenizer.pad_token,
            'eos_token': tokenizer.eos_token,
            'unk_token': tokenizer.unk_token,
            'bos_token': tokenizer.bos_token,
            'pad_token_id': tokenizer.pad_token_id,
            'eos_token_id': tokenizer.eos_token_id,
            'unk_token_id': tokenizer.unk_token_id,
            'bos_token_id': tokenizer.bos_token_id,
        } 