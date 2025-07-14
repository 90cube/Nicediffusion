"""
LoRA 로드 패널
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio

class LoraLoadPanel:
    """LoRA 로드 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.lora_container = None
        self.no_loras = True
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full gap-2'):
            # 헤더
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('LoRA Load').classes('text-lg font-bold text-purple-400')
                
                # 버튼들: 폴더 열기 + 리프레시
                with ui.row().classes('gap-2'):
                    # 리프레시 버튼
                    ui.button(
                        icon='refresh',
                        on_click=self._refresh_lora_panel
                    ).props('flat dense color=white size=sm').tooltip('LoRA 패널 새로고침')
                    
                    # 폴더 열기 버튼
                    self.folder_button = ui.button(
                        icon='folder_open',
                        on_click=self._open_lora_folder
                    ).props('flat dense color=white size=sm').tooltip('LoRA 폴더 열기')
            
            # LoRA 목록 컨테이너 (전체 높이 사용)
            with ui.scroll_area().classes('w-full flex-1'):
                self.lora_container = ui.column().classes('w-full')
                self._show_empty_state()
        
        # LoRA 목록 업데이트 구독
        self.state.subscribe('loras_updated', self._update_lora_list)
        
        # 시작 시 LoRA 자동 로드
        asyncio.create_task(self._load_loras_on_start())
    
    async def _load_loras_on_start(self):
        """시작 시 LoRA 자동 로드"""
        try:
            from ..services.model_scanner import ModelScanner
            from ..utils.config_loader import ConfigLoader
            
            config = ConfigLoader()
            paths_config = config.get_paths_config()
            
            scanner = ModelScanner(paths_config)
            loras = await scanner.scan_loras()
            
            # StateManager에 LoRA 정보 저장
            self.state.set('loras', loras)
            
            # UI 업데이트
            await self._update_lora_list(loras)
            
            print(f"✅ LoRA 로드 완료: {sum(len(items) for items in loras.values())}개")
        except Exception as e:
            print(f"❌ LoRA 로드 실패: {e}")
    
    def _show_empty_state(self):
        """빈 상태 표시"""
        if self.lora_container:
            self.lora_container.clear()
            with self.lora_container:
                with ui.column().classes('w-full items-center justify-center p-4'):
                    ui.icon('folder_open').classes('text-4xl text-gray-500 mb-2')
                    ui.label('LoRA 파일이 없습니다').classes('text-gray-400 text-sm text-center')
                    ui.label('models/lora 폴더에').classes('text-gray-500 text-xs text-center')
                    ui.label('.safetensors 파일을 넣어주세요').classes('text-gray-500 text-xs text-center')
    
    async def _update_lora_list(self, loras):
        """LoRA 목록 업데이트"""
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
            
            # 현재 선택된 LoRA들
            current_loras = self.state.get('current_loras', [])
            
            # 폴더별로 그룹화하여 표시
            for folder, items in loras.items():
                if items:
                    # 폴더명 표시
                    if folder != 'Root':
                        ui.label(folder).classes('text-sm font-bold text-purple-300 mt-2 mb-1')
                    
                    # LoRA 아이템들
                    for item in items:
                        # 호환성 체크
                        compatible = item.get('base_model', '정보 없음') == model_type or item.get('base_model', '정보 없음') == '정보 없음'
                        is_selected = item.get('path') in current_loras
                        
                        with ui.card().classes('w-full mb-2 p-3 cursor-pointer').on('click', lambda e, lora=item: self._on_lora_click(lora)).on('dblclick', lambda e, lora=item: self._on_lora_double_click(lora)):
                            # 첫 번째 행: LoRA 이름과 체크박스
                            with ui.row().classes('w-full items-center justify-between mb-2'):
                                # LoRA 이름 (20자 제한)
                                lora_name = item['name']
                                display_name = lora_name[:20] + ('...' if len(lora_name) > 20 else '')
                                ui.label(display_name).classes('text-sm font-medium text-white')
                                
                                # 체크박스
                                checkbox = ui.checkbox(
                                    value=is_selected,
                                    on_change=lambda e, path=item['path']: self._on_lora_toggle(e, path)
                                ).props('color=purple')
                                
                                # 호환성 표시
                                if not compatible:
                                    checkbox.disable()
                                    ui.icon('warning').classes('text-yellow-500 text-sm').tooltip(
                                        f'이 LoRA는 {item.get("base_model", "정보 없음")}용입니다'
                                    )
                            
                            # 두 번째 행: 베이스 모델 타입
                            with ui.row().classes('w-full items-center mb-2'):
                                ui.label('베이스 모델 타입:').classes('text-xs text-gray-400 mr-2')
                                ui.label(item.get('base_model', '정보 없음')).classes('text-xs text-blue-300')
                            
                            # 세 번째 행: 트리거 워드 (미리보기)
                            metadata = item.get('metadata', {})
                            trigger_words = metadata.get('suggested_tags', [])
                            if trigger_words and len(trigger_words) > 0:
                                with ui.row().classes('w-full items-start mb-2'):
                                    ui.label('트리거 워드:').classes('text-xs text-gray-400 mr-2 mt-1')
                                    # 첫 3개만 표시
                                    preview_words = trigger_words[:3]
                                    with ui.row().classes('flex-wrap gap-1'):
                                        for word in preview_words:
                                            ui.chip(word).props('size=sm color=green').classes('text-xs')
                                        if len(trigger_words) > 3:
                                            ui.chip(f'+{len(trigger_words) - 3}').props('size=sm color=gray').classes('text-xs')
                            else:
                                with ui.row().classes('w-full items-center mb-2'):
                                    ui.label('트리거 워드:').classes('text-xs text-gray-400 mr-2')
                                    ui.label('트리거 워드 없음').classes('text-xs text-gray-500')
    
    def _on_lora_click(self, lora):
        """LoRA 클릭 시 LoRA Info에 정보 전달"""
        try:
            # LoRA Info 패널에 정보 전달
            self.state.set('selected_lora_info', lora)
            self.state._notify('lora_info_updated', lora)
            
            print(f"📋 LoRA 정보 선택: {lora['name']}")
        except Exception as e:
            print(f"LoRA 정보 전달 실패: {e}")
    
    def _on_lora_double_click(self, lora):
        """LoRA 더블 클릭 시 프롬프트에 <lora:로라이름:가중치> 추가"""
        try:
            # 현재 프롬프트 가져오기
            current_prompt = self.state.get('prompt', '')
            
            # LoRA 태그 생성 (기본 가중치 1.0)
            lora_tag = f"<lora:{lora['name']}:1.0>"
            
            # 이미 같은 LoRA가 있으면 제거
            import re
            pattern = rf"<lora:{re.escape(lora['name'])}:[^>]*>"
            new_prompt = re.sub(pattern, '', current_prompt).strip()
            
            # 새 LoRA 태그 추가
            if new_prompt:
                new_prompt += f", {lora_tag}"
            else:
                new_prompt = lora_tag
            
            # 프롬프트 업데이트
            self.state.set('prompt', new_prompt)
            self.state._notify('prompt_updated', new_prompt)
            
            ui.notify(f'LoRA "{lora["name"]}" 프롬프트에 추가됨', type='positive')
            print(f"➕ LoRA 프롬프트 추가: {lora_tag}")
        except Exception as e:
            print(f"LoRA 프롬프트 추가 실패: {e}")
            ui.notify(f'LoRA 프롬프트 추가 실패: {str(e)}', type='negative')
    
    def _on_lora_toggle(self, e, lora_path):
        """LoRA 선택 토글"""
        current_loras = self.state.get('current_loras', [])
        
        if e.value:
            # LoRA 추가
            if lora_path not in current_loras:
                current_loras.append(lora_path)
                ui.notify(f'LoRA 추가됨', type='positive')
        else:
            # LoRA 제거
            if lora_path in current_loras:
                current_loras.remove(lora_path)
                ui.notify(f'LoRA 제거됨', type='info')
        
        self.state.set('current_loras', current_loras)
        
        # LoRA Info 패널 업데이트 트리거
        self.state._notify('loras_updated', self.state.get('loras', {}))
    
    def _open_lora_folder(self):
        """LoRA 폴더 열기"""
        import platform
        import subprocess
        
        lora_path = Path(self.state.config.get('paths', {}).get('loras', 'models/loras'))
        lora_path.mkdir(parents=True, exist_ok=True)
        
        try:
            if platform.system() == 'Windows':
                subprocess.run(['explorer', str(lora_path)])
            elif platform.system() == 'Darwin':
                subprocess.run(['open', str(lora_path)])
            else:
                subprocess.run(['xdg-open', str(lora_path)])
            
            ui.notify('LoRA 폴더를 열었습니다', type='info')
        except Exception as e:
            ui.notify(f'폴더 열기 실패: {e}', type='negative')
    
    def _refresh_lora_panel(self):
        """LoRA 패널 새로고침"""
        print("🔄 LoRA 패널 새로고침 중...")
        
        # LoRA 목록 다시 스캔
        asyncio.create_task(self._rescan_loras())
        
        ui.notify('LoRA 패널이 새로고침되었습니다', type='info')
    
    async def _rescan_loras(self):
        """LoRA 목록 다시 스캔"""
        try:
            # StateManager를 통해 LoRA 다시 스캔
            from ..services.model_scanner import ModelScanner
            from ..utils.config_loader import ConfigLoader
            
            # ConfigLoader를 통해 paths_config 가져오기
            config = ConfigLoader()
            paths_config = config.get_paths_config()
            
            scanner = ModelScanner(paths_config)
            loras = await scanner.scan_loras()
            
            # StateManager에 LoRA 정보 저장
            self.state.set('loras', loras)
            
            # UI 업데이트
            await self._update_lora_list(loras)
        except Exception as e:
            print(f"❌ LoRA 스캔 실패: {e}")
            # UI 컨텍스트 오류 방지를 위해 notify 대신 print만 사용
            print(f'LoRA 스캔 실패: {str(e)}') 