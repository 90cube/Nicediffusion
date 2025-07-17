"""
Python-JavaScript 브릿지 (단순화된 버전)
필요한 통신 기능만 포함
"""

from nicegui import ui
import json
import base64
import io
from PIL import Image
import numpy as np
from typing import Dict, Any, Optional

class CanvasBridge:
    """Python-JavaScript 브릿지 클래스 (단순화된 버전)"""
    
    def __init__(self, state_manager=None):
        self.state_manager = state_manager
        
    def set_state_manager(self, state_manager):
        """StateManager 설정"""
        self.state_manager = state_manager
        
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
            
    def switch_mode(self, mode: str):
        """모드 전환"""
        self.send_to_canvas('switchMode', mode)
        
    def load_image(self, image_path: str):
        """이미지 로드"""
        self.send_to_canvas('loadImage', image_path)
        
    def clear_canvas(self):
        """Canvas 비우기"""
        self.send_to_canvas('clearCanvas')
        
    def get_canvas_data(self) -> Dict[str, Any]:
        """Canvas 데이터 추출"""
        try:
            # JavaScript에서 데이터 가져오기
            js_code = '''
                const data = {
                    image: window.canvasManager ? window.canvasManager.getImageData() : null,
                    mask: window.canvasManager ? window.canvasManager.getMaskData() : null,
                    metadata: window.canvasManager ? window.canvasManager.getMetadata() : null
                };
                JSON.stringify(data);
            '''
            
            # JavaScript 실행 결과를 문자열로 변환
            result = ui.run_javascript(js_code)
            if result and str(result).strip():
                return json.loads(str(result))
            else:
                return {}
                
        except Exception as e:
            print(f"❌ Canvas 데이터 추출 실패: {e}")
            return {}
            
    def export_canvas_image(self) -> Optional[np.ndarray]:
        """Canvas 이미지 내보내기"""
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
        """Canvas 마스크 내보내기"""
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