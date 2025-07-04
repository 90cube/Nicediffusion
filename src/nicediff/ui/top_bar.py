# 파일 경로: src/nicediff/ui/top_bar.py (최종 아키텍처 수정본)

from nicegui import ui
from typing import Dict, List, Any, Optional
from pathlib import Path
import asyncio, json, base64, io
from PIL import Image
from ..core.state_manager import StateManager
from ..services.metadata_parser import MetadataParser

class TopBar:
    """최종 개편된 상단 바 (안정화된 UI 빌드 및 업데이트 로직)"""

    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.selected_model_info: Optional[Dict[str, Any]] = None
        self.is_expanded = True
        
        # UI 요소 참조 변수
        self.album_container: Optional[ui.column] = None
        self.vae_select: Optional[ui.select] = None
        self.content_row: Optional[ui.grid] = None
        self.toggle_button: Optional[ui.button] = None
        self.preview_image: Optional[ui.image] = None
        self.prompt_area: Optional[ui.markdown] = None
        self.neg_prompt_area: Optional[ui.markdown] = None
        self.params_label: Optional[ui.label] = None
        self.apply_button: Optional[ui.button] = None
        self.copy_prompt_button: Optional[ui.button] = None
        self.copy_neg_prompt_button: Optional[ui.button] = None

        # 이벤트 구독
        self.state.subscribe('models_updated', self._on_models_updated)
        self.state.subscribe('vaes_updated', self._on_vaes_updated)

    async def _on_models_updated(self, models: Dict[str, List[Dict[str, Any]]]):
        """모델 목록을 받으면, 앨범 UI를 채웁니다."""
        if self.album_container is not None:
            await self._build_checkpoint_album(models)

    async def _on_vaes_updated(self, vaes: Dict[str, List[Dict[str, Any]]]):
        """VAE 목록을 받으면, VAE 드롭다운을 채웁니다."""
        if self.vae_select is not None:
            options = ['None'] + [item['filename'] for items in vaes.values() for item in items]
            self.vae_select.options, self.vae_select.value = options, 'None'
            self.vae_select.update()
            
    async def _load_and_display_model(self, model_info: Dict[str, Any]):
        """모델 로딩, 메타데이터 파싱, UI 업데이트를 순차적으로 처리합니다."""
        success = await self.state.load_model_pipeline(model_info)
        
        if success:
            model_path = Path(model_info['path'])
            metadata = MetadataParser.extract_from_safetensors(model_path)
            
            preview_path = model_path.with_suffix('.png')
            if preview_path.exists():
                png_meta = MetadataParser.extract_from_png(preview_path)
                metadata.update(png_meta)
            
            self.selected_model_info = model_info
            self.selected_model_info['metadata'] = metadata
            
            self._update_metadata_ui()

    def _update_metadata_ui(self):
        """저장된 selected_model_info를 바탕으로 메타데이터 UI를 직접 업데이트합니다."""
        # UI 요소가 준비되지 않았다면 함수를 즉시 종료하는 방어 코드
        if not all([self.preview_image, self.prompt_area, self.neg_prompt_area,
                    self.params_label, self.apply_button, self.copy_prompt_button, 
                    self.copy_neg_prompt_button]):
            return

        if not self.selected_model_info: return
            
        metadata = self.selected_model_info.get('metadata', {})
        
        preview_path = Path(self.selected_model_info['path']).with_suffix('.png')
        if preview_path.exists():
            try:
                with open(preview_path, "rb") as f:
                    b64_str = base64.b64encode(f.read()).decode('utf-8')
                self.preview_image.set_source(f"data:image/png;base64,{b64_str}")
            except Exception:
                self.preview_image.set_source('https://placehold.co/256x256/2d3748/e2e8f0?text=Preview+Error')
        else:
            self.preview_image.set_source('https://placehold.co/256x256/2d3748/e2e8f0?text=No+Preview')
        
        prompt = metadata.get('prompt', '')
        neg_prompt = metadata.get('negative_prompt', '')
        params = metadata.get('parameters', {})
        
        self.prompt_area.set_content(f"**긍정:** {prompt if prompt else '정보 없음'}")
        self.neg_prompt_area.set_content(f"**부정:** {neg_prompt if neg_prompt else '정보 없음'}")
        
        # 버튼의 클릭 이벤트를 매번 새로 지정하지 않도록 구조 변경
        # on_click 핸들러는 render 시점에 한 번만 설정
        
        param_str = ' | '.join(f"{k}: {v}" for k, v in params.items() if k not in ['width', 'height'])
        self.params_label.set_text(param_str if param_str else "파라미터 정보 없음")
        
        # .visible 속성을 사용하여 버튼의 가시성을 제어
        self.apply_button.visible = bool(params)

    async def _build_checkpoint_album(self, models: Dict[str, List[Dict[str, Any]]]):
        """체크포인트 앨범 UI를 만듭니다."""
        self.album_container.clear()
        if not models:
            with self.album_container:
                ui.label("체크포인트 모델이 없습니다.").classes("m-4 text-center text-gray-500")
            return

        sorted_folders = sorted(models.keys(), key=lambda x: (x != 'Root', x.lower()))
        with self.album_container:
            for folder in sorted_folders:
                items = models.get(folder, [])
                if not items: continue
                with ui.expansion(folder, icon='folder', value=True).classes('w-full').props('header-class="bg-gray-600 text-white"'):
                    with ui.grid(columns=2).classes('w-full gap-2 p-2'):
                        for model_data in items:
                            with ui.card().tight().classes('hover:shadow-lg transition-shadow w-full'):
                                with ui.row().classes('w-full h-24 bg-gray-800 flex items-center justify-center'):
                                    preview_path = Path(model_data['path']).with_suffix('.png')
                                    if preview_path.exists():
                                        try:
                                            with open(preview_path, "rb") as f:
                                                b64_str = base64.b64encode(f.read()).decode('utf-8')
                                            ui.image(f"data:image/png;base64,{b64_str}").classes('w-full h-full object-cover')
                                        except Exception as e:
                                            ui.icon('error_outline', color='red-500').tooltip(f'미리보기 오류: {e}')
                                    else:
                                        ui.label('PNG EMPTY').classes('text-gray-500 font-medium')
                                
                                with ui.card_section().classes('p-1 w-full'):
                                    ui.label(model_data['name']).classes('text-xs w-full text-center font-medium h-6 truncate')
                                    ui.button('로드', on_click=lambda m=model_data: self._load_and_display_model(m)) \
                                        .props('dense color=positive size=xs').classes('w-full mt-1')
    
    def _toggle_visibility(self):
        self.is_expanded = not self.is_expanded
        self.content_row.set_visibility(self.is_expanded)
        self.toggle_button.props(f"icon={'expand_less' if self.is_expanded else 'expand_more'}")

    def _copy_to_clipboard(self, key: str, label: str):
        if not self.selected_model_info:
            ui.notify('먼저 모델을 선택해주세요', type='warning')
            return
        
        text_to_copy = self.selected_model_info.get('metadata', {}).get(key, '')
        if not text_to_copy:
            ui.notify(f'{label} 내용이 없습니다', type='warning')
            return
            
        ui.run_javascript(f'navigator.clipboard.writeText({json.dumps(text_to_copy)})')
        ui.notify(f'{label}가 클립보드에 복사되었습니다', type='positive')

    def _apply_metadata_to_params(self):
        if not self.selected_model_info:
            ui.notify('먼저 모델을 선택해주세요', type='warning')
            return
            
        params = self.selected_model_info.get('metadata', {}).get('parameters', {})
        if not params:
            ui.notify('적용할 파라미터가 없습니다', type='warning')
            return
            
        current_params = self.state.get('current_params')
        for key, value in params.items():
            if hasattr(current_params, key):
                setattr(current_params, key, value)
        
        self.state.set('current_params', current_params)
        ui.notify('파라미터가 적용되었습니다', type='success')

    async def render(self):
        """UI 틀을 먼저 만들고, 데이터는 나중에 채우는 안정적인 구조"""
        with ui.card().tight().classes('w-full'):
            with ui.row().classes('w-full p-1 bg-gray-900 items-center'):
                ui.label("모델 라이브러리").classes("text-lg font-bold text-white ml-2")
                ui.space()
                self.toggle_button = ui.button(icon='expand_less', on_click=self._toggle_visibility).props('flat round color=white')
            
            self.content_row = ui.grid(columns='35% 55% 10%').classes('w-full p-2 bg-gray-800 items-start gap-2')
            with self.content_row:
                with ui.card().tight().classes('w-full h-64'):
                    self.album_container = ui.scroll_area().classes('w-full h-full')
                
                with ui.card().tight().classes('w-full h-64 bg-gray-700'):
                    with ui.column().classes('w-full h-full p-2 gap-1'):
                        self.preview_image = ui.image('https://placehold.co/256x256/2d3748/e2e8f0?text=Select+Model').classes('w-full h-40 object-contain bg-gray-800 rounded-md')
                        with ui.card_section().classes('p-2 w-full'):
                            with ui.row().classes('items-center w-full'):
                                self.prompt_area = ui.markdown('**긍정:** 모델을 선택하고 로드하세요.').classes('text-xs h-8 overflow-y-auto flex-grow')
                                self.copy_prompt_button = ui.button(icon='content_copy', on_click=lambda: self._copy_to_clipboard('prompt', '긍정 프롬프트')).props('dense flat size=xs')
                            
                            with ui.row().classes('items-center w-full'):
                                self.neg_prompt_area = ui.markdown('**부정:**').classes('text-xs h-8 overflow-y-auto flex-grow')
                                self.copy_neg_prompt_button = ui.button(icon='content_copy', on_click=lambda: self._copy_to_clipboard('negative_prompt', '부정 프롬프트')).props('dense flat size=xs')
                            
                            self.params_label = ui.label("파라미터 정보 없음").classes('text-xs text-gray-400 mt-1')
                            self.apply_button = ui.button('파라미터 적용', on_click=self._apply_metadata_to_params).props('dense size=sm color=blue').classes('w-full mt-2')
                            self.apply_button.visible = False # 초기에 숨김

                with ui.column().classes('w-full h-full'):
                    ui.label('VAE').classes('text-white font-medium text-xs')
                    self.vae_select = ui.select(options=['None'], value='None').props('dark outlined dense').classes('w-full').on('change', lambda e: self.state.set('current_vae', e.value))
        
        # UI가 모두 생성된 후, 초기 모델 목록을 가져와 앨범을 채웁니다.
        await self._on_models_updated(self.state.get('available_models', {}))
        await self._on_vaes_updated(self.state.get('available_vaes', {}))
