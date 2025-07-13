"""
LoRA 선택 패널
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio

class LoraPanel:
    """LoRA 패널"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.lora_container = None
        self.no_loras = True
    
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.card().classes('w-full h-full p-4 bg-gray-700'):
            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('LoRA').classes('text-lg font-bold text-cyan-400')
                
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
            
            # LoRA 목록 컨테이너
            with ui.scroll_area().classes('w-full h-40'):
                self.lora_container = ui.column().classes('w-full')
                self._show_empty_state()
        
        # LoRA 목록 업데이트 구독
        self.state.subscribe('loras_updated', self._update_lora_list)
    
    def _show_empty_state(self):
        """빈 상태 표시"""
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
            
            # 폴더별로 그룹화하여 표시
            for folder, items in loras.items():
                if items:
                    # 폴더명 표시
                    if folder != 'Root':
                        ui.label(folder).classes('text-sm font-bold text-cyan-300 mt-2 mb-1')
                    
                    # LoRA 아이템들
                    for item in items:
                        # 호환성 체크
                        compatible = item.get('base_model', 'SD1.5') == model_type
                        
                        with ui.row().classes('w-full items-center gap-2 p-1'):
                            # 체크박스
                            checkbox = ui.checkbox(
                                text=item['name'][:20] + ('...' if len(item['name']) > 20 else ''),
                                on_change=lambda e, path=item['path']: self._on_lora_toggle(e, path)
                            ).classes('flex-1 text-sm')
                            
                            # 호환성 표시
                            if not compatible:
                                checkbox.disable()
                                ui.icon('warning').classes('text-yellow-500 text-sm').tooltip(
                                    f'이 LoRA는 {item.get("base_model", "SD1.5")}용입니다'
                                )
                            
                            # 트리거 워드가 있으면 표시
                            if item.get('trigger_words'):
                                ui.icon('info').classes('text-blue-400 text-sm').tooltip(
                                    f'트리거: {", ".join(item["trigger_words"])}'
                                )
    
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
    
    def _on_lora_added(self, data):
        """LoRA 추가 이벤트 핸들러"""
        lora_info = data.get('lora', {})
        lora_name = lora_info.get('name', 'Unknown')
        print(f"✅ LoRA 추가됨: {lora_name}")
        # UI 업데이트 (필요한 경우)
        # 예: LoRA 목록 새로고침, 선택 상태 업데이트 등
    
    def _on_lora_removed(self, data):
        """LoRA 제거 이벤트 핸들러"""
        lora_id = data.get('lora_id', '')
        print(f"✅ LoRA 제거됨: {lora_id}")
        # UI 업데이트 (필요한 경우)
        # 예: LoRA 목록 새로고침, 선택 상태 업데이트 등

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
            scanner = ModelScanner()
            loras = await scanner.scan_loras()
            await self._update_lora_list(loras)
        except Exception as e:
            print(f"❌ LoRA 스캔 실패: {e}")
            ui.notify(f'LoRA 스캔 실패: {str(e)}', type='negative')