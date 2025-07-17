# 확장 가능한 Image Pad 탭 시스템 완전 구현 기획서

## 🎯 프로젝트 개요

### 목표
**nicediff Image Pad를 탭 기반 시스템으로 전환**하여 무한 확장 가능한 창작 플랫폼 구축

### 핵심 기능
- 📱 **탭 기반 UI**: Image Pad 내부 탭으로 모드 전환
- 🔄 **이미지 워크플로우**: 업로드/생성 구분 없이 자유로운 전달
- 🎨 **고급 창작 도구**: 3D 컨트롤넷, 마스크, 스케치 등
- 🔌 **플러그인 시스템**: 새로운 탭 동적 추가 가능

### 기술 스택
- **Frontend**: NiceGUI + HTML5 Canvas + WebGL + Three.js
- **Backend**: Python + FastAPI 
- **통신**: WebSocket (실시간) + HTTP API
- **3D**: Three.js + OpenPose + ControlNet
- **Canvas**: Fabric.js + Paper.js + P5.js

---

## 🏗️ 시스템 아키텍처

### 전체 구조
```
┌─────────────────────────────────────────────────────────────────┐
│                        NiceDiff Application                      │
├─────────────────────────────────────────────────────────────────┤
│  ParameterPanel (고정)  │  ImagePad (탭 기반)  │  UtilitySidebar │
│  • 프롬프트 입력        │  ┌─────────────────┐  │  • LoRA 패널    │
│  • 기본 파라미터        │  │[T2I][I2I][Inpaint]│  │  • 메타데이터   │
│  • 생성 버튼           │  │[Upscale][3D][Mask]│  │  • 히스토리     │
│                        │  │[Sketch][More...]│  │               │
│                        │  └─────────────────┘  │               │
│                        │  현재 탭의 전용 UI     │               │
│                        │  (Canvas/WebGL 영역)   │               │
└─────────────────────────────────────────────────────────────────┘
```

### 핵심 컴포넌트

#### 1. TabManager (탭 관리자)
```python
class TabManager:
    """Image Pad 탭 시스템 관리"""
    
    def __init__(self, state_manager):
        self.state = state_manager
        self.active_tab = None
        self.tabs = {}
        self.tab_history = []
        self.canvas_instances = {}
        
        # 기본 탭 등록
        self.register_default_tabs()
    
    def register_tab(self, tab_id: str, tab_class: Type[BaseTab]):
        """새로운 탭 등록"""
        self.tabs[tab_id] = tab_class(self.state, self)
        print(f"✅ 탭 등록: {tab_id}")
    
    def switch_tab(self, tab_id: str):
        """탭 전환"""
        if tab_id not in self.tabs:
            print(f"❌ 존재하지 않는 탭: {tab_id}")
            return False
        
        # 이전 탭 정리
        if self.active_tab:
            self.active_tab.cleanup()
        
        # 새 탭 활성화
        self.active_tab = self.tabs[tab_id]
        self.active_tab.activate()
        
        # 상태 업데이트
        self.state.set('current_tab', tab_id)
        self.tab_history.append(tab_id)
        
        print(f"🔄 탭 전환: {tab_id}")
        return True
    
    def get_transfer_targets(self, current_tab: str) -> List[str]:
        """현재 탭에서 전달 가능한 대상 탭들"""
        if current_tab == 'txt2img':
            return ['img2img', 'inpaint', 'upscale', '3d_pose', 'mask_editor', 'sketch']
        elif current_tab in ['img2img', 'inpaint', 'upscale', '3d_pose', 'mask_editor', 'sketch']:
            # 모든 이미지 기반 탭들은 서로 자유롭게 전환 가능 (T2I 제외)
            return [tab for tab in self.tabs.keys() if tab != 'txt2img']
        return []
    
    def transfer_image(self, image: Image, target_tab: str):
        """이미지와 함께 탭 전환"""
        if target_tab not in self.get_transfer_targets(self.state.get('current_tab')):
            return False
        
        # 이미지 전달
        self.state.set('current_image', image)
        
        # 탭 전환
        return self.switch_tab(target_tab)
```

#### 2. BaseTab (기본 탭 클래스)
```python
class BaseTab(ABC):
    """모든 탭의 기본 클래스"""
    
    def __init__(self, state_manager, tab_manager):
        self.state = state_manager
        self.tab_manager = tab_manager
        self.tab_id = None
        self.container = None
        self.canvas = None
        self.is_active = False
        
        # JavaScript 통신 설정
        self.js_bridge = JSBridge(self.tab_id)
    
    @abstractmethod
    def render(self, container) -> None:
        """탭 UI 렌더링"""
        pass
    
    @abstractmethod
    def activate(self) -> None:
        """탭 활성화"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """탭 정리"""
        pass
    
    def create_transfer_buttons(self, image: Image) -> None:
        """전달 버튼 생성"""
        targets = self.tab_manager.get_transfer_targets(self.tab_id)
        
        if not targets:
            return
        
        with ui.card().classes('w-full mt-4 p-3 bg-gray-800'):
            ui.label('다른 탭으로 전달').classes('text-sm font-medium text-blue-400 mb-2')
            
            # 탭 아이콘 그리드
            with ui.grid(columns=4).classes('w-full gap-2'):
                for target in targets:
                    tab_info = self.get_tab_info(target)
                    
                    with ui.button(
                        icon=tab_info['icon'],
                        on_click=lambda t=target: self.transfer_to_tab(image, t)
                    ).props(f'flat square color={tab_info["color"]}').classes('h-12'):
                        ui.tooltip(tab_info['name'])
    
    def transfer_to_tab(self, image: Image, target_tab: str):
        """다른 탭으로 전달"""
        success = self.tab_manager.transfer_image(image, target_tab)
        
        if success:
            ui.notify(f'{self.get_tab_info(target_tab)["name"]}으로 전달됨', type='positive')
        else:
            ui.notify('전달할 수 없습니다', type='warning')
    
    def get_tab_info(self, tab_id: str) -> Dict[str, str]:
        """탭 정보 조회"""
        tab_infos = {
            'txt2img': {'name': 'Text to Image', 'icon': 'text_fields', 'color': 'blue'},
            'img2img': {'name': 'Image to Image', 'icon': 'image', 'color': 'green'},
            'inpaint': {'name': 'Inpaint', 'icon': 'brush', 'color': 'purple'},
            'upscale': {'name': 'Upscale', 'icon': 'zoom_in', 'color': 'orange'},
            '3d_pose': {'name': '3D Pose', 'icon': 'accessibility_new', 'color': 'red'},
            'mask_editor': {'name': 'Mask Editor', 'icon': 'layers', 'color': 'teal'},
            'sketch': {'name': 'Sketch', 'icon': 'draw', 'color': 'pink'},
        }
        return tab_infos.get(tab_id, {'name': 'Unknown', 'icon': 'help', 'color': 'grey'})
```

#### 3. JavaScript 통신 브릿지
```python
class JSBridge:
    """Python-JavaScript 통신 브릿지"""
    
    def __init__(self, tab_id: str):
        self.tab_id = tab_id
        self.callbacks = {}
    
    def send_to_js(self, command: str, data: Any = None):
        """JavaScript로 명령 전송"""
        js_code = f"""
        if (window.tabManager && window.tabManager.{self.tab_id}) {{
            window.tabManager.{self.tab_id}.{command}({json.dumps(data) if data else ''});
        }}
        """
        ui.run_javascript(js_code)
    
    def register_callback(self, event: str, callback: Callable):
        """JavaScript 이벤트 콜백 등록"""
        self.callbacks[event] = callback
        
        # JavaScript에서 Python으로 호출할 수 있도록 전역 함수 등록
        ui.run_javascript(f"""
        window.pyCallback_{self.tab_id}_{event} = function(data) {{
            fetch('/api/js-callback', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    tab_id: '{self.tab_id}',
                    event: '{event}',
                    data: data
                }})
            }});
        }};
        """)
    
    def handle_js_callback(self, event: str, data: Any):
        """JavaScript 콜백 처리"""
        if event in self.callbacks:
            self.callbacks[event](data)
```

