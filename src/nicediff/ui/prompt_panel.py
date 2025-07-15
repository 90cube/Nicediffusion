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
        self.token_count_positive = None
        self.token_count_negative = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        # 현재 파라미터 가져오기
        current_params = self.state.get('current_params')
        
        with ui.column().classes('w-full gap-3'):
            # 헤더: 제목과 리프레시 버튼
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('프롬프트').classes('text-lg font-bold text-green-400')
                
                # 리프레시 버튼
                ui.button(
                    icon='refresh',
                    on_click=self._refresh_prompt_panel
                ).props('round color=white text-color=black size=sm').tooltip('프롬프트 패널 새로고침')
            
            # 긍정 프롬프트
            with ui.column().classes('w-full'):
                with ui.row().classes('items-center justify-between mb-1'):
                    ui.label('긍정프롬프트').classes('text-green-400 font-bold')
                    with ui.row().classes('gap-2'):
                        self.char_count_positive = ui.label(f'{len(current_params.prompt)}자').classes('text-xs text-gray-400')
                        self.token_count_positive = ui.label('0 토큰').classes('text-xs text-blue-400')
                
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
                
                # 고급 프롬프트 처리 버튼들
                with ui.row().classes('gap-1 mt-1'):
                    ui.button(
                        'BREAK',
                        on_click=self._add_break_keyword
                    ).props('dense flat size=sm color=orange').tooltip('BREAK 키워드 추가')
                    
                    ui.button(
                        icon='tune',
                        on_click=self._show_weight_dialog
                    ).props('dense flat size=sm color=blue').tooltip('가중치 적용')
                    
                    ui.button(
                        icon='optimize',
                        on_click=self._optimize_prompt
                    ).props('dense flat size=sm color=green').tooltip('프롬프트 최적화')
                
                # 프롬프트 분석 결과 표시
                self.analysis_container = ui.column().classes('mt-2 p-2 bg-gray-700 rounded text-xs')
                self.analysis_container.visible = False
            
            # 부정 프롬프트
            with ui.column().classes('w-full'):
                with ui.row().classes('items-center justify-between mb-1'):
                    ui.label('부정프롬프트').classes('text-pink-400 font-bold')
                    with ui.row().classes('gap-2'):
                        self.char_count_negative = ui.label(f'{len(current_params.negative_prompt)}자').classes('text-xs text-gray-400')
                        self.token_count_negative = ui.label('0 토큰').classes('text-xs text-blue-400')
                
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
        """긍정 프롬프트 변경 (StateManager 메서드 호출)"""
        text = self.state.get('current_params').prompt
        if self.char_count_positive:
            self.char_count_positive.set_text(f'{len(text)}자')
        
        # 토큰 수 계산 및 표시
        token_count = self.state.calculate_token_count(text)
        if self.token_count_positive:
            self.token_count_positive.set_text(f'{token_count} 토큰')
        
        # 프롬프트 분석 (토큰 수가 50 이상일 때만)
        if token_count >= 50:
            analysis = self.state.analyze_prompt(text)
            self._show_analysis(analysis)
        else:
            # 분석 결과 숨기기
            if hasattr(self, 'analysis_container') and self.analysis_container:
                self.analysis_container.visible = False
        
        # StateManager 메서드 호출로 변경
        self.state.update_prompt(text, self.state.get('current_params').negative_prompt)
    
    def _on_negative_change(self, e):
        """부정 프롬프트 변경 (StateManager 메서드 호출)"""
        text = self.state.get('current_params').negative_prompt
        self.char_count_negative.set_text(f'{len(text)}자')
        
        # 토큰 수 계산 및 표시
        token_count = self.state.calculate_token_count(text)
        self.token_count_negative.set_text(f'{token_count} 토큰')
        
        # StateManager 메서드 호출로 변경
        self.state.update_prompt(self.state.get('current_params').prompt, text)
    
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
    
    def _add_break_keyword(self):
        """BREAK 키워드 추가"""
        current_text = self.positive_textarea.value
        if current_text:
            # 문장 끝에 BREAK 추가
            new_text = self.state.add_break_keyword(current_text)
            self.positive_textarea.set_value(new_text)
            self._on_positive_change(type('', (), {'args': new_text})())
            ui.notify('BREAK 키워드가 추가되었습니다', type='info')
        else:
            ui.notify('먼저 프롬프트를 입력해주세요', type='warning')
    
    def _show_weight_dialog(self):
        """가중치 적용 다이얼로그"""
        current_text = self.positive_textarea.value
        if not current_text:
            ui.notify('먼저 프롬프트를 입력해주세요', type='warning')
            return
        
        with ui.dialog() as dialog, ui.card():
            ui.label('가중치 적용').classes('text-lg font-bold')
            
            with ui.row().classes('gap-2'):
                keyword_input = ui.input(label='키워드', placeholder='가중치를 적용할 키워드')
                weight_input = ui.number(label='가중치', value=1.1, min=0.1, max=2.0, step=0.1)
            
            with ui.row().classes('gap-2'):
                ui.button('적용', on_click=lambda: self._apply_weight(
                    keyword_input.value, weight_input.value, dialog
                ))
                ui.button('취소', on_click=dialog.close)
    
    def _apply_weight(self, keyword: str, weight: float, dialog):
        """가중치 적용"""
        if not keyword:
            ui.notify('키워드를 입력해주세요', type='warning')
            return
        
        current_text = self.positive_textarea.value
        weighted_keyword = self.state.apply_weight(keyword, weight)
        
        # 키워드를 가중치 구문으로 교체
        import re
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, current_text):
            new_text = re.sub(pattern, weighted_keyword, current_text, count=1)
        else:
            # 키워드가 없으면 끝에 추가
            new_text = f"{current_text}, {weighted_keyword}"
        
        self.positive_textarea.set_value(new_text)
        self._on_positive_change(type('', (), {'args': new_text})())
        
        dialog.close()
        ui.notify(f'가중치가 적용되었습니다: {weighted_keyword}', type='success')
    
    def _optimize_prompt(self):
        """프롬프트 최적화"""
        current_text = self.positive_textarea.value
        if not current_text:
            ui.notify('먼저 프롬프트를 입력해주세요', type='warning')
            return
        
        # 프롬프트 분석
        analysis = self.state.analyze_prompt(current_text)
        
        # 분석 결과 표시
        self._show_analysis(analysis)
        
        # 최적화 제안
        if not analysis['is_optimized']:
            optimized_text = self.state.optimize_prompt(current_text)
            if optimized_text != current_text:
                with ui.dialog() as dialog, ui.card():
                    ui.label('프롬프트 최적화 제안').classes('text-lg font-bold')
                    ui.label('현재 프롬프트:').classes('font-bold')
                    ui.label(current_text).classes('text-sm bg-gray-800 p-2 rounded')
                    ui.label('최적화된 프롬프트:').classes('font-bold mt-2')
                    ui.label(optimized_text).classes('text-sm bg-green-800 p-2 rounded')
                    
                    with ui.row().classes('gap-2 mt-2'):
                        ui.button('적용', on_click=lambda: self._apply_optimized_prompt(optimized_text, dialog))
                        ui.button('취소', on_click=dialog.close)
    
    def _apply_optimized_prompt(self, optimized_text: str, dialog):
        """최적화된 프롬프트 적용"""
        self.positive_textarea.set_value(optimized_text)
        self._on_positive_change(type('', (), {'args': optimized_text})())
        dialog.close()
        ui.notify('최적화된 프롬프트가 적용되었습니다', type='success')
    
    def _show_analysis(self, analysis: dict):
        """프롬프트 분석 결과 표시"""
        self.analysis_container.clear()
        
        with self.analysis_container:
            # 토큰 수 표시
            token_color = 'text-red-400' if analysis['token_count'] > 77 else 'text-green-400'
            ui.label(f"토큰 수: {analysis['token_count']}/77").classes(token_color)
            
            # 세그먼트 정보
            if analysis['segments']:
                ui.label(f"세그먼트: {len(analysis['segments'])}개").classes('text-blue-400')
            
            # 가중치 정보
            if analysis['weights']:
                ui.label("가중치:").classes('text-yellow-400')
                for keyword, weight in analysis['weights'].items():
                    ui.label(f"  {keyword}: {weight}").classes('text-xs')
            
            # 제안사항
            if analysis['suggestions']:
                ui.label("제안사항:").classes('text-orange-400')
                for suggestion in analysis['suggestions']:
                    ui.label(f"  {suggestion}").classes('text-xs')
        
        self.analysis_container.visible = True
        
    async def _on_prompt_updated(self, prompt):
        """외부에서 프롬프트 업데이트"""
        # prompt가 dict인 경우 문자열로 변환
        if isinstance(prompt, dict):
            prompt = str(prompt)
        elif not isinstance(prompt, str):
            prompt = str(prompt)
            
        if self.positive_textarea and self.positive_textarea.value != prompt:
            self.positive_textarea.set_value(prompt)
            self._on_positive_change(type('', (), {'args': prompt})())
    
    async def _on_state_restored(self, data: dict):
        """
        StateManager로부터 상태 복원 이벤트를 받았을 때
        프롬프트 입력 UI를 업데이트합니다.
        """
        params = data.get('params')
    
    def _on_prompt_changed(self, data):
        """프롬프트 변경 이벤트 핸들러"""
        prompt = data.get('prompt', '')
        negative_prompt = data.get('negative_prompt', '')
        
        # UI 업데이트 (다른 컴포넌트에서 변경된 경우)
        if self.positive_textarea and self.positive_textarea.value != prompt:
            self.positive_textarea.set_value(prompt)
            self.char_count_positive.set_text(f'{len(prompt)}자')
        
        if self.negative_textarea and self.negative_textarea.value != negative_prompt:
            self.negative_textarea.set_value(negative_prompt)
            self.char_count_negative.set_text(f'{len(negative_prompt)}자')

        # params 객체가 정상적으로 존재하는지 확인 후 UI 업데이트
        if params:
            # 올바른 속성명 사용: positive_textarea와 negative_textarea
            if self.positive_textarea:
                self.positive_textarea.set_value(params.prompt)
                self._on_positive_change(None)
            if self.negative_textarea:
                self.negative_textarea.set_value(params.negative_prompt)
                self._on_negative_change(None)

    def _refresh_prompt_panel(self):
        """프롬프트 패널 새로고침"""
        print("🔄 프롬프트 패널 새로고침 중...")
        
        # 현재 파라미터로 UI 업데이트
        current_params = self.state.get('current_params')
        self._update_ui_from_state(current_params)
        
        ui.notify('프롬프트 패널이 새로고침되었습니다', type='info')