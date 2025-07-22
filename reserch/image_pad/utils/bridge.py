from ....core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)
"""
Python-JavaScript Bridge for Canvas Communication
Canvas 매니저와 Python 간의 표준화된 통신 인터페이스
"""

import base64
import io
from typing import Optional, Dict, Any, List
from PIL import Image
import numpy as np
from nicegui import ui


class CanvasBridge:
    """Canvas와 Python 간의 통신을 담당하는 Bridge 클래스"""
    
    def __init__(self, canvas_id: str):
        self.canvas_id = canvas_id
        self.is_ready = False
        self.event_handlers = {}
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """JavaScript 이벤트 핸들러 설정"""
        
        # NiceGUI의 이벤트 핸들러는 나중에 구현
        # 현재는 기본 핸들러만 설정
        pass
    
    def register_event_handler(self, event_name: str, handler):
        """이벤트 핸들러 등록"""
        self.event_handlers[event_name] = handler
    
    def create_canvas_manager(self) -> bool:
        """Canvas 매니저 생성"""
        if not self.is_ready:
            script = f"""
                if (typeof createCanvasManager === 'function') {{
                    createCanvasManager('{self.canvas_id}');
                    console.log('✅ Canvas 매니저 생성됨: {self.canvas_id}');
                }} else {{
                    console.error('❌ createCanvasManager 함수를 찾을 수 없음');
                }}
            """
            ui.run_javascript(script)
            return True
        return False
    
    def load_image(self, image: Image.Image, options: Dict[str, Any] = None) -> bool:
        """PIL Image를 Canvas에 로드"""
        if not self.is_ready:
            warning_emoji(r"Canvas가 준비되지 않음")
            return False
        
        try:
            # PIL Image를 base64로 변환
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # JavaScript 함수 호출
            options_dict = options or {}
            script = f"""
                if (typeof loadImageToCanvas === 'function') {{
                    const success = loadImageToCanvas('{self.canvas_id}', '{img_str}', {options_dict});
                    if (success) {{
                        console.log('✅ 이미지 로드 성공');
                    }} else {{
                        console.error('❌ 이미지 로드 실패');
                    }}
                }} else {{
                    console.error('❌ loadImageToCanvas 함수를 찾을 수 없음');
                }}
            """
            ui.run_javascript(script)
            return True
            
        except Exception as e:
            failure(f"이미지 로드 실패: {e}")
            return False
    
    def load_image_from_base64(self, base64_data: str, options: Dict[str, Any] = None) -> bool:
        """Base64 이미지를 Canvas에 로드"""
        if not self.is_ready:
            warning_emoji(r"Canvas가 준비되지 않음")
            return False
        
        try:
            options_dict = options or {}
            script = f"""
                if (typeof loadImageToCanvas === 'function') {{
                    const success = loadImageToCanvas('{self.canvas_id}', '{base64_data}', {options_dict});
                    if (success) {{
                        console.log('✅ Base64 이미지 로드 성공');
                    }} else {{
                        console.error('❌ Base64 이미지 로드 실패');
                    }}
                }} else {{
                    console.error('❌ loadImageToCanvas 함수를 찾을 수 없음');
                }}
            """
            ui.run_javascript(script)
            return True
            
        except Exception as e:
            failure(f"Base64 이미지 로드 실패: {e}")
            return False
    
    def remove_object(self, object_id: str) -> bool:
        """객체 삭제"""
        if not self.is_ready:
            return False
        
        script = f"""
            const manager = getCanvasManager('{self.canvas_id}');
            if (manager) {{
                const success = manager.removeObject('{object_id}');
                if (success) {{
                    console.log('✅ 객체 삭제 성공: {object_id}');
                }} else {{
                    console.error('❌ 객체 삭제 실패: {object_id}');
                }}
            }}
        """
        ui.run_javascript(script)
        return True
    
    def clear_canvas(self) -> bool:
        """Canvas 초기화"""
        if not self.is_ready:
            return False
        
        script = f"""
            const manager = getCanvasManager('{self.canvas_id}');
            if (manager) {{
                manager.clearCanvas();
                console.log('✅ Canvas 초기화 완료');
            }}
        """
        ui.run_javascript(script)
        return True
    
    def get_canvas_state(self) -> Dict[str, Any]:
        """Canvas 상태 가져오기"""
        if not self.is_ready:
            return {}
        
        # JavaScript에서 상태를 가져오는 함수 호출
        script = f"""
            const manager = getCanvasManager('{self.canvas_id}');
            if (manager) {{
                const state = manager.getCanvasState();
                console.log('📊 Canvas 상태:', state);
                // Python으로 상태 전송 (실제 구현에서는 더 복잡한 통신 필요)
            }}
        """
        ui.run_javascript(script)
        return {}
    
    def resize_canvas(self, width: int, height: int) -> bool:
        """Canvas 크기 조정"""
        if not self.is_ready:
            return False
        
        script = f"""
            const manager = getCanvasManager('{self.canvas_id}');
            if (manager) {{
                manager.canvas.setDimensions({{
                    width: {width},
                    height: {height}
                }});
                manager.canvas.renderAll();
                console.log('📐 Canvas 크기 조정:', {width}, 'x', {height});
            }}
        """
        ui.run_javascript(script)
        return True
    
    def select_object(self, object_id: str) -> bool:
        """객체 선택"""
        if not self.is_ready:
            return False
        
        script = f"""
            const manager = getCanvasManager('{self.canvas_id}');
            if (manager) {{
                const object = manager.objects.get('{object_id}');
                if (object) {{
                    manager.canvas.setActiveObject(object);
                    manager.canvas.renderAll();
                    console.log('🎯 객체 선택됨: {object_id}');
                }}
            }}
        """
        ui.run_javascript(script)
        return True
    
    def set_object_properties(self, object_id: str, properties: Dict[str, Any]) -> bool:
        """객체 속성 설정"""
        if not self.is_ready:
            return False
        
        # 속성을 JSON으로 변환
        import json
        props_json = json.dumps(properties)
        
        script = f"""
            const manager = getCanvasManager('{self.canvas_id}');
            if (manager) {{
                const object = manager.objects.get('{object_id}');
                if (object) {{
                    const props = {props_json};
                    object.set(props);
                    manager.canvas.renderAll();
                    console.log('⚙️ 객체 속성 설정됨: {object_id}', props);
                }}
            }}
        """
        ui.run_javascript(script)
        return True
    
    def export_canvas_as_image(self) -> Optional[str]:
        """Canvas를 이미지로 내보내기"""
        if not self.is_ready:
            return None
        
        # JavaScript에서 Canvas 데이터를 가져오는 함수 호출
        script = f"""
            const manager = getCanvasManager('{self.canvas_id}');
            if (manager) {{
                const dataURL = manager.canvas.toDataURL('image/png');
                console.log('📸 Canvas 내보내기 완료');
                // Python으로 데이터 전송 (실제 구현에서는 더 복잡한 통신 필요)
            }}
        """
        ui.run_javascript(script)
        return None
    
    def wait_for_ready(self, timeout: float = 10.0) -> bool:
        """Canvas 준비 대기"""
        import time
        start_time = time.time()
        
        while not self.is_ready and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        return self.is_ready 