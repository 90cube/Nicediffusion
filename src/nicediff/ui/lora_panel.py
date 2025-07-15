"""
LoRA 선택 패널 - Load LoRA (체크포인트와 동일한 카드 스타일)
"""

from nicegui import ui
from pathlib import Path
from typing import Dict, List, Any
from ..core.state_manager import StateManager
import asyncio
import re

class LoraPanel:
    """LoRA 패널 - Load LoRA (하위폴더별 구분 및 정보 표시)"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.lora_container = None
        self.no_loras = True
        
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.card().classes('w-full h-full p-4 bg-gray-700'):
            # 헤더
            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Load LoRA').classes('text-lg font-bold text-cyan-400')
                
                # 버튼들
                with ui.row().classes('gap-2'):
                    # 폴더 열기 버튼
                    ui.button(
                        icon='folder_open',
                        on_click=self._open_lora_folder
                    ).props('flat dense color=white size=sm').tooltip('LoRA 폴더 열기')
                    
                    # 리프레시 버튼
                    ui.button(
                        icon='refresh',
                        on_click=self._refresh_lora_panel
                    ).props('flat dense color=white size=sm').tooltip('LoRA 패널 새로고침')
            
            # LoRA 목록 컨테이너
            with ui.scroll_area().classes('w-full h-40'):
                self.lora_container = ui.column().classes('w-full')
                self._show_empty_state()
        
        # LoRA 목록 업데이트 구독
        self.state.subscribe('loras_updated', self._update_lora_list)
        
        # 로드된 LoRA 목록 업데이트 구독
        self.state.subscribe('loaded_loras', self._update_loaded_loras)
        
        # 초기 LoRA 목록 로드
        available_loras = self.state.get('available_loras', {})
        if available_loras:
            await self._update_lora_list(available_loras)
    
    async def _update_loaded_loras(self, loaded_loras):
        """로드된 LoRA 목록 업데이트"""
        # 현재 LoRA 목록을 다시 업데이트하여 로드 상태 반영
        available_loras = self.state.get('available_loras', {})
        await self._update_lora_list(available_loras)
    
    def _show_empty_state(self):
        """빈 상태 표시"""
        if self.lora_container:
            self.lora_container.clear()
            with self.lora_container:
                with ui.column().classes('w-full items-center justify-center p-4'):
                    ui.icon('folder_open').classes('text-4xl text-gray-500 mb-2')
                    ui.label('LoRA 파일이 없습니다').classes('text-gray-400 text-sm text-center')
                    ui.label('models/loras 폴더에').classes('text-gray-500 text-xs text-center')
                    ui.label('.safetensors 파일을 넣어주세요').classes('text-gray-500 text-xs text-center')
    
    def _extract_trigger_word(self, metadata):
        """메타데이터에서 트리거 워드 추출 (우선순위: ss_tag_frequency > ss_trigger_words > 'No trigger')"""
        if not metadata:
            return 'No trigger'
        
        # 1. ss_tag_frequency가 가장 자세한 정보
        if 'ss_tag_frequency' in metadata:
            tag_freq = metadata['ss_tag_frequency']
            if isinstance(tag_freq, str) and tag_freq.strip():
                return tag_freq.strip()
        
        # 2. ss_trigger_words가 가장 직접적인 정보
        if 'ss_trigger_words' in metadata:
            trigger_words = metadata['ss_trigger_words']
            if isinstance(trigger_words, str) and trigger_words.strip():
                return trigger_words.strip()
        
        # 3. 기타 SS_로 시작하는 키들에서 추출
        for key, value in metadata.items():
            if key.startswith('ss_') and isinstance(value, str) and value.strip():
                return value.strip()
        
        return 'No trigger'
    
    def _on_lora_click(self, lora_info):
        """LoRA 클릭 - 실제 로드"""
        try:
            # LoRA 로드
            asyncio.create_task(self._load_lora_async(lora_info))
        except Exception as e:
            ui.notify(f'LoRA 로드 실패: {str(e)}', type='negative')
            print(f"❌ LoRA 로드 오류: {e}")
    
    async def _load_lora_async(self, lora_info):
        """LoRA 비동기 로드"""
        try:
            success = await self.state.load_lora(lora_info, weight=1.0)
            if success:
                ui.notify(f'LoRA 로드됨: {lora_info["name"]}', type='positive')
                print(f"✅ LoRA 로드: {lora_info['name']}")
            else:
                ui.notify(f'LoRA 로드 실패: {lora_info["name"]}', type='negative')
                print(f"❌ LoRA 로드 실패: {lora_info['name']}")
        except Exception as e:
            ui.notify(f'LoRA 로드 오류: {str(e)}', type='negative')
            print(f"❌ LoRA 로드 오류: {e}")
    
    def _on_lora_double_click(self, lora_info):
        """LoRA 더블클릭 - 프롬프트에 양식 추가"""
        try:
            # LoRA 문법 양식 생성
            lora_name = Path(lora_info['path']).stem  # 파일명에서 확장자 제거
            lora_syntax = f'<lora:{lora_name}:1.0>'
            
            # 현재 프롬프트 가져오기 (문자열로 처리)
            current_params = self.state.get('current_params')
            current_prompt = ""
            
            # prompt가 문자열인지 확인하고 안전하게 처리
            if current_params and hasattr(current_params, 'prompt'):
                if isinstance(current_params.prompt, str):
                    current_prompt = current_params.prompt
                elif isinstance(current_params.prompt, dict):
                    # 딕셔너리인 경우 positive 키에서 가져오기
                    current_prompt = current_params.prompt.get('positive', '')
                else:
                    current_prompt = str(current_params.prompt)
            
            # 기존 프롬프트에 추가 (기존 프롬프트 유지)
            if current_prompt and current_prompt.strip():
                new_prompt = f"{current_prompt.strip()}, {lora_syntax}"
            else:
                new_prompt = lora_syntax
            
            # StateManager의 update_prompt 메서드를 사용하여 프롬프트 업데이트
            current_negative_prompt = current_params.negative_prompt if hasattr(current_params, 'negative_prompt') else ""
            self.state.update_prompt(new_prompt, current_negative_prompt)
            
            ui.notify(f'프롬프트에 추가됨: {lora_syntax}', type='positive')
            print(f"✅ LoRA 양식 추가: {lora_syntax}")
            print(f"📝 새 프롬프트: {new_prompt}")
            
        except Exception as e:
            ui.notify(f'LoRA 양식 추가 실패: {str(e)}', type='negative')
            print(f"❌ LoRA 양식 추가 오류: {e}")
    
    async def _update_lora_list(self, loras):
        """LoRA 목록 업데이트 (체크포인트와 동일한 카드 스타일)"""
        if not self.lora_container:
            return
        
        self.lora_container.clear()
        
        if not loras or all(len(items) == 0 for items in loras.values()):
            # LoRA가 없는 경우
            self.no_loras = True
            self._show_empty_state()
            return
        
        # LoRA가 있는 경우
        self.no_loras = False
        with self.lora_container:
            # 현재 모델 타입 확인
            current_model = self.state.get('current_model')
            model_type = 'SDXL' if current_model and 'xl' in current_model.lower() else 'SD1.5'
            
            # 로드된 LoRA 목록 가져오기
            loaded_loras = self.state.get_loaded_loras()
            loaded_lora_names = [lora['name'] for lora in loaded_loras]
            
            # 폴더별로 그룹화하여 표시
            sorted_folders = sorted(loras.keys(), key=lambda x: (x != 'Root', x.lower()))
            for folder in sorted_folders:
                items = loras[folder]
                if items:
                    with ui.expansion(folder, icon='folder', value=True).classes('w-full').props('header-class="bg-gray-600 text-white"'):
                        with ui.grid(columns=2).classes('w-full gap-2 p-2'):
                            for item in items:
                                self._create_lora_card(item, loaded_lora_names, model_type)
            
            # 로드된 LoRA 목록 표시
            if loaded_loras:
                ui.label("🔄 로드된 LoRA").classes('text-sm font-bold text-green-400 mt-4 mb-2')
                for loaded_lora in loaded_loras:
                    with ui.card().classes('w-full bg-green-600 p-2 mb-2'):
                        ui.label(f"✅ {loaded_lora['name']} (weight: {loaded_lora['weight']})").classes('text-sm font-bold text-white')
                        
                        # 언로드 버튼
                        ui.button(
                            '언로드',
                            on_click=lambda e, name=loaded_lora['name']: self._unload_lora(name)
                        ).props('dense size=sm color=red').classes('mt-1')
    
    def _create_lora_card(self, lora_info: Dict[str, Any], loaded_lora_names: List[str], current_model_type: str):
        """개별 LoRA 카드를 생성합니다 (체크포인트와 동일한 스타일)."""
        lora_name = lora_info['name']
        model_type_info = lora_info.get('base_model', 'SD1.5')
        trigger_word = self._extract_trigger_word(lora_info.get('metadata', {}))
        is_loaded = lora_name in loaded_lora_names
        
        # 호환성 체크
        compatible = model_type_info == current_model_type
        
        with ui.card().tight().classes('hover:shadow-lg transition-shadow w-full cursor-pointer').on('click', lambda m=lora_info: self._on_lora_click(m)).on('dblclick', lambda m=lora_info: self._on_lora_double_click(m)):
            with ui.image(self._get_lora_preview_src(lora_info)).classes('w-full h-24 object-cover bg-gray-800 relative'):
                # LoRA 타입 배지 (우상단)
                badge_color = {'SDXL': 'bg-purple-600', 'SD1.5': 'bg-blue-600'}.get(model_type_info, 'bg-gray-600')
                ui.badge(model_type_info, color=badge_color).classes('absolute top-1 right-1 text-xs')
                
                # 로드 상태 표시 (좌상단)
                if is_loaded:
                    ui.badge('LOADED', color='green').classes('absolute top-1 left-1 text-xs')
                
                # 호환성 표시 (우하단)
                if not compatible:
                    ui.icon('warning').classes('absolute bottom-1 right-1 text-yellow-400 text-xs').tooltip('모델 타입 불일치')
                else:
                    ui.icon('check_circle').classes('absolute bottom-1 right-1 text-green-400 text-xs').tooltip('모델 타입 일치')
            
            with ui.card_section().classes('p-1 w-full'):
                # LoRA 이름
                ui.label(lora_name).classes('text-xs w-full text-center font-medium h-6 truncate').tooltip(lora_name)
                
                # 트리거 워드 (썸네일 아래)
                if trigger_word and trigger_word != 'No trigger':
                    ui.label(trigger_word).classes('text-xs w-full text-center text-purple-300 h-4 truncate').tooltip(trigger_word)
    
    def _get_lora_preview_src(self, lora_info: Dict[str, Any]) -> str:
        """LoRA 썸네일 이미지 소스를 반환합니다."""
        lora_path = Path(lora_info['path'])
        png_path = lora_path.with_suffix('.png')
        
        if png_path.exists():
            return str(png_path)
        else:
            # 기본 LoRA 아이콘 또는 빈 이미지
            return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzc0MTUxIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iI2ZmZiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkxvUkE8L3RleHQ+PC9zdmc+'
    
    async def _unload_lora(self, lora_name: str):
        """LoRA 언로드"""
        try:
            success = await self.state.unload_lora(lora_name)
            if success:
                ui.notify(f'LoRA 언로드됨: {lora_name}', type='positive')
                print(f"✅ LoRA 언로드: {lora_name}")
            else:
                ui.notify(f'LoRA 언로드 실패: {lora_name}', type='negative')
                print(f"❌ LoRA 언로드 실패: {lora_name}")
        except Exception as e:
            ui.notify(f'LoRA 언로드 오류: {str(e)}', type='negative')
            print(f"❌ LoRA 언로드 오류: {e}")
    
    async def _refresh_lora_panel(self):
        """LoRA 패널 새로고침"""
        try:
            # 모델 스캐너를 통해 LoRA 목록 다시 스캔
            from ..services.model_scanner import ModelScanner
            paths_config = {'loras': 'models/loras'}
            scanner = ModelScanner(paths_config)
            all_models = await scanner.scan_all_models()
            loras = all_models.get('loras', {})
            await self._update_lora_list(loras)
            ui.notify('LoRA 패널이 새로고침되었습니다', type='positive')
        except Exception as e:
            ui.notify(f'LoRA 패널 새로고침 실패: {str(e)}', type='negative')
    
    async def _open_lora_folder(self):
        """LoRA 폴더 열기"""
        try:
            import subprocess
            import platform
            
            lora_path = Path('models/loras')
            if not lora_path.exists():
                lora_path.mkdir(parents=True, exist_ok=True)
            
            if platform.system() == 'Windows':
                subprocess.run(['explorer', str(lora_path)])
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', str(lora_path)])
            else:  # Linux
                subprocess.run(['xdg-open', str(lora_path)])
            
            ui.notify('LoRA 폴더가 열렸습니다', type='positive')
        except Exception as e:
            ui.notify(f'폴더 열기 실패: {str(e)}', type='negative')