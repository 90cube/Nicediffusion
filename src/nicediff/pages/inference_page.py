# 파일 경로: src/nicediff/pages/inference_page.py
# (중복 제거 및 구조 정리 완료된 최종 버전)

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
    """추론 페이지 (UI 컴포넌트 조립 및 이벤트 중앙 관리)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        
        # 모든 UI 컴포넌트 인스턴스 생성
        self.top_bar = TopBar(state_manager)
        self.sidebar = UtilitySidebar(state_manager)
        self.image_pad = ImagePad(state_manager)
        self.param_panel = ParameterPanel(state_manager)
        self.prompt_panel = PromptPanel(state_manager)
        self.lora_panel = LoraPanel(state_manager)
        self.metadata_panel = MetadataPanel(state_manager)

    def _on_destroy(self):
        """페이지 소멸 시 모든 콜백 구독을 안전하게 해지합니다."""
        print("InferencePage 소멸: 모든 구독을 해지합니다.")
        
        # render에서 구독했던 모든 이벤트를 여기서 해지합니다.
        self.state.unsubscribe('is_generating_changed', self.param_panel._on_generate_status_change)
        
        # 다른 모든 구독들도 여기에 추가하여 관리합니다.
        # 예: self.state.unsubscribe('model_selection_changed', self.metadata_panel._on_model_selected)

    async def render(self):
        """페이지의 모든 UI를 렌더링하고, 이벤트를 중앙에서 한번만 구독합니다."""
        
        with ui.column().classes('main-layout bg-gray-850 text-white') as page_container:
            await self.top_bar.render()
            
            with ui.row().classes('content-row'):
                await self.sidebar.render()
                
                with ui.column().classes('flex-1 min-w-0 h-full gap-2 p-2 overflow-hidden'):
                    with ui.card().classes('w-full flex-1 min-h-0 p-0 overflow-hidden'):
                        await self.image_pad.render()
                    with ui.card().classes('w-full h-48 bg-gray-700 p-4 overflow-y-auto'):
                        await self.prompt_panel.render()
                
                with ui.column().classes('right-panel-constrain h-full bg-gray-800 p-2 gap-2 overflow-y-auto'):
                    await self.param_panel.render()
                    await self.lora_panel.render()
                    await self.metadata_panel.render()

        # --- [핵심] ---
        # 모든 UI가 화면에 완전히 그려진 후, 필요한 모든 이벤트를 여기서 한번만 연결(구독)합니다.
        print("InferencePage: 모든 UI 렌더링 완료. 이벤트 구독을 시작합니다.")
        
        # UI 컴포넌트들을 StateManager에 등록 (다른 컴포넌트에서 접근 가능하도록)
        self.state.set('image_pad', self.image_pad)
        self.state.set('sidebar', self.sidebar)
        self.state.set('param_panel', self.param_panel)
        self.state.set('prompt_panel', self.prompt_panel)
        self.state.set('lora_panel', self.lora_panel)
        self.state.set('metadata_panel', self.metadata_panel)
        self.state.set('top_bar', self.top_bar)
        
        # 기존 구독
        self.state.subscribe('is_generating_changed', self.param_panel._on_generate_status_change)
        
        # 새로 추가된 이벤트 구독들
        self.state.subscribe('param_changed', self.param_panel._on_param_changed)
        self.state.subscribe('prompt_changed', self.prompt_panel._on_prompt_changed)
        self.state.subscribe('vae_changed', self.top_bar._on_vae_changed)
        self.state.subscribe('lora_added', self.lora_panel._on_lora_added)
        self.state.subscribe('lora_removed', self.lora_panel._on_lora_removed)
        self.state.subscribe('image_generated', self.image_pad._on_image_generated)
        self.state.subscribe('generation_started', self.image_pad._on_generation_started)
        self.state.subscribe('history_updated', self.sidebar._update_history)
        self.state.subscribe('model_selection_changed', self.top_bar._on_model_selected)
        self.state.subscribe('model_selection_changed', self.metadata_panel._on_model_selected)
        
        # 사용자 알림 이벤트 구독 (TopBar에서 처리하므로 중복 구독 방지)
        # self.state.subscribe('user_notification', self._on_user_notification)
        self.state.subscribe('generation_failed', self.param_panel._on_generation_failed)
        
        # 페이지 컨테이너가 소멸될 때 _on_destroy 함수를 안전하게 연결
        page_container.on('destroy', self._on_destroy)