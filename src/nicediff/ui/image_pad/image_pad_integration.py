#!/usr/bin/env python3
"""
커스텀 이미지 패드 통합 래퍼
메인 프로그램과 연결하는 인터페이스
"""

import threading
import numpy as np
from typing import Optional, Callable
from .custom_image_pad import CustomImagePad

class ImagePadIntegration:
    def __init__(self, state_manager, callback_function: Optional[Callable] = None):
        """
        이미지 패드 통합 초기화
        
        Args:
            state_manager: 메인 프로그램의 StateManager
            callback_function: 추가 콜백 함수 (선택사항)
        """
        self.state_manager = state_manager
        self.callback_function = callback_function
        self.image_pad = None
        self.image_pad_thread = None
        
    def open_image_pad(self):
        """이미지 패드 창 열기"""
        if self.image_pad is None:
            # 별도 스레드에서 이미지 패드 실행
            self.image_pad_thread = threading.Thread(target=self._run_image_pad, daemon=True)
            self.image_pad_thread.start()
            
    def _run_image_pad(self):
        """이미지 패드 실행"""
        def on_image_uploaded(np_image: np.ndarray):
            """이미지 업로드 시 호출되는 콜백"""
            print(f"🖼️ 커스텀 이미지 패드에서 이미지 업로드됨: {np_image.shape}")
            
            # StateManager에 이미지 저장
            self.state_manager.set('uploaded_image', np_image)
            self.state_manager.set('init_image', np_image)  # PIL Image로 변환 필요시
            
            # 자동으로 img2img 모드로 전환
            self.state_manager.set('current_mode', 'img2img')
            
            # 추가 콜백 실행
            if self.callback_function:
                self.callback_function(np_image)
                
        # 이미지 패드 생성 및 실행
        self.image_pad = CustomImagePad(callback_function=on_image_uploaded)
        self.image_pad.run()
        
    def close_image_pad(self):
        """이미지 패드 창 닫기"""
        if self.image_pad:
            self.image_pad.close()
            self.image_pad = None
            
    def get_current_image(self) -> Optional[np.ndarray]:
        """현재 이미지 가져오기"""
        if self.image_pad:
            return self.image_pad.get_current_image()
        return None
        
    def get_current_image_path(self) -> Optional[str]:
        """현재 이미지 파일 경로 가져오기"""
        if self.image_pad:
            return self.image_pad.get_current_image_path()
        return None
        
    def is_open(self) -> bool:
        """이미지 패드가 열려있는지 확인"""
        return self.image_pad is not None

# 사용 예시
if __name__ == "__main__":
    # 테스트용 StateManager 모킹
    class MockStateManager:
        def __init__(self):
            self.data = {}
            
        def set(self, key, value):
            self.data[key] = value
            print(f"StateManager.set({key}, {type(value)})")
            
    # 테스트
    state_manager = MockStateManager()
    
    def test_callback(np_image):
        print(f"테스트 콜백 실행: {np_image.shape}")
        
    integration = ImagePadIntegration(state_manager, test_callback)
    integration.open_image_pad() 