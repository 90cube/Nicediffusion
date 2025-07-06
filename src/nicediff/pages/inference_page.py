# 파일 경로: src/nicediff/pages/inference_page.py
# (수정 완료)

from nicegui import ui
from ..core.state_manager import StateManager
from ..ui.top_bar import TopBar
from ..ui.utility_sidebar import UtilitySidebar
from ..ui.image_pad import ImagePad
from ..ui.parameter_panel import ParameterPanel
from ..ui.prompt_panel import PromptPanel
from ..ui.lora_panel import LoraPanel
from ..ui.metadata_panel import MetadataPanel

class InferencePage:
    """추론 페이지 (구독 로직 중앙 관리)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        
        # UI 컴포넌트들
        self.top_bar = TopBar(state_manager)
        self.sidebar = UtilitySidebar(state_manager)
        self.image_pad = ImagePad(state_manager)
        self.param_panel = ParameterPanel(state_manager)
        self.prompt_panel = PromptPanel(state_manager)
        self.lora_panel = LoraPanel(state_manager)
        self.metadata_panel = MetadataPanel(state_manager)

    # --- [수정된 부분 ①] ---
    # 페이지가 소멸될 때 구독을 해지하는 메서드 추가
    def _on_destroy(self):
        """페이지 소멸 시 모든 콜백 구독을 안전하게 해지합니다."""
        print("InferencePage 소멸: 모든 구독을 해지합니다.")
        self.state.unsubscribe('is_generating_changed', self.param_panel._on_generate_status_change)
        self.state.unsubscribe('current_params_changed', self.param_panel._update_ui_from_state)

    async def render(self):
        """페이지 렌더링 (구독 로직 중앙 관리)"""
        with ui.column().classes('main-layout bg-gray-850 text-white') as page_container:
            # ... (페이지 레이아웃 코드는 그대로) ...
            await self.top_bar.render()
            with ui.row().classes('content-row'):
                await self.sidebar.render()
                with ui.column().classes('flex-1 min-w-0 h-full gap-2 p-2 overflow-hidden').style('width: 100%'):
                    with ui.card().classes('w-full flex-1 min-h-0 p-0 overflow-hidden'):
                        await self.image_pad.render()
                    with ui.card().classes('w-full h-48 bg-gray-700 p-4 overflow-y-auto'):
                        await self.prompt_panel.render()
                with ui.column().classes('right-panel-constrain h-full bg-gray-800 p-2 gap-2 overflow-y-auto'):
                    with ui.card().classes('w-full bg-gray-700 '):
                        await self.param_panel.render()
                    with ui.card().classes('w-full bg-gray-700'):
                        await self.lora_panel.render()
                    with ui.card().classes('w-full bg-teal-800 p-3'):
                        await self.metadata_panel.render()

        # --- [수정된 부분 ②] ---
        # 모든 UI가 렌더링된 후, 필요한 모든 상태 변화를 안전하게 구독합니다.
        self.state.subscribe('is_generating_changed', self.param_panel._on_generate_status_change)
        self.state.subscribe('current_params_changed', self.param_panel._update_ui_from_state)
        
        # 페이지 컨테이너가 소멸될 때 _on_destroy 메서드를 호출하도록 등록합니다.
        page_container.on('destroy', self._on_destroy)

    async def render(self):
        """페이지 렌더링 (구독 로직 중앙 관리)"""
        # --- [수정된 부분 ②] ---
        # 페이지의 최상위 컨테이너를 변수에 담아 destroy 이벤트를 연결합니다.
        with ui.column().classes('main-layout bg-gray-850 text-white') as page_container:
            # 상단 바
            await self.top_bar.render()
            
            # 메인 컨텐츠 영역
            with ui.row().classes('content-row'):
                # 좌측 사이드바
                await self.sidebar.render()
                
                # 중앙 컨텐츠 영역
                with ui.column().classes('flex-1 min-w-0 h-full gap-2 p-2 overflow-hidden').style('width: 100%'):
                    with ui.card().classes('w-full flex-1 min-h-0 p-0 overflow-hidden'):
                        await self.image_pad.render()
                    
                    with ui.card().classes('w-full h-48 bg-gray-700 p-4 overflow-y-auto'):
                        await self.prompt_panel.render()
                
                # 우측 패널 영역
                with ui.column().classes('right-panel-constrain h-full bg-gray-800 p-2 gap-2 overflow-y-auto'):
                    with ui.card().classes('w-full bg-gray-700'):
                        # ParameterPanel의 UI가 먼저 완전히 생성되도록 기다립니다.
                        await self.param_panel.render()
                    
                    with ui.card().classes('w-full bg-gray-700'):
                        await self.lora_panel.render()
                    
                    with ui.card().classes('w-full bg-teal-800 p-3'):
                        await self.metadata_panel.render()

        # --- [수정된 부분 ③] ---
        # 모든 UI가 렌더링된 후, 안전하게 상태 변화를 구독합니다.
        self.state.subscribe('is_generating_changed', self.param_panel._on_generate_status_change)
        
        # 페이지 컨테이너가 소멸될 때 _on_destroy 메서드를 호출하도록 등록합니다.
        page_container.on('destroy', self._on_destroy)