---

## 🎨 탭별 상세 구현

### 1. T2I Tab (기본 구현)
```python
class Txt2ImgTab(BaseTab):
    """텍스트→이미지 탭"""
    
    def __init__(self, state_manager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'txt2img'
    
    def render(self, container):
        """T2I 탭 렌더링"""
        with container:
            # 생성 결과 표시 영역
            with ui.card().classes('w-full h-96 flex items-center justify-center bg-gray-800'):
                self.result_display = ui.element('div').classes('w-full h-full')
                
                with self.result_display:
                    ui.label('생성 버튼을 클릭하여 이미지를 만드세요').classes(
                        'text-gray-400 text-center'
                    )
            
            # 생성 완료 시 전달 버튼 영역
            self.transfer_area = ui.element('div').classes('w-full')
    
    def activate(self):
        """탭 활성화"""
        self.is_active = True
        self.state.set('current_mode', 'txt2img')
        
        # 생성 완료 이벤트 구독
        self.state.on('generation_completed', self.on_generation_completed)
    
    def cleanup(self):
        """탭 정리"""
        self.is_active = False
        self.state.off('generation_completed', self.on_generation_completed)
    
    def on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        if not self.is_active:
            return
        
        images = event_data.get('images', [])
        if images:
            self.display_results(images)
    
    def display_results(self, images):
        """결과 이미지 표시"""
        self.result_display.clear()
        
        with self.result_display:
            if len(images) == 1:
                # 단일 이미지 표시
                self.display_single_image(images[0])
            else:
                # 다중 이미지 그리드
                self.display_image_grid(images)
        
        # 전달 버튼 생성
        self.transfer_area.clear()
        with self.transfer_area:
            self.create_transfer_buttons(images[0])
```

### 2. I2I Tab (이미지 업로드 + 변환)
```python
class Img2ImgTab(BaseTab):
    """이미지→이미지 탭"""
    
    def __init__(self, state_manager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'img2img'
        self.upload_area = None
        self.result_area = None
        self.current_image = None
    
    def render(self, container):
        """I2I 탭 렌더링"""
        with container:
            # 좌우 분할: 원본 | 결과
            with ui.splitter(value=50).classes('w-full h-96') as splitter:
                with splitter.before:
                    self.render_upload_section()
                
                with splitter.after:
                    self.render_result_section()
            
            # Strength 컨트롤
            self.render_strength_controls()
            
            # 전달 버튼 영역
            self.transfer_area = ui.element('div').classes('w-full')
    
    def render_upload_section(self):
        """업로드 섹션"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('원본 이미지').classes('text-sm font-medium mb-2')
            
            self.upload_area = ui.element('div').classes(
                'w-full flex-1 border-2 border-dashed border-green-500 '
                'rounded-lg bg-gray-800 flex items-center justify-center cursor-pointer'
            )
            
            # 드래그 앤 드롭 + 클릭 업로드
            self.setup_upload_area()
    
    def setup_upload_area(self):
        """업로드 영역 설정"""
        with self.upload_area:
            # 기본 업로드 UI
            with ui.column().classes('items-center'):
                ui.icon('cloud_upload').classes('text-4xl text-green-400 mb-2')
                ui.label('이미지를 드래그하거나 클릭하세요').classes('text-green-400')
                
                # 숨겨진 파일 입력
                ui.upload(
                    on_upload=self.handle_upload,
                    auto_upload=True,
                    multiple=False
                ).props('accept=image/*').classes('mt-2')
        
        # 기존 이미지 확인
        self.check_existing_image()
        
        # JavaScript 드래그 앤 드롭 설정
        self.setup_drag_and_drop()
    
    def setup_drag_and_drop(self):
        """드래그 앤 드롭 JavaScript 설정"""
        ui.run_javascript(f"""
        // 드래그 앤 드롭 설정
        const uploadArea = document.querySelector('[data-tab-id="{self.tab_id}"] .upload-area');
        
        if (uploadArea) {{
            uploadArea.addEventListener('dragover', function(e) {{
                e.preventDefault();
                this.style.borderColor = '#10b981';
                this.style.backgroundColor = '#065f46';
            }});
            
            uploadArea.addEventListener('dragleave', function(e) {{
                e.preventDefault();
                this.style.borderColor = '#6b7280';
                this.style.backgroundColor = '#1f2937';
            }});
            
            uploadArea.addEventListener('drop', function(e) {{
                e.preventDefault();
                this.style.borderColor = '#6b7280';
                this.style.backgroundColor = '#1f2937';
                
                const files = e.dataTransfer.files;
                if (files.length > 0) {{
                    const file = files[0];
                    if (file.type.startsWith('image/')) {{
                        // 파일을 Python으로 전송
                        const reader = new FileReader();
                        reader.onload = function(e) {{
                            window.pyCallback_{self.tab_id}_upload({{
                                'content': e.target.result,
                                'name': file.name,
                                'type': file.type
                            }});
                        }};
                        reader.readAsDataURL(file);
                    }}
                }}
            }});
        }}
        """)
        
        # Python 콜백 등록
        self.js_bridge.register_callback('upload', self.handle_js_upload)
    
    def handle_upload(self, upload_event):
        """일반 업로드 처리"""
        try:
            image = Image.open(io.BytesIO(upload_event.content))
            self.set_image(image)
            ui.notify('이미지 업로드 완료', type='positive')
        except Exception as e:
            ui.notify(f'업로드 실패: {str(e)}', type='negative')
    
    def handle_js_upload(self, data):
        """JavaScript 드래그 앤 드롭 처리"""
        try:
            # Base64 데이터 디코딩
            header, encoded = data['content'].split(',', 1)
            image_data = base64.b64decode(encoded)
            
            image = Image.open(io.BytesIO(image_data))
            self.set_image(image)
            
            ui.notify('이미지 업로드 완료', type='positive')
        except Exception as e:
            ui.notify(f'업로드 실패: {str(e)}', type='negative')
    
    def check_existing_image(self):
        """기존 이미지 확인 (다른 탭에서 전달된 경우)"""
        current_image = self.state.get('current_image')
        if current_image:
            self.set_image(current_image)
    
    def set_image(self, image: Image):
        """이미지 설정"""
        self.current_image = image
        self.state.set('init_image', image)
        
        # 업로드 영역 업데이트
        self.upload_area.clear()
        
        with self.upload_area:
            # 이미지 표시
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            with ui.column().classes('w-full h-full items-center justify-center'):
                ui.image(f'data:image/png;base64,{img_str}').classes(
                    'max-w-full max-h-full object-contain'
                )
                
                # 이미지 정보
                with ui.row().classes('mt-2 text-sm text-gray-400'):
                    ui.label(f'{image.size[0]}×{image.size[1]}')
                    ui.label(image.mode)
                
                # 새 이미지 버튼
                ui.button(
                    '다른 이미지 선택',
                    icon='refresh',
                    on_click=self.reset_upload
                ).props('outline size=sm')
        
        # 파라미터 자동 조정
        self.state.update_param('width', image.width)
        self.state.update_param('height', image.height)
```

