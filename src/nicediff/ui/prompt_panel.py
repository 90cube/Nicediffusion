"""
프롬프트 입력 패널
"""

from nicegui import ui
from ..core.state_manager import StateManager

class PromptPanel:
    """프롬프트 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.positive_textarea = None
        self.negative_textarea = None
        self.char_count_positive = None
        self.char_count_negative = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        # 현재 파라미터 가져오기
        current_params = self.state.get('current_params')
        
        with ui.column().classes('w-full gap-3'):
            # 긍정 프롬프트
            with ui.column().classes('w-full'):
                with ui.row().classes('items-center justify-between mb-1'):
                    ui.label('긍정프롬프트').classes('text-green-400 font-bold')
                    self.char_count_positive = ui.label(f'{len(current_params.prompt)}자').classes('text-xs text-gray-400')
                
                self.positive_textarea = ui.textarea(
                    placeholder='생성하고 싶은 이미지를 설명하세요...\n예: a beautiful sunset over mountains, highly detailed, 4k'
                ).props('dark outlined').classes('w-full bg-gray-800').props('rows=4').bind_value(current_params, 'prompt')
                
                # 프롬프트 도우미 버튼들
                with ui.row().classes('gap-1 mt-1'):
                    ui.button(
                        icon='casino',
                        on_click=self._insert_random_prompt
                    ).props('dense flat size=sm').tooltip('랜덤 프롬프트')
                    
                    ui.button(
                        icon='auto_awesome',
                        on_click=self._improve_prompt
                    ).props('dense flat size=sm').tooltip('프롬프트 개선 (LLM)')
                    
                    ui.button(
                        icon='clear',
                        on_click=lambda: self._clear_positive_prompt()
                    ).props('dense flat size=sm').tooltip('지우기')
            
            # 부정 프롬프트
            with ui.column().classes('w-full'):
                with ui.row().classes('items-center justify-between mb-1'):
                    ui.label('부정프롬프트').classes('text-pink-400 font-bold')
                    self.char_count_negative = ui.label(f'{len(current_params.negative_prompt)}자').classes('text-xs text-gray-400')
                
                self.negative_textarea = ui.textarea(
                    placeholder='원하지 않는 요소를 입력하세요...\n예: low quality, blurry, bad anatomy'
                ).props('dark outlined').classes('w-full bg-gray-800').props('rows=3').bind_value(current_params, 'negative_prompt')
                
                # 부정 프롬프트 프리셋
                with ui.row().classes('gap-1 mt-1 flex-wrap'):
                    presets = [
                        ('일반', 'low quality, worst quality, bad anatomy, bad hands'),
                        ('사실적', 'cartoon, anime, illustration, painting, drawing'),
                        ('일러스트', 'photo, realistic, 3d render, photography'),
                    ]
                    
                    for name, preset in presets:
                        ui.button(
                            name,
                            on_click=lambda p=preset: self._apply_negative_preset(p)
                        ).props('dense flat size=xs')
        
        # 이벤트 바인딩
        self._setup_bindings()
        
        # 프롬프트 업데이트 구독
        self.state.subscribe('prompt_updated', self._on_prompt_updated)
        self.state.subscribe('state_restored', self._on_state_restored)
    
    def _setup_bindings(self):
        """이벤트 바인딩 설정"""
        # 텍스트 변경 시 글자 수 업데이트 및 상태 저장
        self.positive_textarea.on('input', self._on_positive_change)
        self.negative_textarea.on('input', self._on_negative_change)
    
    def _on_positive_change(self, e):
        """긍정 프롬프트 변경"""
        text = self.state.get('current_params').prompt
        self.char_count_positive.set_text(f'{len(text)}자')
        
        # 상태 변경 알림
        self.state._notify('current_params_changed', self.state.get('current_params'))
        print(f"✏️ 프롬프트 업데이트: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    def _on_negative_change(self, e):
        """부정 프롬프트 변경"""
        text = self.state.get('current_params').negative_prompt
        self.char_count_negative.set_text(f'{len(text)}자')
        
        # 상태 변경 알림
        self.state._notify('current_params_changed', self.state.get('current_params'))
        print(f"✏️ 부정 프롬프트 업데이트: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    def _clear_positive_prompt(self):
        """긍정 프롬프트 지우기"""
        params = self.state.get('current_params')
        params.prompt = ''
        self.state.set('current_params', params)
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
        self.positive_textarea.set_value(prompt)
        self._on_positive_change(type('', (), {'args': prompt})())
        
        ui.notify('랜덤 프롬프트가 적용되었습니다', type='info')
    
    async def _improve_prompt(self):
        """LLM으로 프롬프트 개선"""
        current_text = self.positive_textarea.value
        
        if not current_text:
            ui.notify('개선할 프롬프트를 입력해주세요', type='warning')
            return
        
        # LLM 상태 확인
        if not self.state.get('llm', {}).get('enabled'):
            ui.notify('LLM이 비활성화되어 있습니다. 상단의 LLM 버튼을 활성화해주세요.', type='warning')
            return
        
        # TODO: Phase 2에서 실제 LLM 통합
        ui.notify('LLM 프롬프트 개선은 Phase 2에서 구현됩니다', type='info')
    
    def _apply_positive_preset(self, preset: str):
        """긍정 프롬프트 프리셋 적용"""
        current = self.positive_textarea.value
        
        if current:
            # 기존 내용에 추가
            new_text = f"{current}, {preset}"
        else:
            new_text = preset
        
        self.positive_textarea.set_value(new_text)
        self._on_positive_change(type('', (), {'args': new_text})())
        
        ui.notify('프리셋이 적용되었습니다', type='success')
    
    def _apply_negative_preset(self, preset: str):
        """부정 프롬프트 프리셋 적용"""
        current = self.negative_textarea.value
        
        if current:
            # 기존 내용에 추가
            new_text = f"{current}, {preset}"
        else:
            new_text = preset
        
        self.negative_textarea.set_value(new_text)
        self._on_negative_change(type('', (), {'args': new_text})())
        
        ui.notify('프리셋이 적용되었습니다', type='success')
    
    def _apply_style_preset(self, style: dict):
        """스타일 프리셋 적용 (긍정/부정 동시)"""
        if 'positive' in style:
            self.positive_textarea.set_value(style['positive'])
            self._on_positive_change(type('', (), {'args': style['positive']})())
        
        if 'negative' in style:
            self.negative_textarea.set_value(style['negative'])
            self._on_negative_change(type('', (), {'args': style['negative']})())
        
        ui.notify('스타일 프리셋이 적용되었습니다', type='success')
        
    async def _on_prompt_updated(self, prompt: str):
        """외부에서 프롬프트 업데이트"""
        if self.positive_textarea and self.positive_textarea.value != prompt:
            self.positive_textarea.set_value(prompt)
            self._on_positive_change(type('', (), {'args': prompt})())
    
    async def _on_state_restored(self, data):
        """상태 복원"""
        params = data.params
        
        if self.positive_textarea:
            self.positive_textarea.set_value(params.prompt)
            self._on_positive_change(type('', (), {'args': params.prompt})())
        
        if self.negative_textarea:
            self.negative_textarea.set_value(params.negative_prompt)
            self._on_negative_change(type('', (), {'args': params.negative_prompt})())