"""
상단 컨트롤 바 컴포넌트 (반응형 수정)
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
        with ui.row().classes('w-full p-2 bg-gray-800 items-center gap-2 min-h-16 flex-wrap lg:flex-nowrap'):
            # Checkpoint 선택 (반응형 너비)
            with ui.row().classes('items-center gap-2 min-w-0'):
                ui.label('Checkpoint').classes('text-white font-medium text-sm hidden sm:block')  # 작은 화면에서 숨김
                ui.label('CP').classes('text-white font-medium text-sm block sm:hidden')  # 작은 화면용 축약
                
                self.model_select = ui.select(
                    options=[],
                    label='Checkpoint'
                ).classes('w-32 sm:w-40 lg:w-48 bg-gray-700').props('dark outlined dense')
            
            # VAE 선택 (반응형 너비)
            with ui.row().classes('items-center gap-2 min-w-0'):
                ui.label('VAE').classes('text-white font-medium text-sm')
                
                self.vae_select = ui.select(
                    options=[],
                    label='VAE'
                ).classes('w-24 sm:w-32 lg:w-40 bg-gray-700').props('dark outlined dense')
            
            # 우측 영역 (유연한 공간)
            ui.space()
            
            # 상태 표시 (반응형)
            self.status_label = ui.label('모델 스캔 중...').classes(
                'text-yellow-400 text-xs sm:text-sm hidden md:block'  # 중간 크기 이상에서만 표시
            )
            
            # 상태 아이콘 (작은 화면용)
            self.status_icon = ui.icon('sync').classes(
                'text-yellow-400 block md:hidden animate-spin'  # 중간 크기 이하에서만 표시
            ).tooltip('모델 스캔 중...')
            
            # 설정 아이콘
            ui.button(icon='settings').props('flat round color=white').classes('flex-shrink-0')
        
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
            self._update_status('모델이 없습니다', 'error', 'error')
            return
        
        # 옵션 생성 (반응형 표시명)
        options = []
        for folder, items in models.items():
            for item in items:
                # 작은 화면용 짧은 이름
                short_name = item['name'][:15] + '...' if len(item['name']) > 15 else item['name']
                # 긴 화면용 전체 이름
                full_name = f"[{folder}] {item['name']}" if folder != 'Root' else item['name']
                
                options.append({
                    'label': full_name,
                    'value': item['path']
                })
        
        self.model_select.set_options(options)
        
        # 첫 번째 모델을 기본값으로 설정
        if options:
            self.model_select.set_value(options[0]['value'])
            self.state.set('current_model', options[0]['value'])
            self._update_status(f'{len(options)}개 모델', 'success', 'check_circle')
    
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
                    # 반응형 표시명
                    short_name = item['name'][:10] + '...' if len(item['name']) > 10 else item['name']
                    full_name = f"[{folder}] {item['name']}" if folder != 'Root' else item['name']
                    
                    options.append({
                        'label': full_name,
                        'value': item['path']
                    })
        
        self.vae_select.set_options(options)
        self.vae_select.set_value(None)  # 기본값은 None
    
    def _update_status(self, message: str, status_type: str, icon_name: str):
        """상태 업데이트"""
        color_map = {
            'loading': 'text-yellow-400',
            'success': 'text-green-400',
            'error': 'text-red-400'
        }
        
        color = color_map.get(status_type, 'text-gray-400')
        
        # 텍스트 상태 업데이트
        if self.status_label:
            self.status_label.set_text(message)
            self.status_label.classes(
                remove='text-yellow-400 text-green-400 text-red-400',
                add=color
            )
        
        # 아이콘 상태 업데이트
        if self.status_icon:
            self.status_icon.set_name(icon_name)
            self.status_icon.classes(
                remove='text-yellow-400 text-green-400 text-red-400 animate-spin',
                add=color
            )
            
            # 로딩 중이면 회전 애니메이션 추가
            if status_type == 'loading':
                self.status_icon.classes(add='animate-spin')
            
            # 툴팁 업데이트
            self.status_icon.tooltip(message)