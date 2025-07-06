# 파일 경로: src/nicediff/ui/parameter_panel.py
# (수정 완료)

from nicegui import ui
import math
from ..core.state_manager import StateManager, GenerationParams

class ParameterPanel:
    """파라미터 패널 (UI 렌더링에만 집중)"""
    
    # ... __init__ 및 다른 메서드들은 그대로 유지 ...
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        
        # ... (생략) ...
        self.ratios_data = [
            ("1:1", 1/1, "1:1 (정사각형)", 'square'), 
            ("4:3", 4/3, "4:3 (표준 TV)", 'horizontal'),
            ("16:9", 16/9, "16:9 (와이드스크린/HD TV)", 'horizontal'),
            ("3:2", 3/2, "3:2 (사진/프린트)", 'horizontal'),
            ("IMAX", 1.43/1, "1.43:1 (아이맥스)", 'horizontal'),
            ("Euro Widescreen", 1.66/1, "1.66:1 (유럽 와이드스크린)", 'horizontal'),
            ("황금비", 1.618/1, "1.618:1 (황금 비율)", 'horizontal'),
        ]
        
        self.selected_display_name = "1:1"
        self.selected_ratio_value = 1/1 
        self.selected_base_orientation = 'square'
        self._is_ratio_inverted = False
        
        self.generate_button = None
        self.width_input = None
        self.height_input = None
        self.model_switch = None
        self.seed_input = None

    def _calculate_dimensions(self):
        target_pixels_map = {"SD15": 512*512, "SDXL": 1024*1024}
        current_sd_model = self.state.get('sd_model', 'SD15') 
        target_pixels = target_pixels_map.get(current_sd_model, 512*512)
        base_ratio_value = self.selected_ratio_value
        
        if self._is_ratio_inverted and self.selected_base_orientation != 'square':
            ratio_to_calculate = 1 / base_ratio_value
        else:
            ratio_to_calculate = base_ratio_value
            
        width = int((target_pixels * ratio_to_calculate)**0.5)
        height = int((target_pixels / ratio_to_calculate)**0.5)
        
        width = max(128, width - (width % 8))
        height = max(128, height - (height % 8))

        current_params: GenerationParams = self.state.get('current_params')
        current_params.width = width
        current_params.height = height
        self.state.set('current_params', current_params)
        
        if self.width_input: self.width_input.value = width
        if self.height_input: self.height_input.value = height

    def _handle_ratio_click(self, dp_name, r_value, orient):
        self._is_ratio_inverted = not self._is_ratio_inverted if self.selected_display_name == dp_name and orient != 'square' else False
        self.selected_display_name = dp_name
        self.selected_ratio_value = r_value
        self.selected_base_orientation = orient
        self._calculate_dimensions()
        self.ratio_buttons_container.refresh()

    async def _on_generate_click(self):
        await self.state.generate_image()
    
    def _on_generate_status_change(self, is_generating: bool):
        if self.generate_button:
            if is_generating:
                self.generate_button.props('loading color=orange').set_text('생성 중...').disable()
            else:
                self.generate_button.props('color=blue', remove='loading').set_text('생성').enable()

    def _on_param_change(self, param_name: str, param_type: type):
        def handler(e):
            current_params = self.state.get('current_params')
            try:
                value = getattr(e, 'value', e.args[0] if e.args else None)
                if value is not None and hasattr(current_params, param_name):
                    converted_value = param_type(value) 
                    setattr(current_params, param_name, converted_value)
                    self.state.set('current_params', current_params)
            except (ValueError, TypeError, IndexError, AttributeError):
                print(f"경고: '{param_name}' 값을 {param_type}으로 변환할 수 없습니다.")
        return handler

    def _randomize_seed(self):
        current_params = self.state.get('current_params')
        current_params.seed = -1
        self.state.set('current_params', current_params)
        if self.seed_input: self.seed_input.update()

    def _handle_model_change(self):
        if self.model_switch:
            new_model = 'SDXL' if self.model_switch.value else 'SD15'
            self.state.set('sd_model', new_model)
            self._calculate_dimensions()

    @ui.refreshable
    def ratio_buttons_container(self):
        with ui.row().classes('w-full flex-wrap justify-center gap-1'):
            for display_name, ratio_value, tooltip_text, orientation in self.ratios_data:
                is_selected = (self.selected_display_name == display_name and not self._is_ratio_inverted)
                button_text = display_name
                if is_selected and self._is_ratio_inverted and orientation != 'square':
                    if ":" in display_name:
                        parts = display_name.split(':')
                        if len(parts) == 2: button_text = f"{parts[1]}:{parts[0]}"
                
                btn_props = f'sm {"color=orange" if is_selected else "outline color=orange"}'
                ui.button(button_text, 
                          on_click=lambda dp=display_name, rv=ratio_value, o=orientation: self._handle_ratio_click(dp, rv, o)) \
                    .props(btn_props).tooltip(tooltip_text)

    async def render(self):
        self._calculate_dimensions()
        comfyui_samplers = ["euler", "dpmpp_2m", "dpmpp_sde_gpu", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde_gpu"]
        comfyui_schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        current_params = self.state.get('current_params')

        with ui.column().classes('w-full gap-3'):
            ui.label('생성 설정').classes('text-lg font-bold text-yellow-400')
            
            with ui.column().classes('gap-2'):
                ui.select(options=comfyui_samplers, label='Sampler', value=current_params.sampler) \
                    .on('update:model-value', self._on_param_change('sampler', str))
                
                ui.select(options=comfyui_schedulers, label='Scheduler', value=current_params.scheduler) \
                    .on('update:model-value', self._on_param_change('scheduler', str))
            
            ui.number(label='Steps', value=current_params.steps, min=1, max=150) \
                .on('update:model-value', self._on_param_change('steps', int))
            
            ui.number(label='CFG Scale', value=current_params.cfg_scale, min=1.0, max=30.0, step=0.5) \
                .on('update:model-value', self._on_param_change('cfg_scale', float))
            
            with ui.row().classes('gap-2'):
                self.width_input = ui.number(value=current_params.width, min=128, max=2048, step=8) \
                    .on('update:model-value', self._on_param_change('width', int))
                
                self.height_input = ui.number(value=current_params.height, min=128, max=2048, step=8) \
                    .on('update:model-value', self._on_param_change('height', int))
            
            with ui.row().classes('w-full flex-center items-center gap-2'):
                self.model_switch = ui.switch(value=(self.state.get('sd_model') == 'SDXL')).props('color=orange') \
                    .on('click', self._handle_model_change)
                ui.label('SDXL').classes('text-xs text-gray-400')

            self.ratio_buttons_container()
            
            with ui.row().classes('w-full gap-2 mt-4'):
                ui.number(label="배치 사이즈", min=1, max=32, value=current_params.batch_size) \
                    .on('update:model-value', self._on_param_change('batch_size', int))
            
                ui.number(label="반복 횟수", min=1, max=100, value=current_params.iterations) \
                    .on('update:model-value', self._on_param_change('iterations', int))

            with ui.row().classes('gap-2 items-center w-full'):
                self.seed_input = ui.number(label='Seed', value=current_params.seed, min=-1) \
                    .on('update:model-value', self._on_param_change('seed', int))
                
                ui.button(icon='casino', on_click=self._randomize_seed)

            self.generate_button = ui.button('생성', on_click=self._on_generate_click) \
                .props('size=lg color=blue').classes('w-full mt-4')
            
            # --- [수정된 부분] ---
            # 여기서 구독하던 로직을 완전히 제거합니다.
            # self.state.subscribe(...)