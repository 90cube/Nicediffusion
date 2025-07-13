"""
중앙 이미지 뷰어/캔버스 컴포넌트 (캔버스 기반 재구성)
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio

class ImagePad:
    """이미지 패드 (캔버스 기반)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_image_path = None
        self.is_processing = False
        self.display_mode = 'contain'  # contain, fill, stretch
        
        # UI 요소들
        self.main_container = None
        self.canvas_container = None
        self.canvas = None
        self.loading_spinner = None
        self.loading_label = None
        self.progress_bar = None
        self.info_label = None
        self.display_buttons = []
        
        # 이벤트 구독 (InferencePage에서 중앙 관리하므로 여기서는 구독하지 않음)
        # self.state.subscribe('generation_started', self._on_generation_started)
        # self.state.subscribe('image_generated', self._on_image_generated)
    
    async def render(self):
        """컴포넌트 렌더링"""
        # 메인 컨테이너
        self.main_container = ui.column().classes('w-full h-full bg-blue-900 rounded-lg overflow-hidden relative')
        
        # 초기 상태: 빈 화면
        await self._show_empty()
    
    async def _show_empty(self):
        """빈 상태 표시"""
        if self.main_container:
            self.main_container.clear()
            
            with self.main_container:
                with ui.column().classes('w-full h-full items-center justify-center gap-4'):
                    ui.icon('image', size='4rem').classes('text-gray-400')
                    ui.label('이미지를 생성하거나 업로드하세요').classes('text-xl text-gray-300')
                    ui.label('텍스트 프롬프트를 입력하고 생성 버튼을 클릭하세요').classes('text-gray-400')
    
    async def _show_loading(self):
        """로딩 상태 표시"""
        if self.main_container:
            self.main_container.clear()
            
            with self.main_container:
                with ui.column().classes('w-full h-full items-center justify-center gap-4'):
                    self.loading_spinner = ui.spinner(size='lg', color='white')
                    self.loading_label = ui.label("이미지 생성 중...").classes('text-xl text-white')
                    self.progress_bar = ui.linear_progress(value=0).classes('w-64')
    
    async def _show_image(self, image_path: str):
        """이미지 표시"""
        self.current_image_path = image_path
        
        # 이미지 파일 존재 확인
        if not Path(image_path).exists():
            await self._show_error(f"이미지 파일을 찾을 수 없습니다: {image_path}")
            return
        
        self.main_container.clear()
        
        with self.main_container:
            # 캔버스 컨테이너 (전체 화면)
            with ui.column().classes('w-full h-full relative') as self.canvas_container:
                # 캔버스 요소 (이미지 표시용)
                self.canvas = ui.html(f'''
                    <div id="image-canvas" class="w-full h-full flex items-center justify-center bg-gray-800 rounded-lg overflow-hidden">
                        <img id="display-image" src="{image_path}" 
                             class="transition-all duration-300 ease-in-out"
                             style="max-width: 100%; max-height: 100%; object-fit: contain; background-color: #374151; border-radius: 0.5rem;">
                    </div>
                ''').classes('w-full h-full')
                
                # 이미지 위에 호버 시 나타나는 도구들
                with ui.row().classes('absolute top-4 right-4 gap-2 opacity-0 hover:opacity-100 transition-opacity duration-300 z-10'):
                    ui.button(icon='fullscreen', on_click=self._show_fullscreen).props('round color=white text-color=black size=sm').tooltip('전체화면')
                    ui.button(icon='download', on_click=self._download_image).props('round color=white text-color=black size=sm').tooltip('다운로드')
                    ui.button(icon='delete', on_click=self._delete_image).props('round color=red size=sm').tooltip('삭제')
                
                # 이미지 정보 표시 (좌측 하단)
                try:
                    from PIL import Image
                    with Image.open(image_path) as img:
                        width, height = img.size
                        info_text = f'{width} × {height}'
                except Exception as e:
                    print(f"⚠️ 이미지 정보 읽기 실패: {e}")
                    info_text = '이미지 정보'
                
                self.info_label = ui.label(info_text).classes('absolute bottom-4 left-4 bg-black bg-opacity-50 rounded px-3 py-1 text-white text-sm')
                
                # 표시 방식 버튼들 (하단 중앙)
                with ui.row().classes('absolute bottom-4 left-1/2 transform -translate-x-1/2 gap-2'):
                    self.display_buttons = [
                        ui.button('Contain', on_click=lambda: self._change_display_mode('contain')).props('size=sm').classes('bg-blue-600 hover:bg-blue-700'),
                        ui.button('Fill', on_click=lambda: self._change_display_mode('fill')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700'),
                        ui.button('Stretch', on_click=lambda: self._change_display_mode('stretch')).props('size=sm').classes('bg-gray-600 hover:bg-gray-700')
                    ]
                    # 기본값 활성화
                    self.display_buttons[0].classes('bg-blue-600')
        
        print(f"🎉 이미지 표시 완료: {image_path}")
    
    async def _show_error(self, message: str):
        """오류 상태 표시"""
        self.main_container.clear()
        
        with self.main_container:
            with ui.column().classes('w-full h-full items-center justify-center gap-4'):
                ui.icon('error', size='4rem').classes('text-red-400')
                ui.label(message).classes('text-xl text-red-300 text-center')
                ui.button('재시도', on_click=self._retry_generation).classes('bg-red-600 hover:bg-red-700')
    
    async def _change_display_mode(self, mode: str):
        """이미지 표시 방식 변경 (JavaScript 사용)"""
        self.display_mode = mode
        
        if self.canvas and self.current_image_path:
            # JavaScript로 직접 스타일 변경
            if mode == 'contain':
                ui.run_javascript('''
                    const img = document.getElementById('display-image');
                    if (img) {
                        img.style.objectFit = 'contain';
                        img.style.maxWidth = '100%';
                        img.style.maxHeight = '100%';
                        img.style.width = 'auto';
                        img.style.height = 'auto';
                    }
                ''')
            elif mode == 'fill':
                ui.run_javascript('''
                    const img = document.getElementById('display-image');
                    if (img) {
                        img.style.objectFit = 'cover';
                        img.style.width = '100%';
                        img.style.height = '100%';
                        img.style.maxWidth = 'none';
                        img.style.maxHeight = 'none';
                    }
                ''')
            elif mode == 'stretch':
                ui.run_javascript('''
                    const img = document.getElementById('display-image');
                    if (img) {
                        img.style.objectFit = 'fill';
                        img.style.width = '100%';
                        img.style.height = '100%';
                        img.style.maxWidth = 'none';
                        img.style.maxHeight = 'none';
                    }
                ''')
            
            # 버튼 스타일 업데이트
            for i, button in enumerate(self.display_buttons):
                if i == ['contain', 'fill', 'stretch'].index(mode):
                    button.classes('bg-blue-600')
                else:
                    button.classes('bg-gray-600')
            
            print(f"🔄 이미지 표시 방식 변경 (JS): {mode}")
            ui.notify(f'이미지 표시 방식: {mode}', type='info')
    
    async def _on_generation_started(self, data):
        """생성 시작 이벤트"""
        if self.is_processing:
            return
        
        self.is_processing = True
        await self._show_loading()
        print("🎨 생성 시작됨 - 로딩 화면 표시")
    
    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트"""
        if not self.is_processing:
            return
        
        self.is_processing = False
        
        if isinstance(data, dict) and 'image_path' in data:
            image_path = data['image_path']
            print(f"🖼️ 이미지 생성 완료: {image_path}")
            
            # 이미지 파일 존재 확인
            if Path(image_path).exists():
                await self._show_image(image_path)
            else:
                await self._show_error(f"생성된 이미지를 찾을 수 없습니다: {image_path}")
        else:
            await self._show_error("이미지 생성 중 오류가 발생했습니다")
    
    def _show_fullscreen(self):
        """전체화면 보기"""
        if self.current_image_path:
            ui.open(self.current_image_path)
            ui.notify('전체화면으로 열렸습니다', type='info')
    
    def _download_image(self):
        """이미지 다운로드"""
        if self.current_image_path:
            ui.download(self.current_image_path)
            ui.notify('이미지 다운로드가 시작되었습니다', type='success')
    
    def _delete_image(self):
        """이미지 삭제"""
        if self.current_image_path:
            try:
                Path(self.current_image_path).unlink()
                self.current_image_path = None
                asyncio.create_task(self._show_empty())
                ui.notify('이미지가 삭제되었습니다', type='success')
            except Exception as e:
                ui.notify(f'이미지 삭제 실패: {e}', type='error')
    
    def _retry_generation(self):
        """생성 재시도"""
        asyncio.create_task(self._show_empty())
        ui.notify('생성을 다시 시도해주세요', type='info')