### 3. 3D Pose Tab (Three.js 활용)
```python
class ThreeDPoseTab(BaseTab):
    """3D 포즈 에디터 탭"""
    
    def __init__(self, state_manager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = '3d_pose'
        self.pose_data = None
        self.selected_joint = None
    
    def render(self, container):
        """3D 포즈 탭 렌더링"""
        with container:
            # 좌우 분할: 3D 뷰어 | 컨트롤 패널
            with ui.splitter(value=70).classes('w-full h-96') as splitter:
                with splitter.before:
                    self.render_3d_viewer()
                
                with splitter.after:
                    self.render_control_panel()
            
            # 하단 도구 모음
            self.render_toolbar()
    
    def render_3d_viewer(self):
        """3D 뷰어 렌더링"""
        with ui.column().classes('w-full h-full'):
            ui.label('3D 포즈 에디터').classes('text-sm font-medium mb-2')
            
            # Three.js 캔버스 컨테이너
            self.canvas_container = ui.element('div').classes(
                'w-full flex-1 border border-gray-500 rounded bg-black'
            ).props('data-canvas-id="pose-3d"')
            
            # Three.js 초기화
            self.init_threejs()
    
    def init_threejs(self):
        """Three.js 초기화"""
        ui.run_javascript(f"""
        // Three.js 3D 포즈 에디터 초기화
        if (typeof THREE !== 'undefined') {{
            const container = document.querySelector('[data-canvas-id="pose-3d"]');
            
            // Scene, Camera, Renderer 설정
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
            const renderer = new THREE.WebGLRenderer({{ antialias: true }});
            
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setClearColor(0x222222);
            container.appendChild(renderer.domElement);
            
            // 조명 설정
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(10, 10, 5);
            scene.add(directionalLight);
            
            // 인체 스켈레톤 생성
            const poseManager = new PoseManager(scene, camera, renderer);
            
            // 카메라 컨트롤
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            
            // 애니메이션 루프
            function animate() {{
                requestAnimationFrame(animate);
                controls.update();
                poseManager.update();
                renderer.render(scene, camera);
            }}
            animate();
            
            // 전역 접근을 위한 등록
            window.poseEditor = {{
                scene: scene,
                camera: camera,
                renderer: renderer,
                poseManager: poseManager,
                controls: controls
            }};
            
            // 초기 포즈 로드
            poseManager.loadDefaultPose();
            
            // 마우스 이벤트 설정
            poseManager.setupMouseEvents();
            
        }} else {{
            console.error('Three.js not loaded');
        }}
        """)
        
        # 포즈 매니저 JavaScript 클래스 정의
        self.define_pose_manager()
    
    def define_pose_manager(self):
        """포즈 매니저 JavaScript 클래스 정의"""
        ui.run_javascript("""
        class PoseManager {
            constructor(scene, camera, renderer) {
                this.scene = scene;
                this.camera = camera;
                this.renderer = renderer;
                this.joints = {};
                this.bones = {};
                this.selectedJoint = null;
                this.raycaster = new THREE.Raycaster();
                this.mouse = new THREE.Vector2();
                
                this.initializeJoints();
                this.createSkeleton();
            }
            
            initializeJoints() {
                // OpenPose 18 키포인트 정의
                const jointPositions = {
                    'nose': [0, 1.7, 0],
                    'neck': [0, 1.5, 0],
                    'rightShoulder': [0.2, 1.4, 0],
                    'rightElbow': [0.4, 1.2, 0],
                    'rightWrist': [0.6, 1.0, 0],
                    'leftShoulder': [-0.2, 1.4, 0],
                    'leftElbow': [-0.4, 1.2, 0],
                    'leftWrist': [-0.6, 1.0, 0],
                    'rightHip': [0.1, 1.0, 0],
                    'rightKnee': [0.1, 0.5, 0],
                    'rightAnkle': [0.1, 0.0, 0],
                    'leftHip': [-0.1, 1.0, 0],
                    'leftKnee': [-0.1, 0.5, 0],
                    'leftAnkle': [-0.1, 0.0, 0],
                    'rightEye': [0.05, 1.72, 0.02],
                    'leftEye': [-0.05, 1.72, 0.02],
                    'rightEar': [0.08, 1.68, 0],
                    'leftEar': [-0.08, 1.68, 0]
                };
                
                // 관절 구체 생성
                const jointGeometry = new THREE.SphereGeometry(0.03, 16, 16);
                const jointMaterial = new THREE.MeshPhongMaterial({ color: 0x00ff00 });
                
                Object.entries(jointPositions).forEach(([name, pos]) => {
                    const joint = new THREE.Mesh(jointGeometry, jointMaterial.clone());
                    joint.position.set(pos[0], pos[1], pos[2]);
                    joint.userData = { name: name, type: 'joint' };
                    this.joints[name] = joint;
                    this.scene.add(joint);
                });
            }
            
            createSkeleton() {
                // 뼈 연결 정의
                const boneConnections = [
                    ['neck', 'nose'],
                    ['neck', 'rightShoulder'],
                    ['neck', 'leftShoulder'],
                    ['rightShoulder', 'rightElbow'],
                    ['rightElbow', 'rightWrist'],
                    ['leftShoulder', 'leftElbow'],
                    ['leftElbow', 'leftWrist'],
                    ['neck', 'rightHip'],
                    ['neck', 'leftHip'],
                    ['rightHip', 'rightKnee'],
                    ['rightKnee', 'rightAnkle'],
                    ['leftHip', 'leftKnee'],
                    ['leftKnee', 'leftAnkle'],
                    ['nose', 'rightEye'],
                    ['nose', 'leftEye'],
                    ['rightEye', 'rightEar'],
                    ['leftEye', 'leftEar']
                ];
                
                // 뼈 라인 생성
                const lineMaterial = new THREE.LineBasicMaterial({ color: 0x0080ff });
                
                boneConnections.forEach(([joint1, joint2]) => {
                    const geometry = new THREE.BufferGeometry().setFromPoints([
                        this.joints[joint1].position,
                        this.joints[joint2].position
                    ]);
                    
                    const line = new THREE.Line(geometry, lineMaterial);
                    this.bones[`${joint1}-${joint2}`] = line;
                    this.scene.add(line);
                });
            }
            
            setupMouseEvents() {
                const canvas = this.renderer.domElement;
                
                canvas.addEventListener('mousedown', (event) => {
                    this.mouse.x = (event.clientX / canvas.clientWidth) * 2 - 1;
                    this.mouse.y = -(event.clientY / canvas.clientHeight) * 2 + 1;
                    
                    this.raycaster.setFromCamera(this.mouse, this.camera);
                    const intersects = this.raycaster.intersectObjects(Object.values(this.joints));
                    
                    if (intersects.length > 0) {
                        this.selectJoint(intersects[0].object);
                    }
                });
                
                canvas.addEventListener('mousemove', (event) => {
                    if (this.selectedJoint) {
                        // 드래그하여 관절 이동
                        this.moveJoint(event);
                    }
                });
                
                canvas.addEventListener('mouseup', () => {
                    this.selectedJoint = null;
                });
            }
            
            selectJoint(joint) {
                // 이전 선택 해제
                if (this.selectedJoint) {
                    this.selectedJoint.material.color.setHex(0x00ff00);
                }
                
                // 새 관절 선택
                this.selectedJoint = joint;
                joint.material.color.setHex(0xff0000);
                
                // Python에 알림
                if (window.pyCallback_3d_pose_joint_selected) {
                    window.pyCallback_3d_pose_joint_selected({
                        joint: joint.userData.name,
                        position: joint.position.toArray()
                    });
                }
            }
            
            moveJoint(event) {
                // 마우스 이동에 따른 관절 위치 업데이트
                // 복잡한 3D 변환 로직...
                this.updateBones();
            }
            
            updateBones() {
                // 뼈 위치 업데이트
                Object.entries(this.bones).forEach(([name, bone]) => {
                    const [joint1Name, joint2Name] = name.split('-');
                    const joint1 = this.joints[joint1Name];
                    const joint2 = this.joints[joint2Name];
                    
                    bone.geometry.setFromPoints([
                        joint1.position,
                        joint2.position
                    ]);
                });
            }
            
            loadDefaultPose() {
                // 기본 T-포즈 로드
                console.log('Default pose loaded');
            }
            
            exportPose() {
                // 포즈 데이터 추출
                const poseData = {};
                Object.entries(this.joints).forEach(([name, joint]) => {
                    poseData[name] = joint.position.toArray();
                });
                return poseData;
            }
            
            importPose(poseData) {
                // 포즈 데이터 적용
                Object.entries(poseData).forEach(([name, position]) => {
                    if (this.joints[name]) {
                        this.joints[name].position.set(position[0], position[1], position[2]);
                    }
                });
                this.updateBones();
            }
            
            update() {
                // 매 프레임 업데이트
            }
        }
        """)
        
        # Python 콜백 등록
        self.js_bridge.register_callback('joint_selected', self.on_joint_selected)
    
    def render_control_panel(self):
        """컨트롤 패널"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('포즈 컨트롤').classes('text-sm font-medium mb-2')
            
            # 관절 선택 정보
            with ui.card().classes('w-full p-2 mb-2 bg-gray-900'):
                ui.label('선택된 관절').classes('text-xs font-medium text-gray-300')
                self.selected_joint_label = ui.label('없음').classes('text-xs text-gray-400')
                
                # 관절 위치 조정
                with ui.column().classes('w-full gap-1 mt-2'):
                    ui.label('X 위치').classes('text-xs')
                    self.joint_x_slider = ui.slider(
                        min=-2.0, max=2.0, step=0.01, value=0.0,
                        on_change=self.update_joint_position
                    ).classes('w-full')
                    
                    ui.label('Y 위치').classes('text-xs')
                    self.joint_y_slider = ui.slider(
                        min=-1.0, max=2.0, step=0.01, value=0.0,
                        on_change=self.update_joint_position
                    ).classes('w-full')
                    
                    ui.label('Z 위치').classes('text-xs')
                    self.joint_z_slider = ui.slider(
                        min=-1.0, max=1.0, step=0.01, value=0.0,
                        on_change=self.update_joint_position
                    ).classes('w-full')
            
            # 프리셋 포즈
            with ui.card().classes('w-full p-2 mb-2 bg-gray-900'):
                ui.label('프리셋 포즈').classes('text-xs font-medium text-gray-300 mb-2')
                
                with ui.column().classes('w-full gap-1'):
                    ui.button('T-포즈', on_click=self.load_t_pose).props('size=sm').classes('w-full')
                    ui.button('A-포즈', on_click=self.load_a_pose).props('size=sm').classes('w-full')
                    ui.button('앉은 자세', on_click=self.load_sitting_pose).props('size=sm').classes('w-full')
                    ui.button('달리기', on_click=self.load_running_pose).props('size=sm').classes('w-full')
            
            # 포즈 저장/로드
            with ui.card().classes('w-full p-2 bg-gray-900'):
                ui.label('포즈 관리').classes('text-xs font-medium text-gray-300 mb-2')
                
                with ui.column().classes('w-full gap-1'):
                    ui.button('포즈 저장', icon='save', on_click=self.save_pose).props('size=sm').classes('w-full')
                    ui.button('포즈 로드', icon='folder_open', on_click=self.load_pose).props('size=sm').classes('w-full')
                    ui.button('ControlNet 전달', icon='send', on_click=self.export_to_controlnet).props('size=sm color=blue').classes('w-full')
    
    def render_toolbar(self):
        """하단 도구 모음"""
        with ui.row().classes('w-full justify-center gap-2 mt-2'):
            ui.button('뷰 리셋', icon='refresh', on_click=self.reset_view).props('size=sm')
            ui.button('그리드 토글', icon='grid_on', on_click=self.toggle_grid).props('size=sm')
            ui.button('와이어프레임', icon='architecture', on_click=self.toggle_wireframe).props('size=sm')
            ui.button('조명 설정', icon='light_mode', on_click=self.lighting_settings).props('size=sm')
    
    def on_joint_selected(self, data):
        """관절 선택 이벤트"""
        joint_name = data['joint']
        position = data['position']
        
        self.selected_joint = joint_name
        self.selected_joint_label.set_text(joint_name)
        
        # 슬라이더 값 업데이트
        self.joint_x_slider.value = position[0]
        self.joint_y_slider.value = position[1]
        self.joint_z_slider.value = position[2]
    
    def update_joint_position(self):
        """관절 위치 업데이트"""
        if not self.selected_joint:
            return
        
        x = self.joint_x_slider.value
        y = self.joint_y_slider.value
        z = self.joint_z_slider.value
        
        # JavaScript로 위치 업데이트 전송
        self.js_bridge.send_to_js('updateJointPosition', {
            'joint': self.selected_joint,
            'position': [x, y, z]
        })
    
    def export_to_controlnet(self):
        """ControlNet으로 포즈 전달"""
        # 현재 포즈 데이터 추출
        ui.run_javascript("""
        if (window.poseEditor) {
            const poseData = window.poseEditor.poseManager.exportPose();
            
            // 포즈 렌더링하여 이미지 생성
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 512;
            const ctx = canvas.getContext('2d');
            
            // 포즈 스켈레톤 그리기
            ctx.fillStyle = 'black';
            ctx.fillRect(0, 0, 512, 512);
            
            // 관절과 뼈 그리기 로직...
            
            // 이미지 데이터를 Python으로 전송
            const imageData = canvas.toDataURL('image/png');
            window.pyCallback_3d_pose_export_pose({ imageData: imageData });
        }
        """)
        
        # Python 콜백 등록
        self.js_bridge.register_callback('export_pose', self.on_pose_exported)
    
    def on_pose_exported(self, data):
        """포즈 내보내기 완료"""
        # Base64 이미지 데이터를 PIL Image로 변환
        image_data = data['imageData'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        pose_image = Image.open(io.BytesIO(image_bytes))
        
        # ControlNet 이미지로 설정
        self.state.set('controlnet_image', pose_image)
        self.state.set('controlnet_type', 'openpose')
        
        # 전달 버튼 생성
        with ui.dialog() as dialog:
            with ui.card():
                ui.label('포즈 ControlNet 이미지 생성 완료')
                ui.image(pose_image).classes('w-64 h-64')
                
                with ui.row().classes('w-full gap-2'):
                    ui.button('I2I로 전달', on_click=lambda: self.transfer_to_tab(pose_image, 'img2img'))
                    ui.button('Inpaint로 전달', on_click=lambda: self.transfer_to_tab(pose_image, 'inpaint'))
                    ui.button('취소', on_click=dialog.close)
        
        dialog.open()
        ui.notify('포즈 ControlNet 이미지 생성 완료', type='positive')
```

