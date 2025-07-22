"""
최적화된 Bridge 클래스
Canvas와 Python 간의 빠른 통신을 위한 개선된 버전
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class BridgeState(Enum):
    """Bridge 상태"""
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class BridgeConfig:
    """Bridge 설정"""
    timeout: float = 2.0  # 기본 타임아웃 2초
    retry_count: int = 2  # 재시도 횟수
    retry_delay: float = 0.1  # 재시도 간격
    enable_fallback: bool = True  # 폴백 시스템 활성화


class OptimizedBridge:
    """최적화된 Bridge 클래스"""
    
    def __init__(self, tab_id: str, config: BridgeConfig = None):
        self.tab_id = tab_id
        self.config = config or BridgeConfig()
        self.state = BridgeState.INITIALIZING
        self.is_ready = False
        self.callbacks = {}
        self.last_ready_check = 0
        self.ready_check_interval = 0.5  # 준비 상태 확인 간격
        
        # 성능 최적화를 위한 캐시
        self._ready_cache = None
        self._ready_cache_time = 0
        self._cache_duration = 0.1  # 캐시 유효 시간
        
        # 초기화 시작
        self._init_bridge()
    
    def _init_bridge(self):
        """Bridge 초기화"""
        try:
            # JavaScript에서 Bridge 초기화
            self._send_js_command("init_bridge", {
                "tab_id": self.tab_id,
                "config": {
                    "timeout": self.config.timeout,
                    "retry_count": self.config.retry_count
                }
            })
            
            # 비동기 초기화 완료 대기
            asyncio.create_task(self._wait_for_ready())
            
        except Exception as e:
            print(f"❌ Bridge 초기화 실패: {e}")
            self.state = BridgeState.ERROR
    
    async def _wait_for_ready(self):
        """Bridge 준비 대기"""
        start_time = time.time()
        
        while time.time() - start_time < self.config.timeout:
            if self._check_js_ready():
                self.state = BridgeState.READY
                self.is_ready = True
                print(f"✅ Bridge 준비 완료: {self.tab_id}")
                return
            
            await asyncio.sleep(0.1)
        
        # 타임아웃 발생
        self.state = BridgeState.TIMEOUT
        print(f"⚠️ Bridge 준비 타임아웃: {self.tab_id}")
        
        # 폴백 시스템 활성화
        if self.config.enable_fallback:
            self._activate_fallback()
    
    def _check_js_ready(self) -> bool:
        """JavaScript 준비 상태 확인 (캐시 적용)"""
        current_time = time.time()
        
        # 캐시된 결과가 유효한 경우
        if (self._ready_cache is not None and 
            current_time - self._ready_cache_time < self._cache_duration):
            return self._ready_cache
        
        # 실제 확인
        try:
            # JavaScript에서 준비 상태 확인
            result = self._send_js_command("check_ready", {"tab_id": self.tab_id})
            self._ready_cache = result.get("ready", False)
            self._ready_cache_time = current_time
            return self._ready_cache
        except Exception:
            self._ready_cache = False
            self._ready_cache_time = current_time
            return False
    
    def _activate_fallback(self):
        """폴백 시스템 활성화"""
        print(f"🔄 폴백 시스템 활성화: {self.tab_id}")
        # 폴백 모드에서는 기본 기능만 제공
        self.is_ready = True
        self.state = BridgeState.READY
    
    def wait_for_ready(self, timeout: float = None) -> bool:
        """Bridge 준비 대기 (동기 버전)"""
        if timeout is None:
            timeout = self.config.timeout
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_ready:
                return True
            
            # 짧은 대기
            time.sleep(0.05)
        
        return False
    
    async def wait_for_ready_async(self, timeout: float = None) -> bool:
        """Bridge 준비 대기 (비동기 버전)"""
        if timeout is None:
            timeout = self.config.timeout
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_ready:
                return True
            
            await asyncio.sleep(0.05)
        
        return False
    
    def _send_js_command(self, command: str, data: Any = None) -> Dict[str, Any]:
        """JavaScript 명령 전송 (최적화된 버전)"""
        try:
            # NiceGUI의 JavaScript 실행
            import nicegui.ui as ui
            
            # 명령을 JSON으로 직렬화
            import json
            command_data = {
                "command": command,
                "data": data,
                "timestamp": time.time()
            }
            
            # JavaScript 실행
            result = ui.run_javascript(f"""
                if (window.bridgeManager) {{
                    return window.bridgeManager.executeCommand({json.dumps(command_data)});
                }} else {{
                    return {{"error": "Bridge manager not found"}};
                }}
            """)
            
            return result or {}
            
        except Exception as e:
            print(f"❌ JavaScript 명령 실행 실패: {e}")
            return {"error": str(e)}
    
    def send_to_js(self, command: str, data: Any = None) -> bool:
        """JavaScript로 데이터 전송 (최적화된 버전)"""
        try:
            if not self.is_ready:
                print(f"⚠️ Bridge가 준비되지 않음: {self.tab_id}")
                return False
            
            result = self._send_js_command(command, data)
            return "error" not in result
            
        except Exception as e:
            print(f"❌ 데이터 전송 실패: {e}")
            return False
    
    def register_callback(self, event: str, callback: Callable):
        """콜백 등록 (최적화된 버전)"""
        self.callbacks[event] = callback
        print(f"📝 콜백 등록: {event}")
    
    def handle_js_callback(self, event: str, data: Any):
        """JavaScript 콜백 처리 (최적화된 버전)"""
        try:
            if event in self.callbacks:
                # 비동기 콜백 실행
                asyncio.create_task(self._execute_callback(event, data))
            else:
                print(f"⚠️ 등록되지 않은 콜백: {event}")
                
        except Exception as e:
            print(f"❌ 콜백 처리 실패: {e}")
    
    async def _execute_callback(self, event: str, data: Any):
        """콜백 실행 (비동기)"""
        try:
            callback = self.callbacks[event]
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            print(f"❌ 콜백 실행 실패: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Bridge 상태 반환"""
        return {
            "tab_id": self.tab_id,
            "state": self.state.value,
            "is_ready": self.is_ready,
            "config": {
                "timeout": self.config.timeout,
                "retry_count": self.config.retry_count,
                "enable_fallback": self.config.enable_fallback
            },
            "callbacks_count": len(self.callbacks)
        }
    
    def reset(self):
        """Bridge 재설정"""
        self.state = BridgeState.INITIALIZING
        self.is_ready = False
        self._ready_cache = None
        self._ready_cache_time = 0
        self._init_bridge()
    
    def cleanup(self):
        """Bridge 정리"""
        try:
            self._send_js_command("cleanup", {"tab_id": self.tab_id})
            self.callbacks.clear()
            print(f"🧹 Bridge 정리 완료: {self.tab_id}")
        except Exception as e:
            print(f"❌ Bridge 정리 실패: {e}")


