"""
좌측 접이식 사이드바 컴포넌트 (반응형 수정)
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio
from ..utils.image_filters import get_available_filters, apply_filter

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
                    
                    # 리프레시 버튼
                    ui.button(
                        icon='refresh',
                        on_click=self._refresh_sidebar
                    ).props('flat').classes('w-full h-10 text-gray-400').tooltip('사이드바 새로고침')
            
            # 확장된 내용 (펼쳐졌을 때만 보임)
            with ui.scroll_area().classes('flex-1 w-full').bind_visibility_from(self, 'is_expanded'):
                with ui.column().classes('w-full p-2 gap-2'):  # 패딩 줄임
                    # 히스토리 섹션
                    with ui.expansion('히스토리', icon='history').classes('w-full'):
                        # 히스토리 헤더 (전체 삭제 버튼 포함)
                        with ui.row().classes('w-full justify-between items-center mb-1'):
                            ui.label('생성 기록').classes('text-xs text-gray-400')
                            with ui.row().classes('gap-1'):
                                ui.button(
                                    icon='folder_open',
                                    on_click=self._open_outputs_folder
                                ).props('flat round').classes('text-blue-400 hover:text-blue-300 text-xs').tooltip('Outputs 폴더 열기')
                                ui.button(
                                    icon='clear_all',
                                    on_click=self._clear_all_history
                                ).props('flat round').classes('text-red-400 hover:text-red-300 text-xs').tooltip('전체 삭제')
                        
                        with ui.scroll_area().classes('w-full h-40'):  # 높이 줄임
                            self.history_container = ui.column().classes('w-full gap-1')  # 갭 줄임
                            self._show_empty_history()
                    
                    # 편집 도구 섹션 (기존)
                    with ui.expansion('편집 도구', icon='edit').classes('w-full'):
                        self._create_edit_tools()
                    
                    # 그림 도구 섹션 (새로 추가)
                    with ui.expansion('그림 도구', icon='palette').classes('w-full'):
                        self._create_drawing_tools()
        
        # 히스토리 업데이트 구독 (InferencePage에서 중앙 관리하므로 여기서는 구독하지 않음)
        # self.state.subscribe('history_updated', self._update_history)

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
        """편집 도구 섹션 생성 (이미지 필터 포함)"""
        with ui.column().classes('w-full gap-2'):
            # 기존 편집 도구(예: 자르기, 회전 등)
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

            # --- 이미지 필터 UI 추가 ---
            ui.label('이미지 필터').classes('text-sm font-medium text-purple-400')
            available_filters = get_available_filters()
            filter_options = {filter_name: filter_name.replace('_', ' ').title() for filter_name in available_filters}
            self.filter_select = ui.select(
                options=filter_options,
                label='필터 선택',
                value=None
            ).props('outlined')
            ui.label('필터 강도').classes('text-sm font-medium')
            self.filter_strength_slider = ui.slider(
                min=0.1,
                max=3.0,
                step=0.1,
                value=1.0
            ).props('outlined')
            with ui.row().classes('w-full gap-2'):
                ui.button(
                    '필터 적용',
                    on_click=self._apply_image_filter
                ).props('outlined color=purple')
                ui.button(
                    '필터 초기화',
                    on_click=self._reset_image_filter
                ).props('outlined color=gray')

    async def _apply_image_filter(self):
        """이미지 필터 적용 (유틸리티 사이드바)"""
        try:
            if not hasattr(self, 'filter_select') or not self.filter_select.value:
                ui.notify('필터를 선택해주세요', type='warning')
                return
            init_image = self.state.get('init_image')
            if not init_image:
                ui.notify('적용할 이미지가 없습니다', type='warning')
                return
            filter_strength = 1.0
            if hasattr(self, 'filter_strength_slider') and self.filter_strength_slider:
                filter_strength = self.filter_strength_slider.value
            filter_name = self.filter_select.value
            import numpy as np
            img_array = np.array(init_image)
            filter_params = {}
            if filter_name in ['brightness', 'contrast']:
                filter_params['factor'] = filter_strength
            elif filter_name == 'blur':
                filter_params['kernel_size'] = int(filter_strength * 5) + 1
            filtered_array = apply_filter(filter_name, img_array, **filter_params)
            from PIL import Image
            filtered_image = Image.fromarray(filtered_array)
            self.state.set('init_image', filtered_image)
            self.state.set('image_filter_applied', True)
            ui.notify(f'{filter_name} 필터가 적용되었습니다', type='positive')
        except Exception as e:
            print(f"❌ 필터 적용 실패: {e}")
            ui.notify(f'필터 적용 실패: {str(e)}', type='negative')

    async def _reset_image_filter(self):
        """이미지 필터 초기화 (유틸리티 사이드바)"""
        try:
            init_image_path = self.state.get('init_image_path')
            if init_image_path:
                from PIL import Image
                original_image = Image.open(init_image_path)
                self.state.set('init_image', original_image)
                self.state.set('image_filter_reset', True)
                ui.notify('필터가 초기화되었습니다', type='positive')
            else:
                ui.notify('원본 이미지를 찾을 수 없습니다', type='warning')
        except Exception as e:
            print(f"❌ 필터 초기화 실패: {e}")
            ui.notify(f'필터 초기화 실패: {str(e)}', type='negative')
    
    def _on_tool_click(self, tool_name: str):
        """편집 도구 클릭"""
        ui.notify(f'{tool_name} 도구는 Phase 2에서 구현됩니다', type='info')
    
    async def _on_method_select(self, method: str):
        """생성 방법 선택 (순서 보장을 위해 async로 변경)"""
        # StateManager에 현재 모드 설정
        self.state.set('current_mode', method)
        
        # 모드별 기본 설정
        if method in ['img2img', 'inpaint', 'upscale']:
            # i2i 관련 모드일 때 기본 Strength 값 설정
            current_params = self.state.get('current_params')
            if not hasattr(current_params, 'strength') or current_params.strength is None:
                self.state.update_param('strength', 0.8)  # 기본값 0.8
                print(f"✅ {method} 모드 기본 Strength 값 설정: 0.8")
            
            # img2img 모드일 때 이미지 패드 자동 새로고침 (먼저 실행)
            if method == 'img2img':
                image_pad = self.state.get('image_pad')
                print(f"🔍 이미지 패드 참조 확인: {image_pad}")
                if image_pad:
                    print(f"🔄 {method} 모드 선택: 이미지 패드 자동 새로고침 시작")
                    await image_pad._refresh_image_pad()
                    print(f"✅ {method} 모드 선택: 이미지 패드 자동 새로고침 완료")
                else:
                    print(f"❌ {method} 모드 선택: 이미지 패드 참조를 찾을 수 없음")
        
        # 이미지 패드 새로고침 완료 후 파라미터 패널 새로고침
        print(f"🔄 {method} 모드: 파라미터 패널 새로고침 시작")
        self.state._notify('mode_changed', {'mode': method})
        print(f"✅ {method} 모드: 파라미터 패널 새로고침 완료")
        
        # 슬롯 오류 방지를 위해 notify 제거
        print(f"🔄 생성 모드 변경: {method}")
    
    def _show_empty_history(self):
        """빈 히스토리 상태 표시"""
        self.history_container.clear()
        with self.history_container:
            with ui.column().classes('w-full items-center justify-center p-2'):
                ui.icon('history').classes('text-2xl text-gray-500 mb-1')
                ui.label('생성된 이미지가 없습니다').classes('text-gray-400 text-xs text-center')
                ui.label('이미지를 생성하면 여기에 표시됩니다').classes('text-gray-500 text-xs text-center')
    
    async def _update_history(self, history_items):
        """히스토리 업데이트 (안전성 검사 추가)"""
        try:
            # 컨테이너가 존재하는지 확인
            if not self.history_container:
                print("⚠️ 히스토리 컨테이너가 없습니다.")
                return
                
            # Client가 유효한지 확인 (더 안전한 검사)
            try:
                if hasattr(self.history_container, 'client'):
                    client = self.history_container.client
                    if client is None:
                        print("⚠️ Client가 삭제되었습니다. 히스토리 업데이트를 건너뜁니다.")
                        return
            except RuntimeError as e:
                if "deleted" in str(e).lower():
                    print("⚠️ Client가 삭제되었습니다. 히스토리 업데이트를 건너뜁니다.")
                    return
                else:
                    raise e
            
            print(f"📋 히스토리 업데이트 시작: {len(history_items)}개 항목")
            
            # 기존 내용 클리어 (안전하게)
            try:
                self.history_container.clear()
                print("✅ 히스토리 컨테이너 초기화")
            except Exception as e:
                print(f"⚠️ 히스토리 컨테이너 클리어 실패: {e}")
                return
            
            # 히스토리 항목들 추가
            for i, item in enumerate(history_items):
                try:
                    print(f"📝 히스토리 항목 {i+1} 처리: {item.get('model', 'Unknown')}")
                    
                    with self.history_container:
                        # 히스토리 아이템 카드
                        with ui.card().classes('w-full bg-gray-700 border border-gray-600'):
                            # 썸네일 이미지
                            if item.get('thumbnail_path'):
                                ui.image(item['thumbnail_path']).classes('w-full h-24 object-cover rounded-t')
                            
                            # 정보 섹션
                            with ui.column().classes('p-2 gap-1'):
                                # 모델명
                                ui.label(item.get('model', 'Unknown Model')).classes('text-xs font-bold text-blue-400')
                                
                                # 파라미터 정보
                                params = item.get('params', {})
                                if params:
                                    size_text = f"{params.get('width', 0)}×{params.get('height', 0)}"
                                    ui.label(f"Size: {size_text}").classes('text-xs text-gray-400')
                                    
                                    steps_text = f"Steps: {params.get('steps', 0)}"
                                    ui.label(steps_text).classes('text-xs text-gray-400')
                                
                                # 액션 버튼들
                                with ui.row().classes('gap-1 mt-2'):
                                    # 복원 버튼
                                    ui.button(
                                        icon='restore',
                                        on_click=lambda item=item: self._restore_from_history(item)
                                    ).props('flat round').classes('text-green-400 hover:text-green-300 text-xs').tooltip('파라미터 복원')
                                    
                                    # 삭제 버튼
                                    ui.button(
                                        icon='delete',
                                        on_click=lambda item=item: self._delete_history_item(item.get('id', ''))
                                    ).props('flat round').classes('text-red-400 hover:text-red-300 text-xs').tooltip('삭제')
                
                except Exception as e:
                    print(f"⚠️ 히스토리 항목 {i+1} 처리 실패: {e}")
                    continue
            
            print(f"✅ 히스토리 업데이트 완료: {len(history_items)}개 항목 표시")
            
        except Exception as e:
            print(f"❌ 히스토리 업데이트 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _delete_history_item(self, history_item):
        """히스토리 아이템 삭제"""
        history_id = history_item.get('id')
        if history_id:
            self.state.delete_history_item(history_id)
        else:
            ui.notify('삭제할 수 없습니다', type='warning')
    
    def _restore_from_history(self, history_item):
        """히스토리에서 복원"""
        history_id = history_item.get('id')
        if history_id:
            self.state.restore_from_history(history_id)
            ui.notify('히스토리에서 복원되었습니다', type='success')
        else:
            ui.notify('복원할 수 없습니다', type='warning')

    def _clear_all_history(self):
        """전체 히스토리 삭제"""
        if ui.confirm('정말로 모든 생성 기록을 삭제하시겠습니까?'):
            self.state.clear_all_history()
            ui.notify('모든 생성 기록이 삭제되었습니다', type='info')
            self._show_empty_history()

    def _open_outputs_folder(self):
        """Outputs 폴더를 엽니다."""
        import subprocess
        import platform
        
        outputs_path = Path('outputs')
        if not outputs_path.exists():
            ui.notify('Outputs 폴더가 존재하지 않습니다', type='warning')
            return
        
        try:
            system = platform.system()
            if system == 'Windows':
                subprocess.run(['explorer', str(outputs_path)], check=True)
            elif system == 'Linux':
                subprocess.run(['xdg-open', str(outputs_path)], check=True)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', str(outputs_path)], check=True)
            else:
                ui.notify(f'지원하지 않는 운영체제: {system}', type='warning')
                return
                
            ui.notify('Outputs 폴더가 열렸습니다', type='info')
        except subprocess.CalledProcessError as e:
            ui.notify(f'폴더 열기 실패: {e}', type='negative')
        except FileNotFoundError:
            ui.notify('시스템 명령어를 찾을 수 없습니다', type='negative')

    def _refresh_sidebar(self):
        """사이드바 새로고침"""
        print("🔄 유틸리티 사이드바 새로고침 중...")
        ui.notify('사이드바가 새로고침되었습니다', type='info')