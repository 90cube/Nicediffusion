"""
우측 파라미터 컨트롤 패널
"""

from nicegui import ui
from ..core.state_manager import StateManager

class ParameterPanel:
    """파라미터 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full gap-3'):
            # 생성 설정 헤더
            ui.label('생성 설정').classes('text-lg font-bold text-yellow-400')
            
            # 샘플러 & 스케줄러
            with ui.column().classes('gap-2'):
                ui.label('샘플러').classes('text-sm text-gray-300')
                ui.select(
                    options=['DPM++ 2M Karras', 'Euler a', 'DDIM'],
                    value='DPM++ 2M Karras'
                ).props('dark outlined dense').classes('bg-gray-700')
                
                ui.label('스케줄러').classes('text-sm text-gray-300')
                ui.select(
                    options=['Karras', 'Normal', 'Simple'],
                    value='Karras'
                ).props('dark outlined dense').classes('bg-gray-700')
            
            # Steps
            ui.label('Steps').classes('text-sm text-gray-300')
            ui.number(value=20, min=1, max=150).props('dark outlined dense').classes('bg-gray-700')
            
            # CFG Scale
            ui.label('CFG Scale').classes('text-sm text-gray-300')
            ui.number(value=7.0, min=1, max=30, step=0.5).props('dark outlined dense').classes('bg-gray-700')
            
            # 이미지 크기
            ui.label('이미지 크기').classes('text-sm text-gray-300')
            with ui.row().classes('gap-2'):
                ui.label('Width').classes('text-xs')
                ui.number(value=512).props('dark outlined dense').classes('bg-gray-700 w-20')
                ui.label('Height').classes('text-xs')
                ui.number(value=512).props('dark outlined dense').classes('bg-gray-700 w-20')
            
            # 비율 프리셋
            ui.label('비율 프리셋').classes('text-sm text-green-400')
            with ui.column().classes('gap-1'):
                # SD1.5 프리셋
                ui.chip('SD15', selectable=True).props('color=green')
                ui.chip('SDXL', selectable=True).props('color=green outline')
                
                # 비율 버튼들
                with ui.row().classes('gap-1 flex-wrap'):
                    for ratio in ['1:1', '2:1', '4:3']:
                        ui.button(ratio).props('sm outline color=orange')
                        
                # 더 많은 비율들
                with ui.row().classes('gap-1 flex-wrap'):
                    ui.button('9(비율 유지기능)').props('sm color=yellow text-black')
                    ui.button('16:9').props('sm color=orange')
                    ui.button('8:5').props('sm color=orange')
            
            # Seed
            ui.label('Seed').classes('text-sm text-gray-300')
            with ui.row().classes('gap-2 items-center'):
                ui.number(value=-1).props('dark outlined dense').classes('bg-gray-700 flex-1')
                ui.button(icon='casino').props('sm round color=blue')
            
            # 생성 버튼
            ui.button('생성').props('size=lg color=blue').classes('w-full mt-4')