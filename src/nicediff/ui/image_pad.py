"""
중앙 이미지 뷰어/캔버스 컴포넌트 (이미지 크기 조정 수정)
"""


from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager

class ImagePad:
    """이미지 패드 (UI 업데이트 안정성 개선)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_image_path = None
        
        # UI 컨테이너 및 요소들을 미리 선언
        self.empty_container = None
        self.loading_container = None
        self.image_display_container = None
        self.current_image_element = None
        self.loading_label = None
        self.progress_bar = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full items-center justify-center bg-blue-900 rounded-lg overflow-hidden relative'):
            # --- [핵심 변경] ---
            # 3가지 상태(Empty, Loading, Image)에 대한 UI 뼈대를 미리 한번만 생성합니다.
            self._setup_ui_skeleton()

        # 초기 상태를 빈 화면으로 설정
        self._show_empty_state()
        
        # 이벤트 구독
        self.state.subscribe('image_generated', self._on_image_generated)
        self.state.subscribe('generation_started', self._on_generation_started)
        self.state.subscribe('generation_progress', self._on_generation_progress)
        self.state.subscribe('generation_failed', self._on_generation_failed)
    
    def _setup_ui_skeleton(self):
        """UI의 뼈대를 미리 한번만 생성하는 함수"""
        # 1. 빈 상태 컨테이너
        with ui.column().classes('items-center justify-center gap-4') as self.empty_container:
            ui.icon('image').classes('text-8xl text-white opacity-50')
            ui.label('생성된 그림 pad').classes('text-4xl font-bold text-white opacity-80')
            ui.label('이미지를 생성하려면 프롬프트를 입력하고').classes('text-lg text-white opacity-60')
            ui.label('"생성" 버튼을 클릭하세요').classes('text-lg text-white opacity-60')
            with ui.row().classes('gap-2 mt-4'):
                ui.icon('lightbulb').classes('text-yellow-400')
                ui.label('Tip: 모델을 먼저 선택해주세요').classes('text-sm text-yellow-400')

        # 2. 로딩 상태 컨테이너
        with ui.column().classes('items-center justify-center gap-4') as self.loading_container:
            ui.spinner(size='lg', color='white')
            self.loading_label = ui.label("이미지 생성 중...").classes('text-xl text-white')
            self.progress_bar = ui.linear_progress(value=0).classes('w-64')

        # 3. 이미지 표시 컨테이너
        with ui.column().classes('w-full h-full items-center justify-center relative') as self.image_display_container:
            self.current_image_element = ui.image().classes('max-w-full max-h-full object-contain rounded-lg shadow-2xl')
            
            # 이미지 위에 호버 시 나타나는 도구들
            with ui.row().classes('absolute top-4 right-4 gap-2 opacity-0 hover:opacity-100 transition-opacity duration-300 z-10'):
                ui.button(icon='fullscreen', on_click=lambda: self._show_fullscreen()).props('round color=white text-color=black size=sm').tooltip('전체화면')
                ui.button(icon='download', on_click=lambda: self._download_image()).props('round color=white text-color=black size=sm').tooltip('다운로드')
                ui.button(icon='zoom_in', on_click=self._toggle_zoom).props('round color=white text-color=black size=sm').tooltip('확대/축소')
                ui.button(icon='delete', on_click=self._delete_image).props('round color=red size=sm').tooltip('삭제')
            
            # 이미지 정보 표시 (하단)
            self.image_info_label = ui.label().classes('absolute bottom-4 left-4 bg-black bg-opacity-50 rounded px-3 py-1 text-white text-sm')


    def _show_empty_state(self):
        """빈 상태를 보여줍니다."""
        if self.empty_container: self.empty_container.visible = True
        if self.loading_container: self.loading_container.visible = False
        if self.image_display_container: self.image_display_container.visible = False

    def _show_loading_state(self, message: str = "이미지 생성 중..."):
        """로딩 상태를 보여줍니다."""
        if self.empty_container: self.empty_container.visible = False
        if self.loading_container: self.loading_container.visible = True
        if self.image_display_container: self.image_display_container.visible = False
        if self.loading_label: self.loading_label.set_text(message)
        if self.progress_bar: self.progress_bar.set_value(0)

    def _show_image(self, image_path: str):
        """이미지를 보여줍니다."""
        self.current_image_path = image_path
        if self.empty_container: self.empty_container.visible = False
        if self.loading_container: self.loading_container.visible = False
        if self.image_display_container: self.image_display_container.visible = True
        
        # --- [핵심 변경] ---
        # 새 이미지 요소를 만드는 대신 .set_source()로 내용만 교체합니다.
        if self.current_image_element: self.current_image_element.set_source(image_path)
        
        # 이미지 정보 업데이트
        if self.image_info_label:
            try:
                from PIL import Image
                with Image.open(image_path) as img:
                    width, height = img.size
                    self.image_info_label.set_text(f'{width} × {height}')
            except Exception:
                self.image_info_label.set_text('이미지 정보')
                
    def _toggle_zoom(self):
        """이미지 확대/축소 토글"""
        if self.current_image_element:
            # 현재 스타일 확인하고 토글
            current_style = getattr(self.current_image_element, '_style', '')
            
            if 'object-fit: cover' in current_style:
                # 원래 크기로 복원
                self.current_image_element.style("""
                    width: auto;
                    height: auto;
                    max-width: 100%;
                    max-height: 100%;
                    object-fit: contain;
                """)
                ui.notify('원본 크기로 조정됨', type='info')
            else:
                # 확대 모드
                self.current_image_element.style("""
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                """)
                ui.notify('확대 모드', type='info')
    
    def _show_error_state(self, error_message: str):
        """오류 상태 표시"""
        # 빈 상태로 표시하고 오류 메시지를 로그에 출력
        self._show_empty_state()
        print(f"❌ 이미지 표시 오류: {error_message}")
        ui.notify(f'이미지 표시 실패: {error_message}', type='negative')
    
    async def _on_generation_started(self, data):
        """생성 시작 이벤트"""
        self._show_loading_state("이미지 생성을 시작합니다...")
    
    async def _on_generation_progress(self, data):
        """생성 진행 이벤트"""
        progress = data.get('progress', 0)
        step = data.get('step', 0)
        total_steps = data.get('total_steps', 20)
        
        if hasattr(self, 'loading_label'):
            self.loading_label.set_text(f'생성 중... ({step}/{total_steps})')
        
        if hasattr(self, 'progress_bar'):
            self.progress_bar.set_value(progress)
    
    def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트 (동기 함수로 변경)"""
        image_path = data.get('image_path')
        if image_path and Path(image_path).exists():
            self._show_image(image_path)
        else:
            self._show_error_state("이미지 파일을 찾을 수 없습니다")
    
    async def _on_generation_failed(self, data):
        """생성 실패 이벤트"""
        error = data.get('error', '알 수 없는 오류가 발생했습니다')
        self._show_error_state(error)
    
    def _download_image(self, image_path):
        if self.current_image_path:
            ui.download(self.current_image_path)
            
    def _show_fullscreen(self):
        """전체화면 표시 (수정 완료)"""
        if self.current_image_path:
            with ui.dialog().props('maximized') as dialog, ui.card().classes('w-full h-full bg-black'):
                with ui.column().classes('w-full h-full items-center justify-center relative'):
                    # 전체화면 이미지
                    # --- [수정] image_path -> self.current_image_path ---
                    ui.image(self.current_image_path).classes('max-w-full max-h-full object-contain')
                    
                    # 닫기 버튼
                    ui.button(
                        icon='close',
                        on_click=dialog.close
                    ).props('flat round color=white size=lg').classes('absolute top-4 right-4')
                    
                    # 이미지 정보
                    with ui.row().classes('absolute bottom-4 left-4 bg-black bg-opacity-70 rounded px-4 py-2 text-white'):
                        # --- [수정] image_path -> self.current_image_path ---
                        ui.label(Path(self.current_image_path).name).classes('text-lg')
                        try:
                            from PIL import Image
                            # --- [수정] image_path -> self.current_image_path ---
                            with Image.open(self.current_image_path) as img:
                                width, height = img.size
                                ui.label(f' • {width} × {height}')
                        except Exception:
                            pass
            dialog.open()
            
    def _delete_image(self):
        """이미지 삭제"""
        # 확인 다이얼로그
        with ui.dialog() as dialog, ui.card():
            ui.label('정말 삭제하시겠습니까?').classes('text-lg')
            with ui.row().classes('gap-2 mt-4'):
                ui.button('취소', on_click=dialog.close).props('flat')
                ui.button(
                    '삭제',
                    on_click=lambda: [self._confirm_delete(), dialog.close()]
                ).props('color=red')
        dialog.open()
    
    def _confirm_delete(self):
        """삭제 확인"""
        if self.current_image:
            try:
                Path(self.current_image).unlink(missing_ok=True)
                # 썸네일도 삭제
                thumbnail_path = Path(self.current_image).parent / f"thumb_{Path(self.current_image).name}"
                thumbnail_path.unlink(missing_ok=True)
                
                self._show_empty_state()
                ui.notify('이미지가 삭제되었습니다', type='success')
            except Exception as e:
                ui.notify(f'삭제 실패: {str(e)}', type='negative')
    
    def _retry_generation(self):
        """재생성"""
        # 마지막 파라미터로 재생성 시도
        import asyncio
        asyncio.create_task(self.state.generate_image())
        ui.notify('이미지를 다시 생성합니다', type='info')