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
        with ui.column().classes('w-full h-screen bg-gray-900 text-white overflow-hidden'):
            # 상단 바 (Checkpoint, VAE, 설정 아이콘)
            await self.top_bar.render()
            
            # 메인 컨텐츠 영역
            with ui.row().classes('flex-1 gap-0'):
                # 좌측 영역: 사이드바 + 이미지 패드 + 파라미터
                with ui.row().classes('flex-1 gap-0'):
                    # 접이식 사이드바
                    await self.sidebar.render()
                    
                    # 중앙 이미지 패드
                    with ui.column().classes('flex-1 bg-blue-900 p-4'):
                        await self.image_pad.render()
                    
                    # 우측 파라미터 패널
                    with ui.column().classes('w-80 bg-gray-800 p-4'):
                        await self.param_panel.render()
                
                # 하단 패널들 (프롬프트, LoRA, 메타데이터)
                with ui.column().classes('w-96 bg-gray-800'):
                    # 프롬프트 패널
                    with ui.card().classes('bg-gray-700 p-4 m-2'):
                        await self.prompt_panel.render()
                    
                    # LoRA 패널
                    with ui.card().classes('bg-gray-700 p-4 m-2 flex-1'):
                        await self.lora_panel.render()
                    
                    # 메타데이터 패널
                    with ui.card().classes('bg-teal-800 p-4 m-2'):
                        await self.metadata_panel.render()