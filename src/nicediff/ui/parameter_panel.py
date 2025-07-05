# parameter_panel.py (생성 기능 완성본)

from nicegui import ui
import math
from src.nicediff.core.state_manager import StateManager, GenerationParams

class ParameterPanel:
    """파라미터 패널"""
    
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
        
        if hasattr(self, 'refresh_image_dimensions'):
            self.refresh_image_dimensions.refresh()

    @ui.refreshable
    async def refresh_image_dimensions(self):
        current_params: GenerationParams = self.state.get('current_params')
        with ui.row().classes('gap-2'):
            ui.label('Width').classes('text-xs')
            ui.number(value=current_params.width).props('dark outlined dense').classes('bg-gray-700 w-20').bind_value(current_params, 'width')
            ui.label('Height').classes('text-xs')
            ui.number(value=current_params.height).props('dark outlined dense').classes('bg-gray-700 w-20').bind_value(current_params, 'height')

    def _handle_ratio_click(self, dp_name, r_value, orient):
        self._is_ratio_inverted = not self._is_ratio_inverted if self.selected_display_name == dp_name and orient != 'square' else False
        self.selected_display_name = dp_name
        self.selected_ratio_value = r_value
        self.selected_base_orientation = orient
        self._calculate_dimensions()
        self.ratio_buttons_container.refresh()

    @ui.refreshable
    def ratio_buttons_container(self):
        with ui.row().classes('w-full flex-wrap justify-center gap-1'):
            sorted_ratios_data = sorted(self.ratios_data, key=lambda item: item[1])
            for display_name, ratio_value, tooltip_text, orientation in sorted_ratios_data:
                is_selected = (self.selected_display_name == display_name and not self._is_ratio_inverted)
                button_text = display_name
                if is_selected and self._is_ratio_inverted and orientation != 'square':
                    if ":" in display_name:
                        parts = display_name.split(':')
                        if len(parts) == 2: button_text = f"{parts[1]}:{parts[0]}"
                
                btn_props = f'sm {"color=orange" if is_selected else "outline color=orange"}'
                ui.button(button_text, on_click=lambda dp=display_name, rv=ratio_value, o=orientation: self._handle_ratio_click(dp, rv, o)).props(btn_props).tooltip(tooltip_text)

    async def _on_generate_click(self):
        """생성 버튼 클릭 처리 (핵심 로직)"""
        print("🎯 생성 버튼 클릭됨!")
        
        # 1. 모델 로드 상태 확인
        current_model = self.state.get('current_model')
        if not current_model:
            ui.notify('⚠️ 모델이 선택되지 않음', type='warning')
            print("❌ 모델이 선택되지 않음")
            return        

        # 2. 파이프라인 로드 상태 확인
        if not self.state.pipeline:
            ui.notify('⚠️ 파이프라인이 로드되지 않음', type='warning')
            print("❌ 파이프라인이 로드되지 않음")
            return
        
        # 3. 프롬프트 확인
        params = self.state.get('current_params')
        if not params.prompt.strip():
            ui.notify('프롬프트가 비어있음', type='warning')
            print("❌ 프롬프트가 비어있음")
            return
        
        # 4. 이미 생성 중인지 확인
        if self.state.get('is_generating'):
            ui.notify('이미 생성 중', type='info')
            print("⚠️ 이미 생성 중")
            return
        
        print(f"🚀 생성 시작: {params.prompt[:50]}...")
        
        # 버튼 상태를 즉시 변경
        self._on_generate_status_change(True)
        
        # 5. 생성 실행
        try:
            success = await self.state.generate_image()
            if success:
                ui.notify('이미지 생성이 완료되었습니다!', type='success')
                print("✅ 이미지 생성 완료")
            else:
                ui.notify('이미지 생성에 실패했습니다', type='negative')
                print("❌ 이미지 생성 실패")
        except Exception as e:
            print(f"❌ 생성 중 오류: {e}")
            import traceback
            traceback.print_exc()
            ui.notify(f'생성 오류: {str(e)}', type='negative')
        finally:
            # 버튼 상태를 원래대로 복원
            self._on_generate_status_change(False)
    
    def _on_generate_status_change(self, is_generating: bool):
        """생성 상태 변경 시 버튼 업데이트"""
        if hasattr(self, 'generate_button'):
            if is_generating:
                self.generate_button.props('loading color=orange')
                self.generate_button.set_text('생성 중...')
            else:
                self.generate_button.props('color=blue')
                self.generate_button.set_text('생성')

    @ui.refreshable
    async def render(self):
        self._calculate_dimensions()
        comfyui_samplers = ["euler", "dpmpp_2m", "dpmpp_sde_gpu", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde_gpu"]
        comfyui_schedulers = ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]
        current_params = self.state.get('current_params')

        with ui.column().classes('w-full gap-3'):
            ui.label('생성 설정').classes('text-lg font-bold text-yellow-400')
            
            with ui.column().classes('gap-2'):
                ui.select(options=comfyui_samplers, label='Sampler', value=current_params.sampler).props('dark outlined dense').classes('bg-gray-700').bind_value(current_params, 'sampler')
                ui.select(options=comfyui_schedulers, label='Scheduler', value=current_params.scheduler).props('dark outlined dense').classes('bg-gray-700').bind_value(current_params, 'scheduler')
            
            ui.number(label='Steps', value=current_params.steps, min=1, max=150).props('dark outlined dense').classes('bg-gray-700').bind_value(current_params, 'steps')
            ui.number(label='CFG Scale', value=current_params.cfg_scale, min=1.0, max=30.0, step=0.5).props('dark outlined dense').classes('bg-gray-700').bind_value(current_params, 'cfg_scale')
            
            await self.refresh_image_dimensions()
            
            with ui.row().classes('w-full flex-center items-center gap-2'):
                model_switch = ui.switch(value=False).props('color=orange')
                ui.label('SDXL').classes('text-xs text-gray-400')

                def handle_model_change():
                    new_model = 'SDXL' if model_switch.value else 'SD15'
                    self.state.set('sd_model', new_model)
                    self._calculate_dimensions()

                model_switch.on('update:model-value', handle_model_change)

            self.ratio_buttons_container()
            
            with ui.row().classes('gap-2 items-center w-full'):
                ui.number(label='Seed', value=current_params.seed, min=-1).props('dark outlined dense').classes('bg-gray-700 flex-grow').bind_value(current_params, 'seed')
                ui.button(icon='casino', on_click=lambda: hasattr(current_params, 'randomize_seed') and current_params.randomize_seed()).props('sm round color=blue')

            # 생성 버튼에 기능 연결
            self.generate_button = ui.button(
                '생성', 
                on_click=self._on_generate_click
            ).props('size=lg color=blue').classes('w-full mt-4')
            
            # 생성 상태 변경 이벤트 구독
            self.state.subscribe('is_generating_changed', self._on_generate_status_change)
            self.state.subscribe('generation_started', lambda _: self._on_generate_status_change(True))
            self.state.subscribe('image_generated', lambda _: self._on_generate_status_change(False))
            self.state.subscribe('generation_failed', lambda _: self._on_generate_status_change(False))