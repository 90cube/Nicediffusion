"""
좌측 접이식 사이드바 컴포넌트 (반응형 수정)
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
        self.layers_container = None

    async def render(self):
        """컴포넌트 렌더링"""
        # 접이식 사이드바 컨테이너 (반응형 너비)
        self.container = ui.column().classes(
            'h-full bg-gray-800 transition-all duration-300 overflow-hidden relative border-r border-gray-600 flex-shrink-0'
        ).style('width: 48px; min-width: 48px')  # 최소 너비 보장
        
        with self.container:
            # 상단: 토글 버튼과 축약된 메뉴들
            with ui.column().classes('w-full'):
                # 토글 버튼
                self.toggle_button = ui.button(
                    '▶',
                    on_click=self.toggle
                ).props('flat').classes('w-full h-12 text-white text-xs').tooltip('사이드바 열기')
                
                # 축약된 섹션 표시 (접혀있을 때)
                with ui.column().classes('w-full').bind_visibility_from(self, 'is_expanded', value=False):
                    ui.button(
                        icon='history',
                        on_click=lambda: self.toggle() if not self.is_expanded else None
                    ).props('flat').classes('w-full h-10 text-gray-400').tooltip('히스토리')
                    
                    ui.button(
                        icon='edit',
                        on_click=lambda: self.toggle() if not self.is_expanded else None
                    ).props('flat').classes('w-full h-10 text-gray-400').tooltip('편집 도구')
            
            # 확장된 내용 (펼쳐졌을 때만 보임)
            with ui.scroll_area().classes('flex-1 w-full').bind_visibility_from(self, 'is_expanded'):
                with ui.column().classes('w-full p-2 gap-2'):  # 패딩 줄임
                    # 히스토리 섹션
                    with ui.expansion('히스토리', icon='history').classes('w-full'):
                        with ui.scroll_area().classes('w-full h-40'):  # 높이 줄임
                            self.history_container = ui.column().classes('w-full gap-1')  # 갭 줄임
                            self._show_empty_history()
                    
                    # 편집 도구 섹션 (기존)
                    with ui.expansion('편집 도구', icon='edit').classes('w-full'):
                        self._create_edit_tools()
                    
                    # 그림 도구 섹션 (새로 추가)
                    with ui.expansion('그림 도구', icon='palette').classes('w-full'):
                        self._create_drawing_tools()
                        
                # 하단: 생성 방법 버튼들 (항상 보임)
                with ui.column().classes('w-full mt-auto border-t border-gray-600'):
                    methods = [
                        ('txt2img', 'TXT'),
                        ('img2img', 'IMG'), 
                        ('inpaint', 'INP'),
                        ('upscale', 'UPS')
                    ]
                    
                    for method, short_name in methods:
                        button_text = method if self.is_expanded else short_name
                        ui.button(
                            button_text,
                            on_click=lambda m=method: self._on_method_select(m)
                        ).props('flat').classes(
                            'w-full h-8 text-white hover:bg-gray-700 border-b border-gray-600 text-xs'
                        ).tooltip(method if not self.is_expanded else '')
        
        # 히스토리 업데이트 구독
        self.state.subscribe('history_updated', self._update_history)

    def _create_drawing_tools(self):
        """그림 도구 섹션 생성"""
        with ui.column().classes('w-full gap-2'):
            # 도구 선택
            with ui.row().classes('w-full gap-1'):
                tools = [
                    ('brush', '브러시', 'brush'),
                    ('eraser', '지우개', 'auto_fix_normal'),
                    ('select', '선택', 'crop_free'),
                    ('move', '이동', 'pan_tool')
                ]
                
                for tool_id, tool_name, icon in tools:
                    ui.button(
                        icon=icon,
                        on_click=lambda t=tool_id: self._on_tool_select(t)
                    ).props('toggle color=blue').classes('flex-1').tooltip(tool_name)
            
            # 브러시 설정
            with ui.expansion('브러시 설정').classes('w-full'):
                # 브러시 크기
                ui.label('크기').classes('text-xs text-gray-400')
                brush_size = ui.slider(min=1, max=100, value=10, step=1).classes('w-full')
                brush_size.on('update:model-value', lambda e: self._on_brush_size_change(e.args))
                
                # 브러시 색상 (마스크용)
                ui.label('색상').classes('text-xs text-gray-400 mt-2')
                with ui.row().classes('gap-1'):
                    colors = ['#ffffff', '#000000', '#ff0000', '#00ff00', '#0000ff']
                    for color in colors:
                        ui.button().props(f'round color=white').style(
                            f'background-color: {color}; width: 20px; height: 20px'
                        ).on('click', lambda c=color: self._on_color_select(c))
            
            # 레이어 관리
            with ui.expansion('레이어').classes('w-full'):
                with ui.column().classes('w-full gap-1'):
                    # 레이어 추가 버튼
                    ui.button(
                        '+ 레이어 추가',
                        icon='add',
                        on_click=self._add_layer
                    ).props('flat').classes('w-full text-xs')
                    
                    # 레이어 목록 (동적으로 업데이트)
                    self.layers_container = ui.column().classes('w-full')
                    self._update_layers_list()
            
            # 마스크 도구
            with ui.expansion('마스크').classes('w-full'):
                with ui.column().classes('w-full gap-2'):
                    # 마스크 보기 토글
                    mask_toggle = ui.switch('마스크 보기', value=False)
                    mask_toggle.on('update:model-value', self._on_mask_toggle)
                    
                    # 마스크 생성 도구
                    ui.button(
                        'SAM 세그멘테이션',
                        icon='auto_awesome',
                        on_click=self._activate_sam_tool
                    ).props('flat').classes('w-full text-xs')
                    
                    ui.button(
                        'YOLO 객체 감지',
                        icon='visibility',
                        on_click=self._activate_yolo_tool
                    ).props('flat').classes('w-full text-xs')
                    
                    # 마스크 편집
                    with ui.row().classes('w-full gap-1'):
                        ui.button(
                            '반전',
                            icon='invert_colors',
                            on_click=self._invert_mask
                        ).props('flat').classes('flex-1 text-xs')
                        
                        ui.button(
                            '지우기',
                            icon='clear',
                            on_click=self._clear_mask
                        ).props('flat').classes('flex-1 text-xs')

    def _on_tool_select(self, tool_id: str):
        """도구 선택"""
        # 캔버스 에디터에 도구 변경 알림
        canvas_editor = self.state.get('canvas_editor')
        if canvas_editor:
            canvas_editor.set_tool(tool_id)
        ui.notify(f'{tool_id} 도구 선택됨', type='info')

    def _on_brush_size_change(self, size: int):
        """브러시 크기 변경"""
        canvas_editor = self.state.get('canvas_editor')
        if canvas_editor:
            canvas_editor.set_brush_size(size)

    def _on_color_select(self, color: str):
        """색상 선택"""
        canvas_editor = self.state.get('canvas_editor')
        if canvas_editor:
            canvas_editor.set_brush_color(color)
    
    def _update_layers_list(self):
        """레이어 목록 업데이트 (초기 구현)"""
        # 실제 레이어 관리는 Phase 2B에서 구현
        self.layers_container.clear()
        with self.layers_container:
            ui.label('레이어가 없습니다.').classes('text-gray-400 text-xs')
            ui.label('(+ 레이어 추가) 버튼을 클릭하세요.').classes('text-gray-500 text-xs')

    def _on_mask_toggle(self, e):
        """마스크 보기 토글"""
        canvas_editor = self.state.get('canvas_editor')
        if canvas_editor:
            canvas_editor.toggle_mask_view(e.value)

    def _add_layer(self):
        """레이어 추가"""
        # Phase 2B에서 구현
        ui.notify('레이어 기능은 Phase 2B에서 구현됩니다', type='info')
        self._update_layers_list()

    def _activate_sam_tool(self):
        """SAM 세그멘테이션 도구 활성화"""
        # Phase 2C에서 구현
        ui.notify('SAM 도구는 Phase 2C에서 구현됩니다', type='info')

    def _activate_yolo_tool(self):
        """YOLO 객체 감지 도구 활성화"""
        # Phase 2C에서 구현
        ui.notify('YOLO 도구는 Phase 2C에서 구현됩니다', type='info')
    
    def _invert_mask(self):
        """마스크 반전"""
        ui.notify('마스크 반전 기능은 Phase 2에서 구현됩니다', type='info')
    
    def _clear_mask(self):
        """마스크 지우기"""
        ui.notify('마스크 지우기 기능은 Phase 2에서 구현됩니다', type='info')

    def toggle(self):
        """사이드바 토글"""
        self.is_expanded = not self.is_expanded
        # 반응형 너비 설정
        if self.is_expanded:
            width = 'min(280px, 25vw)'  # 최대 뷰포트 너비의 25%
            min_width = '280px'
        else:
            width = '48px'
            min_width = '48px'
        
        self.container.style(f'width: {width}; min-width: {min_width}')
        self.toggle_button.set_text('◀' if self.is_expanded else '▶')
        self.toggle_button.tooltip('사이드바 닫기' if self.is_expanded else '사이드바 열기')
    
    def _create_edit_tools(self):
        """편집 도구 생성"""
        with ui.column().classes('w-full gap-1'):  # 갭 줄임
            tools = [
                ('crop', '자르기'),
                ('rotate_right', '회전'),
                ('flip', '뒤집기'),
                ('tune', '조정'),
            ]
            
            for icon, name in tools:
                ui.button(
                    text=name,
                    icon=icon,
                    on_click=lambda t=name: self._on_tool_click(t)
                ).props('flat').classes('w-full justify-start text-white hover:bg-gray-700 h-8 text-xs')
    
    def _on_tool_click(self, tool_name: str):
        """편집 도구 클릭"""
        ui.notify(f'{tool_name} 도구는 Phase 2에서 구현됩니다', type='info')
    
    def _on_method_select(self, method: str):
        """생성 방법 선택"""
        self.state.set('generation_method', method)
        ui.notify(f'{method} 모드로 변경되었습니다', type='info')
    
    def _show_empty_history(self):
        """빈 히스토리 상태 표시"""
        self.history_container.clear()
        with self.history_container:
            with ui.column().classes('w-full items-center justify-center p-2'):
                ui.icon('history').classes('text-2xl text-gray-500 mb-1')
                ui.label('생성된 이미지가 없습니다').classes('text-gray-400 text-xs text-center')
                ui.label('이미지를 생성하면 여기에 표시됩니다').classes('text-gray-500 text-xs text-center')
    
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
            for item in history_items[:15]:  # 개수 줄임 (15개)
                with ui.card().classes('w-full p-1 cursor-pointer hover:bg-gray-700').on(
                    'click',
                    lambda i=item: self._restore_from_history(i)
                ):
                    with ui.row().classes('gap-1 items-center'):
                        # 썸네일 (크기 줄임)
                        if hasattr(item, 'thumbnail_path') and Path(item.thumbnail_path).exists():
                            ui.image(item.thumbnail_path).classes('w-8 h-8 rounded object-cover')
                        else:
                            ui.icon('image').classes('w-8 h-8 text-gray-400')
                        
                        # 정보
                        with ui.column().classes('flex-1 min-w-0'):
                            # 시간
                            if hasattr(item, 'timestamp'):
                                time_str = item.timestamp.strftime('%H:%M')
                                ui.label(time_str).classes('text-xs text-gray-400')
                            
                            # 프롬프트 (일부만, 더 짧게)
                            if hasattr(item, 'params') and hasattr(item.params, 'prompt'):
                                prompt_preview = item.params.prompt[:20] + '...' if len(item.params.prompt) > 20 else item.params.prompt
                                ui.label(prompt_preview).classes('text-xs text-white truncate')
    
    def _restore_from_history(self, history_item):
        """히스토리에서 복원"""
        if hasattr(history_item, 'id'):
            self.state.restore_from_history(history_item.id)
            ui.notify('히스토리에서 복원되었습니다', type='success')
        else:
            ui.notify('복원할 수 없습니다', type='warning')