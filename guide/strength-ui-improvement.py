# parameter_panel.py의 i2i 컨트롤 부분 개선

async def render_i2i_controls(self):
    """i2i 모드 전용 컨트롤 렌더링 (개선된 버전)"""
    current_mode = self.state.get('current_mode', 'txt2img')
    
    if current_mode in ['img2img', 'inpaint', 'upscale']:
        with ui.card().classes('w-full bg-gray-800 p-3 mt-2'):
            ui.label('🎨 Image to Image 설정').classes('text-lg font-bold mb-3')
            
            # Denoising Strength
            current_params = self.state.get('current_params')
            strength_value = getattr(current_params, 'strength', 0.8)
            
            with ui.column().classes('w-full gap-2'):
                # 슬라이더와 값 표시
                with ui.row().classes('w-full items-center gap-2'):
                    ui.label('Denoising Strength:').classes('text-sm font-medium')
                    ui.label(f'{strength_value:.2f}').classes(
                        'text-sm font-bold px-2 py-1 bg-blue-600 rounded min-w-[50px] text-center'
                    )
                
                # 슬라이더
                self.strength_slider = ui.slider(
                    min=0.0, 
                    max=1.0, 
                    step=0.05,
                    value=strength_value
                ).props('label-always color=blue').on(
                    'update:model-value', 
                    self._on_strength_change
                ).classes('w-full')
                
                # 실제 적용될 스텝 수 표시
                steps = getattr(current_params, 'steps', 20)
                actual_steps = int(steps * strength_value)
                
                with ui.row().classes('w-full text-xs text-gray-400 mt-1'):
                    ui.label(f'실제 디노이징 스텝: {actual_steps}/{steps}')
                    ui.label('•').classes('mx-2')
                    ui.label(f'건너뛸 스텝: {steps - actual_steps}')
                
                # 프리셋 버튼들
                ui.label('빠른 설정:').classes('text-sm mt-2')
                with ui.row().classes('w-full gap-2'):
                    ui.button('0.3', on_click=lambda: self._set_strength(0.3)) \
                        .props('size=sm outline').tooltip('약한 변경 (원본 70% 유지)')
                    ui.button('0.5', on_click=lambda: self._set_strength(0.5)) \
                        .props('size=sm outline').tooltip('중간 변경 (반반)')
                    ui.button('0.7', on_click=lambda: self._set_strength(0.7)) \
                        .props('size=sm outline').tooltip('강한 변경 (원본 30% 유지)')
                    ui.button('1.0', on_click=lambda: self._set_strength(1.0)) \
                        .props('size=sm outline').tooltip('완전 재생성')
                
                # 설명
                with ui.expansion('Denoising Strength란?', icon='info').classes('w-full mt-2'):
                    ui.markdown('''
                    **Denoising Strength**는 원본 이미지를 얼마나 변경할지 결정합니다:
                    
                    - **0.0**: 원본 그대로 (변경 없음)
                    - **0.3**: 약간의 변경 (색상, 조명 조정)
                    - **0.5**: 중간 변경 (구조는 유지, 스타일 변경)
                    - **0.7**: 많은 변경 (전체적인 재해석)
                    - **1.0**: 완전 재생성 (프롬프트만 따름)
                    
                    💡 **팁**: 처음에는 0.5로 시작해서 조정하세요!
                    ''').classes('text-xs')
            
            # 이미지 정보
            init_image = self.state.get('init_image')
            if init_image:
                with ui.card().classes('w-full bg-blue-900 bg-opacity-30 p-2 mt-2'):
                    ui.label('📷 업로드된 이미지').classes('text-sm font-medium mb-1')
                    with ui.row().classes('w-full text-xs gap-4'):
                        if hasattr(init_image, 'size'):
                            ui.label(f'크기: {init_image.size[0]}×{init_image.size[1]}')
                        if hasattr(init_image, 'mode'):
                            ui.label(f'모드: {init_image.mode}')

async def _on_strength_change(self, e):
    """Strength 변경 처리"""
    new_value = e.args
    self.state.update_param('strength', float(new_value))
    
    # UI 업데이트
    current_params = self.state.get('current_params')
    steps = getattr(current_params, 'steps', 20)
    actual_steps = int(steps * new_value)
    
    # 실시간 피드백
    ui.notify(
        f'Denoising: {actual_steps} 스텝 실행 예정', 
        type='info',
        timeout=1000
    )

async def _set_strength(self, value: float):
    """Strength 프리셋 설정"""
    self.strength_slider.value = value
    self.state.update_param('strength', value)
    
    # 피드백
    descriptions = {
        0.3: "약한 변경 모드",
        0.5: "중간 변경 모드",
        0.7: "강한 변경 모드",
        1.0: "완전 재생성 모드"
    }
    ui.notify(
        f'{descriptions.get(value, "커스텀")} 설정됨', 
        type='positive',
        timeout=2000
    )