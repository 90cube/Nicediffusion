"""
중앙 이미지 뷰어/캔버스 컴포넌트
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager

class ImagePad:
    """이미지 패드"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_image = None
        self.image_container = None
        self.is_empty = True
    
    async def render(self):
        """컴포넌트 렌더링"""
        # 파란색 배경의 이미지 패드
        with ui.column().classes('w-full h-full items-center justify-center bg-blue-900 rounded-lg'):
            self.image_container = ui.column().classes('w-full h-full items-center justify-center')
            self._show_empty_state()
        
        # 이미지 생성 완료 이벤트 구독
        self.state.subscribe('image_generated', self._on_image_generated)
        self.state.subscribe('generation_started', self._on_generation_started)
        self.state.subscribe('generation_progress', self._on_generation_progress)
        self.state.subscribe('generation_failed', self._on_generation_failed)
    
    def _show_empty_state(self):
        """빈 상태 표시"""
        self.image_container.clear()
        self.is_empty = True
        
        with self.image_container:
            with ui.column().classes('items-center justify-center gap-4'):
                # 큰 아이콘
                ui.icon('image').classes('text-8xl text-white opacity-50')
                
                # 메인 텍스트
                ui.label('생성된 그림 pad').classes(
                    'text-4xl font-bold text-white opacity-80'
                )
                
                # 서브 텍스트
                ui.label('이미지를 생성하려면 프롬프트를 입력하고').classes(
                    'text-lg text-white opacity-60'
                )
                ui.label('"생성" 버튼을 클릭하세요').classes(
                    'text-lg text-white opacity-60'
                )
                
                # 힌트
                with ui.row().classes('gap-2 mt-4'):
                    ui.icon('lightbulb').classes('text-yellow-400')
                    ui.label('Tip: 모델을 먼저 선택해주세요').classes(
                        'text-sm text-yellow-400'
                    )
    
    def _show_loading_state(self, message: str = "이미지 생성 중..."):
        """로딩 상태 표시"""
        self.image_container.clear()
        self.is_empty = False
        
        with self.image_container:
            with ui.column().classes('items-center justify-center gap-4'):
                # 로딩 스피너
                ui.spinner(size='lg', color='white')
                
                # 상태 메시지
                self.loading_label = ui.label(message).classes(
                    'text-xl text-white'
                )
                
                # 진행률 바
                self.progress_bar = ui.linear_progress(value=0).classes('w-64')
    
    def _show_image(self, image_path: str):
        """이미지 표시"""
        self.image_container.clear()
        self.is_empty = False
        self.current_image = image_path
        
        with self.image_container:
            # 이미지 표시
            img = ui.image(image_path).classes(
                'max-w-full max-h-full object-contain rounded-lg shadow-2xl'
            )
            
            # 이미지 위에 호버 시 나타나는 도구들
            with ui.row().classes('absolute top-4 right-4 gap-2 opacity-0 hover:opacity-100 transition-opacity'):
                ui.button(
                    icon='download',
                    on_click=lambda: self._download_image(image_path)
                ).props('round color=white text-color=black').tooltip('다운로드')
                
                ui.button(
                    icon='fullscreen',
                    on_click=lambda: self._show_fullscreen(image_path)
                ).props('round color=white text-color=black').tooltip('전체화면')
                
                ui.button(
                    icon='delete',
                    on_click=self._delete_image
                ).props('round color=red').tooltip('삭제')
    
    def _show_error_state(self, error_message: str):
        """오류 상태 표시"""
        self.image_container.clear()
        self.is_empty = True
        
        with self.image_container:
            with ui.column().classes('items-center justify-center gap-4'):
                # 오류 아이콘
                ui.icon('error').classes('text-8xl text-red-500')
                
                # 오류 메시지
                ui.label('이미지 생성 실패').classes(
                    'text-2xl font-bold text-red-500'
                )
                ui.label(error_message).classes(
                    'text-lg text-white opacity-80 text-center max-w-md'
                )
                
                # 재시도 버튼
                ui.button(
                    '다시 시도',
                    icon='refresh',
                    on_click=self._retry_generation
                ).props('color=primary')
    
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
    
    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트"""
        image_path = data.get('path')
        if image_path and Path(image_path).exists():
            self._show_image(image_path)
        else:
            self._show_error_state("이미지 파일을 찾을 수 없습니다")
    
    async def _on_generation_failed(self, data):
        """생성 실패 이벤트"""
        error = data.get('error', '알 수 없는 오류가 발생했습니다')
        self._show_error_state(error)
    
    def _download_image(self, image_path):
        """이미지 다운로드"""
        # TODO: Phase 2에서 구현
        ui.notify('다운로드 기능은 Phase 2에서 구현됩니다', type='info')
    
    def _show_fullscreen(self, image_path):
        """전체화면 표시"""
        with ui.dialog() as dialog, ui.card().classes('w-screen h-screen'):
            ui.image(image_path).classes('w-full h-full object-contain')
            ui.button(
                icon='close',
                on_click=dialog.close
            ).props('flat round').classes('absolute top-4 right-4')
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
                    on_click=lambda: [self._show_empty_state(), dialog.close()]
                ).props('color=red')
        dialog.open()
    
    def _retry_generation(self):
        """재생성"""
        # TODO: Phase 2에서 마지막 파라미터로 재생성
        ui.notify('재생성 기능은 Phase 2에서 구현됩니다', type='info')