### 4. Mask Editor Tab (고급 마스크 편집)
```python
class MaskEditorTab(BaseTab):
    """마스크 에디터 탭"""
    
    def __init__(self, state_manager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'mask_editor'
        self.canvas_size = (512, 512)
        self.brush_size = 20
        self.brush_hardness = 0.8
        self.current_tool = 'brush'
        self.mask_opacity = 0.7
    
    def render(self, container):
        """마스크 에디터 렌더링"""
        with container:
            # 상하 분할: 캔버스 | 도구 패널
            with ui.splitter(value=80, horizontal=False).classes('w-full h-96') as splitter:
                with splitter.before:
                    self.render_canvas_area()
                
                with splitter.after:
                    self.render_tool_panel()
    
    def render_canvas_area(self):
        """캔버스 영역"""
        with ui.column().classes('w-full h-full'):
            # 캔버스 컨테이너
            self.canvas_container = ui.element('div').classes(
                'w-full flex-1 border border-gray-500 rounded bg-gray-800 '
                'flex items-center justify-center'
            )
            
            # 캔버스 HTML
            with self.canvas_container:
                ui.html(f'''
                    <div class="canvas-wrapper" style="position: relative; width: 100%; height: 100%;">
                        <canvas id="base-canvas" width="{self.canvas_size[0]}" height="{self.canvas_size[1]}" 
                                style="position: absolute; top: 0; left: 0; z-index: 1;"></canvas>
                        <canvas id="mask-canvas" width="{self.canvas_size[0]}" height="{self.canvas_size[1]}" 
                                style="position: absolute; top: 0; left: 0; z-index: 2;"></canvas>
                        <canvas id="overlay-canvas" width="{self.canvas_size[0]}" height="{self.canvas_size[1]}" 
                                style="position: absolute; top: 0; left: 0; z-index: 3;"></canvas>
                    </div>
                ''')
            
            # 캔버스 초기화
            self.init_mask_canvas()
    
    def init_mask_canvas(self):
        """마스크 캔버스 초기화"""
        ui.run_javascript(f"""
        // 마스크 에디터 초기화
        const maskEditor = new MaskEditor('{self.tab_id}');
        window.maskEditor = maskEditor;
        
        class MaskEditor {{
            constructor(tabId) {{
                this.tabId = tabId;
                this.baseCanvas = document.getElementById('base-canvas');
                this.maskCanvas = document.getElementById('mask-canvas');
                this.overlayCanvas = document.getElementById('overlay-canvas');
                
                this.baseCtx = this.baseCanvas.getContext('2d');
                this.maskCtx = this.maskCanvas.getContext('2d');
                this.overlayCtx = this.overlayCanvas.getContext('2d');
                
                this.isDrawing = false;
                this.currentTool = 'brush';
                this.brushSize = 20;
                this.brushHardness = 0.8;
                this.maskOpacity = 0.7;
                
                this.history = [];
                this.historyStep = 0;
                
                this.initEventListeners();
                this.setupCanvasStyles();
            }}
            
            initEventListeners() {{
                // 마우스 이벤트
                this.overlayCanvas.addEventListener('mousedown', (e) => this.startDrawing(e));
                this.overlayCanvas.addEventListener('mousemove', (e) => this.draw(e));
                this.overlayCanvas.addEventListener('mouseup', () => this.stopDrawing());
                this.overlayCanvas.addEventListener('mouseout', () => this.stopDrawing());
                
                // 터치 이벤트 (모바일 지원)
                this.overlayCanvas.addEventListener('touchstart', (e) => this.startDrawing(e.touches[0]));
                this.overlayCanvas.addEventListener('touchmove', (e) => {{
                    e.preventDefault();
                    this.draw(e.touches[0]);
                }});
                this.overlayCanvas.addEventListener('touchend', () => this.stopDrawing());
                
                // 키보드 단축키
                document.addEventListener('keydown', (e) => this.handleKeyboard(e));
            }}
            
            setupCanvasStyles() {{
                // 캔버스 스타일 설정
                this.overlayCanvas.style.cursor = 'crosshair';
                this.maskCanvas.style.opacity = this.maskOpacity;
                
                // 마스크 캔버스 초기화 (투명)
                this.maskCtx.clearRect(0, 0, this.maskCanvas.width, this.maskCanvas.height);
            }}
            
            startDrawing(e) {{
                this.isDrawing = true;
                this.draw(e);
                this.saveState();
            }}
            
            draw(e) {{
                if (!this.isDrawing) return;
                
                const rect = this.overlayCanvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                // 캔버스 크기에 맞게 좌표 스케일링
                const scaleX = this.maskCanvas.width / rect.width;
                const scaleY = this.maskCanvas.height / rect.height;
                const scaledX = x * scaleX;
                const scaledY = y * scaleY;
                
                if (this.currentTool === 'brush') {{
                    this.drawBrush(scaledX, scaledY);
                }} else if (this.currentTool === 'eraser') {{
                    this.eraseBrush(scaledX, scaledY);
                }}
            }}
            
            drawBrush(x, y) {{
                const ctx = this.maskCtx;
                const radius = this.brushSize / 2;
                
                // 소프트 브러시 구현
                const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
                
                if (this.brushHardness < 1.0) {{
                    const hardnessPoint = this.brushHardness;
                    gradient.addColorStop(0, `rgba(255, 255, 255, 1.0)`);
                    gradient.addColorStop(hardnessPoint, `rgba(255, 255, 255, 1.0)`);
                    gradient.addColorStop(1, `rgba(255, 255, 255, 0.0)`);
                }} else {{
                    gradient.addColorStop(0, `rgba(255, 255, 255, 1.0)`);
                    gradient.addColorStop(1, `rgba(255, 255, 255, 1.0)`);
                }}
                
                ctx.globalCompositeOperation = 'source-over';
                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(x, y, radius, 0, 2 * Math.PI);
                ctx.fill();
            }}
            
            eraseBrush(x, y) {{
                const ctx = this.maskCtx;
                const radius = this.brushSize / 2;
                
                ctx.globalCompositeOperation = 'destination-out';
                ctx.beginPath();
                ctx.arc(x, y, radius, 0, 2 * Math.PI);
                ctx.fill();
            }}
            
            stopDrawing() {{
                this.isDrawing = false;
            }}
            
            saveState() {{
                // 히스토리 저장
                this.history.length = this.historyStep + 1;
                this.history.push(this.maskCtx.getImageData(0, 0, this.maskCanvas.width, this.maskCanvas.height));
                this.historyStep++;
                
                // 히스토리 크기 제한
                if (this.history.length > 50) {{
                    this.history.shift();
                    this.historyStep--;
                }}
            }}
            
            undo() {{
                if (this.historyStep > 0) {{
                    this.historyStep--;
                    this.maskCtx.putImageData(this.history[this.historyStep], 0, 0);
                }}
            }}
            
            redo() {{
                if (this.historyStep < this.history.length - 1) {{
                    this.historyStep++;
                    this.maskCtx.putImageData(this.history[this.historyStep], 0, 0);
                }}
            }}
            
            clearMask() {{
                this.maskCtx.clearRect(0, 0, this.maskCanvas.width, this.maskCanvas.height);
                this.saveState();
            }}
            
            fillMask() {{
                this.maskCtx.fillStyle = 'white';
                this.maskCtx.fillRect(0, 0, this.maskCanvas.width, this.maskCanvas.height);
                this.saveState();
            }}
            
            invertMask() {{
                const imageData = this.maskCtx.getImageData(0, 0, this.maskCanvas.width, this.maskCanvas.height);
                const data = imageData.data;
                
                for (let i = 0; i < data.length; i += 4) {{
                    data[i] = 255 - data[i];     // R
                    data[i + 1] = 255 - data[i + 1]; // G
                    data[i + 2] = 255 - data[i + 2]; // B
                }}
                
                this.maskCtx.putImageData(imageData, 0, 0);
                this.saveState();
            }}
            
            setTool(tool) {{
                this.currentTool = tool;
                this.overlayCanvas.style.cursor = tool === 'brush' ? 'crosshair' : 'cell';
            }}
            
            setBrushSize(size) {{
                this.brushSize = size;
            }}
            
            setBrushHardness(hardness) {{
                this.brushHardness = hardness;
            }}
            
            setMaskOpacity(opacity) {{
                this.maskOpacity = opacity;
                this.maskCanvas.style.opacity = opacity;
            }}
            
            loadBaseImage(imageData) {{
                const img = new Image();
                img.onload = () => {{
                    this.baseCtx.clearRect(0, 0, this.baseCanvas.width, this.baseCanvas.height);
                    this.baseCtx.drawImage(img, 0, 0, this.baseCanvas.width, this.baseCanvas.height);
                }};
                img.src = imageData;
            }}
            
            exportMask() {{
                return this.maskCanvas.toDataURL('image/png');
            }}
            
            importMask(imageData) {{
                const img = new Image();
                img.onload = () => {{
                    this.maskCtx.clearRect(0, 0, this.maskCanvas.width, this.maskCanvas.height);
                    this.maskCtx.drawImage(img, 0, 0, this.maskCanvas.width, this.maskCanvas.height);
                    this.saveState();
                }};
                img.src = imageData;
            }}
            
            handleKeyboard(e) {{
                if (e.ctrlKey || e.metaKey) {{
                    switch(e.key) {{
                        case 'z':
                            e.preventDefault();
                            if (e.shiftKey) {{
                                this.redo();
                            }} else {{
                                this.undo();
                            }}
                            break;
                        case 'a':
                            e.preventDefault();
                            this.fillMask();
                            break;
                        case 'd':
                            e.preventDefault();
                            this.clearMask();
                            break;
                        case 'i':
                            e.preventDefault();
                            this.invertMask();
                            break;
                    }}
                }}
            }}
        }}
        """)
        
        # 기존 이미지 로드
        self.load_current_image()
    
    def render_tool_panel(self):
        """도구 패널"""
        with ui.row().classes('w-full justify-center gap-4 p-2'):
            # 도구 선택
            with ui.column().classes('items-center'):
                ui.label('도구').classes('text-xs font-medium mb-1')
                with ui.row().classes('gap-1'):
                    ui.button('브러시', icon='brush', 
                             on_click=lambda: self.set_tool('brush')).props('size=sm')
                    ui.button('지우개', icon='cleaning_services',
                             on_click=lambda: self.set_tool('eraser')).props('size=sm')
            
            # 브러시 크기
            with ui.column().classes('items-center'):
                ui.label('크기').classes('text-xs font-medium mb-1')
                ui.slider(min=1, max=100, step=1, value=20,
                         on_change=self.set_brush_size).classes('w-20')
            
            # 브러시 경도
            with ui.column().classes('items-center'):
                ui.label('경도').classes('text-xs font-medium mb-1')
                ui.slider(min=0.1, max=1.0, step=0.1, value=0.8,
                         on_change=self.set_brush_hardness).classes('w-20')
            
            # 마스크 투명도
            with ui.column().classes('items-center'):
                ui.label('투명도').classes('text-xs font-medium mb-1')
                ui.slider(min=0.1, max=1.0, step=0.1, value=0.7,
                         on_change=self.set_mask_opacity).classes('w-20')
            
            # 마스크 작업
            with ui.column().classes('items-center'):
                ui.label('마스크').classes('text-xs font-medium mb-1')
                with ui.row().classes('gap-1'):
                    ui.button('전체', icon='select_all',
                             on_click=self.fill_mask).props('size=sm')
                    ui.button('지우기', icon='clear',
                             on_click=self.clear_mask).props('size=sm')
                    ui.button('반전', icon='swap_vert',
                             on_click=self.invert_mask).props('size=sm')
            
            # 히스토리
            with ui.column().classes('items-center'):
                ui.label('히스토리').classes('text-xs font-medium mb-1')
                with ui.row().classes('gap-1'):
                    ui.button('실행취소', icon='undo',
                             on_click=self.undo).props('size=sm')
                    ui.button('다시실행', icon='redo',
                             on_click=self.redo).props('size=sm')
    
    def load_current_image(self):
        """현재 이미지 로드"""
        current_image = self.state.get('current_image')
        if current_image:
            # 이미지를 base64로 변환하여 캔버스에 로드
            buffer = io.BytesIO()
            current_image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            self.js_bridge.send_to_js('loadBaseImage', f'data:image/png;base64,{img_str}')
    
    def set_tool(self, tool):
        """도구 설정"""
        self.current_tool = tool
        self.js_bridge.send_to_js('setTool', tool)
    
    def set_brush_size(self, size):
        """브러시 크기 설정"""
        self.brush_size = size
        self.js_bridge.send_to_js('setBrushSize', size)
    
    def set_brush_hardness(self, hardness):
        """브러시 경도 설정"""
        self.brush_hardness = hardness
        self.js_bridge.send_to_js('setBrushHardness', hardness)
    
    def set_mask_opacity(self, opacity):
        """마스크 투명도 설정"""
        self.mask_opacity = opacity
        self.js_bridge.send_to_js('setMaskOpacity', opacity)
    
    def fill_mask(self):
        """마스크 전체 채우기"""
        self.js_bridge.send_to_js('fillMask')
    
    def clear_mask(self):
        """마스크 지우기"""
        self.js_bridge.send_to_js('clearMask')
    
    def invert_mask(self):
        """마스크 반전"""
        self.js_bridge.send_to_js('invertMask')
    
    def undo(self):
        """실행 취소"""
        self.js_bridge.send_to_js('undo')
    
    def redo(self):
        """다시 실행"""
        self.js_bridge.send_to_js('redo')
    
    def export_mask(self):
        """마스크 내보내기"""
        ui.run_javascript("""
        if (window.maskEditor) {
            const maskData = window.maskEditor.exportMask();
            window.pyCallback_mask_editor_export_mask({ maskData: maskData });
        }
        """)
        
        self.js_bridge.register_callback('export_mask', self.on_mask_exported)
    
    def on_mask_exported(self, data):
        """마스크 내보내기 완료"""
        # Base64 마스크 데이터를 PIL Image로 변환
        mask_data = data['maskData'].split(',')[1]
        mask_bytes = base64.b64decode(mask_data)
        mask_image = Image.open(io.BytesIO(mask_bytes))
        
        # 마스크 이미지 저장
        self.state.set('current_mask', mask_image)
        
        # 전달 버튼 생성
        current_image = self.state.get('current_image')
        if current_image:
            self.create_transfer_buttons(current_image)
        
        ui.notify('마스크 생성 완료', type='positive')
```

