"""
메타데이터 표시 패널
"""

from nicegui import ui
from ..core.state_manager import StateManager

class MetadataPanel:
    """메타데이터 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.metadata_content = None
        self.current_metadata = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.card().classes('w-full h-full p-4 bg-teal-800'):
            ui.label('메타데이터').classes('text-lg font-bold mb-2 text-white')
            
            # 메타데이터 표시 영역
            with ui.scroll_area().classes('w-full h-full'):
                self.metadata_content = ui.column().classes('w-full')
                self._show_empty_state()
        
        # 이벤트 구독
        self.state.subscribe('model_selected', self._on_model_selected)
        self.state.subscribe('lora_selected', self._on_lora_selected)
    
    def _show_empty_state(self):
        """빈 상태 표시"""
        self.metadata_content.clear()
        with self.metadata_content:
            with ui.column().classes('w-full items-center justify-center p-4'):
                ui.icon('info').classes('text-4xl text-teal-400 mb-2')
                ui.label('메타데이터가 없습니다').classes('text-teal-300 text-sm text-center')
                ui.label('모델이나 LoRA를 선택하면').classes('text-teal-400 text-xs text-center')
                ui.label('정보가 여기에 표시됩니다').classes('text-teal-400 text-xs text-center')
    
    def _show_metadata(self, metadata: dict, source_type: str = 'model'):
        """메타데이터 표시"""
        self.metadata_content.clear()
        self.current_metadata = metadata
        
        with self.metadata_content:
            # 소스 타입 표시
            source_label = '모델' if source_type == 'model' else 'LoRA'
            ui.chip(source_label, color='teal').props('text-color=white')
            
            # 기본 정보
            if metadata.get('name'):
                ui.label(f"이름: {metadata['name']}").classes('text-sm text-white mt-2')
            
            if metadata.get('description'):
                ui.label('설명:').classes('text-sm font-bold text-teal-300 mt-2')
                ui.label(metadata['description']).classes('text-xs text-white')
            
            # 프롬프트 정보
            if metadata.get('prompt'):
                with ui.expansion('긍정 프롬프트', icon='add_circle').classes('w-full mt-2'):
                    ui.label(metadata['prompt']).classes('text-xs text-white')
                    ui.button(
                        '복사',
                        icon='content_copy',
                        on_click=lambda: self._copy_to_clipboard(metadata['prompt'], '긍정 프롬프트')
                    ).props('dense flat color=teal-300')
            
            if metadata.get('negative_prompt'):
                with ui.expansion('부정 프롬프트', icon='remove_circle').classes('w-full mt-2'):
                    ui.label(metadata['negative_prompt']).classes('text-xs text-white')
                    ui.button(
                        '복사',
                        icon='content_copy',
                        on_click=lambda: self._copy_to_clipboard(metadata['negative_prompt'], '부정 프롬프트')
                    ).props('dense flat color=teal-300')
            
            # 파라미터 정보
            if metadata.get('parameters'):
                with ui.expansion('생성 파라미터', icon='tune').classes('w-full mt-2'):
                    params = metadata['parameters']
                    param_list = []
                    
                    if 'steps' in params:
                        param_list.append(f"Steps: {params['steps']}")
                    if 'cfg_scale' in params:
                        param_list.append(f"CFG: {params['cfg_scale']}")
                    if 'sampler' in params:
                        param_list.append(f"Sampler: {params['sampler']}")
                    if 'seed' in params:
                        param_list.append(f"Seed: {params['seed']}")
                    
                    ui.label(' | '.join(param_list)).classes('text-xs text-white')
                    
                    # 파라미터 적용 버튼
                    ui.button(
                        '파라미터 적용 →',
                        icon='arrow_forward',
                        on_click=self._apply_parameters
                    ).props('color=teal-300').classes('mt-2')
            
            # 트리거 워드 (LoRA용)
            if metadata.get('trigger_words'):
                ui.label('트리거 워드:').classes('text-sm font-bold text-teal-300 mt-4')
                with ui.row().classes('gap-1 flex-wrap mt-1'):
                    for word in metadata['trigger_words']:
                        ui.button(
                            word,
                            on_click=lambda w=word: self._add_trigger_word(w)
                        ).props('dense outline color=teal-300').classes('text-xs')
    
    def _copy_to_clipboard(self, text: str, label: str):
        """클립보드에 복사"""
        # JavaScript를 사용한 클립보드 복사
        ui.run_javascript(f'''
            navigator.clipboard.writeText(`{text}`).then(() => {{
                console.log('Copied to clipboard');
            }});
        ''')
        ui.notify(f'{label}가 복사되었습니다', type='positive')
    
    def _apply_parameters(self):
        """파라미터 적용"""
        if not self.current_metadata or not self.current_metadata.get('parameters'):
            return
        
        params = self.current_metadata['parameters']
        current_params = self.state.get('current_params')
        
        # 파라미터 업데이트
        if 'steps' in params:
            current_params.steps = params['steps']
        if 'cfg_scale' in params:
            current_params.cfg_scale = params['cfg_scale']
        if 'sampler' in params:
            current_params.sampler = params['sampler']
        if 'width' in params:
            current_params.width = params['width']
        if 'height' in params:
            current_params.height = params['height']
        
        # 상태 알림
        self.state.set('current_params', current_params)
        ui.notify('파라미터가 적용되었습니다', type='success')
    
    def _add_trigger_word(self, word: str):
        """트리거 워드 추가"""
        # 현재 프롬프트 가져오기
        current_prompt = self.state.get('current_params').prompt
        
        # 프롬프트에 추가
        if current_prompt:
            new_prompt = f"{current_prompt}, {word}"
        else:
            new_prompt = word
        
        # 상태 업데이트
        self.state.get('current_params').prompt = new_prompt
        self.state._notify('prompt_updated', new_prompt)
        
        ui.notify(f'"{word}" 추가됨', type='positive')
    
    async def _on_model_selected(self, model_info):
        """모델 선택 이벤트"""
        if model_info and model_info.get('metadata'):
            self._show_metadata(model_info['metadata'], 'model')
        else:
            self._show_empty_state()
    
    async def _on_lora_selected(self, lora_info):
        """LoRA 선택 이벤트"""
        if lora_info and lora_info.get('metadata'):
            self._show_metadata(lora_info['metadata'], 'lora')
        else:
            self._show_empty_state()