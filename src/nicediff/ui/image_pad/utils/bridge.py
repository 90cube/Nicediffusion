"""
Python-JavaScript 브릿지
양방향 통신을 관리하는 모듈
"""

from nicegui import ui
import json
import base64
import io
from PIL import Image
import numpy as np
from typing import Dict, Any, Optional, Callable

class CanvasBridge:
    """Python-JavaScript 브릿지 클래스"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.state_manager = None
        
    def set_state_manager(self, state_manager):
        """StateManager 설정"""
        self.state_manager = state_manager
        
    def register_handler(self, event_type: str, handler: Callable):
        """이벤트 핸들러 등록"""
        self.handlers[event_type] = handler
        print(f"🔗 브릿지 핸들러 등록: {event_type}")
        
    def send_to_canvas(self, command: str, data: Any = None):
        """Canvas로 명령 전송"""
        try:
            if data is not None:
                json_data = json.dumps(data, default=str)
                js_code = f'window.canvasManager.{command}({json_data})'
            else:
                js_code = f'window.canvasManager.{command}()'
                
            ui.run_javascript(js_code)
            print(f"📤 Canvas 명령 전송: {command}")
            
        except Exception as e:
            print(f"❌ Canvas 명령 전송 실패: {e}")
            
    def receive_from_canvas(self, event_type: str, data: Any):
        """Canvas에서 데이터 수신"""
        try:
            if event_type in self.handlers:
                self.handlers[event_type](data)
                print(f"📥 Canvas 이벤트 수신: {event_type}")
            else:
                print(f"⚠️ 처리되지 않은 Canvas 이벤트: {event_type}")
                
        except Exception as e:
            print(f"❌ Canvas 이벤트 처리 실패: {e}")
            
    def handle_file_upload(self, filename: str, base64_data: str):
        """파일 업로드 처리"""
        try:
            print(f"📁 파일 업로드 처리: {filename}")
            
            # Base64 데이터에서 이미지 추출
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
                
            image_bytes = base64.b64decode(base64_data)
            pil_image = Image.open(io.BytesIO(image_bytes))
            
            # RGBA → RGB 변환
            if pil_image.mode == 'RGBA':
                background = Image.new('RGB', pil_image.size, (255, 255, 255))
                background.paste(pil_image, mask=pil_image.split()[-1])
                pil_image = background
                
            # numpy 배열로 변환
            np_image = np.array(pil_image)
            
            # StateManager에 저장
            if self.state_manager:
                self.state_manager.set('init_image', pil_image)
                self.state_manager.set('uploaded_image', np_image)
                self.state_manager.set('init_image_name', filename)
                self.state_manager.set('init_image_size', pil_image.size)
                
            print(f"✅ 파일 업로드 완료: {filename} ({pil_image.size[0]}×{pil_image.size[1]})")
            
        except Exception as e:
            print(f"❌ 파일 업로드 처리 실패: {e}")
            
    def handle_canvas_data(self, canvas_data: Dict[str, Any]):
        """Canvas 데이터 처리"""
        try:
            event_type = canvas_data.get('type')
            data = canvas_data.get('data')
            
            if event_type == 'image_loaded' and data:
                self._handle_image_loaded(data)
            elif event_type == 'mask_updated' and data:
                self._handle_mask_updated(data)
            elif event_type == 'tool_changed' and data:
                self._handle_tool_changed(data)
            else:
                print(f"⚠️ 알 수 없는 Canvas 이벤트: {event_type}")
                
        except Exception as e:
            print(f"❌ Canvas 데이터 처리 실패: {e}")
            
    def _handle_image_loaded(self, data: Dict[str, Any]):
        """이미지 로드 완료 처리"""
        try:
            image_data = data.get('imageData')
            if image_data and self.state_manager:
                # Base64 이미지 데이터를 PIL Image로 변환
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                    
                image_bytes = base64.b64decode(image_data)
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                self.state_manager.set('canvas_image', pil_image)
                print(f"✅ Canvas 이미지 로드 완료: {pil_image.size}")
                
        except Exception as e:
            print(f"❌ 이미지 로드 처리 실패: {e}")
            
    def _handle_mask_updated(self, data: Dict[str, Any]):
        """마스크 업데이트 처리"""
        try:
            mask_data = data.get('maskData')
            if mask_data and self.state_manager:
                # Base64 마스크 데이터를 PIL Image로 변환
                if ',' in mask_data:
                    mask_data = mask_data.split(',')[1]
                    
                mask_bytes = base64.b64decode(mask_data)
                mask_image = Image.open(io.BytesIO(mask_bytes))
                
                self.state_manager.set('mask_image', mask_image)
                print(f"✅ 마스크 업데이트 완료: {mask_image.size}")
                
        except Exception as e:
            print(f"❌ 마스크 업데이트 처리 실패: {e}")
            
    def _handle_tool_changed(self, data: Dict[str, Any]):
        """도구 변경 처리"""
        try:
            tool = data.get('tool')
            if tool and self.state_manager:
                self.state_manager.set('current_tool', tool)
                print(f"✅ 도구 변경: {tool}")
                
        except Exception as e:
            print(f"❌ 도구 변경 처리 실패: {e}")
            
    def switch_mode(self, mode: str):
        """모드 전환"""
        self.send_to_canvas('switchMode', mode)
        
    def load_image(self, image_path: str):
        """이미지 로드"""
        self.send_to_canvas('loadImage', image_path)
        
    def clear_canvas(self):
        """Canvas 비우기"""
        self.send_to_canvas('clearCanvas')
        
    def set_tool(self, tool: str):
        """도구 설정"""
        self.send_to_canvas('setTool', tool)
        
    def set_brush_size(self, size: int):
        """브러시 크기 설정"""
        self.send_to_canvas('setBrushSize', size)
        
    def set_brush_hardness(self, hardness: float):
        """브러시 경도 설정"""
        self.send_to_canvas('setBrushHardness', hardness)
        
    def get_canvas_data(self) -> Dict[str, Any]:
        """Canvas 데이터 추출"""
        try:
            # JavaScript에서 데이터 가져오기
            js_code = '''
                const data = {
                    image: window.canvasManager.getImageData(),
                    mask: window.canvasManager.getMaskData(),
                    metadata: window.canvasManager.getMetadata()
                };
                JSON.stringify(data);
            '''
            
            result = ui.run_javascript(js_code)
            if result and hasattr(result, 'result'):
                return json.loads(result.result)
            else:
                return {}
                
        except Exception as e:
            print(f"❌ Canvas 데이터 추출 실패: {e}")
            return {}
            
    def export_canvas_image(self) -> Optional[np.ndarray]:
        """Canvas 이미지를 numpy 배열로 내보내기"""
        try:
            canvas_data = self.get_canvas_data()
            image_data = canvas_data.get('image')
            
            if image_data:
                # Base64 이미지 데이터를 numpy 배열로 변환
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                    
                image_bytes = base64.b64decode(image_data)
                pil_image = Image.open(io.BytesIO(image_bytes))
                return np.array(pil_image)
                
        except Exception as e:
            print(f"❌ Canvas 이미지 내보내기 실패: {e}")
            
        return None
        
    def export_canvas_mask(self) -> Optional[np.ndarray]:
        """Canvas 마스크를 numpy 배열로 내보내기"""
        try:
            canvas_data = self.get_canvas_data()
            mask_data = canvas_data.get('mask')
            
            if mask_data:
                # Base64 마스크 데이터를 numpy 배열로 변환
                if ',' in mask_data:
                    mask_data = mask_data.split(',')[1]
                    
                mask_bytes = base64.b64decode(mask_data)
                mask_image = Image.open(io.BytesIO(mask_bytes))
                return np.array(mask_image)
                
        except Exception as e:
            print(f"❌ Canvas 마스크 내보내기 실패: {e}")
            
        return None 