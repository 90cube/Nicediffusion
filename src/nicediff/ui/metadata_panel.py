"""
메타데이터 표시 패널
"""

from nicegui import ui
from typing import Dict, Any, Optional
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
        self.state.subscribe('model_selection_changed', self._on_model_selected)
        #self.state.subscribe('lora_selected', self._on_lora_selected) # LoRA 로직은 나중에 추가
    
    def _show_empty_state(self):
        """빈 상태 표시"""
        self.metadata_content.clear()
        with self.metadata_content:
            with ui.column().classes('w-full items-center justify-center p-4'):
                ui.icon('info').classes('text-4xl text-teal-400 mb-2')
                ui.label('메타데이터가 없습니다').classes('text-teal-300 text-sm text-center')
                ui.label('모델이나 LoRA를 선택하면').classes('text-teal-400 text-xs text-center')
                ui.label('정보가 여기에 표시됩니다').classes('text-teal-400 text-xs text-center')
    
    def _show_metadata(self, model_info: dict, source_type: str = 'model'):
        """[수정] 메타데이터를 3가지 섹션으로 분리하여 표시"""
        self.metadata_content.clear()
        self.current_metadata = model_info.get('metadata', {})
        
        with self.metadata_content:
            ui.label(model_info.get('name', '알 수 없음')).classes('text-md font-bold text-white')

            # 1. 긍정 프롬프트 (복사만 가능)
            positive_prompt = self.current_metadata.get('prompt', '')
            if positive_prompt:
                with ui.expansion('긍정 프롬프트', icon='add_circle').classes('w-full mt-2'):
                    ui.label(positive_prompt).classes('text-xs text-white bg-gray-800 p-2 rounded max-h-24 overflow-y-auto')
                    ui.button('복사', icon='content_copy', on_click=lambda: self._copy_to_clipboard(positive_prompt, '긍정 프롬프트')) \
                        .props('dense flat color=teal-300 size=xs')

            # 2. 부정 프롬프트 (복사만 가능)
            negative_prompt = self.current_metadata.get('negative_prompt', '')
            if negative_prompt:
                with ui.expansion('부정 프롬프트', icon='remove_circle').classes('w-full mt-1'):
                    ui.label(negative_prompt).classes('text-xs text-white bg-gray-800 p-2 rounded max-h-24 overflow-y-auto')
                    ui.button('복사', icon='content_copy', on_click=lambda: self._copy_to_clipboard(negative_prompt, '부정 프롬프트')) \
                        .props('dense flat color=teal-300 size=xs')

            # 3. 생성 파라미터 (적용 가능)
            params = self.current_metadata.get('parameters', {})
            if params:
                with ui.expansion('생성 파라미터', icon='tune').classes('w-full mt-1'):
                    param_items = [f"{k}: {v}" for k, v in params.items()]
                    ui.label(' | '.join(param_items)).classes('text-xs text-white bg-gray-800 p-2 rounded')
                    ui.button('파라미터 패널에 적용', icon='send', on_click=self._apply_parameters_to_panel) \
                        .props('color=blue size=sm').classes('w-full mt-2')


    def _copy_to_clipboard(self, text: str, label: str):
        """클립보드에 복사 (개선된 방식)"""
        # JavaScript를 사용한 클립보드 복사
        escaped_text = text.replace('`', '\\`').replace('\\', '\\\\')
        ui.run_javascript(f'''
            navigator.clipboard.writeText(`{escaped_text}`).then(() => {{
                console.log('Copied to clipboard: {label}');
            }}).catch(err => {{
                console.error('Failed to copy: ', err);
                // Fallback: 임시 textarea 사용
                const textarea = document.createElement('textarea');
                textarea.value = `{escaped_text}`;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }});
        ''')
        ui.notify(f'{label}가 복사되었습니다', type='positive')
    
    def _apply_parameters_to_panel(self):
        """[수정] 파라미터를 검증하고 ParameterPanel로 전달하는 알림을 보냅니다."""
        if not self.current_metadata or 'parameters' not in self.current_metadata:
            ui.notify('적용할 파라미터가 없습니다', type='warning')
            return

        params_to_apply = self.current_metadata['parameters']
        
        # 유효성 검사 (나에게 없는 샘플러/스케줄러는 제외)
        valid_params = {}
        
        # 샘플러 목록 (parameter_panel.py와 동일하게 유지)
        comfyui_samplers = ["euler", "euler_a", "dpmpp_2m", "dpmpp_sde_gpu", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde_gpu"]
        # 스케줄러 목록
        comfyui_schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        
        for key, value in params_to_apply.items():
            if key == 'sampler' and value not in comfyui_samplers:
                ui.notify(f"'{value}' 샘플러는 지원되지 않아 제외합니다.", type='warning')
                continue
            if key == 'scheduler' and value not in comfyui_schedulers:
                ui.notify(f"'{value}' 스케줄러는 지원되지 않아 제외합니다.", type='warning')
                continue
            valid_params[key] = value

        if not valid_params:
            ui.notify('적용할 유효한 파라미터가 없습니다.', type='info')
            return

        # ParameterPanel로 보낼 새로운 알림
        self.state._notify('apply_params_from_metadata', valid_params)
        ui.notify('파라미터가 패널로 전달되었습니다.', type='success')

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
        """모델 선택 이벤트 (연결 확인 로직 수정)"""
        with self.metadata_content:
            # --- [핵심 수정] ---
            # 'is_connected' -> 'disconnected' 속성으로 변경하고, not을 제거합니다.
            # "연결이 끊겼으면"을 직접 확인합니다.
            if ui.context.client.disconnected:
                print("클라이언트 연결이 끊겨 MetadataPanel UI 업데이트를 건너뜁니다.")
                return 
            
            # 연결이 되어 있을 때만 아래의 UI 업데이트 로직 실행
            if model_info:
                self._show_metadata(model_info, 'model')
            else:
                self._show_empty_state()

    async def _on_lora_selected(self, lora_info):
        """LoRA 선택 이벤트"""
        if lora_info and lora_info.get('metadata'):
            self._show_metadata(lora_info['metadata'], 'lora')
        else:
            self._show_empty_state()