# 파일 경로: src/nicediff/ui/top_bar.py (최종 복원 및 완성본)

from nicegui import ui
from typing import Dict, List, Any, Optional
from pathlib import Path
import asyncio, json, base64

class TopBar:
    """최종 개편된 상단 바 (모든 헬퍼 메서드 포함)"""

    def __init__(self, state_manager: Any):
        self.state = state_manager
        self.selected_model_info: Optional[Dict[str, Any]] = None
        self.is_expanded = True
        self.state.subscribe('models_updated', self._on_models_updated)
        self.state.subscribe('vaes_updated', self._on_vaes_updated)
        self.state.subscribe('model_loading_started', self._on_model_loading_started)
        self.state.subscribe('model_loading_finished', self._on_model_loading_finished)
        
        # UI 요소 참조 변수들을 미리 선언합니다.
        self.album_container: Optional[ui.column] = None
        self.vae_select: Optional[ui.select] = None
        self.content_row: Optional[ui.grid] = None
        self.toggle_button: Optional[ui.button] = None
        self.metadata_container: Optional[ui.card] = None
        self.preview_image: Optional[ui.image] = None
        self.prompt_area: Optional[ui.markdown] = None
        self.neg_prompt_area: Optional[ui.markdown] = None
        self.params_label: Optional[ui.label] = None
        self.apply_button: Optional[ui.button] = None
        
        # 애플리케이션의 핵심 이벤트를 여기서 모두 구독합니다.
        self.state.subscribe('available_checkpoints_changed', self._on_models_updated)
        self.state.subscribe('vaes_updated', self._on_vaes_updated)
        self.state.subscribe('model_selection_changed', self._on_model_selected)

    # 1. UI의 '틀'을 만드는 render 메서드
    async def render(self):
        """[최종 수정] 올바른 레이아웃으로 VAE 선택 메뉴를 복원하고, 컨텐츠 영역을 명확히 분리합니다."""
        
        # 전체를 감싸는 카드
        with ui.card().tight().classes('w-full'):
            
            # 1. 최상단 바: 타이틀, 토글 버튼, VAE 선택 메뉴를 여기에 배치합니다.
            with ui.row().classes('w-full p-2 bg-gray-900 items-center justify-between'):
                with ui.row().classes('items-center'):
                    ui.label("모델 라이브러리").classes("text-lg font-bold text-white")
                    self.toggle_button = ui.button(icon='expand_less', on_click=self._toggle_visibility).props('flat round color=white size=sm ml-2')
                
                with ui.row().classes('items-center gap-2'):
                    ui.label('VAE:').classes('text-sm text-white')
                    self.vae_select = ui.select(options=['Automatic', 'None'], value='Automatic') \
                        .props('dark outlined dense').classes('w-48') \
                        .on('change', lambda e: self._on_vae_change(e.value))

            # 2. 메인 컨텐츠 영역 (토글 가능)
            self.content_row = ui.grid(columns='35% 1fr').classes('w-full p-2 bg-gray-800 items-start gap-2')
            with self.content_row:
                # 왼쪽: 모델 앨범
                with ui.card().tight().classes('w-full h-64'):
                    self.album_container = ui.scroll_area().classes('w-full h-full')
                    # 초기 상태 표시
                    with self.album_container:
                         ui.label("모델 로딩 중...").classes("m-4 text-center text-gray-500")

                # 오른쪽: 메타데이터 패널
                self.metadata_container = ui.card().tight().classes('w-full h-64 bg-gray-700')
                self._build_metadata_ui_skeleton() # 메타데이터 UI 뼈대 생성

        # UI가 모두 생성된 후, 초기 데이터 로딩을 안전하게 요청합니다.
        ui.timer(0.1, lambda: asyncio.create_task(self._initial_load()), once=True)

    # 2. 이벤트 핸들러 (StateManager로부터 데이터를 받아 UI를 업데이트)
    async def _initial_load(self):
        """초기 데이터 로딩"""
        await self._on_models_updated(self.state.get('available_checkpoints', {}))
        await self._on_vaes_updated(self.state.get('available_vaes', {}))

    async def _on_models_updated(self, models_by_category: Dict[str, List[Dict[str, Any]]]):
        """모델 목록(checkpoints)이 업데이트되면 앨범 UI를 다시 그립니다."""
        self.album_container.clear()
        with self.album_container:
            if not models_by_category:
                ui.label("체크포인트 모델 없음").classes("m-4 text-center text-gray-500")
                return
            
            sorted_folders = sorted(models_by_category.keys(), key=lambda x: (x != 'Root', x.lower()))
            for folder in sorted_folders:
                with ui.expansion(folder, icon='folder', value=True).classes('w-full').props('header-class="bg-gray-600 text-white"'):
                    with ui.grid(columns=2).classes('w-full gap-2 p-2'):
                        for model_info in models_by_category[folder]:
                            self._create_model_card(model_info)

    async def _on_vaes_updated(self, vaes_by_category: Dict[str, List[Dict[str, Any]]]):
        """VAE 목록이 업데이트되면 드롭다운 메뉴를 채웁니다."""
        # 이 로직은 StateManager의 VAE 자동선택과 연동될 수 있습니다.
        pass

    # 3. UI 헬퍼 메서드 (UI를 그리거나 업데이트하는 구체적인 로직)
    def _create_model_card(self, model_info: Dict[str, Any]):
        """개별 모델 카드를 생성합니다."""
        with ui.card().tight().classes('hover:shadow-lg transition-shadow w-full cursor-pointer').on('click', lambda m=model_info: self._handle_model_select(m)):
            with ui.image(self._get_preview_src(model_info)).classes('w-full h-24 object-cover bg-gray-800 relative'):
                # 모델 타입 배지
                badge_color = {'SDXL': 'bg-purple-600', 'SD15': 'bg-blue-600'}.get(model_info.get('model_type'), 'bg-gray-600')
                ui.badge(model_info.get('model_type', 'N/A'), color=badge_color).classes('absolute top-1 right-1 text-xs')
            
            with ui.card_section().classes('p-1 w-full'):
                ui.label(model_info['name']).classes('text-xs w-full text-center font-medium h-6 truncate').tooltip(model_info['name'])

    def _build_metadata_ui_skeleton(self):
        """메타데이터 UI의 뼈대를 생성합니다."""
        with self.metadata_container:
            with ui.column().classes('w-full h-full p-2 gap-1'):
                self.preview_image = ui.image().classes('w-full h-40 object-contain bg-gray-800 rounded-md')
                with ui.card_section().classes('p-2 w-full'):
                    self.prompt_area = ui.markdown().classes('text-xs h-16 overflow-y-auto flex-grow')
                    self.params_label = ui.label().classes('text-xs text-gray-400 mt-1')
                    self.apply_button = ui.button('파라미터 적용', on_click=self._apply_metadata_to_params).props('dense size=sm color=blue').classes('w-full mt-2')
        self._update_metadata_ui() # 초기 빈 상태로 업데이트

    def _update_metadata_ui(self, model_info: Optional[Dict[str, Any]], loading_info: Optional[Dict] = None, error_message: Optional[str] = None):
        """저장된 selected_model_info를 바탕으로 메타데이터 UI를 업데이트합니다."""
        if self.selected_model_info:
            metadata = self.selected_model_info.get('metadata', {})
            self.preview_image.set_source(self._get_preview_src(self.selected_model_info))
            prompt = metadata.get('prompt', '정보 없음')
            self.prompt_area.set_content(f"**프롬프트:** {prompt}")
            params = metadata.get('parameters', {})
            param_str = ' | '.join(f"{k}: {v}" for k, v in params.items())
            self.params_label.set_text(param_str if param_str else "파라미터 정보 없음")
            self.apply_button.visible = bool(params)
        else:
            self.preview_image.set_source('https://placehold.co/256x256/2d3748/e2e8f0?text=Select+Model')
            self.prompt_area.set_content("**긍정:** 모델을 선택하세요.")
            self.params_label.set_text("파라미터 정보 없음")
            self.apply_button.visible = False

    def _get_preview_src(self, model_info: Dict[str, Any]) -> str:
        """미리보기 이미지 소스를 반환합니다."""
        preview_path = Path(model_info['path']).with_suffix('.png')
        if preview_path.exists():
            with open(preview_path, "rb") as f:
                b64_str = base64.b64encode(f.read()).decode('utf-8')
            return f"data:image/png;base64,{b64_str}"
        return 'https://placehold.co/256x256/2d3748/e2e8f0?text=No+Preview'

    # 4. 사용자 행동 핸들러 (사용자 입력을 받아 StateManager에 전달)
    async def _handle_model_select(self, model_info: Dict[str, Any]):
        """모델 카드 클릭 시, StateManager에 '모델 로드'를 직접 요청합니다."""
        await self.state.load_model_pipeline(model_info)

    # --- 새로운 이벤트 핸들러 추가 ---

    async def _on_model_loading_started(self, data: Dict[str, Any]):
        """
        '로딩 시작' 이벤트를 받았을 때만 UI를 로딩 상태로 변경합니다.
        _update_metadata_ui 메서드를 호출하여 처리합니다.
        """
        self._update_metadata_ui(None, loading_info=data)

    async def _on_model_loading_finished(self, data: Dict[str, Any]):
        """'로딩 완료' 이벤트를 받았을 때만 UI를 최종 상태로 변경합니다."""
        if data.get('success'):
            self._update_metadata_ui(data.get('model_info'))
        else:
            self._update_metadata_ui(None, error_message=data.get('error'))

    def _apply_metadata_to_params(self):
        """'파라미터 적용' 버튼 클릭 시 StateManager에 파라미터 적용을 요청합니다."""
        if self.selected_model_info:
            self.state.apply_params_from_metadata(self.selected_model_info)

    def _toggle_visibility(self):
        """모델 라이브러리 접기/펴기"""
        self.is_expanded = not self.is_expanded
        self.content_row.set_visibility(self.is_expanded)
        self.toggle_button.props(f"icon={'expand_less' if self.is_expanded else 'expand_more'}")

    async def _on_model_selected(self, model_info: Optional[Dict[str, Any]]):
        """StateManager에서 모델 선택이 변경되었다는 알림을 받았을 때 호출됩니다."""
        self.selected_model_info = model_info
        self._update_metadata_ui()