class FastBridge(OptimizedBridge):
    """초고속 Bridge (최소 기능)"""
    
    def __init__(self, tab_id: str):
        # 최소 설정으로 초고속 초기화
        config = BridgeConfig(
            timeout=1.0,  # 1초 타임아웃
            retry_count=1,  # 1회 재시도
            retry_delay=0.05,  # 0.05초 간격
            enable_fallback=True
        )
        super().__init__(tab_id, config)
    
    def _init_bridge(self):
        """초고속 초기화"""
        # 최소한의 초기화만 수행
        self.is_ready = True
        self.state = BridgeState.READY
        print(f"⚡ 초고속 Bridge 준비: {self.tab_id}")
    
    def wait_for_ready(self, timeout: float = None) -> bool:
        """즉시 준비 상태 반환"""
        return True
    
    async def wait_for_ready_async(self, timeout: float = None) -> bool:
        """즉시 준비 상태 반환 (비동기)"""
        return True


# Bridge 팩토리
class BridgeFactory:
    """Bridge 생성 팩토리"""
    
    @staticmethod
    def create_bridge(tab_id: str, bridge_type: str = "optimized") -> OptimizedBridge:
        """Bridge 생성"""
        if bridge_type == "fast":
            return FastBridge(tab_id)
        else:
            return OptimizedBridge(tab_id)
    
    @staticmethod
    def create_txt2img_bridge() -> OptimizedBridge:
        """Txt2Img용 최적화된 Bridge"""
        config = BridgeConfig(
            timeout=1.5,  # Txt2Img는 빠른 응답 필요
            retry_count=1,
            enable_fallback=True
        )
        return OptimizedBridge("txt2img", config)
    
    @staticmethod
    def create_img2img_bridge() -> OptimizedBridge:
        """Img2Img용 최적화된 Bridge"""
        config = BridgeConfig(
            timeout=2.0,  # Img2Img는 이미지 처리 시간 고려
            retry_count=2,
            enable_fallback=True
        )
        return OptimizedBridge("img2img", config) 