"""
좌측 접이식 사이드바 컴포넌트
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager

class UtilitySidebar:
    """유틸리티 사이드바"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.is_expanded = False
        self.container = None
        self.history_container = None
        self.toggle_button = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        # 세로 탭 형태의 사이드바
        self.container = ui.column().classes(
            'h-full bg-purple-800 transition-all duration-300 overflow-hidden relative'
        ).style('width: 50px')
        
        with self.container:
            # 토글 버튼
            self.toggle_button = ui.button(
                '▶',
                on_click=self.toggle
            ).props('flat').classes('w-full text-white')
            
            # 확장된 내용
            with ui.column().classes('p-2 absolute left-0 top-12 w-64').bind_visibility_from(self, 'is_expanded'):
                # 히스토리 섹션
                ui.label('히스토리').classes('font-bold text-white mb-2')
                ui.separator().classes('bg-purple-600')
                
                # 히스토리 컨테이너
                with ui.scroll_area().classes('w-full h-64 bg-purple-900 rounded p-2'):
                    self.history_container = ui.column().classes('w-full gap-2')
                    self._show_empty_history()
                
                ui.separator().classes('bg-purple-600 my-4')
                
                # 편집 도구 섹션
                ui.label('편집 도구').classes('font-bold text-white mb-2')
                self._create_edit_tools()
            
            # 하단의 생성 방법 버튼들 (접혀있을 때도 보임)
            with ui.column().classes('absolute bottom-0 left-0 right-0 p-1 gap-1'):
                for i, method in enumerate(['txt2img', 'img2img', 'inpaint', 'upscale']):
                    btn = ui.button(
                        method if self.is_expanded else method[:3].upper()
                    ).props('flat').classes(
                        'w-full h-16 bg-red-600 hover:bg-red-700 text-white text-xs'
                    )
                    
                    if not self.is_expanded:
                        btn.tooltip(method)
        
        # 히스토리 업데이트 구독
        self.state.subscribe('history_updated', self._update_history)
    
    def toggle(self):
        """사이드바 토글"""
        self.is_expanded = not self.is_expanded
        width = '280px' if self.is_expanded else '50px'
        self.container.style(f'width: {width}')
        self.toggle_button.set_text('◀' if self.is_expanded else '▶')
    
    def _show_empty_history(self):
        """빈 히스토리 상태 표시"""
        self.history_container.clear()
        with self.history_container:
            with ui.column().classes('w-full items-center justify-center p-4'):
                ui.icon('history').classes('text-4xl text-purple-400 mb-2')
                ui.label('아직 생성된 이미지가 없습니다').classes('text-purple-300 text-sm text-center')
                ui.label('이미지를 생성하면').classes('text-purple-400 text-xs text-center')
                ui.label('여기에 표시됩니다').classes('text-purple-400 text-xs text-center')
    
    async def _update_history(self, history_items):
        """히스토리 업데이트"""
        if not self.history_container:
            return
        
        self.history_container.clear()
        
        if not history_items:
            self._show_empty_history()
            return
        
        # 히스토리 아이템 표시 (최신순)
        with self.history_container:
            for item in history_items[:20]:  # 최대 20개만 표시
                with ui.card().classes('w-full p-2 cursor-pointer hover:bg-purple-700').on(
                    'click',
                    lambda i=item: self._restore_from_history(i)
                ):
                    with ui.row().classes('gap-2 items-center'):
                        # 썸네일
                        if Path(item.thumbnail_path).exists():
                            ui.image(item.thumbnail_path).classes('w-12 h-12 rounded')
                        else:
                            ui.icon('image').classes('w-12 h-12 text-purple-400')
                        
                        # 정보
                        with ui.column().classes('flex-1 min-w-0'):
                            # 시간
                            time_str = item.timestamp.strftime('%H:%M:%S')