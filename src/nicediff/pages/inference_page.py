"""
이미지 생성 워크스페이스 페이지 (반응형 수정)
"""

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
    """추론 페이지"""
    
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
    
    async def render(self):
        """페이지 렌더링 (CSS 클래스 적용으로 레이아웃 안정화)"""
        # 전체 컨테이너 - 뷰포트에 맞춤
        with ui.column().classes('main-layout bg-gray-900 text-white'):
            # 상단 바 (고정 높이)
            await self.top_bar.render()
            
            # 메인 컨텐츠 영역 (나머지 공간 모두 사용)
            with ui.row().classes('content-row'):
                # 좌측 접이식 사이드바
                await self.sidebar.render()
                
                # 중앙 컨텐츠 영역 (유연한 크기)
                with ui.column().classes('flex-1 min-w-0 h-full gap-2 p-2 overflow-hidden'):
                    # 중앙 이미지 패드 (남은 세로 공간 채우기)
                    with ui.card().classes('w-full flex-1 min-h-0 p-0 overflow-hidden'):
                        await self.image_pad.render()
                    
                    # 프롬프트 패널 (고정 높이)
                    with ui.card().classes('w-full h-48 bg-gray-700 p-4 overflow-y-auto'):
                        await self.prompt_panel.render()
                
                # 우측 패널 영역 (CSS로 너비 제한)
                with ui.column().classes('right-panel-constrain h-full bg-gray-800 p-2 gap-2 overflow-y-auto'):
                    # 파라미터 패널
                    with ui.card().classes('w-full bg-gray-700 p-3'):
                        await self.param_panel.render()
                    
                    # LoRA 패널
                    with ui.card().classes('w-full bg-gray-700 p-3'):
                        await self.lora_panel.render()
                    
                    # 메타데이터 패널 (크기 축소)
                    with ui.card().classes('w-full bg-teal-800 p-3'):
                        await self.metadata_panel.render()