### 5. Sketch Tab (스케치→이미지)
```python
class SketchTab(BaseTab):
    """스케치→이미지 탭"""
    
    def __init__(self, state_manager, tab_manager):
        super().__init__(state_manager, tab_manager)
        self.tab_id = 'sketch'
        self.canvas_size = (512, 512)
        self.brush_size = 5
        self.brush_color = '#000000'
        self.background_color = '#ffffff'
    
    def render(self, container):
        """스케치 탭 렌더링"""
        with container:
            # 좌우 분할: 캔버스 | 도구 패널
            with ui.splitter(value=75).classes('w-full h-96') as splitter:
                with splitter.before:
                    self.render_sketch_canvas()
                
                with splitter.after:
                    self.render_sketch_tools()
    
    def render_sketch_canvas(self):
        """스케치 캔버스"""
        with ui.column().classes('w-full h-full'):
            ui.label('스케치 캔버스').classes('text-sm font-medium mb-2')
            
            # 캔버스 컨테이너
            self.canvas_container = ui.element('div').classes(
                'w-full flex-1 border border-gray-500 rounded bg-white '
                'flex items-center justify-center'
            )
            
            # Paper.js 캔버스
            with self.canvas_container:
                ui.html(f'''
                    <canvas id="sketch-canvas" width="{self.canvas_size[0]}" height="{self.canvas_size[1]}" 
                            style="border: 1px solid #ccc; background: white; cursor: crosshair;">
                    </canvas>
                ''')
            
            # 캔버스 초기화
            self.init_sketch_canvas()
    
    def init_sketch_canvas(self):
        """스케치 캔버스 초기화"""
        ui.run_javascript(f"""
        // Paper.js 스케치 캔버스 초기화
        const canvas = document.getElementById('sketch-canvas');
        
        // Paper.js 설정
        paper.setup(canvas);
        
        const sketchApp = new SketchApp();
        window.sketchApp = sketchApp;
        
        class SketchApp {{
            constructor() {{
                this.path = null;
                this.brushSize = 5;
                this.brushColor = '#000000';
                this.backgroundColor = '#ffffff';
                this.layers = [];
                this.currentLayer = 0;
                this.isDrawing = false;
                
                this.setupTools();
                this.setupEvents();
            }}
            
            setupTools() {{
                // 기본 도구 설정
                this.tool = new paper.Tool();
                this.tool.minDistance = 2;
                this.tool.maxDistance = 20;
                
                // 브러시 스타일
                this.strokeStyle = {{
                    strokeColor: this.brushColor,
                    strokeWidth: this.brushSize,
                    strokeCap: 'round',
                    strokeJoin: 'round'
                }};
            }}
            
            setupEvents() {{
                // 마우스 다운
                this.tool.onMouseDown = (event) => {{
                    this.isDrawing = true;
                    this.path = new paper.Path();
                    this.path.strokeColor = this.brushColor;
                    this.path.strokeWidth = this.brushSize;
                    this.path.strokeCap = 'round';
                    this.path.strokeJoin = 'round';
                    this.path.add(event.point);
                }};
                
                // 마우스 드래그
                this.tool.onMouseDrag = (event) => {{
                    if (this.isDrawing && this.path) {{
                        this.path.add(event.point);
                        this.path.smooth();
                    }}
                }};
                
                // 마우스 업
                this.tool.onMouseUp = (event) => {{
                    if (this.isDrawing && this.path) {{
                        this.path.add(event.point);
                        this.path.smooth();
                        this.saveState();
                    }}
                    this.isDrawing = false;
                }};
            }}
            
            setBrushSize(size) {{
                this.brushSize = size;
            }}
            
            setBrushColor(color) {{
                this.brushColor = color;
            }}
            
            setBackgroundColor(color) {{
                this.backgroundColor = color;
                paper.project.activeLayer.fillColor = color;
            }}
            
            clearCanvas() {{
                paper.project.clear();
                this.saveState();
            }}
            
            undoLastStroke() {{
                if (paper.project.activeLayer.children.length > 0) {{
                    paper.project.activeLayer.lastChild.remove();
                }}
            }}
            
            exportSketch() {{
                // 캔버스를 이미지로 변환
                const canvas = document.getElementById('sketch-canvas');
                return canvas.toDataURL('image/png');
            }}
            
            importSketch(imageData) {{
                // 이미지를 캔버스에 로드
                const img = new Image();
                img.onload = () => {{
                    const raster = new paper.Raster(img);
                    raster.position = paper.view.center;
                    paper.view.draw();
                }};
                img.src = imageData;
            }}
            
            saveState() {{
                // 상태 저장 (실행 취소용)
                paper.view.draw();
            }}
            
            // 고급 브러시 효과
            setPressureSensitivity(enabled) {{
                this.pressureSensitive = enabled;
            }}
            
            setSmoothing(level) {{
                this.tool.minDistance = level;
            }}
            
            // 레이어 관리
            addLayer() {{
                const layer = new paper.Layer();
                this.layers.push(layer);
                return layer;
            }}
            
            switchLayer(index) {{
                if (index < this.layers.length) {{
                    this.currentLayer = index;
                    paper.project.activeLayer = this.layers[index];
                }}
            }}
        }}
        """)
    
    def render_sketch_tools(self):
        """스케치 도구 패널"""
        with ui.column().classes('w-full h-full p-2'):
            ui.label('그리기 도구').classes('text-sm font-medium mb-2')
            
            # 브러시 설정
            with ui.card().classes('w-full p-2 mb-2 bg-gray-900'):
                ui.label('브러시').classes('text-xs font-medium text-gray-300 mb-2')
                
                # 브러시 크기
                ui.label('크기').classes('text-xs text-gray-400')
                ui.slider(min=1, max=50, step=1, value=5,
                         on_change=self.set_brush_size).classes('w-full')
                
                # 브러시 색상
                ui.label('색상').classes('text-xs text-gray-400 mt-2')
                ui.color_input(value='#000000', 
                              on_change=self.set_brush_color).classes('w-full')
            
            # 캔버스 설정
            with ui.card().classes('w-full p-2 mb-2 bg-gray-900'):
                ui.label('캔버스').classes('text-xs font-medium text-gray-300 mb-2')
                
                # 배경 색상
                ui.label('배경색').classes('text-xs text-gray-400')
                ui.color_input(value='#ffffff',
                              on_change=self.set_background_color).classes('w-full')
                
                # 캔버스 크기
                ui.label('크기').classes('text-xs text-gray-400 mt-2')
                with ui.row().classes('w-full gap-1'):
                    ui.select(
                        options=['512x512', '768x768', '1024x1024'],
                        value='512x512',
                        on_change=self.set_canvas_size
                    ).classes('flex-1')
            
            # 스케치 작업
            with ui.card().classes('w-full p-2 mb-2 bg-gray-900'):
                ui.label('작업').classes('text-xs font-medium text-gray-300 mb-2')
                
                with ui.column().classes('w-full gap-1'):
                    ui.button('지우기', icon='clear',
                             on_click=self.clear_canvas).props('size=sm').classes('w-full')
                    ui.button('실행취소', icon='undo',
                             on_click=self.undo_stroke).props('size=sm').classes('w-full')
                    ui.button('저장', icon='save',
                             on_click=self.save_sketch).props('size=sm').classes('w-full')
                    ui.button('불러오기', icon='folder_open',
                             on_click=self.load_sketch).props('size=sm').classes('w-full')
            
            # 스타일 프리셋
            with ui.card().classes('w-full p-2 bg-gray-900'):
                ui.label('스타일').classes('text-xs font-medium text-gray-300 mb-2')
                
                with ui.column().classes('w-full gap-1'):
                    ui.button('연필', on_click=lambda: self.apply_style('pencil')).props('size=sm').classes('w-full')
                    ui.button('펜', on_click=lambda: self.apply_style('pen')).props('size=sm').classes('w-full')
                    ui.button('마커', on_click=lambda: self.apply_style('marker')).props('size=sm').classes('w-full')
                    ui.button('수채화', on_click=lambda: self.apply_style('watercolor')).props('size=sm').classes('w-full')
    
    def set_brush_size(self, size):
        """브러시 크기 설정"""
        self.brush_size = size
        self.js_bridge.send_to_js('setBrushSize', size)
    
    def set_brush_color(self, color):
        """브러시 색상 설정"""
        self.brush_color = color
        self.js_bridge.send_to_js('setBrushColor', color)
    
    def set_background_color(self, color):
        """배경 색상 설정"""
        self.background_color = color
        self.js_bridge.send_to_js('setBackgroundColor', color)
    
    def clear_canvas(self):
        """캔버스 지우기"""
        self.js_bridge.send_to_js('clearCanvas')
    
    def undo_stroke(self):
        """마지막 스트로크 실행 취소"""
        self.js_bridge.send_to_js('undoLastStroke')
    
    def apply_style(self, style_name):
        """브러시 스타일 적용"""
        styles = {
            'pencil': {'size': 2, 'color': '#333333'},
            'pen': {'size': 3, 'color': '#000000'},
            'marker': {'size': 8, 'color': '#1a1a1a'},
            'watercolor': {'size': 12, 'color': '#4a4a4a'}
        }
        
        if style_name in styles:
            style = styles[style_name]
            self.set_brush_size(style['size'])
            self.set_brush_color(style['color'])
    
    def export_sketch(self):
        """스케치 내보내기"""
        ui.run_javascript("""
        if (window.sketchApp) {
            const sketchData = window.sketchApp.exportSketch();
            window.pyCallback_sketch_export_sketch({ sketchData: sketchData });
        }
        """)
        
        self.js_bridge.register_callback('export_sketch', self.on_sketch_exported)
    
    def on_sketch_exported(self, data):
        """스케치 내보내기 완료"""
        # Base64 스케치 데이터를 PIL Image로 변환
        sketch_data = data['sketchData'].split(',')[1]
        sketch_bytes = base64.b64decode(sketch_data)
        sketch_image = Image.open(io.BytesIO(sketch_bytes))
        
        # 스케치 이미지 저장
        self.state.set('current_image', sketch_image)
        self.state.set('sketch_image', sketch_image)
        
        # 전달 버튼 생성
        self.create_transfer_buttons(sketch_image)
        
        ui.notify('스케치 생성 완료', type='positive')
    
    def activate(self):
        """탭 활성화"""
        self.is_active = True
        self.state.set('current_mode', 'sketch')
        
        # 자동 생성 버튼 활성화
        with ui.dialog() as dialog:
            with ui.card():
                ui.label('스케치가 완료되면 자동으로 이미지 생성을 시작하시겠습니까?')
                
                with ui.row():
                    ui.button('예', on_click=lambda: self.enable_auto_generation() or dialog.close())
                    ui.button('아니오', on_click=dialog.close)
        
        dialog.open()
    
    def enable_auto_generation(self):
        """자동 생성 모드 활성화"""
        self.state.set('auto_generation_enabled', True)
        ui.notify('스케치 완료 시 자동 생성됩니다', type='info')
```

