# parameter_panel.py (이벤트 핸들링 오류 수정)

from nicegui import ui
import math
from src.nicediff.core.state_manager import StateManager, GenerationParams

class ParameterPanel:
    """파라미터 패널 (이벤트 핸들링 오류 수정 완료)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        
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
        
        # UI 요소 참조
        self.generate_button = None
        self.width_input = None
        self.height_input = None
        self.model_switch = None

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
        
        width = width - (width % 8)
        height = height - (height % 8)
        
        width = max(128, width)
        height = max(128, height)

        current_params: GenerationParams = self.state.get('current_params')
        current_params.width = width
        current_params.height = height
        self.state.set('current_params', current_params)
        
        # UI 업데이트
        if self.width_input:
            self.width_input.value = width
        if self.height_input:
            self.height_input.value = height

    def _handle_ratio_click(self, dp_name, r_value, orient):
        self._is_ratio_inverted = not self._is_ratio_inverted if self.selected_display_name == dp_name and orient != 'square' else False
        self.selected_display_name = dp_name
        self.selected_ratio_value = r_value
        self.selected_base_orientation = orient
        self._calculate_dimensions()

    async def _on_generate_click(self):
        """StateManager에 생성을 '요청'만 합니다."""
        print("🚀 UI에서 생성 요청을 StateManager로 전달합니다...")
        await self.state.generate_image()
    
    def _on_generate_status_change(self, is_generating: bool):
        """생성 상태 변경 시 버튼 업데이트"""
        if self.generate_button:
            if is_generating:
                self.generate_button.props('loading color=orange')
                self.generate_button.set_text('생성 중...')
                self.generate_button.disable()
            else:
                self.generate_button.props('color=blue')
                self.generate_button.props(remove='loading')
                self.generate_button.set_text('생성')
                self.generate_button.enable()

    def _on_width_change(self, e):
        """폭 변경 시 호출"""
        current_params = self.state.get('current_params')
        try:
            # NiceGUI 이벤트에서 값 추출 방식 수정
            value = getattr(e, 'value', None) or getattr(e, 'args', [None])[0]
            if value is not None:
                current_params.width = int(value)
                self.state.set('current_params', current_params)
        except (ValueError, TypeError, IndexError):
            pass

    def _on_height_change(self, e):
        """높이 변경 시 호출"""
        current_params = self.state.get('current_params')
        try:
            # NiceGUI 이벤트에서 값 추출 방식 수정
            value = getattr(e, 'value', None) or getattr(e, 'args', [None])[0]
            if value is not None:
                current_params.height = int(value)
                self.state.set('current_params', current_params)
        except (ValueError, TypeError, IndexError):
            pass

    def _on_param_change(self, param_name: str):
        """일반 파라미터 변경을 위한 클로저 생성"""
        def handler(e):
            current_params = self.state.get('current_params')
            try:
                # NiceGUI 이벤트에서 값 추출 방식 수정
                value = getattr(e, 'value', None) or getattr(e, 'args', [None])[0]
                if value is not None and hasattr(current_params, param_name):
                    setattr(current_params, param_name, value)
                    self.state.set('current_params', current_params)
            except (ValueError, TypeError, IndexError, AttributeError):
                pass
        return handler

    def _randomize_seed(self):
        """시드 랜덤화"""
        current_params = self.state.get('current_params')
        current_params.randomize_seed()
        self.state.set('current_params', current_params)
        # seed input UI 업데이트
        if hasattr(self, 'seed_input'):
            self.seed_input.value = current_params.seed

    def _handle_model_change(self):
        """모델 타입 변경 핸들러 (스위치 상태 직접 확인)"""
        if self.model_switch:
            new_model = 'SDXL' if self.model_switch.value else 'SD15'
            self.state.set('sd_model', new_model)
            self._calculate_dimensions()
            print(f"🔄 모델 타입 변경: {new_model}")

    async def render(self):
        """패널 렌더링"""
        self._calculate_dimensions()
        comfyui_samplers = ["euler", "dpmpp_2m", "dpmpp_sde_gpu", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde_gpu"]
        comfyui_schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        current_params = self.state.get('current_params')

        with ui.column().classes('w-full gap-3'):
            ui.label('생성 설정').classes('text-lg font-bold text-yellow-400')
            
            # 샘플러 및 스케줄러
            with ui.column().classes('gap-2'):
                sampler_select = ui.select(
                    options=comfyui_samplers, 
                    label='Sampler', 
                    value=current_params.sampler
                ).props('dark outlined dense').classes('bg-gray-700')
                sampler_select.on('update:model-value', self._on_param_change('sampler'))
                
                scheduler_select = ui.select(
                    options=comfyui_schedulers, 
                    label='Scheduler', 
                    value=current_params.scheduler
                ).props('dark outlined dense').classes('bg-gray-700')
                scheduler_select.on('update:model-value', self._on_param_change('scheduler'))
            
            # Steps와 CFG
            steps_input = ui.number(
                label='Steps', 
                value=current_params.steps, 
                min=1, 
                max=150
            ).props('dark outlined dense').classes('bg-gray-700')
            steps_input.on('update:model-value', self._on_param_change('steps'))
            
            cfg_input = ui.number(
                label='CFG Scale', 
                value=current_params.cfg_scale, 
                min=1.0, 
                max=30.0, 
                step=0.5
            ).props('dark outlined dense').classes('bg-gray-700')
            cfg_input.on('update:model-value', self._on_param_change('cfg_scale'))
            
            # 이미지 크기
            with ui.row().classes('gap-2'):
                ui.label('Width').classes('text-xs')
                self.width_input = ui.number(
                    value=current_params.width,
                    min=128,
                    max=2048,
                    step=8
                ).props('dark outlined dense').classes('bg-gray-700 w-20')
                self.width_input.on('update:model-value', self._on_width_change)
                
                ui.label('Height').classes('text-xs')
                self.height_input = ui.number(
                    value=current_params.height,
                    min=128,
                    max=2048,
                    step=8
                ).props('dark outlined dense').classes('bg-gray-700 w-20')
                self.height_input.on('update:model-value', self._on_height_change)
            
            # 모델 타입 스위치 (수정된 이벤트 핸들링)
            with ui.row().classes('w-full flex-center items-center gap-2'):
                current_model_type = self.state.get('sd_model', 'SD15')
                self.model_switch = ui.switch(value=(current_model_type == 'SDXL')).props('color=orange')
                self.model_switch.on('click', self._handle_model_change)  # click 이벤트 사용
                ui.label('SDXL').classes('text-xs text-gray-400')

            # 비율 버튼들
            with ui.row().classes('w-full flex-wrap justify-center gap-1'):
                sorted_ratios_data = sorted(self.ratios_data, key=lambda item: item[1])
                for display_name, ratio_value, tooltip_text, orientation in sorted_ratios_data:
                    is_selected = (self.selected_display_name == display_name and not self._is_ratio_inverted)
                    button_text = display_name
                    if is_selected and self._is_ratio_inverted and orientation != 'square':
                        if ":" in display_name:
                            parts = display_name.split(':')
                            if len(parts) == 2: 
                                button_text = f"{parts[1]}:{parts[0]}"
                    
                    btn_props = f'sm {"color=orange" if is_selected else "outline color=orange"}'
                    ui.button(
                        button_text, 
                        on_click=lambda dp=display_name, rv=ratio_value, o=orientation: self._handle_ratio_click(dp, rv, o)
                    ).props(btn_props).tooltip(tooltip_text)
            
            # 배치 및 반복 설정
            with ui.row().classes('w-full gap-2 mt-4'):
                batch_input = ui.number(
                    label="배치 사이즈", 
                    min=1, 
                    max=32, 
                    value=current_params.batch_size
                ).props('dark outlined dense').classes('flex-1').tooltip('한 번에 생성할 이미지 수')
                batch_input.on('update:model-value', self._on_param_change('batch_size'))
            
                iterations_input = ui.number(
                    label="반복 횟수", 
                    min=1, 
                    max=100, 
                    value=current_params.iterations
                ).props('dark outlined dense').classes('flex-1').tooltip('이 생성 작업을 몇 번 반복할지')
                iterations_input.on('update:model-value', self._on_param_change('iterations'))

            # 시드 설정
            with ui.row().classes('gap-2 items-center w-full'):
                self.seed_input = ui.number(
                    label='Seed', 
                    value=current_params.seed, 
                    min=-1
                ).props('dark outlined dense').classes('bg-gray-700 flex-grow')
                self.seed_input.on('update:model-value', self._on_param_change('seed'))
                
                ui.button(
                    icon='casino', 
                    on_click=self._randomize_seed
                ).props('sm round color=blue').tooltip('랜덤 시드')

            # 생성 버튼
            self.generate_button = ui.button(
                '생성', 
                on_click=self._on_generate_click
            ).props('size=lg color=blue').classes('w-full mt-4')
            
            # 생성 상태 변경 이벤트 구독
            self.state.subscribe('is_generating_changed', self._on_generate_status_change)
            self.state.subscribe('generation_started', lambda _: self._on_generate_status_change(True))
            self.state.subscribe('generation_finished', lambda _: self._on_generate_status_change(False))
            self.state.subscribe('generation_failed', lambda _: self._on_generate_status_change(False))