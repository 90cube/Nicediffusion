# 파일 경로: src/nicediff/ui/top_bar.py (오류 수정 버전)

from nicegui import ui
from typing import Dict, List, Any, Optional
from pathlib import Path
import asyncio, json, base64

class TopBar:
    """최종 개편된 상단 바 (오류 수정 완료)"""

    def __init__(self, state_manager: Any):
        self.state = state_manager
        self.selected_model_info: Optional[Dict[str, Any]] = None
        self.is_expanded = True
        self.state.subscribe('models_updated', self._on_models_updated)
        self.state.subscribe('vae_updated', self._on_vae_updated)
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
        self.main_card: Optional[ui.card] = None
        
        # 애플리케이션의 핵심 이벤트를 여기서 모두 구독합니다.
        self.state.subscribe('available_checkpoints_changed', self._on_models_updated)
        self.state.subscribe('vae_updated', self._on_vae_updated)
        self.state.subscribe('model_selection_changed', self._on_model_selected)

    # 1. UI의 '틀'을 만드는 render 메서드
    async def render(self):
        """[최종 수정] 반응형 레이아웃으로 TopBar 개선"""
        
    # 전체를 감싸는 카드 (overflow 제어)
        self.main_card = ui.card().tight().classes('w-full overflow-hidden transition-all duration-300')
        with self.main_card:
            
            # 1. 최상단 바: 반응형 레이아웃
            with ui.row().classes('w-full p-2 bg-gray-900 items-center justify-between flex-wrap gap-2'):
                # 왼쪽: 타이틀과 토글 버튼
                with ui.row().classes('items-center flex-shrink-0'):
                    ui.label("모델 라이브러리").classes("text-lg font-bold text-white")
                    self.toggle_button = ui.button(icon='expand_less', on_click=self._toggle_visibility).props('flat round color=white size=sm ml-2')
                
                # 오른쪽: VAE 선택 (반응형)
                with ui.row().classes('items-center gap-2 flex-shrink-0 min-w-0'):
                    ui.label('VAE:').classes('text-sm text-white flex-shrink-0')
                    self.vae_select = ui.select(options=['Automatic', 'None'], value='Automatic') \
                        .props('dark outlined dense') \
                        .classes('w-48 min-w-32 max-w-64') \
                        .on('change', lambda e: self._on_vae_change(e.value))

            # 2. 메인 컨텐츠 영역 (토글 가능, 반응형)
            self.content_row = ui.row().classes('w-full p-2 bg-gray-800 gap-2 flex-wrap lg:flex-nowrap')
            with self.content_row:
                # 왼쪽: 모델 앨범 (반응형 너비)
                with ui.card().tight().classes('w-full lg:w-2/5 xl:w-1/3 h-64 min-w-0'):
                    with ui.card_section().classes('p-2'):
                        ui.label('체크포인트 모델').classes('text-sm font-bold text-white mb-2')
                    self.album_container = ui.scroll_area().classes('w-full h-52')
                    # 초기 상태 표시
                    with self.album_container:
                         ui.label("모델 로딩 중...").classes("m-4 text-center text-gray-500")

                # 오른쪽: 메타데이터 패널 (반응형 너비)
                self.metadata_container = ui.card().tight().classes('w-full lg:w-3/5 xl:w-2/3 h-64 bg-gray-700 min-w-0')
                self._build_metadata_ui_skeleton() # 메타데이터 UI 뼈대 생성

        # UI가 모두 생성된 후, 초기 데이터 로딩을 안전하게 요청합니다.
        ui.timer(0.1, lambda: asyncio.create_task(self._initial_load()), once=True)

    # 2. 이벤트 핸들러 (StateManager로부터 데이터를 받아 UI를 업데이트)
    async def _initial_load(self):
        """초기 데이터 로딩"""
        await self._on_models_updated(self.state.get('available_checkpoints', {}))
        await self._on_vae_updated(self.state.get('available_vae', {}))

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

    async def _on_vae_updated(self, vae_by_category: Dict[str, List[Dict[str, Any]]]):
        """VAE 목록이 업데이트되면 드롭다운 메뉴를 채웁니다."""
        # VAE 옵션 업데이트
        vae_options = ['Automatic', 'None']
        
        if vae_by_category:
            for folder_name, folder_vae in vae_by_category.items():
                for vae_info in folder_vae:
                    display_name = vae_info['name']
                    if folder_name != 'Root':
                        display_name = f"{folder_name}/{vae_info['name']}"
                    vae_options.append(display_name)
        
        if self.vae_select:
            self.vae_select.options = vae_options
            print(f"✅ VAE 옵션 업데이트 완료: {len(vae_options)-2}개 VAE 발견")

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
        """메타데이터 UI의 뼈대를 생성합니다 (반응형 개선)."""
        with self.metadata_container:
            with ui.column().classes('w-full h-full p-2 gap-1 relative'): # 'relative' 클래스 추가
                # --- NEW: 로딩 스피너를 여기에 추가하고 처음엔 숨김 ---
                self.loading_spinner = ui.spinner(size='lg').props('color=white') \
                    .classes('absolute-center bg-gray-800 bg-opacity-70 p-4 rounded-full z-10') \
                    .set_visibility(False)

                self.preview_image = ui.image().classes('w-full h-32 object-contain bg-gray-800 rounded-md flex-shrink-0')
                
                # 스크롤 가능한 메타데이터 영역
                with ui.scroll_area().classes('w-full flex-1 min-h-0'):
                    with ui.column().classes('w-full gap-2'):
                        self.prompt_area = ui.markdown().classes('text-xs')
                        self.params_label = ui.label().classes('text-xs text-gray-400')
                        self.apply_button = ui.button('파라미터 적용', on_click=self._apply_metadata_to_params).props('dense size=sm color=blue').classes('w-full')
        
        self._update_metadata_ui() # 초기 빈 상태로 업데이트 (인자 없이 호출)

    def _update_metadata_ui(self, model_info: Optional[Dict[str, Any]] = None, loading_info: Optional[Dict] = None, error_message: Optional[str] = None):
        """[오류 수정] model_info를 옵셔널 파라미터로 변경하고, 전달되지 않으면 self.selected_model_info를 사용합니다."""
        
        # 만약 model_info가 전달되지 않았다면, self.selected_model_info를 사용
        if model_info is None:
            model_info = self.selected_model_info
        
        # 로딩 상태 처리
        if loading_info:
            self.preview_image.set_source('https://placehold.co/256x256/2d3748/e2e8f0?text=Loading...')
            self.prompt_area.set_content(f"**로딩 중...** {loading_info.get('name', '')}")
            self.params_label.set_text("모델을 로드하고 있습니다...")
            self.apply_button.visible = False
            return
        
        # 에러 상태 처리
        if error_message:
            self.preview_image.set_source('https://placehold.co/256x256/dc2626/ffffff?text=Error')
            self.prompt_area.set_content(f"**오류:** {error_message}")
            self.params_label.set_text("로딩에 실패했습니다")
            self.apply_button.visible = False
            return
        
        # 정상 상태 처리
        if model_info:
            metadata = model_info.get('metadata', {})
            self.preview_image.set_source(self._get_preview_src(model_info))
            prompt = metadata.get('prompt', '정보 없음')
            self.prompt_area.set_content(f"**프롬프트:** {prompt}")
            params = metadata.get('parameters', {})
            param_str = ' | '.join(f"{k}: {v}" for k, v in params.items())
            self.params_label.set_text(param_str if param_str else "파라미터 정보 없음")
            self.apply_button.visible = bool(params)
        else:
            # 빈 상태
            self.preview_image.set_source('https://placehold.co/256x256/2d3748/e2e8f0?text=Select+Model')
            self.prompt_area.set_content("**긍정:** 모델을 선택하세요.")
            self.params_label.set_text("파라미터 정보 없음")
            self.apply_button.visible = False

    def _get_preview_src(self, model_info: Dict[str, Any]) -> str:
        """미리보기 이미지 소스를 반환합니다."""
        preview_path = Path(model_info['path']).with_suffix('.png')
        if preview_path.exists():
            try:
                with open(preview_path, "rb") as f:
                    b64_str = base64.b64encode(f.read()).decode('utf-8')
                return f"data:image/png;base64,{b64_str}"
            except Exception as e:
                print(f"미리보기 이미지 로드 실패: {e}")
        return 'https://placehold.co/256x256/2d3748/e2e8f0?text=No+Preview'

    # 4. 사용자 행동 핸들러 (사용자 입력을 받아 StateManager에 전달)
    async def _handle_model_select(self, model_info: Dict[str, Any]):
        """모델 카드 클릭 시, StateManager에 '모델 로드'를 직접 요청합니다."""
        # 먼저 선택 상태를 업데이트
        self.selected_model_info = model_info
        self._update_metadata_ui(model_info)
        
        # 그 다음 로딩 요청
        await self.state.load_model_pipeline(model_info)

    def _on_vae_change(self, vae_value: str):
        """VAE 선택 변경 처리 (개선)"""
        print(f"VAE 선택됨: {vae_value}")
        
        if vae_value == 'Automatic':
            # 자동 VAE 선택 - 현재 모델 정보 기준으로 재선택
            current_model = self.state.get('current_model_info')
            if current_model:
                asyncio.create_task(self.state._auto_select_vae(current_model))
            else:
                self.state.set('current_vae_path', 'baked_in')
                
        elif vae_value == 'None':
            # VAE 없음
            self.state.set('current_vae_path', None)
            ui.notify('VAE가 비활성화되었습니다', type='info')
            
        else:
            # 특정 VAE 선택
            vae_path = self.state.find_vae_by_name(vae_value)
            if vae_path:
                asyncio.create_task(self.state.load_vae(vae_path))
            else:
                ui.notify(f'VAE "{vae_value}"를 찾을 수 없습니다', type='warning')

    # --- 이벤트 핸들러 ---

    async def _on_model_loading_started(self, data: Dict[str, Any]):
        """이제 전체를 지우지 않고, 스피너만 보여줍니다."""
        if self.loading_spinner:
            self.loading_spinner.set_visibility(True)

    async def _on_model_loading_finished(self, data: Dict[str, Any]):
        """로딩이 끝나면 스피너를 숨깁니다."""
        if self.loading_spinner:
            self.loading_spinner.set_visibility(False)
        
        # 로딩 실패 시 알림
        if not data.get('success'):
            ui.notify(f"모델 로드 실패: {data.get('error', '알 수 없는 오류')}", type='negative')

    def _apply_metadata_to_params(self):
        """'파라미터 적용' 버튼 클릭 시 StateManager에 파라미터 적용을 요청합니다."""
        if self.selected_model_info and hasattr(self.state, 'apply_params_from_metadata'):
            self.state.apply_params_from_metadata(self.selected_model_info)
            ui.notify('메타데이터 파라미터가 적용되었습니다', type='success')
        else:
            ui.notify('적용할 파라미터가 없습니다', type='warning')

    def _toggle_visibility(self):
        """'펼치기/접기'를 '전체화면/원래대로' 기능으로 업그레이드합니다."""
        self.is_expanded = not self.is_expanded
    
        if self.is_expanded:
            # 펼칠 때: 전체 화면을 덮는 스타일로 변경
            self.main_card.classes(
                remove='max-h-80', # 기존 높이 제한이 있다면 제거
                add='fixed top-0 left-0 w-screen h-screen z-50' # 전체화면 CSS 클래스
            )
            self.content_row.classes(remove='h-64') # 컨텐츠 높이 제한 해제
            self.toggle_button.props('icon=close') # 아이콘을 닫기 버튼으로
            self.toggle_button.tooltip('라이브러리 닫기')

        else:
            # 접을 때: 원래 스타일로 복원
            self.main_card.classes(
                add='max-h-80', # 원래 높이 제한을 다시 줄 수 있습니다
                remove='fixed top-0 left-0 w-screen h-screen z-50'
            )
            self.content_row.classes(add='h-64') # 컨텐츠 높이 복원
            self.toggle_button.props('icon=fullscreen') # 아이콘을 전체화면 버튼으로
            self.toggle_button.tooltip('라이브러리 전체화면')

    async def _on_model_selected(self, model_info: Optional[Dict[str, Any]]):
        """StateManager에서 모델 선택이 변경되었다는 알림을 받았을 때 호출됩니다."""
        self.selected_model_info = model_info
        self._update_metadata_ui()  # 인자 없이 호출 (이제 옵셔널이므로 문제없음)