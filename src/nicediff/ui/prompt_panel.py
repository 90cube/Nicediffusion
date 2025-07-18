"""
프롬프트 입력 패널
"""

from typing import List
from nicegui import ui
from ..core.state_manager import StateManager
from ..services.preset_manager import PresetManager

class PromptPanel:
    """프롬프트 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.preset_manager = PresetManager()
        self.positive_textarea = None
        self.negative_textarea = None
        self.char_count_positive = None
        self.char_count_negative = None
        self.token_count_positive = None
        self.token_count_negative = None
        
        # 고급 인코딩 설정
        self.use_custom_tokenizer = True
        self.weight_interpretation = "A1111"  # "A1111" 또는 "comfy++"
        
        # 이벤트 구독 설정
        self.state.subscribe('metadata_prompts_apply', self._on_metadata_prompts_apply)
    
    async def render(self):
        """컴포넌트 렌더링 - 탭 방식으로 변경"""
        # 현재 파라미터 가져오기
        current_params = self.state.get('current_params')
        
        with ui.column().classes('w-full gap-1'):
            # 고급 프롬프트 설정 (상단에 추가)
            with ui.expansion('고급 프롬프트 설정', icon='settings').classes('w-full mb-2'):
                with ui.row().classes('w-full gap-4 items-center'):
                    # 커스텀 토크나이저 토글
                    ui.label('커스텀 토크나이저:').classes('min-w-fit text-xs')
                    self.custom_tokenizer_switch = ui.switch(
                        value=self.use_custom_tokenizer,
                        on_change=self._on_tokenizer_change
                    ).props('color=blue size=sm')
                    
                    # 가중치 해석 방식 선택
                    ui.label('가중치 처리:').classes('min-w-fit ml-4 text-xs')
                    self.weight_mode_select = ui.select(
                        options=['A1111', 'comfy++'],
                        value=self.weight_interpretation,
                        on_change=self._on_weight_mode_change
                    ).classes('min-w-32').props('dense')
            
            # 헤더: 제목과 리프레시 버튼
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Prompt').classes('text-sm font-bold text-green-400')
                
                # 리프레시 버튼
                ui.button(
                    icon='refresh',
                    on_click=self._refresh_prompt_panel
                ).props('round color=white text-color=black size=xs').tooltip('프롬프트 패널 새로고침')
            
            # 탭 컨테이너 - 크기 최소화
            with ui.tabs().classes('w-full') as tabs:
                ui.tab('+', icon='add_circle').classes('text-green-400 text-xs').props('dense')
                ui.tab('-', icon='remove_circle').classes('text-pink-400 text-xs').props('dense')
            
            # 탭 패널 컨테이너
            with ui.tab_panels(tabs, value='+').classes('w-full flex-1 min-h-0'):
                # 긍정 프롬프트 탭
                with ui.tab_panel('+').classes('w-full h-full'):
                    with ui.column().classes('w-full h-full gap-1'):
                        # 긍정 프롬프트 헤더
                        with ui.row().classes('items-center justify-between'):
                            ui.label('+').classes('text-green-400 font-bold text-xs')
                            with ui.row().classes('gap-2'):
                                self.char_count_positive = ui.label(f'{len(current_params.prompt)}자').classes('text-xs text-gray-400')
                                self.token_count_positive = ui.label('0 토큰').classes('text-xs text-blue-400')
                        
                        # 긍정 프롬프트 텍스트 영역
                        self.positive_textarea = ui.textarea(
                            placeholder='생성하고 싶은 이미지를 설명하세요...\n예: a beautiful sunset over mountains, highly detailed, 4k'
                        ).props('dark outlined').classes('w-full flex-1 min-h-0').props('rows=4').bind_value(current_params, 'prompt')
                        
                        # 긍정 프롬프트 도우미 버튼들
                        with ui.row().classes('gap-1 flex-wrap'):
                            ui.button(
                                icon='casino',
                                on_click=self._insert_random_prompt
                            ).props('dense flat size=sm').tooltip('랜덤 프롬프트')
                            
                            ui.button(
                                icon='clear',
                                on_click=lambda: self._clear_positive_prompt()
                            ).props('dense flat size=sm').tooltip('지우기')
                            
                            ui.button(
                                'BREAK',
                                on_click=self._add_break_keyword
                            ).props('dense flat size=sm color=orange').tooltip('BREAK 키워드 추가')
                        
                        # 긍정 프롬프트 프리셋 버튼들
                        with ui.row().classes('gap-1 flex-wrap mt-2'):
                            ui.label('프리셋:').classes('text-xs text-gray-400 mr-2')
                            for preset in self.preset_manager.get_positive_presets():
                                ui.button(
                                    preset['name'],
                                    on_click=lambda p=preset: self._add_positive_preset(p)
                                ).props('size=sm color=green outline').tooltip(preset['description'])
                        
                        # 프롬프트 분석 결과 표시 (제거됨 - 팝업으로 대체)
                
                # 부정 프롬프트 탭
                with ui.tab_panel('-').classes('w-full h-full'):
                    with ui.column().classes('w-full h-full gap-1'):
                        # 부정 프롬프트 헤더
                        with ui.row().classes('items-center justify-between'):
                            ui.label('-').classes('text-pink-400 font-bold text-xs')
                            with ui.row().classes('gap-2'):
                                self.char_count_negative = ui.label(f'{len(current_params.negative_prompt)}자').classes('text-xs text-gray-400')
                                self.token_count_negative = ui.label('0 토큰').classes('text-xs text-blue-400')
                        
                        # 부정 프롬프트 텍스트 영역
                        self.negative_textarea = ui.textarea(
                            placeholder='원하지 않는 요소를 입력하세요...\n예: low quality, blurry, bad anatomy'
                        ).props('dark outlined').classes('w-full flex-1 min-h-0').props('rows=4').bind_value(current_params, 'negative_prompt')
                        
                        # 부정 프롬프트 프리셋
                        with ui.row().classes('gap-1 flex-wrap'):
                            ui.label('프리셋:').classes('text-xs text-gray-400 mr-2')
                            for preset in self.preset_manager.get_negative_presets():
                                ui.button(
                                    preset['name'],
                                    on_click=lambda p=preset: self._add_negative_preset(p)
                                ).props('size=sm color=red outline').tooltip(preset['description'])
        
        # 이벤트 바인딩
        self._setup_bindings()
        
        # 프롬프트 업데이트 구독
        self.state.subscribe('prompt_updated', self._on_prompt_updated)
        self.state.subscribe('state_restored', self._on_state_restored)
    
    def _setup_bindings(self):
        """이벤트 바인딩 설정"""
        # 텍스트 변경 시 글자 수 업데이트 및 상태 저장
        if self.positive_textarea:
            self.positive_textarea.on('input', self._on_positive_change)
        if self.negative_textarea:
            self.negative_textarea.on('input', self._on_negative_change)
    
    def _on_positive_change(self, e):
        """긍정 프롬프트 변경 (StateManager 메서드 호출)"""
        text = self.state.get('current_params').prompt
        if self.char_count_positive:
            self.char_count_positive.set_text(f'{len(text)}자')
        
        # 토큰 수 계산 및 표시
        token_count = self.state.calculate_token_count(text)
        if self.token_count_positive:
            self.token_count_positive.set_text(f'{token_count} 토큰')
        
        # 프롬프트 분석 (팝업으로 대체됨)
        
        # StateManager 메서드 호출로 변경
        self.state.update_prompt(text, self.state.get('current_params').negative_prompt)
    
    def _on_negative_change(self, e):
        """부정 프롬프트 변경 (StateManager 메서드 호출)"""
        text = self.state.get('current_params').negative_prompt
        if self.char_count_negative:
            self.char_count_negative.set_text(f'{len(text)}자')
        
        # 토큰 수 계산 및 표시
        token_count = self.state.calculate_token_count(text)
        if self.token_count_negative:
            self.token_count_negative.set_text(f'{token_count} 토큰')
        
        # StateManager 메서드 호출로 변경
        self.state.update_prompt(self.state.get('current_params').prompt, text)
    
    def _clear_positive_prompt(self):
        """긍정 프롬프트 지우기"""
        params = self.state.get('current_params')
        params.prompt = ''
        self.state.set('current_params', params)
        if self.positive_textarea:
            self.positive_textarea.set_value('')
    
    def _insert_random_prompt(self):
        """랜덤 프롬프트 삽입"""
        # 샘플 프롬프트들
        sample_prompts = [
            "a majestic mountain landscape at sunset, dramatic clouds, golden hour lighting, highly detailed, 8k",
            "portrait of a cyberpunk character, neon lights, futuristic city background, detailed face, digital art",
            "magical forest with glowing mushrooms, fireflies, moonlight, fantasy art, ethereal atmosphere",
            "steampunk airship flying over victorian city, brass and copper details, cloudy sky, intricate design",
            "underwater coral reef, colorful fish, sun rays through water, photorealistic, vibrant colors",
        ]
        
        import random
        prompt = random.choice(sample_prompts)
        if self.positive_textarea:
            self.positive_textarea.set_value(prompt)
        self._on_positive_change(type('', (), {'args': prompt})())
        
        ui.notify('랜덤 프롬프트가 적용되었습니다', type='info')
    

    
    def _apply_positive_preset(self, preset: str):
        """긍정 프롬프트 프리셋 적용"""
        current = self.positive_textarea.value if self.positive_textarea else ''
        
        if current:
            # 기존 내용에 추가
            new_text = f"{current}, {preset}"
        else:
            new_text = preset
        
        if self.positive_textarea:
            self.positive_textarea.set_value(new_text)
        self._on_positive_change(type('', (), {'args': new_text})())
        
        ui.notify('프리셋이 적용되었습니다', type='positive')
    
    def _apply_negative_preset(self, preset: str):
        """부정 프롬프트 프리셋 적용"""
        current = self.negative_textarea.value if self.negative_textarea else ''
        
        if current:
            # 기존 내용에 추가
            new_text = f"{current}, {preset}"
        else:
            new_text = preset
        
        if self.negative_textarea:
            self.negative_textarea.set_value(new_text)
        self._on_negative_change(type('', (), {'args': new_text})())
        
        ui.notify('프리셋이 적용되었습니다', type='positive')
    
    def _apply_style_preset(self, style: dict):
        """스타일 프리셋 적용 (긍정/부정 동시)"""
        if 'positive' in style and self.positive_textarea:
            self.positive_textarea.set_value(style['positive'])
            self._on_positive_change(type('', (), {'args': style['positive']})())
        
        if 'negative' in style and self.negative_textarea:
            self.negative_textarea.set_value(style['negative'])
            self._on_negative_change(type('', (), {'args': style['negative']})())
        
        ui.notify('스타일 프리셋이 적용되었습니다', type='positive')
    
    def _add_break_keyword(self):
        """BREAK 키워드 추가"""
        current_text = self.positive_textarea.value if self.positive_textarea else ''
        if current_text:
            # 문장 끝에 BREAK 추가
            new_text = self.state.add_break_keyword(current_text)
            if self.positive_textarea:
                self.positive_textarea.set_value(new_text)
            self._on_positive_change(type('', (), {'args': new_text})())
            ui.notify('BREAK 키워드가 추가되었습니다', type='info')
        else:
            ui.notify('먼저 프롬프트를 입력해주세요', type='warning')
    

    

    

    

    
    # _show_analysis 메서드 제거됨 (팝업으로 대체)
        
    async def _on_prompt_updated(self, prompt_data):
        """외부에서 프롬프트 업데이트"""
        # prompt_data가 딕셔너리인 경우 (StateManager.update_prompt에서 오는 경우)
        if isinstance(prompt_data, dict):
            positive_prompt = prompt_data.get('positive', '')
            negative_prompt = prompt_data.get('negative', '')
            
            # 긍정 프롬프트 업데이트
            if self.positive_textarea and self.positive_textarea.value != positive_prompt:
                self.positive_textarea.set_value(positive_prompt)
                self._on_positive_change(type('', (), {'args': positive_prompt})())
            
            # 부정 프롬프트 업데이트
            if self.negative_textarea and self.negative_textarea.value != negative_prompt:
                self.negative_textarea.set_value(negative_prompt)
                self._on_negative_change(type('', (), {'args': negative_prompt})())
        
        # prompt_data가 문자열인 경우 (기존 호환성)
        elif isinstance(prompt_data, str):
            if self.positive_textarea and self.positive_textarea.value != prompt_data:
                self.positive_textarea.set_value(prompt_data)
                self._on_positive_change(type('', (), {'args': prompt_data})())
        
        # 기타 타입인 경우 문자열로 변환
        else:
            prompt_str = str(prompt_data)
            if self.positive_textarea and self.positive_textarea.value != prompt_str:
                self.positive_textarea.set_value(prompt_str)
                self._on_positive_change(type('', (), {'args': prompt_str})())
    
    async def _on_state_restored(self, data: dict):
        """
        StateManager로부터 상태 복원 이벤트를 받았을 때
        프롬프트 입력 UI를 업데이트합니다.
        """
        params = data.get('params') if data else None
        # if params:
        #     if self.positive_textarea:
        #         self.positive_textarea.set_value(params.prompt)
        #         self._on_positive_change(None)
        #     if self.negative_textarea:
        #         self.negative_textarea.set_value(params.negative_prompt)
        #         self._on_negative_change(None)

    def _on_prompt_changed(self, data):
        """프롬프트 변경 이벤트 핸들러"""
        prompt = data.get('prompt', '')
        negative_prompt = data.get('negative_prompt', '')
        
        # UI 업데이트 (다른 컴포넌트에서 변경된 경우)
        if self.positive_textarea and self.positive_textarea.value != prompt:
            self.positive_textarea.set_value(prompt)
            if self.char_count_positive:
                self.char_count_positive.set_text(f'{len(prompt)}자')
        
        if self.negative_textarea and self.negative_textarea.value != negative_prompt:
            self.negative_textarea.set_value(negative_prompt)
            if self.char_count_negative:
                self.char_count_negative.set_text(f'{len(negative_prompt)}자')

    def _refresh_prompt_panel(self):
        """프롬프트 패널 새로고침"""
        print("🔄 프롬프트 패널 새로고침 중...")
        
        # 현재 파라미터로 UI 업데이트
        current_params = self.state.get('current_params')
        # if hasattr(self, '_update_ui_from_state'):
        #     self._update_ui_from_state(current_params)
        ui.notify('프롬프트 패널이 새로고침되었습니다', type='info')

    def _on_metadata_prompts_apply(self, data):
        """메타데이터 프롬프트 적용 이벤트 핸들러"""
        if self.positive_textarea:
            self.positive_textarea.set_value(data.get('positive_prompt', ''))
            self._on_positive_change(type('', (), {'args': data.get('positive_prompt', '')})())
        if self.negative_textarea:
            self.negative_textarea.set_value(data.get('negative_prompt', ''))
            self._on_negative_change(type('', (), {'args': data.get('negative_prompt', '')})())
    
    def _on_tokenizer_change(self, event):
        """커스텀 토크나이저 설정 변경"""
        self.use_custom_tokenizer = event.args[0]
        self.state.set('use_custom_tokenizer', self.use_custom_tokenizer)
        print(f"✅ 커스텀 토크나이저: {'활성화' if self.use_custom_tokenizer else '비활성화'}")
    
    def _on_weight_mode_change(self, event):
        """가중치 해석 방식 변경"""
        self.weight_interpretation = event.args[0]
        self.state.set('weight_interpretation', self.weight_interpretation)
        print(f"✅ 가중치 처리 방식: {self.weight_interpretation}")
    
    def _add_positive_preset(self, preset):
        """긍정 프롬프트 프리셋 추가"""
        if self.positive_textarea:
            current_prompt = self.positive_textarea.value or ''
            
            if current_prompt and not current_prompt.endswith(', '):
                new_prompt = current_prompt + ', ' + preset['prompt']
            else:
                new_prompt = current_prompt + preset['prompt']
            
            self.positive_textarea.set_value(new_prompt)
            self.state.update_param('prompt', new_prompt)
            
            ui.notify(f"프리셋 '{preset['name']}' 추가됨", type='positive')
    
    def _add_negative_preset(self, preset):
        """부정 프롬프트 프리셋 추가"""
        if self.negative_textarea:
            current_prompt = self.negative_textarea.value or ''
            
            if current_prompt and not current_prompt.endswith(', '):
                new_prompt = current_prompt + ', ' + preset['prompt']
            else:
                new_prompt = current_prompt + preset['prompt']
            
            self.negative_textarea.set_value(new_prompt)
            self.state.update_param('negative_prompt', new_prompt)
            
            ui.notify(f"부정 프리셋 '{preset['name']}' 추가됨", type='positive')