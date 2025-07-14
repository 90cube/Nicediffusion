"""
LoRA Info 패널
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio

class LoraPanel:
    """LoRA Info 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.lora_container = None
        self.selected_lora = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full gap-2'):
            # 헤더
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('LoRA Info').classes('text-lg font-bold text-cyan-400')
            
            # LoRA 정보 컨테이너 (전체 높이 사용)
            with ui.scroll_area().classes('w-full flex-1'):
                self.lora_container = ui.column().classes('w-full')
                self._show_empty_state()
        
        # LoRA 정보 업데이트 구독
        self.state.subscribe('lora_info_updated', self._update_lora_info)
    
    def _show_empty_state(self):
        """빈 상태 표시"""
        if self.lora_container:
            self.lora_container.clear()
            with self.lora_container:
                with ui.column().classes('w-full items-center justify-center p-4'):
                    ui.icon('auto_awesome').classes('text-4xl text-gray-500 mb-2')
                    ui.label('LoRA 정보가 없습니다').classes('text-gray-400 text-sm text-center')
                    ui.label('LoRA Load에서 LoRA를 클릭하면').classes('text-gray-500 text-xs text-center')
                    ui.label('상세 정보가 표시됩니다').classes('text-gray-500 text-xs text-center')
    
    async def _update_lora_info(self, lora_info):
        """선택된 LoRA 정보 업데이트"""
        if not self.lora_container:
            return
        
        self.selected_lora = lora_info
        self.lora_container.clear()
        
        if not lora_info:
            self._show_empty_state()
            return
        
        # LoRA 이름과 트리거 워드만 표시
        with self.lora_container:
            # LoRA 이름 (큰 글씨)
            ui.label(lora_info.get('name', 'Unknown')).classes('text-lg font-bold text-white mb-3')
            
            # 트리거 워드 카드
            metadata = lora_info.get('metadata', {})
            trigger_words = metadata.get('suggested_tags', [])
            if trigger_words and len(trigger_words) > 0:
                with ui.card().classes('w-full mb-3 p-3'):
                    ui.label('트리거 워드').classes('text-sm font-bold text-cyan-300 mb-2')
                    
                    # 트리거 워드들을 버튼으로 표시
                    with ui.row().classes('w-full flex-wrap gap-2'):
                        for word in trigger_words:
                            ui.button(
                                word,
                                on_click=lambda e, w=word: self._add_trigger_word(w)
                            ).props('dense flat color=green size=sm').classes('text-xs')
                    
                    # 전체 추가 버튼
                    ui.button(
                        '모든 트리거 워드 추가',
                        on_click=lambda: self._add_all_trigger_words(trigger_words)
                    ).props('flat color=green size=sm').classes('mt-2')
            else:
                with ui.card().classes('w-full mb-3 p-3'):
                    ui.label('트리거 워드').classes('text-sm font-bold text-cyan-300 mb-2')
                    ui.label('트리거 워드 없음').classes('text-xs text-gray-500 mt-1')
    
    def _add_trigger_word(self, word: str):
        """트리거 워드를 프롬프트에 추가"""
        try:
            # 현재 프롬프트 가져오기
            current_prompt = self.state.get('prompt', '')
            
            # 트리거 워드가 이미 있으면 추가하지 않음
            if word not in current_prompt:
                # 프롬프트 끝에 트리거 워드 추가
                new_prompt = current_prompt + (', ' if current_prompt else '') + word
                self.state.set('prompt', new_prompt)
                
                # 프롬프트 패널 업데이트 트리거
                self.state._notify('prompt_updated', new_prompt)
                
                ui.notify(f'트리거 워드 "{word}" 추가됨', type='positive')
            else:
                ui.notify(f'트리거 워드 "{word}"가 이미 프롬프트에 있습니다', type='info')
        except Exception as e:
            print(f"트리거 워드 추가 실패: {e}")
            ui.notify(f'트리거 워드 추가 실패: {str(e)}', type='negative')
    
    def _add_all_trigger_words(self, trigger_words: list):
        """모든 트리거 워드를 프롬프트에 추가"""
        try:
            # 현재 프롬프트 가져오기
            current_prompt = self.state.get('prompt', '')
            
            # 이미 있는 트리거 워드 제외
            new_words = []
            for word in trigger_words:
                if word not in current_prompt:
                    new_words.append(word)
            
            if new_words:
                # 프롬프트에 새 트리거 워드들 추가
                new_prompt = current_prompt + (', ' if current_prompt else '') + ', '.join(new_words)
                self.state.set('prompt', new_prompt)
                
                # 프롬프트 패널 업데이트 트리거
                self.state._notify('prompt_updated', new_prompt)
                
                ui.notify(f'{len(new_words)}개 트리거 워드 추가됨', type='positive')
            else:
                ui.notify('모든 트리거 워드가 이미 프롬프트에 있습니다', type='info')
        except Exception as e:
            print(f"트리거 워드 일괄 추가 실패: {e}")
            ui.notify(f'트리거 워드 일괄 추가 실패: {str(e)}', type='negative')