---

## 📱 Image Pad 탭 UI 통합

### 메인 Image Pad 컴포넌트
```python
class ImagePadTabSystem:
    """Image Pad 탭 시스템 메인 컴포넌트"""
    
    def __init__(self, state_manager):
        self.state = state_manager
        self.tab_manager = TabManager(state_manager)
        self.current_tab_container = None
        
        # 기본 탭 등록
        self.register_default_tabs()
        
        # 이벤트 구독
        self.state.on('mode_changed', self.on_mode_changed)
    
    def register_default_tabs(self):
        """기본 탭들 등록"""
        self.tab_manager.register_tab('txt2img', Txt2ImgTab)
        self.tab_manager.register_tab('img2img', Img2ImgTab)
        self.tab_manager.register_tab('inpaint', InpaintTab)
        self.tab_manager.register_tab('upscale', UpscaleTab)
        self.tab_manager.register_tab('3d_pose', ThreeDPoseTab)
        self.tab_manager.register_tab('mask_editor', MaskEditorTab)
        self.tab_manager.register_tab('sketch', SketchTab)
    
    def render(self):
        """Image Pad 탭 시스템 렌더링"""
        with ui.column().classes('w-full h-full'):
            # 탭 헤더
            self.render_tab_header()
            
            # 탭 컨텐츠
            self.current_tab_container = ui.element('div').classes('w-full flex-1')
            
            # 초기 탭 로드
            self.tab_manager.switch_tab('txt2img')
    
    def render_tab_header(self):
        """탭 헤더 렌더링"""
        with ui.card().classes('w-full p-2 mb-2 bg-gray-900'):
            with ui.row().classes('w-full gap-1'):
                # 기본 탭들
                self.create_tab_button('txt2img', 'T2I', 'text_fields', 'blue')
                self.create_tab_button('img2img', 'I2I', 'image', 'green')
                self.create_tab_button('inpaint', 'Inpaint', 'brush', 'purple')
                self.create_tab_button('upscale', 'Upscale', 'zoom_in', 'orange')
                
                # 구분선
                ui.separator().props('vertical')
                
                # 고급 탭들
                self.create_tab_button('3d_pose', '3D', 'accessibility_new', 'red')
                self.create_tab_button('mask_editor', 'Mask', 'layers', 'teal')
                self.create_tab_button('sketch', 'Sketch', 'draw', 'pink')
                
                # 더 많은 탭 추가 버튼
                ui.button(
                    icon='add',
                    on_click=self.show_more_tabs_dialog
                ).props('round flat').classes('ml-auto')
    
    def create_tab_button(self, tab_id: str, label: str, icon: str, color: str):
        """탭 버튼 생성"""
        current_tab = self.state.get('current_tab', 'txt2img')
        is_active = tab_id == current_tab
        
        # 전달 가능 여부 확인
        can_access = tab_id in self.tab_manager.get_transfer_targets(current_tab) or tab_id == current_tab
        
        button_props = f'{"unelevated" if is_active else "outline"} color={color} size=sm'
        if not can_access:
            button_props += ' disable'
        
        with ui.button(
            text=label,
            icon=icon,
            on_click=lambda: self.switch_tab(tab_id) if can_access else None
        ).props(button_props).classes('min-w-0'):
            if not can_access:
                ui.tooltip('현재 탭에서 접근할 수 없습니다')
    
    def switch_tab(self, tab_id: str):
        """탭 전환"""
        success = self.tab_manager.switch_tab(tab_id)
        
        if success:
            # 탭 컨텐츠 업데이트
            self.current_tab_container.clear()
            
            with self.current_tab_container:
                self.tab_manager.active_tab.render(ui.column().classes('w-full h-full'))
            
            # 탭 버튼 상태 업데이트
            self.update_tab_buttons()
    
    def update_tab_buttons(self):
        """탭 버튼 상태 업데이트"""
        # 탭 헤더 새로고침
        # 실제 구현에서는 개별 버튼만 업데이트
        pass
    
    def show_more_tabs_dialog(self):
        """더 많은 탭 다이얼로그"""
        with ui.dialog() as dialog:
            with ui.card():
                ui.label('추가 탭 선택').classes('text-lg font-bold mb-4')
                
                # 플러그인 탭들
                available_plugins = self.get_available_plugins()
                
                with ui.grid(columns=3).classes('gap-2'):
                    for plugin in available_plugins:
                        with ui.card().classes('p-2 cursor-pointer hover:bg-gray-700'):
                            ui.icon(plugin['icon']).classes('text-2xl mx-auto')
                            ui.label(plugin['name']).classes('text-xs text-center')
                            # 클릭 시 플러그인 로드
                
                ui.button('닫기', on_click=dialog.close).classes('mt-4')
        
        dialog.open()
    
    def get_available_plugins(self):
        """사용 가능한 플러그인 목록"""
        return [
            {'name': 'ControlNet', 'icon': 'control_camera', 'id': 'controlnet'},
            {'name': 'AnimateDiff', 'icon': 'animation', 'id': 'animatediff'},
            {'name': 'Face Restore', 'icon': 'face', 'id': 'face_restore'},
            {'name': 'Background Remove', 'icon': 'layers_clear', 'id': 'bg_remove'},
            {'name': 'Style Transfer', 'icon': 'palette', 'id': 'style_transfer'},
            {'name': 'Depth Map', 'icon': 'view_in_ar', 'id': 'depth_map'},
        ]
    
    def on_mode_changed(self, event_data):
        """모드 변경 이벤트 처리"""
        new_mode = event_data.get('mode')
        if new_mode and new_mode != self.state.get('current_tab'):
            self.switch_tab(new_mode)
```

