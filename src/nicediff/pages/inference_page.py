# 파일 경로: src/nicediff/pages/inference_page.py
# (중복 제거 및 구조 정리 완료된 최종 버전)

from nicegui import ui
from ..core.state_manager import StateManager
from ..ui.top_bar import TopBar
from ..ui.utility_sidebar import UtilitySidebar
from ..ui.image_pad import ImagePadTabSystem
from ..ui.parameter_panel import ParameterPanel
from ..ui.prompt_panel import PromptPanel
from ..ui.lora_panel import LoraPanel
from ..core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)

class InferencePage:
    """추론 페이지 (UI 컴포넌트 조립 및 이벤트 중앙 관리)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        
        # 모든 UI 컴포넌트 인스턴스 생성
        self.top_bar = TopBar(state_manager)
        self.sidebar = UtilitySidebar(state_manager)
        self.image_pad = ImagePadTabSystem(state_manager)
        self.param_panel = ParameterPanel(state_manager)
        self.prompt_panel = PromptPanel(state_manager)
        self.lora_panel = LoraPanel(state_manager)

    def _on_destroy(self):
        """페이지 소멸 시 모든 콜백 구독을 안전하게 해지합니다."""
        info(r"InferencePage 소멸: 모든 구독을 해지합니다.")
        
        # render에서 구독했던 모든 이벤트를 여기서 해지합니다.
        self.state.unsubscribe('is_generating_changed', self.param_panel._on_generate_status_change)
        
        # 다른 모든 구독들도 여기에 추가하여 관리합니다.
        # 예: self.state.unsubscribe('model_selection_changed', self.metadata_panel._on_model_selected)

    async def render(self):
        """페이지의 모든 UI를 렌더링하고, 이벤트를 중앙에서 한번만 구독합니다."""
        
        with ui.column().classes('w-full h-screen bg-gray-850 text-white overflow-hidden') as page_container:
            await self.top_bar.render()
            
            with ui.row().classes('flex-1 min-h-0 w-full gap-2 p-2 overflow-hidden'):
                await self.sidebar.render()
                
                with ui.column().classes('flex-1 min-w-0 h-full gap-2 overflow-hidden'):
                    with ui.card().classes('w-full flex-1 min-h-0 p-0 overflow-hidden'):
                        self.image_pad.render()
                    
                    # 프롬프트 패널과 LoRA 패널을 가로로 배치 (같은 높이)
                    with ui.row().classes('w-full h-100 gap-2 overflow-hidden'):
                        # 프롬프트 패널 (유연한 너비)
                        with ui.card().classes('flex-1 h-full bg-gray-700 p-2 overflow-hidden'):
                            await self.prompt_panel.render()
                       
                        # LoRA 패널 (450px 고정 너비)
                        with ui.card().classes('w-[450px] h-full bg-gray-700 p-2 overflow-y-auto min-h-0'):
                            await self.lora_panel.render()
                
                # 오른쪽 패널: 파라미터 패널만 배치
                with ui.column().classes('w-[300px] h-full gap-2 overflow-hidden'):
                    # 파라미터 패널 (전체 높이)
                    with ui.card().classes('w-full h-full bg-gray-800 p-2 overflow-y-auto overflow-x-hidden min-h-0'):
                        await self.param_panel.render()

        # --- [핵심] ---
        # 모든 UI가 화면에 완전히 그려진 후, 필요한 모든 이벤트를 여기서 한번만 연결(구독)합니다.
        info(r"InferencePage: 모든 UI 렌더링 완료. 이벤트 구독을 시작합니다.")
        
        # UI 컴포넌트들을 StateManager에 등록 (다른 컴포넌트에서 접근 가능하도록)
        self.state.set('image_pad', self.image_pad)
        self.state.set('sidebar', self.sidebar)
        self.state.set('param_panel', self.param_panel)
        self.state.set('prompt_panel', self.prompt_panel)
        self.state.set('lora_panel', self.lora_panel)
        self.state.set('top_bar', self.top_bar)
        
        # 기존 구독
        self.state.subscribe('is_generating_changed', self.param_panel._on_generate_status_change)
        
        # 새로 추가된 이벤트 구독들
        self.state.subscribe('param_changed', self.param_panel._on_param_changed)
        self.state.subscribe('prompt_changed', self.prompt_panel._on_prompt_changed)
        self.state.subscribe('vae_changed', self.top_bar._on_vae_changed)
        self.state.subscribe('generation_started', lambda data: self.image_pad.on_mode_changed(data))
        self.state.subscribe('history_updated', self.sidebar._update_history)
        self.state.subscribe('model_selection_changed', self.top_bar._on_model_selected)
        
        # 사용자 알림 이벤트 구독 (TopBar에서 처리하므로 중복 구독 방지)
        # self.state.subscribe('user_notification', self._on_user_notification)
        self.state.subscribe('generation_failed', self.param_panel._on_generation_failed)
        
        # 페이지 컨테이너가 소멸될 때 _on_destroy 함수를 안전하게 연결
        page_container.on('destroy', self._on_destroy)