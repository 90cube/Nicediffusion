# 파일 경로: src/nicediff/ui/parameter_panel.py

from nicegui import ui
import math
from ..core.state_manager import StateManager, GenerationParams

class ParameterPanel:
    """파라미터 패널 (UI 렌더링에만 집중)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        
        # 비율 데이터
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
        self.seed_input = None
        self.steps_input = None
        self.cfg_input = None
        self.sampler_select = None
        self.scheduler_select = None
        self.batch_size_input = None
        self.iterations_input = None

    def _on_generate_status_change(self, is_generating: bool):
        """[최종 수정] 경합 상태 방지를 위한 최종 안전장치(try-except) 추가"""
        try:
            # 기존의 안전장치 코드
            button = getattr(self, 'generate_button', None)
            
            # 버튼이 존재하지 않으면(None 이면) 즉시 함수를 종료
            if not button:
                return

            # 버튼이 존재할 때만 아래 상태 변경 로직 실행
            if is_generating:
                button.props('loading color=orange').set_text('생성 중...').disable()
            else:
                button.props('color=blue', remove='loading').set_text('생성').enable()
                
        except Exception as e:
            # 이 핸들러가 호출되었지만, 대상 버튼이 파괴되는 등 알 수 없는 UI 관련 오류 발생 시
            # 사용자에게 오류를 표시하는 대신, 콘솔에만 조용히 기록하고 무시합니다.
            # 이렇게 하면 프로그램이 멈추거나 보기 싫은 오류 메시지를 출력하지 않습니다.
            # 디버깅이 필요할때만 주석 해제하고 pass 지우기.
            #print(f"UI 업데이트 중 안전하게 처리된 오류 (무시 가능): {e}")
            pass

    def _calculate_dimensions(self):
        """선택된 비율과 모델에 따라 이미지 크기 계산"""
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
        """비율 버튼 클릭 처리"""
        self._is_ratio_inverted = not self._is_ratio_inverted if self.selected_display_name == dp_name and orient != 'square' else False
        self.selected_display_name = dp_name
        self.selected_ratio_value = r_value
        self.selected_base_orientation = orient
        self._calculate_dimensions()
        self.ratio_buttons_container.refresh()

    async def _on_generate_click(self):
        """생성 버튼 클릭"""
        await self.state.generate_image()

    def _on_param_change(self, param_name: str, param_type: type):
        """파라미터 변경 핸들러 팩토리"""
        def handler(e):
            current_params = self.state.get('current_params')
            try:
                # NiceGUI의 select 컴포넌트는 e.value로 값을 전달합니다
                if hasattr(e, 'value'):
                    value = e.value
                elif hasattr(e, 'args') and e.args:
                    value = e.args[0] if isinstance(e.args, (list, tuple)) else e.args
                else:
                    print(f"경고: '{param_name}' 이벤트에서 값을 찾을 수 없습니다.")
                    return
                
                if value is not None and hasattr(current_params, param_name):
                    converted_value = param_type(value) 
                    setattr(current_params, param_name, converted_value)
                    self.state.set('current_params', current_params)
                    print(f"✅ {param_name} 업데이트: {converted_value}")
            except (ValueError, TypeError, AttributeError) as ex:
                print(f"경고: '{param_name}' 값을 {param_type}으로 변환할 수 없습니다. 오류: {ex}")
        return handler

    def _randomize_seed(self):
        """시드 랜덤화"""
        current_params = self.state.get('current_params')
        current_params.seed = -1
        self.state.set('current_params', current_params)
        if self.seed_input: self.seed_input.update()

    def _handle_model_change(self):
        """모델 타입 변경 처리"""
        if self.model_switch:
            new_model = 'SDXL' if self.model_switch.value else 'SD15'
            self.state.set('sd_model', new_model)
            self._calculate_dimensions()

    def _update_ui_from_state(self, params):
        """상태 변경 시 UI 업데이트"""
        if self.width_input and self.width_input.value != params.width:
            self.width_input.set_value(params.width)
        if self.height_input and self.height_input.value != params.height:
            self.height_input.set_value(params.height)
        if self.steps_input and self.steps_input.value != params.steps:
            self.steps_input.set_value(params.steps)
        if self.cfg_input and self.cfg_input.value != params.cfg_scale:
            self.cfg_input.set_value(params.cfg_scale)
        if self.seed_input and self.seed_input.value != params.seed:
            self.seed_input.set_value(params.seed)
        if self.sampler_select and self.sampler_select.value != params.sampler:
            self.sampler_select.set_value(params.sampler)
        if self.scheduler_select and self.scheduler_select.value != params.scheduler:
            self.scheduler_select.set_value(params.scheduler)

    def _on_state_restored(self, data):
        """메타데이터에서 파라미터가 복원될 때 호출"""
        params = data.get('params')
        if params:
            self._update_ui_from_state(params)

    @ui.refreshable
    def ratio_buttons_container(self):
        """비율 버튼 컨테이너 (새로고침 가능)"""
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
        """컴포넌트 렌더링"""
        self._calculate_dimensions()
        comfyui_samplers = ["euler", "euler_a", "dpmpp_2m", "dpmpp_sde_gpu", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde_gpu"]
        comfyui_schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        current_params = self.state.get('current_params')

        with ui.column().classes('w-full gap-3'):
            ui.label('생성 설정').classes('text-lg font-bold text-yellow-400')
            
            # 샘플러와 스케줄러
            with ui.column().classes('gap-2'):
                self.sampler_select = ui.select(options=comfyui_samplers, label='Sampler', value=current_params.sampler) \
                    .on('update:model-value', self._on_param_change('sampler', str))
                
                self.scheduler_select = ui.select(options=comfyui_schedulers, label='Scheduler', value=current_params.scheduler) \
                    .on('update:model-value', self._on_param_change('scheduler', str))
            
            # Steps와 CFG Scale
            self.steps_input = ui.number(label='Steps', value=current_params.steps, min=1, max=150) \
                .on('update:model-value', self._on_param_change('steps', int))
            
            self.cfg_input = ui.number(label='CFG Scale', value=current_params.cfg_scale, min=1.0, max=30.0, step=0.5) \
                .on('update:model-value', self._on_param_change('cfg_scale', float))
            
            # 이미지 크기
            with ui.row().classes('gap-2'):
                self.width_input = ui.number(value=current_params.width, label='너비', min=128, max=2048, step=8) \
                    .on('update:model-value', self._on_param_change('width', int))
                
                self.height_input = ui.number(value=current_params.height, label='높이', min=128, max=2048, step=8) \
                    .on('update:model-value', self._on_param_change('height', int))
            
            # 모델 타입 스위치
            with ui.row().classes('w-full flex-center items-center gap-2'):
                self.model_switch = ui.switch(value=(self.state.get('sd_model') == 'SDXL')).props('color=orange') \
                    .on('click', self._handle_model_change)
                ui.label('SDXL').classes('text-xs text-gray-400')

            # 비율 버튼들
            self.ratio_buttons_container()
            
            # 배치 설정
            with ui.row().classes('w-full gap-2 mt-4'):
                self.batch_size_input = ui.number(label="배치 사이즈", min=1, max=32, value=current_params.batch_size) \
                    .on('update:model-value', self._on_param_change('batch_size', int))
            
                self.iterations_input = ui.number(label="반복 횟수", min=1, max=100, value=current_params.iterations) \
                    .on('update:model-value', self._on_param_change('iterations', int))

            # 시드 설정
            with ui.row().classes('gap-2 items-center w-full'):
                self.seed_input = ui.number(label='Seed', value=current_params.seed, min=-1) \
                    .on('update:model-value', self._on_param_change('seed', int))
                
                ui.button(icon='casino', on_click=self._randomize_seed)

            # 생성 버튼
            self.generate_button = ui.button('생성', on_click=self._on_generate_click) \
                .props('size=lg color=blue').classes('w-full mt-4')
            
            # MetadataPanel 로부터 파라미터를 받기 위한 구독
            self.state.subscribe('apply_params_from_metadata', self._on_params_received)
            # 히스토리 등 다른 곳에서 상태가 복원될 때 UI를 업데이트 하기 위한 구독
            self.state.subscribe('state_restored', self._on_state_restored)

    def _on_params_received(self, params: dict):
        """MetadataPanel로부터 받은 파라미터를 UI와 상태에 적용합니다."""
        if not params: return

        current_params = self.state.get('current_params')
        
        # 받은 파라미터로 상태 업데이트
        for key, value in params.items():
            if hasattr(current_params, key):
                try:
                    # 데이터 타입에 맞게 변환
                    param_type = type(getattr(current_params, key))
                    setattr(current_params, key, param_type(value))
                except (ValueError, TypeError):
                    print(f"경고: 메타데이터 값 '{value}'를 '{key}'에 적용 실패")

        # UI 업데이트는 아래 set 호출에 의해 자동으로 처리됨
        self.state.set('current_params', current_params)
        ui.notify('파라미터가 적용되었습니다.', type='positive')