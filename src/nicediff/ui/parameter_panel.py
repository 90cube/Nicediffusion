# 파일 경로: src/nicediff/ui/parameter_panel.py

from nicegui import ui
import math
import asyncio
from ..core.state_manager import StateManager, GenerationParams
from ..utils.image_filters import get_available_filters, apply_filter

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
        self.img2img_switch = None  # i2i 모드 스위치
        self.strength_slider = None  # Strength(Denoise) 슬라이더
        self.size_match_toggle = None  # 크기 일치 토글
        self.clip_skip_input = None
        
        # 필터 관련 UI 요소들
        self.filter_select = None
        self.filter_strength_slider = None
        self.apply_filter_button = None
        
        # 시드 고정 상태
        self.seed_pinned = False
        
        # 이벤트 구독 (한 번만 등록)
        self._setup_event_subscriptions()
    
    def _setup_event_subscriptions(self):
        """이벤트 구독 설정 (중복 방지)"""
        # StateManager의 params_updated 이벤트 구독 (UI 동기화용)
        self.state.subscribe('params_updated', self._on_params_updated)
        # 히스토리 등 다른 곳에서 상태가 복원될 때 UI를 업데이트 하기 위한 구독
        self.state.subscribe('state_restored', self._on_state_restored)
        # 메타데이터 파라미터 적용 이벤트 구독 (오직 '파라미터 적용' 버튼 클릭 시에만)
        self.state.subscribe('metadata_params_apply', self._on_metadata_params_apply)
        # 모드 변경 이벤트 구독 (Denoise 슬라이더 표시/숨김용)
        self.state.subscribe('mode_changed', self._on_mode_changed)
        # 생성 상태 변경 이벤트 구독
        self.state.subscribe('generation_started', lambda data: self._on_generate_status_change(True))
        self.state.subscribe('generation_finished', lambda data: self._on_generate_status_change(False))

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
        """선택된 비율과 모델에 따라 이미지 크기 계산 (비율 버튼 클릭 시에만 사용)"""
        current_sd_model = self.state.get('sd_model', 'SD15') 
        base_ratio_value = self.selected_ratio_value
        
        if self._is_ratio_inverted and self.selected_base_orientation != 'square':
            ratio_to_calculate = 1 / base_ratio_value
        else:
            ratio_to_calculate = base_ratio_value
        
        # SD15 최적화된 크기 설정 - 사용자 설정 종횡비 우선 적용
        if current_sd_model == 'SD15':
            # 사용자가 선택한 종횡비를 우선적으로 적용
            # 1:1 (square) at 512x512
            if abs(ratio_to_calculate - 1.0) < 0.01:  # 1:1 정사각형
                width = height = 512
            elif ratio_to_calculate > 1.0:  # 가로가 긴 경우 (landscape)
                # 가로 기준으로 크기 설정 (더 자연스러운 landscape)
                width = 768
                height = int(width / ratio_to_calculate)
                # 8의 배수로 조정
                height = height - (height % 8)
                # 최소 크기 보장
                if height < 512:
                    height = 512
                    width = int(height * ratio_to_calculate)
                    width = width - (width % 8)
            else:  # 세로가 긴 경우 (portrait)
                # 세로 기준으로 크기 설정 (더 자연스러운 portrait)
                height = 768
                width = int(height * ratio_to_calculate)
                # 8의 배수로 조정
                width = width - (width % 8)
                # 최소 크기 보장
                if width < 512:
                    width = 512
                    height = int(width / ratio_to_calculate)
                    height = height - (height % 8)
            
        else:  # SDXL
            # SDXL: 종횡비 미리 설정값 우선 적용 (실전에서 사용되는 다양한 해상도 허용)
            # 1:1 (square) at 1024x1024
            if abs(ratio_to_calculate - 1.0) < 0.01:  # 1:1 정사각형
                width = height = 1024
            elif ratio_to_calculate > 1.0:  # 가로가 긴 경우 (landscape)
                # 가로 기준으로 크기 설정 (더 자연스러운 landscape)
                width = 1024
                height = int(width / ratio_to_calculate)
                # 8의 배수로 조정
                height = height - (height % 8)
                # 최소 크기 보장 (실전에서 사용되는 768, 832 등 허용)
                if height < 768:
                    height = 768
                    width = int(height * ratio_to_calculate)
                    width = width - (width % 8)
            else:  # 세로가 긴 경우 (portrait)
                # 세로 기준으로 크기 설정 (더 자연스러운 portrait)
                height = 1024
                width = int(height * ratio_to_calculate)
                # 8의 배수로 조정
                width = width - (width % 8)
                # 최소 크기 보장 (실전에서 사용되는 768, 832 등 허용)
                if width < 768:
                    width = 768
                    height = int(width / ratio_to_calculate)
                    height = height - (height % 8)

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
        print(f"🔄 생성 버튼 클릭됨")
        current_mode = self.state.get('current_mode', 'txt2img')
        print(f"🔍 현재 모드: {current_mode}")
        
        # txt2img 모드에서 시드 고정이 해제되어 있으면 시드 랜덤화
        if current_mode == 'txt2img' and not self.seed_pinned:
            print(f"🎲 시드 고정이 해제되어 있음 - 시드 랜덤화 실행")
            self._randomize_seed()
        
        # 규칙 5: img2img 모드에서 이미지가 업로드되지 않았을 때 생성 시도하지 않음
        if current_mode in ['img2img', 'inpaint', 'upscale']:
            print(f"🔄 img2img 모드 감지: 이미지 업로드 확인 중...")
            
            # StateManager에서 이미지 확인
            init_image = self.state.get('init_image')
            print(f"🔍 StateManager.get('init_image') 결과: {init_image}")
            
            if init_image is None:
                print(f"❌ img2img 모드에서 init_image가 None - 생성 중단")
                ui.notify('img2img 모드에서는 이미지를 먼저 업로드해주세요', type='warning')
                return
            else:
                # numpy 배열인 경우 shape 정보 출력, PIL Image인 경우 size와 mode 정보 출력
                if hasattr(init_image, 'shape'):
                    print(f"✅ img2img 모드에서 이미지 확인됨: 크기={init_image.shape[1]}×{init_image.shape[0]}, 타입={type(init_image)}")
                elif hasattr(init_image, 'size'):
                    print(f"✅ img2img 모드에서 이미지 확인됨: 크기={init_image.size}, 모드={init_image.mode}, 타입={type(init_image)}")
                else:
                    print(f"✅ img2img 모드에서 이미지 확인됨: 타입={type(init_image)}")
                
                # 추가 디버그: 이미지 경로도 확인
                init_image_path = self.state.get('init_image_path')
                init_image_name = self.state.get('init_image_name')
                print(f"🔍 추가 이미지 정보: 경로={init_image_path}, 이름={init_image_name}")
        else:
            print(f"✅ txt2img 모드: 이미지 업로드 불필요")
        
        print(f"🔄 이미지 생성 시작...")
        await self.state.generate_image()
        print(f"✅ 이미지 생성 요청 완료")

    def _on_param_change(self, param_name: str, param_type: type):
        """파라미터 변경 핸들러 팩토리 (StateManager 메서드 호출)"""
        def handler(e):
            try:
                # NiceGUI의 select 컴포넌트는 e.value로 값을 전달합니다
                if hasattr(e, 'value'):
                    value = e.value
                elif hasattr(e, 'args') and e.args:
                    value = e.args[0] if isinstance(e.args, (list, tuple)) else e.args
                else:
                    print(f"경고: '{param_name}' 이벤트에서 값을 찾을 수 없습니다.")
                    return
                
                if value is not None:
                    converted_value = param_type(value) 
                    # StateManager 메서드 호출로 변경
                    self.state.update_param(param_name, converted_value)
            except (ValueError, TypeError, AttributeError) as ex:
                print(f"경고: '{param_name}' 값을 {param_type}으로 변환할 수 없습니다. 오류: {ex}")
        return handler

    def _randomize_seed(self):
        """시드 랜덤화"""
        import random
        new_seed = random.randint(1, 2147483647)
        self.state.update_param('seed', new_seed)
        if self.seed_input:
            self.seed_input.value = new_seed

    def _toggle_seed_pin(self):
        """시드 고정 토글"""
        self.seed_pinned = not self.seed_pinned
        if hasattr(self, 'seed_pin_button'):
            # 아이콘 변경: 고정됨 = push_pin, 고정 해제됨 = push_pin_outlined
            icon_name = 'push_pin' if self.seed_pinned else 'push_pin_outlined'
            self.seed_pin_button.props(f'icon={icon_name}')
            
            # 클래스 변경
            self.seed_pin_button.classes(
                f'{"bg-blue-600 text-white" if self.seed_pinned else "text-gray-400 hover:text-white"}'
            )
            
            # 툴팁 변경
            self.seed_pin_button.tooltip('시드 고정' if not self.seed_pinned else '시드 고정 해제')
        print(f"🔒 시드 고정: {'활성화' if self.seed_pinned else '비활성화'}")

    def _handle_model_change(self):
        """모델 타입 변경 처리"""
        if self.model_switch:
            new_model = 'SDXL' if self.model_switch.value else 'SD15'
            self.state.set('sd_model', new_model)
            
            # img2img 모드에서는 기존 이미지 크기 유지, txt2img 모드에서만 기본 크기 적용
            current_mode = self.state.get('current_mode', 'txt2img')
            if current_mode == 'img2img':
                # img2img 모드: 기존 이미지 크기 유지
                init_image = self.state.get('init_image')
                if init_image is not None:
                    # numpy 배열인 경우 shape에서 크기 추출, PIL Image인 경우 size에서 추출
                    if hasattr(init_image, 'shape'):
                        height, width = init_image.shape[:2]
                    elif hasattr(init_image, 'size'):
                        width, height = init_image.size
                    else:
                        # 기본 크기 사용
                        width, height = 512, 512
                    
                    self.state.update_param('width', width)
                    self.state.update_param('height', height)
                    print(f"✅ img2img 모드: 기존 이미지 크기 유지 {width}×{height}")
                else:
                    # 이미지가 없으면 기본 크기 적용
                    self._calculate_dimensions()
            else:
                # txt2img 모드: 기본 크기 적용
                self._calculate_dimensions()

    def _handle_infinite_generation_change(self):
        """무한 반복 생성 토글 처리"""
        if self.infinite_generation_switch:
            is_enabled = self.infinite_generation_switch.value
            self.state.set('infinite_generation', is_enabled)
            print(f"🔄 무한 반복 생성: {'활성화' if is_enabled else '비활성화'}")
    
    def _handle_size_match_toggle(self):
        """크기 일치 토글 처리"""
        if self.size_match_toggle:
            is_enabled = self.size_match_toggle.value
            self.state.update_param('size_match_enabled', is_enabled)
            print(f"🔄 크기 일치 토글: {'활성화' if is_enabled else '비활성화'}")
            
            # 크기 일치가 활성화되면 업로드된 이미지 크기로 파라미터 업데이트
            if is_enabled:
                init_image = self.state.get('init_image')
                if init_image is not None:
                    # numpy 배열인 경우 shape에서 크기 추출, PIL Image인 경우 size에서 추출
                    if hasattr(init_image, 'shape'):
                        height, width = init_image.shape[:2]
                    elif hasattr(init_image, 'size'):
                        width, height = init_image.size
                    else:
                        # 기본 크기 사용
                        width, height = 512, 512
                    
                    self.state.update_param('width', width)
                    self.state.update_param('height', height)
                    print(f"✅ 업로드된 이미지 크기로 파라미터 업데이트: {width}×{height}")
                    ui.notify(f'파라미터가 업로드된 이미지 크기로 설정되었습니다: {width}×{height}', type='positive')

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
    
    def _on_param_changed(self, data):
        """파라미터 변경 이벤트 핸들러"""
        param_name = data.get('param')
        value = data.get('value')
        if param_name and hasattr(self, f'{param_name}_input'):
            input_widget = getattr(self, f'{param_name}_input')
            if input_widget and input_widget.value != value:
                input_widget.set_value(value)
    
    def _on_generation_failed(self, data):
        """생성 실패 이벤트 핸들러"""
        error_msg = data.get('error', '알 수 없는 오류')
        print(f"❌ 생성 실패: {error_msg}")
        # UI에서 에러 상태 표시 (예: 버튼 색상 변경 등)
        if self.generate_button:
            self.generate_button.props('color=red').set_text('생성 실패')

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

    @ui.refreshable
    async def render(self):
        """컴포넌트 렌더링 (새로고침 가능)"""
        comfyui_samplers = ["euler", "euler_a", "dpmpp_2m", "dpmpp_sde_gpu", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde_gpu"]
        comfyui_schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        current_params = self.state.get('current_params')

        with ui.column().classes('w-full gap-2 min-w-0 overflow-hidden'):
            # 헤더: 제목과 리프레시 버튼
            with ui.row().classes('w-full items-center justify-between min-w-0'):
                ui.label('생성 설정').classes('text-lg font-bold text-yellow-400')
                
                # 리프레시 버튼
                ui.button(
                    icon='refresh',
                    on_click=self._refresh_parameter_panel
                ).props('round color=white text-color=black size=sm').tooltip('파라미터 패널 새로고침')
            
            # 모드 선택 버튼들 (헤더 아래에 작은 크기로 배치)
            with ui.row().classes('w-full justify-center gap-1 mb-3 min-w-0'):
                current_mode = self.state.get('current_mode', 'txt2img')
                modes = [
                    ('txt2img', 'TXT', 'text_fields'),
                    ('img2img', 'IMG', 'image'),
                    ('inpaint', 'INP', 'auto_fix_normal'),
                    ('upscale', 'UPS', 'zoom_in')
                ]
                
                for mode, short_name, icon in modes:
                    is_active = current_mode == mode
                    ui.button(
                        icon=icon,
                        on_click=lambda e, m=mode: asyncio.create_task(self._on_mode_button_click(m))
                    ).props('flat round').classes(
                        f'text-xs {"bg-blue-600 text-white" if is_active else "text-gray-400 hover:text-white"}'
                    ).tooltip(mode.upper())
            


            # txt2img 모드 전용 파라미터 배치
            current_mode = self.state.get('current_mode', 'txt2img')
            if current_mode == 'txt2img':
                # 샘플러 | 스케줄러
                with ui.row().classes('w-full gap-1 min-w-0'):
                    self.sampler_select = ui.select(options=comfyui_samplers, label='Sampler', value=current_params.sampler) \
                        .on('update:model-value', self._on_param_change('sampler', str)).classes('flex-1 min-w-0')
                    
                    self.scheduler_select = ui.select(options=comfyui_schedulers, label='Scheduler', value=current_params.scheduler) \
                        .on('update:model-value', self._on_param_change('scheduler', str)).classes('flex-1 min-w-0')
                
                # CFG | Steps
                with ui.row().classes('w-full gap-1 min-w-0'):
                    self.cfg_input = ui.number(label='CFG', value=current_params.cfg_scale, min=1.0, max=30.0, step=0.5) \
                        .on('update:model-value', self._on_param_change('cfg_scale', float)).classes('flex-1 min-w-0')
                    
                    self.steps_input = ui.number(label='Steps', value=current_params.steps, min=1, max=150) \
                        .on('update:model-value', self._on_param_change('steps', int)).classes('flex-1 min-w-0')
                
                # 너비 | 높이 SDXL 토글
                current_sd_model = self.state.get('sd_model', 'SD15')
                min_size = 512 if current_sd_model == 'SD15' else 768
                
                with ui.row().classes('w-full gap-1 min-w-0'):
                    self.width_input = ui.number(value=current_params.width, label='너비', min=min_size, max=2048, step=8) \
                        .on('update:model-value', self._on_param_change('width', int)).classes('flex-1 min-w-0')
                    
                    self.height_input = ui.number(value=current_params.height, label='높이', min=min_size, max=2048, step=8) \
                        .on('update:model-value', self._on_param_change('height', int)).classes('flex-1 min-w-0')
                
                # SDXL 토글
                with ui.row().classes('w-full justify-center items-center gap-2 min-w-0'):
                    self.model_switch = ui.switch(value=(self.state.get('sd_model') == 'SDXL')).props('color=orange') \
                        .on('click', self._handle_model_change)
                    ui.label('SDXL').classes('text-xs text-gray-400')

                # 종횡비 셋팅 (그대로 유지)
                self.ratio_buttons_container()
                
                # SEED 설정 (기본 랜덤, 시드 고정 버튼)
                with ui.row().classes('w-full gap-1 items-center min-w-0'):
                    self.seed_input = ui.number(label='Seed', value=current_params.seed, min=-1) \
                        .on('update:model-value', self._on_param_change('seed', int)).classes('flex-1 min-w-0')
                    
                    # 시드 고정 버튼 (핀 모양 아이콘) - 고정 크기로 설정
                    icon_name = 'push_pin' if self.seed_pinned else 'push_pin_outlined'
                    self.seed_pin_button = ui.button(
                        icon=icon_name,
                        on_click=lambda e: self._toggle_seed_pin()
                    ).props('flat round size=sm').classes(
                        f'self-center min-w-[32px] min-h-[32px] {"bg-blue-600 text-white" if self.seed_pinned else "text-gray-400 hover:text-white"}'
                    ).tooltip('시드 고정' if not self.seed_pinned else '시드 고정 해제')
                
                # CLIP SKIP
                clip_skip_value = getattr(current_params, 'clip_skip', 1)
                self.clip_skip_input = ui.number(label='CLIP Skip', value=clip_skip_value, min=1, max=12, step=1) \
                    .on('update:model-value', self._on_param_change('clip_skip', int)).classes('w-full min-w-0')
                
                # 배치 사이즈 | 반복회수 | 무한 반복 생성 토글
                with ui.row().classes('w-full gap-1 items-center min-w-0'):
                    self.batch_size_input = ui.number(label="배치", min=1, max=32, value=current_params.batch_size) \
                        .on('update:model-value', self._on_param_change('batch_size', int)).classes('flex-1 min-w-0')
                
                    self.iterations_input = ui.number(label="반복", min=1, max=100, value=current_params.iterations) \
                        .on('update:model-value', self._on_param_change('iterations', int)).classes('flex-1 min-w-0')
                
                    # 무한 반복 생성 토글 (무한 아이콘)
                    infinite_generation = self.state.get('infinite_generation', False)
                    self.infinite_generation_switch = ui.switch(value=infinite_generation).props('color=red') \
                        .on('click', self._handle_infinite_generation_change)
                    ui.icon('all_inclusive').classes('text-red-400 text-sm').tooltip('무한 반복 생성')
            
            # img2img 모드 전용 컨트롤들 (기존 유지)
            elif current_mode in ['img2img', 'inpaint', 'upscale']:
                # 이미지 크기 적용 버튼 (i2i 모드일 때만, 비율 아래에 표시)
                init_image = self.state.get('init_image')
                if init_image is not None:
                    with ui.card().classes('w-full bg-blue-900 p-2 mt-2'):
                        with ui.row().classes('w-full justify-between items-center'):
                            ui.label('업로드된 이미지').classes('text-sm font-medium text-blue-300')
                            ui.button(
                                icon='aspect_ratio',
                                on_click=self._apply_image_size_to_params
                            ).props('round color=blue text-color=white size=sm').tooltip('이미지 크기를 파라미터에 적용')
                        
                        with ui.row().classes('w-full justify-between text-xs'):
                            # numpy 배열 처리
                            if hasattr(init_image, 'shape'):
                                # numpy 배열인 경우
                                width, height = init_image.shape[1], init_image.shape[0]
                            else:
                                # PIL Image인 경우
                                width, height = init_image.size[0], init_image.size[1]
                            ui.label(f'크기: {width}×{height}').classes('text-blue-200')
                            ui.label(f'모드: {getattr(init_image, "mode", "N/A")}').classes('text-blue-200')
                        
                        # 현재 파라미터와 비교
                        current_width = getattr(current_params, 'width', 512)
                        current_height = getattr(current_params, 'height', 512)
                        # numpy 배열 비교 문제 해결
                        image_size = init_image.size
                        if isinstance(image_size, (list, tuple)):
                            image_width, image_height = image_size[0], image_size[1]
                        else:
                            # numpy 배열인 경우
                            image_width, image_height = int(image_size[0]), int(image_size[1])
                        
                        if current_width != image_width or current_height != image_height:
                            ui.label('⚠️ 파라미터 크기와 다릅니다').classes('text-xs text-yellow-400')
                        else:
                            ui.label('✅ 파라미터 크기와 일치합니다').classes('text-xs text-green-400')

                # Denoise Strength 슬라이더
                current_params = self.state.get('current_params')
                strength_value = getattr(current_params, 'strength', 0.8)
                size_match_enabled = getattr(current_params, 'size_match_enabled', False)
                
                with ui.column().classes('w-full gap-2 mt-4') as self.denoise_container:
                    ui.label('Denoise Strength').classes('text-sm font-medium text-blue-400')
                    self.strength_slider = ui.slider(
                        min=0.0, 
                        max=1.0, 
                        step=0.01, 
                        value=strength_value
                    ).on('update:model-value', self._on_param_change('strength', float))
                    
                    # Strength 값 표시
                    with ui.row().classes('w-full justify-between text-xs text-gray-400'):
                        ui.label('0.0 (원본 유지)')
                        ui.label(f'{strength_value:.2f}')
                        ui.label('1.0 (완전 새로 생성)')
                    
                    # Strength 설명
                    ui.label('이미지 변형 강도: 낮을수록 원본 유지, 높을수록 새로 생성').classes('text-xs text-gray-500')
                
                # 크기 일치 토글
                with ui.row().classes('w-full items-center gap-2 mt-4'):
                    self.size_match_toggle = ui.switch(value=size_match_enabled).props('color=green') \
                        .on('click', self._handle_size_match_toggle)
                    ui.label('크기 일치').classes('text-sm text-green-400')
                    ui.label('(업로드된 이미지 크기로 생성)').classes('text-xs text-gray-500')
                
                # 이미지 필터 섹션 (I2I 제안서 스타일)
                with ui.column().classes('w-full gap-2 mt-4') as self.filter_container:
                    ui.label('이미지 필터').classes('text-sm font-medium text-purple-400')
                    
                    # 필터 선택
                    available_filters = get_available_filters()
                    filter_options = {filter_name: filter_name.replace('_', ' ').title() for filter_name in available_filters}
                    
                    self.filter_select = ui.select(
                        options=filter_options,
                        label='필터 선택',
                        value=None
                    ).props('outlined')
                    
                    # 필터 강도 슬라이더 (일부 필터에만 적용)
                    ui.label('필터 강도').classes('text-sm font-medium')
                    self.filter_strength_slider = ui.slider(
                        min=0.1,
                        max=3.0,
                        step=0.1,
                        value=1.0
                    ).props('outlined')
                    
                    # 필터 적용 버튼
                    with ui.row().classes('w-full gap-2'):
                        self.apply_filter_button = ui.button(
                            '필터 적용',
                            on_click=self._apply_image_filter
                        ).props('outlined color=purple')
                        
                        ui.button(
                            '필터 초기화',
                            on_click=self._reset_image_filter
                        ).props('outlined color=gray')



            # 생성 버튼
            self.generate_button = ui.button('생성', on_click=self._on_generate_click) \
                .props('size=lg color=blue').classes('w-full mt-4')


    def _on_params_updated(self, data: dict):
        """StateManager에서 파라미터가 업데이트될 때 UI를 업데이트합니다."""
        current_params = self.state.get('current_params')
        
        print(f"🔄 파라미터 UI 업데이트 시작: {list(data.keys())}")
        
        # 각 파라미터별로 UI 업데이트 (더 강력한 방법 사용)
        if 'width' in data and self.width_input:
            try:
                self.width_input.set_value(current_params.width)
                print(f"✅ width UI 업데이트: {current_params.width}")
            except Exception as e:
                print(f"❌ width UI 업데이트 실패: {e}")
                
        if 'height' in data and self.height_input:
            try:
                self.height_input.set_value(current_params.height)
                print(f"✅ height UI 업데이트: {current_params.height}")
            except Exception as e:
                print(f"❌ height UI 업데이트 실패: {e}")
                
        if 'steps' in data and self.steps_input:
            try:
                self.steps_input.set_value(current_params.steps)
                print(f"✅ steps UI 업데이트: {current_params.steps}")
            except Exception as e:
                print(f"❌ steps UI 업데이트 실패: {e}")
                
        if 'cfg_scale' in data and self.cfg_input:
            try:
                self.cfg_input.set_value(current_params.cfg_scale)
                print(f"✅ cfg_scale UI 업데이트: {current_params.cfg_scale}")
            except Exception as e:
                print(f"❌ cfg_scale UI 업데이트 실패: {e}")
                
        if 'seed' in data and self.seed_input:
            try:
                self.seed_input.set_value(current_params.seed)
                print(f"✅ seed UI 업데이트: {current_params.seed}")
            except Exception as e:
                print(f"❌ seed UI 업데이트 실패: {e}")
                
        if 'sampler' in data and self.sampler_select:
            try:
                self.sampler_select.set_value(current_params.sampler)
                print(f"✅ sampler UI 업데이트: {current_params.sampler}")
            except Exception as e:
                print(f"❌ sampler UI 업데이트 실패: {e}")
                
        if 'scheduler' in data and self.scheduler_select:
            try:
                self.scheduler_select.set_value(current_params.scheduler)
                print(f"✅ scheduler UI 업데이트: {current_params.scheduler}")
            except Exception as e:
                print(f"❌ scheduler UI 업데이트 실패: {e}")
                
        if 'clip_skip' in data and self.clip_skip_input:
            try:
                clip_skip_value = getattr(current_params, 'clip_skip', 1)
                self.clip_skip_input.set_value(clip_skip_value)
                print(f"✅ clip_skip UI 업데이트: {clip_skip_value}")
            except Exception as e:
                print(f"❌ clip_skip UI 업데이트 실패: {e}")
        
        print(f"✅ 파라미터 UI 업데이트 완료: {list(data.keys())}")



    def _on_metadata_params_apply(self, params: dict):
        """메타데이터 파라미터 적용 (오직 '파라미터 적용' 버튼 클릭 시에만 호출됨)"""
        if not params: 
            return

        print(f"🔧 메타데이터 파라미터 적용 시작: {list(params.keys())}")

        # 실제 상태에 파라미터 적용
        for key, value in params.items():
            try:
                if key == 'width':
                    self.state.update_param('width', int(value))
                elif key == 'height':
                    self.state.update_param('height', int(value))
                elif key == 'steps':
                    self.state.update_param('steps', int(value))
                elif key == 'cfg_scale':
                    self.state.update_param('cfg_scale', float(value))
                elif key == 'seed':
                    self.state.update_param('seed', int(value))
                elif key == 'sampler':
                    self.state.update_param('sampler', str(value))
                elif key == 'scheduler':
                    self.state.update_param('scheduler', str(value))
                elif key == 'clip_skip':
                    self.state.update_param('clip_skip', int(value))
            except (ValueError, TypeError) as e:
                print(f"경고: 메타데이터 값 '{value}'를 '{key}' 상태에 적용 실패: {e}")

        print(f"✅ 메타데이터 파라미터 적용 완료: {list(params.keys())}")
        ui.notify('메타데이터 파라미터가 파라미터 패널에 적용되었습니다!', type='positive')



    async def _on_mode_changed(self, data):
        """모드 변경 이벤트 핸들러 (Denoise 슬라이더 표시/숨김용)"""
        new_mode = data.get('mode', 'txt2img')
        print(f"🔄 모드 변경 감지: {new_mode} - 파라미터 패널 새로고침")
        
        # 무한 루프 방지를 위해 디바운싱 적용
        if hasattr(self, '_refresh_task') and not self._refresh_task.done():
            return
        
        self._refresh_task = asyncio.create_task(self._refresh_parameter_panel())

    async def _refresh_parameter_panel(self):
        """파라미터 패널 새로고침"""
        print("🔄 파라미터 패널 새로고침 중...")
        
        try:
            # @ui.refreshable로 만든 render 함수를 새로고침
            self.render.refresh()
            print(f"✅ 파라미터 패널 새로고침 완료")
        except Exception as e:
            print(f"❌ 파라미터 패널 새로고침 실패: {e}")
            # 실패 시 알림만 표시
            ui.notify('파라미터 패널 새로고침 중 오류가 발생했습니다', type='warning')
    
    def _apply_image_size_to_params(self):
        """업로드된 이미지의 크기를 파라미터에 적용"""
        try:
            # 현재 업로드된 이미지 가져오기
            init_image = self.state.get('init_image')
            if init_image is None:
                ui.notify('업로드된 이미지가 없습니다', type='warning')
                return
            
            # 이미지 크기 가져오기
            width, height = init_image.size
            
            # StateManager를 통해 파라미터 업데이트
            self.state.update_param('width', width)
            self.state.update_param('height', height)
            
            # 성공 알림
            ui.notify(f'이미지 크기가 파라미터에 적용되었습니다: {width}×{height}', type='positive')
            print(f"✅ 이미지 크기 파라미터 적용: {width}×{height}")
            
        except Exception as e:
            print(f"❌ 이미지 크기 파라미터 적용 실패: {e}")
            ui.notify(f'이미지 크기 적용 실패: {e}', type='negative')
    
    async def _apply_image_filter(self):
        """이미지 필터 적용 (I2I 제안서 스타일)"""
        try:
            # 필터 선택 확인
            if not self.filter_select or not self.filter_select.value:
                ui.notify('필터를 선택해주세요', type='warning')
                return
            
            # 이미지 확인
            init_image = self.state.get('init_image')
            if not init_image:
                ui.notify('적용할 이미지가 없습니다', type='warning')
                return
            
            # 필터 강도 가져오기
            filter_strength = 1.0
            if self.filter_strength_slider:
                filter_strength = self.filter_strength_slider.value
            
            # 필터 적용
            filter_name = self.filter_select.value
            import numpy as np
            img_array = np.array(init_image)
            
            # 필터별 파라미터 설정
            filter_params = {}
            if filter_name in ['brightness', 'contrast']:
                filter_params['factor'] = filter_strength
            elif filter_name == 'blur':
                filter_params['kernel_size'] = int(filter_strength * 5) + 1
            
            # 필터 적용
            filtered_array = apply_filter(filter_name, img_array, **filter_params)
            
            # 결과를 StateManager에 저장
            from PIL import Image
            filtered_image = Image.fromarray(filtered_array)
            self.state.set('init_image', filtered_image)
            
            # ImagePad 업데이트 트리거
            self.state.set('image_filter_applied', True)
            
            ui.notify(f'{filter_name} 필터가 적용되었습니다', type='positive')
            
        except Exception as e:
            print(f"❌ 필터 적용 실패: {e}")
            ui.notify(f'필터 적용 실패: {str(e)}', type='negative')
    
    async def _reset_image_filter(self):
        """이미지 필터 초기화"""
        try:
            # 원본 이미지 경로에서 다시 로드
            init_image_path = self.state.get('init_image_path')
            if init_image_path:
                from PIL import Image
                original_image = Image.open(init_image_path)
                self.state.set('init_image', original_image)
                
                # ImagePad 업데이트 트리거
                self.state.set('image_filter_reset', True)
                
                ui.notify('필터가 초기화되었습니다', type='positive')
            else:
                ui.notify('원본 이미지를 찾을 수 없습니다', type='warning')
                
        except Exception as e:
            print(f"❌ 필터 초기화 실패: {e}")
            ui.notify(f'필터 초기화 실패: {str(e)}', type='negative')

    async def _on_mode_button_click(self, mode: str):
        """모드 선택 버튼 클릭 처리"""
        print(f"🔄 모드 선택: {mode}")
        
        # StateManager에 현재 모드 설정
        self.state.set('current_mode', mode)
        
        # 모드별 기본 설정
        if mode in ['img2img', 'inpaint', 'upscale']:
            # i2i 관련 모드일 때 기본 Strength 값 설정
            current_params = self.state.get('current_params')
            if not hasattr(current_params, 'strength') or current_params.strength is None:
                self.state.update_param('strength', 0.8)  # 기본값 0.8
                print(f"✅ {mode} 모드 기본 Strength 값 설정: 0.8")
        
        # 모드 변경 이벤트 발생
        self.state._notify('mode_changed', {'mode': mode})
        
        # 파라미터 패널 새로고침
        self.render.refresh()
        
        print(f"✅ 모드 변경 완료: {mode}")