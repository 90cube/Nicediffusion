"""
중앙 이미지 뷰어/캔버스 컴포넌트 (모드 기반 아키텍처)
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio
from PIL import Image
import numpy as np
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import json
import base64
import io

class ModeHandler(ABC):
    """각 모드의 기본 인터페이스"""
    
    @abstractmethod
    def setup(self, container):
        """UI 설정"""
        pass
    
    @abstractmethod
    def activate(self):
        """모드 활성화"""
        pass
    
    @abstractmethod
    def deactivate(self):
        """모드 비활성화"""
        pass
    
    @abstractmethod
    def get_generation_data(self):
        """생성용 데이터 추출"""
        pass

class ViewModeHandler(ModeHandler):
    """뷰 모드 핸들러 - 생성된 이미지 표시"""
    
    def __init__(self, image_pad):
        self.image_pad = image_pad
        self.current_image_path = None
        
    def setup(self, container):
        """뷰 모드 UI 설정"""
        with container:
            # 상단 도구바
            with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                ui.label('이미지 뷰어').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                ui.button(icon='refresh', on_click=self.image_pad._refresh_image_pad).props('round color=white text-color=black size=sm')
            
            # 메인 캔버스 영역
            with ui.column().classes('w-full h-full relative') as self.canvas_container:
                self.canvas = ui.html('''
                    <div id="view-canvas" class="w-full h-full flex items-center justify-center bg-gray-800 rounded-lg overflow-hidden">
                        <div id="view-placeholder" class="text-center text-gray-400">
                            <div class="text-6xl mb-4">🖼️</div>
                            <div class="text-xl">생성된 이미지가 여기에 표시됩니다</div>
                        </div>
                    </div>
                ''').classes('w-full h-full')
                
                # 이미지 도구 (호버 시 표시)
                with ui.row().classes('absolute top-16 right-4 gap-2 opacity-0 hover:opacity-100 transition-opacity duration-300 z-10'):
                    ui.button(icon='fullscreen', on_click=self._show_fullscreen).props('round color=white text-color=black size=sm').tooltip('전체화면')
                    ui.button(icon='download', on_click=self._download_image).props('round color=white text-color=black size=sm').tooltip('다운로드')
                    ui.button(icon='delete', on_click=self._delete_image).props('round color=red size=sm').tooltip('삭제')
                
                # 표시 방식 버튼
                with ui.row().classes('absolute bottom-4 left-1/2 transform -translate-x-1/2 gap-2'):
                    ui.button('Contain', on_click=lambda: self._change_display_mode('contain')).props('size=sm').classes('bg-blue-600 hover:bg-blue-700')
                    ui.button('Fill', on_click=lambda: self._change_display_mode('fill')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700')
                    ui.button('Stretch', on_click=lambda: self._change_display_mode('stretch')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700')
    
    def activate(self):
        """뷰 모드 활성화"""
        print("🖼️ 뷰 모드 활성화")
        
    def deactivate(self):
        """뷰 모드 비활성화"""
        print("🖼️ 뷰 모드 비활성화")
        
    def get_generation_data(self):
        """생성용 데이터 추출"""
        return {}
        
    def _show_fullscreen(self):
        """전체화면 표시"""
        if self.current_image_path:
            ui.run_javascript(f'window.open("{self.current_image_path}", "_blank")')
            
    def _download_image(self):
        """이미지 다운로드"""
        if self.current_image_path:
            ui.download(self.current_image_path)
            
    def _delete_image(self):
        """이미지 삭제"""
        if self.current_image_path:
            try:
                Path(self.current_image_path).unlink()
                self.image_pad._show_empty()
            except Exception as e:
                print(f"❌ 이미지 삭제 실패: {e}")
                
    def _change_display_mode(self, mode: str):
        """표시 방식 변경"""
        ui.run_javascript(f'''
            const img = document.getElementById('display-image');
            if (img) {{
                img.style.objectFit = '{mode}';
            }}
        ''')

class Img2ImgModeHandler(ModeHandler):
    """Img2Img 모드 핸들러"""
    
    def __init__(self, image_pad):
        self.image_pad = image_pad
        self.upload_area = None
        
    def setup(self, container):
        """Img2Img 모드 UI 설정"""
        with container:
            # 상단 도구바
            with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                ui.label('이미지 → 이미지').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                ui.button(icon='refresh', on_click=self.image_pad._refresh_image_pad).props('round color=white text-color=black size=sm')
            
            # 메인 캔버스 영역
            with ui.column().classes('w-full h-full relative') as self.canvas_container:
                # Canvas 요소
                self.canvas = ui.html('''
                    <canvas id="img2img-canvas" 
                            style="width:100%; height:100%; max-width:800px; max-height:600px; border:1px solid #333; background: repeating-conic-gradient(#808080 0% 25%, transparent 0% 50%) 50% / 20px 20px;">
                    </canvas>
                ''').classes('w-full h-full')
                
                # 드래그앤드롭 오버레이
                self.upload_area = ui.html('''
                    <div id="img2img-upload-area" style="position:absolute; top:0; left:0; width:100%; height:100%; 
                         background:rgba(26,26,26,0.9); display:flex; align-items:center; justify-content:center;
                         transition:opacity 0.3s; cursor:pointer;">
                        <div style="text-align:center; pointer-events:none;">
                            <div style="font-size:48px;">📁</div>
                            <div>이미지를 여기에 드래그앤드롭하세요</div>
                            <div style="font-size:12px; margin-top:8px;">또는 클릭하여 파일 선택</div>
                        </div>
                    </div>
                ''').classes('absolute inset-0 z-10')
                
                # 이미지 도구 (호버 시 표시)
                with ui.row().classes('absolute top-16 right-4 gap-2 opacity-0 hover:opacity-100 transition-opacity duration-300 z-10'):
                    ui.button(icon='aspect_ratio', on_click=self._apply_image_size).props('round color=blue text-color=white size=sm').tooltip('이미지 크기 적용')
                    ui.button(icon='clear', on_click=self._clear_image).props('round color=orange size=sm').tooltip('이미지 제거')
                
                # 이미지 정보 (좌측 하단)
                self.info_label = ui.label('').classes('absolute bottom-4 left-4 bg-black bg-opacity-50 rounded px-3 py-1 text-white text-sm')
    
    def activate(self):
        """Img2Img 모드 활성화"""
        print("🔄 Img2Img 모드 활성화")
        # 드래그앤드롭 이벤트 설정
        ui.run_javascript('''
            const uploadArea = document.getElementById('img2img-upload-area');
            if (uploadArea) {
                uploadArea.addEventListener('click', () => {
                    // 파일 선택 다이얼로그 열기
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = 'image/*';
                    input.onchange = (e) => {
                        const file = e.target.files[0];
                        if (file) {
                            // Python으로 파일 전송
                            window.handleFileUpload(file);
                        }
                    };
                    input.click();
                });
                
                uploadArea.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    uploadArea.style.background = 'rgba(59,130,246,0.3)';
                });
                
                uploadArea.addEventListener('dragleave', (e) => {
                    e.preventDefault();
                    uploadArea.style.background = 'rgba(26,26,26,0.9)';
                });
                
                uploadArea.addEventListener('drop', (e) => {
                    e.preventDefault();
                    uploadArea.style.background = 'rgba(26,26,26,0.9)';
                    const file = e.dataTransfer.files[0];
                    if (file && file.type.startsWith('image/')) {
                        window.handleFileUpload(file);
                    }
                });
            }
        ''')
        
    def deactivate(self):
        """Img2Img 모드 비활성화"""
        print("🔄 Img2Img 모드 비활성화")
        
    def get_generation_data(self):
        """생성용 데이터 추출"""
        init_image = self.image_pad.state.get('init_image')
        if init_image is not None:
            return {'init_image': init_image}
        return {}
        
    def _apply_image_size(self):
        """이미지 크기를 파라미터에 적용"""
        init_image = self.image_pad.state.get('init_image')
        if init_image is not None:
            try:
                if hasattr(init_image, 'size'):
                    width, height = init_image.size
                else:
                    # numpy 배열인 경우
                    height, width = init_image.shape[:2]
                
                self.image_pad.state.update_param('width', int(width))
                self.image_pad.state.update_param('height', int(height))
                print(f"✅ 이미지 크기 적용: {width}×{height}")
            except Exception as e:
                print(f"❌ 이미지 크기 적용 실패: {e}")
                
    def _clear_image(self):
        """이미지 제거"""
        self.image_pad.state.set('init_image', None)
        self.image_pad.state.set('uploaded_image', None)
        ui.run_javascript('''
            const canvas = document.getElementById('img2img-canvas');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
            
            const uploadArea = document.getElementById('img2img-upload-area');
            if (uploadArea) {
                uploadArea.style.display = 'flex';
            }
        ''')
        print("🗑️ 이미지 제거 완료")

class InpaintModeHandler(ModeHandler):
    """Inpaint 모드 핸들러"""
    
    def __init__(self, image_pad):
        self.image_pad = image_pad
        
    def setup(self, container):
        """Inpaint 모드 UI 설정"""
        with container:
            # 상단 도구바
            with ui.row().classes('absolute top-4 left-4 right-4 justify-between items-center z-10'):
                ui.label('인페인팅').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                ui.button(icon='refresh', on_click=self.image_pad._refresh_image_pad).props('round color=white text-color=black size=sm')
            
            # 메인 캔버스 영역
            with ui.column().classes('w-full h-full relative') as self.canvas_container:
                # Canvas 요소 (마스크 편집용)
                self.canvas = ui.html('''
                    <canvas id="inpaint-canvas" 
                            style="width:100%; height:100%; max-width:800px; max-height:600px; border:1px solid #333;">
                    </canvas>
                ''').classes('w-full h-full')
                
                # 도구 팔레트 (우측)
                with ui.column().classes('absolute right-4 top-16 gap-2'):
                    ui.button(icon='brush', on_click=lambda: self._set_tool('brush')).props('round color=blue size=sm').tooltip('브러시')
                    ui.button(icon='crop_square', on_click=lambda: self._set_tool('rectangle')).props('round color=green size=sm').tooltip('사각형 선택')
                    ui.button(icon='radio_button_unchecked', on_click=lambda: self._set_tool('circle')).props('round color=purple size=sm').tooltip('원형 선택')
                    ui.button(icon='undo', on_click=self._undo).props('round color=orange size=sm').tooltip('실행 취소')
                    ui.button(icon='redo', on_click=self._redo).props('round color=orange size=sm').tooltip('다시 실행')
                
                # 브러시 설정 (하단)
                with ui.row().classes('absolute bottom-4 left-4 gap-4'):
                    ui.label('브러시 크기:').classes('text-white text-sm')
                    ui.slider(min=1, max=100, value=20, on_change=lambda e: self._set_brush_size(e.value)).props('color=blue')
                    ui.label('브러시 경도:').classes('text-white text-sm')
                    ui.slider(min=0, max=1, value=0.8, step=0.1, on_change=lambda e: self._set_brush_hardness(e.value)).props('color=green')
    
    def activate(self):
        """Inpaint 모드 활성화"""
        print("🎨 Inpaint 모드 활성화")
        # Canvas 도구 초기화
        ui.run_javascript('''
            if (window.inpaintCanvas) {
                window.inpaintCanvas.init();
            }
        ''')
        
    def deactivate(self):
        """Inpaint 모드 비활성화"""
        print("🎨 Inpaint 모드 비활성화")
        
    def get_generation_data(self):
        """생성용 데이터 추출"""
        init_image = self.image_pad.state.get('init_image')
        mask_image = self.image_pad.state.get('mask_image')
        return {
            'init_image': init_image,
            'mask_image': mask_image
        }
        
    def _set_tool(self, tool: str):
        """도구 설정"""
        ui.run_javascript(f'window.inpaintCanvas.setTool("{tool}")')
        
    def _set_brush_size(self, size: int):
        """브러시 크기 설정"""
        ui.run_javascript(f'window.inpaintCanvas.setBrushSize({size})')
        
    def _set_brush_hardness(self, hardness: float):
        """브러시 경도 설정"""
        ui.run_javascript(f'window.inpaintCanvas.setBrushHardness({hardness})')
        
    def _undo(self):
        """실행 취소"""
        ui.run_javascript('window.inpaintCanvas.undo()')
        
    def _redo(self):
        """다시 실행"""
        ui.run_javascript('window.inpaintCanvas.redo()')

class ImagePad:
    """이미지 패드 (모드 기반 아키텍처)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_mode = 'view'
        self.layers = {
            'image': None,
            'mask': None,
            'preview': None
        }
        self.canvas_manager = None
        
        # 모드 핸들러들
        self.mode_handlers = {
            'view': ViewModeHandler(self),
            'txt2img': ViewModeHandler(self),
            'img2img': Img2ImgModeHandler(self),
            'inpaint': InpaintModeHandler(self),
            'upscale': Img2ImgModeHandler(self)
        }
        
        self.current_handler = None
        self.main_container = None
        
        # 이벤트 구독
        self.state.subscribe('current_mode', self._on_mode_changed)
        self.state.subscribe('image_generated', self._on_image_generated)
        self.state.subscribe('uploaded_image', self._on_uploaded_image_changed)
        
    async def render(self):
        """컴포넌트 렌더링"""
        self.main_container = ui.column().classes('w-full h-full bg-blue-900 rounded-lg overflow-hidden relative')
        
        # 현재 모드에 따른 핸들러 설정
        current_mode = self.state.get('current_mode', 'txt2img')
        await self._switch_mode(current_mode)
        
    async def _switch_mode(self, mode: str):
        """모드 전환"""
        if self.current_handler:
            self.current_handler.deactivate()
            
        self.current_mode = mode
        handler_class = self.mode_handlers.get(mode, self.mode_handlers['view'])
        
        if self.main_container:
            self.main_container.clear()
            self.current_handler = handler_class
            self.current_handler.setup(self.main_container)
            self.current_handler.activate()
            
        print(f"🔄 모드 전환: {mode}")
        
    async def _on_mode_changed(self, mode: str):
        """모드 변경 이벤트 처리"""
        await self._switch_mode(mode)
        
    async def _on_image_generated(self, data: dict):
        """이미지 생성 완료 이벤트 처리"""
        image_path = data.get('image_path')
        if image_path and Path(image_path).exists():
            await self._show_generated_image(image_path)
            
    async def _on_uploaded_image_changed(self, np_image):
        """업로드된 이미지 변경 이벤트 처리"""
        if np_image is not None:
            await self._show_uploaded_image(np_image)
            
    async def _show_generated_image(self, image_path: str):
        """생성된 이미지 표시"""
        if self.current_handler and hasattr(self.current_handler, 'current_image_path'):
            self.current_handler.current_image_path = image_path
            
        # JavaScript로 이미지 표시
        ui.run_javascript(f'''
            const canvas = document.getElementById('{self.current_mode}-canvas');
            if (canvas) {{
                const ctx = canvas.getContext('2d');
                const img = new Image();
                img.onload = function() {{
                    canvas.width = canvas.clientWidth;
                    canvas.height = canvas.clientHeight;
                    
                    const scale = Math.min(
                        canvas.width / img.width,
                        canvas.height / img.height
                    );
                    const x = (canvas.width - img.width * scale) / 2;
                    const y = (canvas.height - img.height * scale) / 2;
                    
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, x, y, img.width * scale, img.height * scale);
                }};
                img.src = '{image_path}';
            }}
        ''')
        
    async def _show_uploaded_image(self, np_image):
        """업로드된 이미지 표시"""
        try:
            # numpy → PIL → base64
            if isinstance(np_image, np.ndarray):
                pil_image = Image.fromarray(np_image)
            else:
                pil_image = np_image
                
            buf = io.BytesIO()
            pil_image.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            # JavaScript로 이미지 표시
            ui.run_javascript(f'''
                const canvas = document.getElementById('{self.current_mode}-canvas');
                if (canvas) {{
                    const ctx = canvas.getContext('2d');
                    const img = new Image();
                    img.onload = function() {{
                        canvas.width = canvas.clientWidth;
                        canvas.height = canvas.clientHeight;
                        
                        const scale = Math.min(
                            canvas.width / img.width,
                            canvas.height / img.height
                        );
                        const x = (canvas.width - img.width * scale) / 2;
                        const y = (canvas.height - img.height * scale) / 2;
                        
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        ctx.drawImage(img, x, y, img.width * scale, img.height * scale);
                    }};
                    img.src = 'data:image/png;base64,{b64}';
                }}
                
                // 드래그앤드롭 영역 숨기기
                const uploadArea = document.getElementById('{self.current_mode}-upload-area');
                if (uploadArea) {{
                    uploadArea.style.display = 'none';
                }}
            ''')
            
            # 이미지 정보 업데이트
            if hasattr(self.current_handler, 'info_label') and self.current_handler.info_label is not None:
                width, height = pil_image.size
                self.current_handler.info_label.set_text(f'{width} × {height}')
                
        except Exception as e:
            print(f"❌ 업로드된 이미지 표시 실패: {e}")
            
    async def _refresh_image_pad(self):
        """이미지 패드 새로고침"""
        current_mode = self.state.get('current_mode', 'txt2img')
        await self._switch_mode(current_mode)
        
    def get_uploaded_image(self) -> Optional[np.ndarray]:
        """업로드된 이미지 반환"""
        return self.state.get('uploaded_image')
        
    def get_uploaded_image_resized(self, width: int, height: int) -> Optional[np.ndarray]:
        """리사이즈된 업로드 이미지 반환"""
        uploaded_image = self.get_uploaded_image()
        if uploaded_image is not None:
            pil_image = Image.fromarray(uploaded_image)
            resized_image = pil_image.resize((width, height), Image.Resampling.LANCZOS)
            return np.array(resized_image)
        return None

