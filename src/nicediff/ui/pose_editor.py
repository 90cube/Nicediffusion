# src/nicediff/ui/pose_editor.py (새로 생성)

from nicegui import ui
from ..core.state_manager import StateManager

class PoseEditor:
    """Three.js 기반 3D 포즈 에디터"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_camera = 'body'  # body, left_hand, right_hand
        
    async def render(self):
        """3D 포즈 에디터 렌더링"""
        
        pose_editor_html = """
        <div id="pose-container" style="width: 100%; height: 100%; position: relative;">
            <div id="three-viewport" style="width: 100%; height: 100%;"></div>
            
            <!-- 카메라 컨트롤 -->
            <div id="camera-controls" style="position: absolute; top: 10px; right: 10px; 
                                          background: rgba(0,0,0,0.7); padding: 10px; border-radius: 5px;">
                <button id="body-cam" onclick="switchCamera('body')" class="cam-btn active">전체</button>
                <button id="left-hand-cam" onclick="switchCamera('left_hand')" class="cam-btn">왼손</button>
                <button id="right-hand-cam" onclick="switchCamera('right_hand')" class="cam-btn">오른손</button>
            </div>
            
            <!-- 포즈 프리셋 -->
            <div id="pose-presets" style="position: absolute; bottom: 10px; left: 10px; 
                                        background: rgba(0,0,0,0.7); padding: 10px; border-radius: 5px;">
                <select id="preset-select" onchange="loadPosePreset(this.value)">
                    <option value="">포즈 프리셋 선택</option>
                    <option value="t_pose">T-포즈</option>
                    <option value="idle">기본 자세</option>
                    <option value="wave">인사</option>
                    <option value="point">가리키기</option>
                    <option value="victory">브이</option>
                </select>
            </div>
        </div>
        
        <style>
        .cam-btn {
            background: #333;
            color: white;
            border: 1px solid #555;
            padding: 5px 10px;
            margin: 2px;
            cursor: pointer;
            border-radius: 3px;
        }
        .cam-btn.active {
            background: #0066ff;
        }
        .cam-btn:hover {
            background: #555;
        }
        .cam-btn.active:hover {
            background: #0088ff;
        }
        #preset-select {
            background: #333;
            color: white;
            border: 1px solid #555;
            padding: 5px;
            border-radius: 3px;
        }
        </style>
        
        <script type="module">
        import * as THREE from 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
        
        // Three.js 초기화
        let scene, renderer, cameras, currentCamera;
        let fbxModel, skeleton, bones = {};
        let isDragging = false, selectedBone = null;
        
        // 카메라 설정
        cameras = {
            body: new THREE.PerspectiveCamera(75, 1, 0.1, 1000),
            left_hand: new THREE.PerspectiveCamera(75, 1, 0.1, 1000),
            right_hand: new THREE.PerspectiveCamera(75, 1, 0.1, 1000)
        };
        
        // 카메라 위치 설정
        cameras.body.position.set(0, 1.6, 3);
        cameras.left_hand.position.set(-0.5, 1.2, 1);
        cameras.right_hand.position.set(0.5, 1.2, 1);
        
        currentCamera = cameras.body;
        
        function initThreeJS() {
            const container = document.getElementById('three-viewport');
            const rect = container.getBoundingClientRect();
            
            // 씬 생성
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x222222);
            
            // 렌더러 생성
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(rect.width, rect.height);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            container.appendChild(renderer.domElement);
            
            // 조명 설정
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
            directionalLight.position.set(5, 10, 5);
            directionalLight.castShadow = true;
            scene.add(directionalLight);
            
            // 기본 스켈레톤 생성 (FBX 대신 임시)
            createBasicSkeleton();
            
            // 이벤트 리스너
            renderer.domElement.addEventListener('mousedown', onMouseDown);
            renderer.domElement.addEventListener('mousemove', onMouseMove);
            renderer.domElement.addEventListener('mouseup', onMouseUp);
            
            // 렌더 루프
            animate();
        }
        
        function createBasicSkeleton() {
            // 기본 인체 스켈레톤 생성
            const bonePositions = {
                'root': [0, 0, 0],
                'spine': [0, 0.5, 0],
                'chest': [0, 1, 0],
                'neck': [0, 1.4, 0],
                'head': [0, 1.6, 0],
                'left_shoulder': [-0.3, 1.2, 0],
                'left_arm': [-0.6, 1.2, 0],
                'left_forearm': [-0.9, 1.1, 0],
                'left_hand': [-1.2, 1, 0],
                'right_shoulder': [0.3, 1.2, 0],
                'right_arm': [0.6, 1.2, 0],
                'right_forearm': [0.9, 1.1, 0],
                'right_hand': [1.2, 1, 0],
                'left_thigh': [-0.2, 0.3, 0],
                'left_shin': [-0.2, -0.2, 0],
                'left_foot': [-0.2, -0.7, 0.1],
                'right_thigh': [0.2, 0.3, 0],
                'right_shin': [0.2, -0.2, 0],
                'right_foot': [0.2, -0.7, 0.1]
            };
            
            // 본 생성
            for (const [boneName, position] of Object.entries(bonePositions)) {
                const geometry = new THREE.SphereGeometry(0.03, 8, 8);
                const material = new THREE.MeshBasicMaterial({ 
                    color: boneName.includes('hand') ? 0xff6666 : 0x66ff66 
                });
                const bone = new THREE.Mesh(geometry, material);
                bone.position.set(...position);
                bone.userData = { boneName, originalPosition: [...position] };
                bones[boneName] = bone;
                scene.add(bone);
            }
            
            // 본 연결선 생성
            createBoneConnections();
        }
        
        function createBoneConnections() {
            const connections = [
                ['root', 'spine'],
                ['spine', 'chest'],
                ['chest', 'neck'],
                ['neck', 'head'],
                ['chest', 'left_shoulder'],
                ['left_shoulder', 'left_arm'],
                ['left_arm', 'left_forearm'],
                ['left_forearm', 'left_hand'],
                ['chest', 'right_shoulder'],
                ['right_shoulder', 'right_arm'],
                ['right_arm', 'right_forearm'],
                ['right_forearm', 'right_hand'],
                ['root', 'left_thigh'],
                ['left_thigh', 'left_shin'],
                ['left_shin', 'left_foot'],
                ['root', 'right_thigh'],
                ['right_thigh', 'right_shin'],
                ['right_shin', 'right_foot']
            ];
            
            connections.forEach(([start, end]) => {
                const startBone = bones[start];
                const endBone = bones[end];
                if (startBone && endBone) {
                    const geometry = new THREE.BufferGeometry().setFromPoints([
                        startBone.position,
                        endBone.position
                    ]);
                    const material = new THREE.LineBasicMaterial({ color: 0x888888 });
                    const line = new THREE.Line(geometry, material);
                    scene.add(line);
                }
            });
        }
        
        function onMouseDown(event) {
            const mouse = new THREE.Vector2();
            mouse.x = (event.clientX / renderer.domElement.clientWidth) * 2 - 1;
            mouse.y = -(event.clientY / renderer.domElement.clientHeight) * 2 + 1;
            
            const raycaster = new THREE.Raycaster();
            raycaster.setFromCamera(mouse, currentCamera);
            
            const intersects = raycaster.intersectObjects(Object.values(bones));
            if (intersects.length > 0) {
                selectedBone = intersects[0].object;
                isDragging = true;
                selectedBone.material.color.setHex(0xffff00); // 선택 표시
            }
        }
        
        function onMouseMove(event) {
            if (!isDragging || !selectedBone) return;
            
            // 본 위치 업데이트 로직
            // 실제로는 더 복잡한 IK/FK 계산 필요
        }
        
        function onMouseUp(event) {
            if (selectedBone) {
                // 원래 색상으로 복원
                const boneName = selectedBone.userData.boneName;
                const isHand = boneName.includes('hand');
                selectedBone.material.color.setHex(isHand ? 0xff6666 : 0x66ff66);
                selectedBone = null;
            }
            isDragging = false;
        }
        
        function animate() {
            requestAnimationFrame(animate);
            renderer.render(scene, currentCamera);
        }
        
        // 글로벌 함수들
        window.switchCamera = function(cameraType) {
            currentCamera = cameras[cameraType];
            
            // 카메라 포커스 설정
            if (cameraType === 'left_hand' && bones.left_hand) {
                currentCamera.lookAt(bones.left_hand.position);
            } else if (cameraType === 'right_hand' && bones.right_hand) {
                currentCamera.lookAt(bones.right_hand.position);
            } else {
                currentCamera.lookAt(new THREE.Vector3(0, 1, 0));
            }
            
            // 버튼 활성화 상태 업데이트
            document.querySelectorAll('.cam-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(cameraType.replace('_', '-') + '-cam').classList.add('active');
        }
        
        window.loadPosePreset = function(presetName) {
            if (!presetName) return;
            
            // 포즈 프리셋 데이터
            const presets = {
                't_pose': {
                    'left_arm': [-0.8, 1.2, 0],
                    'right_arm': [0.8, 1.2, 0],
                    'left_forearm': [-1.1, 1.2, 0],
                    'right_forearm': [1.1, 1.2, 0]
                },
                'wave': {
                    'right_arm': [0.5, 1.4, 0],
                    'right_forearm': [0.6, 1.6, 0],
                    'right_hand': [0.7, 1.7, 0]
                }
                // 추가 프리셋들...
            };
            
            const preset = presets[presetName];
            if (preset) {
                for (const [boneName, position] of Object.entries(preset)) {
                    if (bones[boneName]) {
                        bones[boneName].position.set(...position);
                    }
                }
                
                // OpenPose 데이터 생성 및 전송
                generateOpenPoseData();
            }
        }
        
        function generateOpenPoseData() {
            // 현재 포즈를 OpenPose 형식으로 변환
            const poseData = {};
            for (const [boneName, bone] of Object.entries(bones)) {
                poseData[boneName] = {
                    x: bone.position.x,
                    y: bone.position.y,
                    z: bone.position.z
                };
            }
            
            // Python으로 데이터 전송
            console.log('Pose data generated:', poseData);
            // window.pywebview?.api?.on_pose_change(poseData);
        }
        
        // 초기화
        initThreeJS();
        </script>
        """
        
        ui.html(pose_editor_html).classes('w-full h-full')
    
    def switch_camera(self, camera_type: str):
        """카메라 전환"""
        self.current_camera = camera_type
        ui.run_javascript(f'window.switchCamera("{camera_type}")')
    
    def load_fbx_model(self, fbx_path: str):
        """FBX 모델 로드"""
        # Phase 2C에서 구현
        pass
    
    def export_openpose(self) -> dict:
        """OpenPose 데이터 추출"""
        # Phase 2C에서 구현
        pass