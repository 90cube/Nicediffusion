"""
토크나이저 선택 패널
"""

from nicegui import ui
from typing import Dict, Any, List
from ..core.state_manager import StateManager


class TokenizerPanel:
    """토크나이저 선택 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.tokenizer_select = None
        self.tokenizer_info = None
        self.stats_container = None
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.card().classes('w-full p-4 bg-purple-800'):
            ui.label('토크나이저 설정').classes('text-lg font-bold mb-2 text-white')
            
            # 토크나이저 선택
            available_tokenizers = self._get_available_tokenizers()
            
            with ui.column().classes('w-full gap-3'):
                # 토크나이저 선택 드롭다운
                self.tokenizer_select = ui.select(
                    options=available_tokenizers,
                    label='토크나이저',
                    value='default'
                ).on('update:model-value', self._on_tokenizer_change)
                
                # 토크나이저 정보 표시
                self.tokenizer_info = ui.column().classes('w-full p-2 bg-gray-700 rounded')
                self._show_tokenizer_info('default')
                
                # 토크나이저 통계
                self.stats_container = ui.column().classes('w-full p-2 bg-gray-700 rounded')
                self._show_tokenizer_stats('default')
                
                # 토크나이저 관리 버튼
                with ui.row().classes('w-full gap-2'):
                    ui.button(
                        '토크나이저 스캔',
                        icon='refresh',
                        on_click=self._rescan_tokenizers
                    ).props('color=blue size=sm')
                    
                    ui.button(
                        '모든 언로드',
                        icon='clear_all',
                        on_click=self._unload_all_tokenizers
                    ).props('color=red size=sm')
    
    def _get_available_tokenizers(self) -> List[str]:
        """사용 가능한 토크나이저 목록"""
        if not hasattr(self.state, 'tokenizer_manager') or not self.state.tokenizer_manager:
            return ['default']
        
        tokenizers = self.state.tokenizer_manager.list_available_tokenizers()
        if not tokenizers:
            return ['default']
        
        return ['default'] + tokenizers
    
    def _on_tokenizer_change(self, tokenizer_name: str):
        """토크나이저 변경 처리"""
        if not hasattr(self.state, 'tokenizer_manager') or not self.state.tokenizer_manager:
            ui.notify('토크나이저 매니저가 초기화되지 않았습니다', type='warning')
            return
        
        if tokenizer_name == 'default':
            # 기본 토크나이저 사용 (파이프라인의 토크나이저)
            self.state.tokenizer_manager.current_tokenizer = None
            ui.notify('기본 토크나이저를 사용합니다', type='info')
        else:
            # 커스텀 토크나이저 로드
            tokenizer = self.state.tokenizer_manager.load_tokenizer(tokenizer_name)
            if tokenizer:
                ui.notify(f'토크나이저 "{tokenizer_name}" 로드 완료', type='positive')
            else:
                ui.notify(f'토크나이저 "{tokenizer_name}" 로드 실패', type='negative')
        
        # 정보 업데이트
        self._show_tokenizer_info(tokenizer_name)
        self._show_tokenizer_stats(tokenizer_name)
    
    def _show_tokenizer_info(self, tokenizer_name: str):
        """토크나이저 정보 표시"""
        if not self.tokenizer_info:
            return
        
        self.tokenizer_info.clear()
        
        with self.tokenizer_info:
            if tokenizer_name == 'default':
                ui.label('기본 토크나이저 (파이프라인 내장)').classes('text-white font-bold')
                ui.label('현재 로드된 모델의 토크나이저를 사용합니다').classes('text-gray-300 text-sm')
            else:
                if not hasattr(self.state, 'tokenizer_manager') or not self.state.tokenizer_manager:
                    ui.label('토크나이저 정보를 불러올 수 없습니다').classes('text-red-400')
                    return
                
                info = self.state.tokenizer_manager.get_tokenizer_info(tokenizer_name)
                if info:
                    ui.label(f'토크나이저: {info["name"]}').classes('text-white font-bold')
                    ui.label(f'경로: {info["path"]}').classes('text-gray-300 text-sm')
                    
                    # 파일 정보
                    with ui.expansion('파일 정보', icon='folder').classes('w-full mt-2'):
                        for file_name, file_info in info['files'].items():
                            size_kb = file_info['size'] / 1024
                            ui.label(f'{file_name}: {size_kb:.1f} KB').classes('text-xs text-gray-400')
                    
                    # 특수 기능
                    features = []
                    if info.get('has_merges'):
                        features.append('Merges 지원')
                    if info.get('has_special_tokens'):
                        features.append('특수 토큰 지원')
                    
                    if features:
                        ui.label(f'기능: {", ".join(features)}').classes('text-green-400 text-sm')
                else:
                    ui.label('토크나이저 정보를 찾을 수 없습니다').classes('text-red-400')
    
    def _show_tokenizer_stats(self, tokenizer_name: str):
        """토크나이저 통계 표시"""
        if not self.stats_container:
            return
        
        self.stats_container.clear()
        
        with self.stats_container:
            if tokenizer_name == 'default':
                ui.label('기본 토크나이저 통계').classes('text-white font-bold')
                ui.label('모델 로드 후 통계가 표시됩니다').classes('text-gray-300 text-sm')
            else:
                if not hasattr(self.state, 'tokenizer_manager') or not self.state.tokenizer_manager:
                    ui.label('토크나이저 통계를 불러올 수 없습니다').classes('text-red-400')
                    return
                
                stats = self.state.tokenizer_manager.get_tokenizer_stats(tokenizer_name)
                if stats:
                    ui.label('토크나이저 통계').classes('text-white font-bold')
                    
                    with ui.row().classes('w-full gap-4'):
                        with ui.column().classes('flex-1'):
                            ui.label(f'최대 길이: {stats["model_max_length"]}').classes('text-xs text-gray-300')
                            ui.label(f'어휘 크기: {stats["vocab_size"]:,}').classes('text-xs text-gray-300')
                        
                        with ui.column().classes('flex-1'):
                            ui.label(f'PAD 토큰: {stats["pad_token"]}').classes('text-xs text-gray-300')
                            ui.label(f'EOS 토큰: {stats["eos_token"]}').classes('text-xs text-gray-300')
                else:
                    ui.label('토크나이저가 로드되지 않았습니다').classes('text-yellow-400')
    
    def _rescan_tokenizers(self):
        """토크나이저 재스캔"""
        if not hasattr(self.state, 'tokenizer_manager') or not self.state.tokenizer_manager:
            ui.notify('토크나이저 매니저가 초기화되지 않았습니다', type='warning')
            return
        
        self.state.tokenizer_manager.scan_tokenizers()
        
        # UI 업데이트
        available_tokenizers = self._get_available_tokenizers()
        if self.tokenizer_select:
            self.tokenizer_select.options = available_tokenizers
        
        ui.notify('토크나이저 스캔 완료', type='positive')
    
    def _unload_all_tokenizers(self):
        """모든 토크나이저 언로드"""
        if not hasattr(self.state, 'tokenizer_manager') or not self.state.tokenizer_manager:
            ui.notify('토크나이저 매니저가 초기화되지 않았습니다', type='warning')
            return
        
        self.state.tokenizer_manager.unload_all_tokenizers()
        
        # UI 업데이트
        if self.tokenizer_select:
            self.tokenizer_select.set_value('default')
        
        ui.notify('모든 토크나이저가 언로드되었습니다', type='info') 