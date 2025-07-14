from .mode_handlers.view_handler import ViewModeHandler
from .mode_handlers.img2img_handler import Img2ImgHandler
from .mode_handlers.inpaint_handler import InpaintHandler
import numpy as np
from typing import Optional
import base64
import io
from PIL import Image

class ImagePad:
    def __init__(self, state_manager):
        self.state = state_manager
        self.current_mode = 'view'
        self.layers = {}
        self.canvas_manager = None
        self.mode_handlers = {
            'view': ViewModeHandler(),
            'txt2img': None,  # 추후 구현
            'img2img': Img2ImgHandler(),
            'inpaint': InpaintHandler(),
            'upscale': None
        }
        self.uploaded_image = None  # numpy array

    def set_uploaded_image(self, np_image: np.ndarray):
        """API로 받은 numpy 이미지를 ImagePad에 세팅"""
        self.uploaded_image = np_image
        # TODO: 레이어에 반영 및 UI 갱신

    def get_uploaded_image(self) -> Optional[np.ndarray]:
        """현재 업로드된 이미지를 numpy array 또는 None으로 반환"""
        return self.uploaded_image 

    def get_uploaded_image_base64(self) -> str:
        """업로드된 numpy 이미지를 base64 PNG로 변환해 반환"""
        if self.uploaded_image is None:
            return ''
        img = Image.fromarray(self.uploaded_image)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{b64}'

    def show_uploaded_image_fit(self, container_width: int, container_height: int):
        """프론트엔드 JS에 fit 표시 명령 전송 (NiceGUI run_javascript 사용)"""
        b64img = self.get_uploaded_image_base64()
        from nicegui import ui
        ui.run_javascript(f'window.canvasManager.loadImageFit("{b64img}", {container_width}, {container_height})')

    def add_image_layer(self):
        """레이어 시스템에 업로드 이미지를 배경/이미지 레이어로 추가 (뼈대)"""
        if self.uploaded_image is not None:
            self.layers['image'] = self.uploaded_image 