"""
표준화된 로깅 시스템
모든 print() 문을 logging으로 대체하기 위한 중앙 로깅 관리
"""

import logging
import sys
from typing import Optional
from pathlib import Path


class NiceDiffLogger:
    """NiceDiffusion 전용 로거"""
    
    def __init__(self, name: str = "nicediff", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 중복 핸들러 방지
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """로거 핸들러 설정"""
        # 콘솔 핸들러 (색상 지원)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 색상 포매터
        formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        # 파일 핸들러
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / "nicediff.log", encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # 핸들러 추가
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def debug(self, message: str):
        """디버그 로그"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """오류 로그"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """치명적 오류 로그"""
        self.logger.critical(message)
    
    # 편의 메서드들 (이모지 포함)
    def success(self, message: str):
        """성공 로그"""
        self.logger.info(f"✅ {message}")
    
    def failure(self, message: str):
        """실패 로그"""
        self.logger.error(f"❌ {message}")
    
    def warning_emoji(self, message: str):
        """경고 로그 (이모지 포함)"""
        self.logger.warning(f"⚠️ {message}")
    
    def info_emoji(self, message: str):
        """정보 로그 (이모지 포함)"""
        self.logger.info(f"ℹ️ {message}")
    
    def debug_emoji(self, message: str):
        """디버그 로그 (이모지 포함)"""
        self.logger.debug(f"🔍 {message}")
    
    def process_emoji(self, message: str):
        """처리 로그 (이모지 포함)"""
        self.logger.info(f"🔄 {message}")
    
    def model_emoji(self, message: str):
        """모델 관련 로그 (이모지 포함)"""
        self.logger.info(f"🤖 {message}")
    
    def image_emoji(self, message: str):
        """이미지 관련 로그 (이모지 포함)"""
        self.logger.info(f"🖼️ {message}")
    
    def canvas_emoji(self, message: str):
        """Canvas 관련 로그 (이모지 포함)"""
        self.logger.info(f"🎨 {message}")
    
    def ui_emoji(self, message: str):
        """UI 관련 로그 (이모지 포함)"""
        self.logger.info(f"🖥️ {message}")


class ColoredFormatter(logging.Formatter):
    """색상 지원 포매터"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # 청록색
        'INFO': '\033[32m',     # 초록색
        'WARNING': '\033[33m',  # 노란색
        'ERROR': '\033[31m',    # 빨간색
        'CRITICAL': '\033[35m', # 자주색
        'RESET': '\033[0m'      # 리셋
    }
    
    def format(self, record):
        # 원본 메시지 저장
        original_msg = record.getMessage()
        
        # 색상 적용
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        colored_levelname = f"{color}{record.levelname}{self.COLORS['RESET']}"
        
        # 레벨명 교체
        record.levelname = colored_levelname
        
        # 포맷팅
        formatted = super().format(record)
        
        return formatted


# 전역 로거 인스턴스
logger = NiceDiffLogger()

# 편의 함수들
def debug(message: str):
    """디버그 로그"""
    logger.debug(message)

def info(message: str):
    """정보 로그"""
    logger.info(message)

def warning(message: str):
    """경고 로그"""
    logger.warning(message)

def error(message: str):
    """오류 로그"""
    logger.error(message)

def success(message: str):
    """성공 로그"""
    logger.success(message)

def failure(message: str):
    """실패 로그"""
    logger.failure(message)

def warning_emoji(message: str):
    """경고 로그 (이모지 포함)"""
    logger.warning_emoji(message)

def info_emoji(message: str):
    """정보 로그 (이모지 포함)"""
    logger.info_emoji(message)

def debug_emoji(message: str):
    """디버그 로그 (이모지 포함)"""
    logger.debug_emoji(message)

def process_emoji(message: str):
    """처리 로그 (이모지 포함)"""
    logger.process_emoji(message)

def model_emoji(message: str):
    """모델 관련 로그 (이모지 포함)"""
    logger.model_emoji(message)

def image_emoji(message: str):
    """이미지 관련 로그 (이모지 포함)"""
    logger.image_emoji(message)

def canvas_emoji(message: str):
    """Canvas 관련 로그 (이모지 포함)"""
    logger.canvas_emoji(message)

def ui_emoji(message: str):
    """UI 관련 로그 (이모지 포함)"""
    logger.ui_emoji(message) 