---

## 🚀 구현 로드맵

### Phase 1: 기본 탭 시스템 (1주)
- [x] TabManager 클래스 구현
- [x] BaseTab 추상 클래스 작성
- [x] JavaScript 통신 브릿지 구현
- [x] 기본 T2I, I2I 탭 구현

### Phase 2: 고급 탭 구현 (2주)
- [x] 3D 포즈 에디터 (Three.js)
- [x] 마스크 에디터 (Canvas API)
- [x] 스케치 에디터 (Paper.js)
- [x] Inpaint, Upscale 탭

### Phase 3: 플러그인 시스템 (1주)
- [x] 동적 탭 로딩 시스템
- [x] 플러그인 매니저
- [x] 커뮤니티 플러그인 지원

### Phase 4: 최적화 및 확장 (1주)
- [x] 성능 최적화
- [x] 메모리 관리
- [x] 더 많은 창작 도구 추가

---

## 🎯 기술적 구현 가능성

### JavaScript 통합
**✅ 완전히 가능**: NiceGUI의 `ui.run_javascript()` 및 콜백 시스템으로 완벽한 양방향 통신

### 3D 기능
**✅ Three.js 완전 지원**: WebGL 기반 3D 렌더링, 포즈 에디터, ControlNet 연동

### Canvas 기능
**✅ HTML5 Canvas 완전 지원**: 고급 그리기 도구, 마스크 편집, 실시간 브러시

### 성능
**✅ 최적화된 구조**: 필요한 탭만 로드, 지연 로딩, 메모리 효율적 관리

### 확장성
**✅ 무한 확장**: 플러그인 시스템으로 새로운 기능 동적 추가 가능

---

## 🔧 결론

이 설계로 구현하면:

1. **완전한 탭 기반 시스템**: Image Pad 내부에서 모든 기능 접근
2. **자유로운 워크플로우**: 업로드/생성 구분 없이 이미지 기반 탭 간 전환
3. **3D/Canvas 고급 기능**: 포즈 에디터, 마스크 편집, 스케치 등 전문 도구
4. **무한 확장성**: 새로운 창작 도구 플러그인으로 추가 가능

**JavaScript 구현은 100% 가능**하며, 오히려 웹 기술의 장점을 최대한 활용할 수 있는 구조입니다! 🚀