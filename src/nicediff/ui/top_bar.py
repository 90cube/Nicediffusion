"""
상단 컨트롤 바 컴포넌트
"""

from nicegui import ui
from ..core.state_manager import StateManager

class TopBar:
    """상단 컨트롤 바"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.container = None
        self.model_select = None
        self.vae_select = None
        self.status_label = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.row().classes('w-full p-2 bg-gray-800 items-center gap-4'):
            # Checkpoint 선택
            with ui.row().classes('items-center gap-2'):
                ui.label('Checkpoint').classes('text-white font-medium')
                # 빈 옵션으로 시작
                self.model_select = ui.select(
                    options=[],
                    label='Checkpoint'
                ).classes('w-48 bg-gray-700').props('dark outlined dense')
            
            # VAE 선택
            with ui.row().classes('items-center gap-2'):
                ui.label('VAE').classes('text-white font-medium')
                # None 옵션만 있는 상태로 시작
                self.vae_select = ui.select(
                    options=[],
                    label='VAE'
                ).classes('w-48 bg-gray-700').props('dark outlined dense')
            
            # 우측 영역
            ui.space()
            
            # 상태 표시
            self.status_label = ui.label('모델 스캔 중...').classes('text-yellow-400 text-sm')
            
            # 설정 아이콘
            ui.button(icon='settings').props('flat round color=white')
        
        # 모델 목록 업데이트 구독
        self.state.subscribe('models_updated', self._update_model_list)
        self.state.subscribe('vaes_updated', self._update_vae_list)
    
    async def _update_model_list(self, models):
        """모델 목록 업데이트"""
        if not self.model_select:
            return
            
        if not models or all(len(items) == 0 for items in models.values()):
            # 모델이 없는 경우
            self.model_select.set_options([])
            self.model_select.set_value(None)
            self.status_label.set_text('모델이 없습니다. models/checkpoint 폴더에 모델을 넣어주세요.')
            self.status_label.classes(remove='text-yellow-400 text-green-400', add='text-red-400')
            return
        
        # 옵션 생성
        options = []
        for folder, items in models.items():
            for item in items:
                display_name = f"[{folder}] {item['name']}" if folder != 'Root' else item['name']
                options.append({'label': display_name, 'value': item['path']})
        
        self.model_select.set_options(options)
        
        # 첫 번째 모델을 기본값으로 설정
        if options:
            self.model_select.set_value(options[0]['value'])
            self.state.set('current_model', options[0]['value'])
            
            self.status_label.set_text(f'{len(options)}개 모델 발견')
            self.status_label.classes(remove='text-yellow-400 text-red-400', add='text-green-400')
    
    async def _update_vae_list(self, vaes):
        """VAE 목록 업데이트"""
        if not self.vae_select:
            return
            
        # 기본 None 옵션
        options = [{'label': 'None', 'value': None}]
        
        # VAE가 있으면 추가
        if vaes:
            for folder, items in vaes.items():
                for item in items:
                    display_name = f"[{folder}] {item['name']}" if folder != 'Root' else item['name']
                    options.append({'label': display_name, 'value': item['path']})
        
        self.vae_select.set_options(options)
        self.vae_select.set_value(None)  # 기본값은 None