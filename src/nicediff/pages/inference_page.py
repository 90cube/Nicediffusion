"""
이미지 생성 워크스페이스 페이지
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
        """페이지 렌더링"""
        # 전체 컨테이너 - 다크 테마 배경
        with ui.column().classes('w-full h-screen bg-gray-900 text-white overflow-hidden no-wrap'):
            # 상단 바 (Checkpoint, VAE, 설정 아이콘)
            await self.top_bar.render()
            
            # 메인 컨텐츠 영역 (좌측 사이드바 + 중앙 + 우측 패널)
            with ui.row().classes('flex-1 w-full gap-0 overflow-hidden'): # flex-1로 남은 공간 채우기
                # 좌측 접이식 사이드바
                await self.sidebar.render()
                
                # 중앙 컨텐츠 영역 (이미지 패드 + 프롬프트 패널)
                with ui.column().classes('flex-1 h-full gap-2 p-2 overflow-hidden'): # flex-1로 남은 공간 채우기
                    # 중앙 이미지 패드
                    with ui.card().classes('w-full flex-grow p-0 overflow-hidden'): # flex-grow로 남은 세로 공간 채우기
                        await self.image_pad.render()
                    
                    # 프롬프트 패널
                    with ui.card().classes('w-full bg-gray-700 p-4'):
                        await self.prompt_panel.render()
                
                # 우측 패널 영역 (파라미터 + LoRA + 메타데이터)
                with ui.column().classes('w-80 h-full bg-gray-800 p-2 gap-2 overflow-y-auto'): # 스케치에 따라 폭 80, 세로 스크롤 가능
                    # 파라미터 패널
                    with ui.card().classes('w-full bg-gray-700 p-4'):
                        await self.param_panel.render()
                    
                    # LoRA 패널
                    with ui.card().classes('w-full bg-gray-700 p-4'):
                        await self.lora_panel.render()
                    
                    # 메타데이터 패널
                    with ui.card().classes('w-full bg-teal-800 p-4'):
                        await self.metadata_panel.render()