# src/nicediff/core/error_handler.py
"""전역 에러 핸들러"""

# UI 직접 import 제거 - 이벤트 기반 알림 시스템 사용
import traceback
from typing import Callable
import functools

class ErrorHandler:
    """에러 처리 유틸리티"""
    
    @staticmethod
    def safe_async(func: Callable):
        """비동기 함수 에러 처리 데코레이터"""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_msg = f"{func.__name__}에서 오류 발생: {str(e)}"
                print(f"❌ {error_msg}")
                traceback.print_exc()
                ui.notify(error_msg, type='negative', duration=5)
                return None
        return wrapper
    
    @staticmethod
    def safe_sync(func: Callable):
        """동기 함수 에러 처리 데코레이터"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"{func.__name__}에서 오류 발생: {str(e)}"
                print(f"❌ {error_msg}")
                traceback.print_exc()
                ui.notify(error_msg, type='negative', duration=5)
                return None
        return wrapper
    
    @staticmethod
    def handle_generation_error(error: Exception):
        """이미지 생성 관련 에러 처리"""
        error_messages = {
            "CUDA out of memory": "GPU 메모리가 부족합니다. 이미지 크기를 줄여주세요.",
            "Pipeline not loaded": "모델이 로드되지 않았습니다. 먼저 모델을 선택해주세요.",
            "No prompt": "프롬프트를 입력해주세요.",
        }
        
        error_str = str(error)
        for key, message in error_messages.items():
            if key in error_str:
                ui.notify(message, type='warning', duration=5)
                return
        
        # 일반 에러
        ui.notify(f"생성 오류: {error_str}", type='negative', duration=5)