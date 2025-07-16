"""
프롬프트 입력 패널
"""

from typing import List
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
        
        # 이벤트 구독 설정
        self.state.subscribe('metadata_prompts_apply', self._on_metadata_prompts_apply)
    
    async def render(self):
        """컴포넌트 렌더링 - 탭 방식으로 변경"""
        # 현재 파라미터 가져오기
        current_params = self.state.get('current_params')
        
        with ui.column().classes('w-full gap-1'):
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
                                icon='auto_awesome',
                                on_click=self._improve_prompt
                            ).props('dense flat size=sm').tooltip('프롬프트 개선 (LLM)')
                            
                            ui.button(
                                icon='clear',
                                on_click=lambda: self._clear_positive_prompt()
                            ).props('dense flat size=sm').tooltip('지우기')
                            
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
                            
                            ui.button(
                                icon='segment',
                                on_click=self._show_long_prompt_dialog
                            ).props('dense flat size=sm color=purple').tooltip('긴 프롬프트 처리')
                        
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
                            presets = [
                                ('일반', 'low quality, worst quality, bad anatomy, bad hands'),
                                ('사실적', 'cartoon, anime, illustration, painting, drawing'),
                                ('일러스트', 'photo, realistic, 3d render, photography'),
                            ]
                            
                            for name, preset in presets:
                                ui.button(
                                    name,
                                    on_click=lambda _, p=preset: self._apply_negative_preset(p)
                                ).props('dense flat size=xs')
        
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
    
    async def _improve_prompt(self):
        """LLM으로 프롬프트 개선"""
        current_text = self.positive_textarea.value if self.positive_textarea else ''
        
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
    
    def _show_weight_dialog(self):
        """가중치 적용 다이얼로그"""
        current_text = self.positive_textarea.value if self.positive_textarea else ''
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
        
        current_text = self.positive_textarea.value if self.positive_textarea else ''
        weighted_keyword = self.state.apply_weight(keyword, weight)
        
        # 키워드를 가중치 구문으로 교체
        import re
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, current_text):
            new_text = re.sub(pattern, weighted_keyword, current_text, count=1)
        else:
            # 키워드가 없으면 끝에 추가
            new_text = f"{current_text}, {weighted_keyword}"
        
        if self.positive_textarea:
            self.positive_textarea.set_value(new_text)
        self._on_positive_change(type('', (), {'args': new_text})())
        
        dialog.close()
        ui.notify(f'가중치가 적용되었습니다: {weighted_keyword}', type='positive')
    
    def _optimize_prompt(self):
        """프롬프트 최적화"""
        current_text = self.positive_textarea.value if self.positive_textarea else ''
        if not current_text:
            ui.notify('먼저 프롬프트를 입력해주세요', type='warning')
            return
        
        # 프롬프트 분석
        analysis = self.state.analyze_prompt(current_text)
        
        # 분석 결과를 팝업 다이얼로그로 표시
        with ui.dialog() as dialog, ui.card().classes('w-96 max-w-full'):
            ui.label('프롬프트 분석 결과').classes('text-lg font-bold mb-4')
            
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
            
            # 최적화 제안
            if not analysis['is_optimized']:
                optimized_text = self.state.optimize_prompt(current_text)
                if optimized_text != current_text:
                    ui.separator().classes('my-4')
                    ui.label('최적화 제안:').classes('font-bold text-green-400')
                    ui.label('현재 프롬프트:').classes('font-bold text-sm')
                    ui.label(current_text).classes('text-sm bg-gray-800 p-2 rounded')
                    ui.label('최적화된 프롬프트:').classes('font-bold text-sm mt-2')
                    ui.label(optimized_text).classes('text-sm bg-green-800 p-2 rounded')
                    
                    with ui.row().classes('gap-2 mt-4'):
                        ui.button('적용', on_click=lambda: self._apply_optimized_prompt(optimized_text, dialog)).props('color=green')
                        ui.button('취소', on_click=dialog.close).props('color=gray')
            else:
                ui.separator().classes('my-4')
                ui.label('✅ 프롬프트가 이미 최적화되어 있습니다').classes('text-green-400 font-bold')
                ui.button('확인', on_click=dialog.close).props('color=blue').classes('mt-2')
    
    def _apply_optimized_prompt(self, optimized_text: str, dialog):
        """최적화된 프롬프트 적용"""
        if self.positive_textarea:
            self.positive_textarea.set_value(optimized_text)
        self._on_positive_change(type('', (), {'args': optimized_text})())
        dialog.close()
        ui.notify('최적화된 프롬프트가 적용되었습니다', type='positive')
    
    def _show_long_prompt_dialog(self):
        """긴 프롬프트 처리 다이얼로그"""
        current_text = self.positive_textarea.value if self.positive_textarea else ''
        
        if not current_text:
            ui.notify('처리할 프롬프트를 입력해주세요', type='warning')
            return
        
        # 프롬프트 통계 정보 가져오기
        stats = self.state.get_prompt_stats(current_text)
        
        # 다이얼로그 표시
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl'):
            ui.label('긴 프롬프트 처리').classes('text-lg font-bold text-purple-400')
            
            with ui.column().classes('w-full gap-4'):
                # 통계 정보
                with ui.card().classes('w-full bg-gray-800 p-4'):
                    ui.label('프롬프트 통계').classes('font-medium text-blue-400')
                    with ui.row().classes('w-full justify-between text-sm'):
                        ui.label(f'총 토큰: {stats["total_tokens"]}')
                        ui.label(f'최대 토큰: {stats["max_tokens"]}')
                        ui.label(f'청크 수: {stats["chunks_count"]}')
                    
                    # 경고 표시
                    if stats['is_truncated']:
                        ui.label('⚠️ 프롬프트가 잘릴 수 있습니다!').classes('text-orange-400 font-medium')
                    else:
                        ui.label('✅ 프롬프트가 토큰 제한 내에 있습니다.').classes('text-green-400 font-medium')
                
                # 청크별 상세 정보
                if stats['chunks_count'] > 1:
                    ui.label('분할된 청크들:').classes('font-medium text-green-400')
                    
                    for i, chunk in enumerate(stats['chunks']):
                        with ui.card().classes('w-full bg-gray-700 p-3'):
                            with ui.row().classes('w-full justify-between items-start'):
                                ui.label(f'청크 {i+1}').classes('font-medium text-blue-400')
                                with ui.column().classes('text-right text-xs'):
                                    ui.label(f'{chunk["tokens"]} 토큰')
                                    ui.label(f'중요도: {chunk["importance"]:.2f}')
                            
                            ui.textarea(value=chunk['text']).props('readonly outlined dense').classes('w-full mt-2')
                
                # 처리 옵션
                ui.label('처리 옵션:').classes('font-medium text-yellow-400')
                with ui.row().classes('w-full gap-2'):
                    ui.button(
                        '자동 BREAK 추가',
                        on_click=lambda: self._add_auto_breaks(current_text, dialog)
                    ).props('color=orange')
                    
                    ui.button(
                        '프롬프트 최적화',
                        on_click=lambda: self._optimize_long_prompt(current_text, dialog)
                    ).props('color=green')
                    
                    ui.button(
                        '수동 분할',
                        on_click=lambda: self._manual_split(current_text, dialog)
                    ).props('color=blue')
                
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('닫기', on_click=dialog.close).props('flat')
        
        dialog.open()
    
    def _add_auto_breaks(self, text: str, dialog):
        """자동으로 BREAK 키워드 추가"""
        optimized_text = self.state.add_break_keyword(text)
        
        if self.positive_textarea:
            self.positive_textarea.set_value(optimized_text)
        self._on_positive_change(type('', (), {'args': optimized_text})())
        
        ui.notify('자동 BREAK 키워드가 추가되었습니다', type='positive')
        dialog.close()
    
    def _optimize_long_prompt(self, text: str, dialog):
        """긴 프롬프트 최적화"""
        optimized_text = self.state.optimize_long_prompt(text)
        
        if self.positive_textarea:
            self.positive_textarea.set_value(optimized_text)
        self._on_positive_change(type('', (), {'args': optimized_text})())
        
        ui.notify('프롬프트가 최적화되었습니다', type='positive')
        dialog.close()
    
    def _manual_split(self, text: str, dialog):
        """수동 분할 다이얼로그"""
        chunks = self.state.split_long_prompt(text)
        
        with ui.dialog() as split_dialog, ui.card().classes('w-full max-w-4xl'):
            ui.label('수동 분할 편집').classes('text-lg font-bold text-blue-400')
            
            with ui.column().classes('w-full gap-4'):
                chunk_textareas = []
                
                for i, chunk in enumerate(chunks):
                    ui.label(f'청크 {i+1} ({chunk["tokens"]} 토큰)').classes('font-medium')
                    textarea = ui.textarea(value=chunk['text']).props('outlined').classes('w-full')
                    chunk_textareas.append(textarea)
                
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('취소', on_click=split_dialog.close).props('flat')
                    ui.button(
                        '적용',
                        on_click=lambda: self._apply_manual_split([ta.value for ta in chunk_textareas], split_dialog, dialog)
                    ).props('color=primary')
        
        split_dialog.open()
    
    def _apply_manual_split(self, chunk_texts: List[str], split_dialog, main_dialog):
        """수동 분할 결과 적용"""
        # BREAK 키워드로 연결
        break_keyword = "BREAK"
        if hasattr(self.state, 'long_prompt_handler') and self.state.long_prompt_handler:
            break_keyword = self.state.long_prompt_handler.break_keyword
        
        result_text = f" {break_keyword} ".join(chunk_texts)
        
        if self.positive_textarea:
            self.positive_textarea.set_value(result_text)
        self._on_positive_change(type('', (), {'args': result_text})())
        
        ui.notify('수동 분할이 적용되었습니다', type='positive')
        split_dialog.close()
        main_dialog.close()
    
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