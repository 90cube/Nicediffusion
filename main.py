import sys
import os
try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

import base64
import io
import numpy as np
from fastapi import FastAPI, UploadFile, File, APIRouter
from nicegui import app
from PIL import Image
from src.nicediff.ui.image_pad.image_pad import ImagePad
from src.nicediff.core.state_manager import StateManager

print("\n\n--- [파이썬 환경 진단 시작] ---\n")
print(f"1. 현재 실행 중인 파이썬 경로:")
print(f"   L> {sys.executable}\n")

expected_path = os.path.normpath("D:/nicediffusion/venv/Scripts/python.exe")
if os.path.normpath(sys.executable) == expected_path:
    print("2. 경로 확인: [성공] 의도한 가상환경의 파이썬이 맞습니다.\n")
else:
    print("2. 경로 확인: [실패] 의도치 않은 다른 경로의 파이썬이 실행되고 있습니다.")
    print(f"   L> 예상 경로: {expected_path}\n")

try:
    version = metadata.version('nicegui')
    print(f"3. NiceGUI 버전: [성공] '{version}' 버전을 찾았습니다.\n")
except metadata.PackageNotFoundError:
    print("3. NiceGUI 버전: [실패] 이 파이썬 환경에는 nicegui가 설치되어 있지 않습니다.\n")

print("--- [진단 끝, 원래 코드 실행 시작] ---\n\n")

import sys
from pathlib import Path

# Windows/Linux 호환 경로 설정
ROOT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

from nicegui import app, ui
from fastapi.staticfiles import StaticFiles
from src.nicediff.pages.inference_page import InferencePage
from src.nicediff.core.state_manager import StateManager

# 전역 상태 관리자 초기화
state_manager = StateManager()

@ui.page('/')
async def main_page():
    """메인 페이지 라우터 (뷰포트 개선)"""
    # 반응형 디자인을 위한 색상 설정
    ui.colors(primary='#3b82f6', dark='#1e293b')
    
    # 반응형 메타 태그 및 뷰포트 설정 (개선)
    ui.add_head_html("""
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
        <style>
            /* 전체 페이지 레이아웃 최적화 */
            html, body {
                margin: 0 !important;
                padding: 0 !important;
                height: 100vh !important;
                overflow-x: hidden !important; /* 가로 스크롤 방지 */
                overflow-y: auto !important; /* 세로 스크롤 허용 */
                box-sizing: border-box;
            }
            
            /* NiceGUI 기본 컨테이너 최적화 */
            .nicegui-content {
                height: 100vh !important;
                max-width: 100vw !important;
                overflow-x: hidden !important;
                box-sizing: border-box;
            }
            
            /* 모든 요소에 박스 사이징 적용 */
            *, *::before, *::after {
                box-sizing: border-box;
            }
            
            /* 스크롤바 스타일링 (다크 테마) */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            
            ::-webkit-scrollbar-track {
                background: #374151;
                border-radius: 4px;
            }
            
            ::-webkit-scrollbar-thumb {
                background: #6b7280;
                border-radius: 4px;
            }
            
            ::-webkit-scrollbar-thumb:hover {
                background: #9ca3af;
            }
            
            /* 컨테이너 최대 너비 제한 및 overflow 제어 */
            .container-responsive {
                max-width: 100vw !important;
                overflow-x: hidden !important;
                box-sizing: border-box;
            }
            
            /* 플렉스 아이템 최소 너비 설정 */
            .flex-item-min {
                min-width: 0 !important;
                flex-shrink: 1 !important;
                box-sizing: border-box;
            }
            
            /* 우측 패널 너비 제한 */
            .right-panel-constrain {
                max-width: 320px !important;
                min-width: 250px !important;
                width: 280px !important;
                flex-shrink: 0 !important;
                box-sizing: border-box;
            }
            
            /* TopBar 반응형 개선 */
            .topbar-responsive {
                flex-wrap: wrap;
                gap: 0.5rem;
                max-width: 100vw;
                overflow-x: hidden;
                box-sizing: border-box;
            }
            
            /* 반응형 텍스트 크기 */
            @media (max-width: 640px) {
                .text-responsive {
                    font-size: 0.75rem !important;
                }
                
                /* 모바일에서 TopBar 개선 */
                .mobile-stack {
                    flex-direction: column !important;
                    align-items: stretch !important;
                }
                
                .mobile-stack > * {
                    width: 100% !important;
                    margin-bottom: 0.5rem !important;
                }
                
                .mobile-text-sm {
                    font-size: 0.7rem !important;
                }
                
                /* 모바일에서 우측 패널 조정 */
                .right-panel-constrain {
                    width: 220px !important;
                    min-width: 200px !important;
                    max-width: 220px !important;
                }
            }
            
            /* 태블릿 크기 */
            @media (max-width: 1024px) {
                .tablet-vertical {
                    flex-direction: column !important;
                }
                
                .topbar-responsive {
                    flex-direction: column;
                    align-items: stretch;
                }
                
                .topbar-responsive .vae-selector {
                    width: 100% !important;
                    max-width: none !important;
                }
                
                /* 태블릿에서 우측 패널 조정 */
                .right-panel-constrain {
                    width: 260px !important;
                    min-width: 240px !important;
                    max-width: 280px !important;
                }
            }
            
            /* 매우 작은 화면 대응 */
            @media (max-width: 480px) {
                .hide-on-mobile {
                    display: none !important;
                }
                
                .right-panel-constrain {
                    width: 200px !important;
                    min-width: 180px !important;
                    max-width: 200px !important;
                }
            }
            
            /* 레이아웃 안정성을 위한 추가 규칙 */
            .main-layout {
                width: 95vw !important;
                height: 95vh !important;
                overflow: hidden !important;
                display: flex !important;
                flex-direction: column !important;
            }
            
            .content-row {
                display: flex !important;
                width: 95% !important;
                overflow: hidden !important;
                flex: 1 !important;
                min-height: 0 !important;
            }
            
            /* 이미지 패드 Fit/Contain 스타일 */
            .image-pad-container {
                background-color: #000000 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                width: 100% !important;
                height: 100% !important;
                overflow: hidden !important;
            }
            
            .image-fit-contain {
                max-width: 100% !important;
                max-height: 100% !important;
                width: auto !important;
                height: auto !important;
                object-fit: contain !important;
                object-position: center !important;
                display: block !important;
                margin: auto !important;
                border-radius: 8px !important;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5) !important;
            }
            
            .image-fit-cover {
                width: 100% !important;
                height: 100% !important;
                object-fit: cover !important;
                object-position: center !important;
                border-radius: 8px !important;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5) !important;
            }
        </style>
    """)
    
    # Inference 페이지 렌더링
    inference_page = InferencePage(state_manager)
    await inference_page.render()

# 정적 파일 서빙 설정
@app.on_startup
async def setup_static_files():
    """정적 파일 서빙 설정"""
    try:
        # outputs 폴더를 정적 파일로 서빙
        outputs_path = Path(__file__).parent / "outputs"
        if outputs_path.exists():
            app.mount("/outputs", StaticFiles(directory=str(outputs_path)), name="outputs")
            print(f"✅ 정적 파일 서빙 설정 완료: {outputs_path}")
        else:
            print(f"⚠️ outputs 폴더가 없습니다: {outputs_path}")
    except Exception as e:
        print(f"⚠️ 정적 파일 서빙 설정 실패: {e}")

# 앱 시작 시 초기화
@app.on_startup
async def startup():
    """앱 시작 시 필요한 초기화 작업"""
    print("🚀 Nicediff 시작 중...")
    await state_manager.initialize()
    print("✅ 초기화 완료")

# 앱 종료 시 정리
@app.on_shutdown
async def shutdown():
    """앱 종료 시 정리 작업"""
    print("🔄 Nicediff 종료 중...")
    await state_manager.cleanup()
    print("👋 종료 완료")

# FastAPI 라우터 생성
router = APIRouter()

# ImagePad 인스턴스 참조 (StateManager에서 가져오거나 싱글턴으로 관리)
state_manager = StateManager()
image_pad = ImagePad(state_manager)

@app.post('/api/upload_image')
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert('RGB')
    np_image = np.array(image)
    image_pad.set_uploaded_image(np_image)
    return {'success': True, 'shape': np_image.shape}

# FastAPI 라우터를 NiceGUI 앱에 등록 (제거 - NiceGUI는 add_router 지원 안함)
# app.add_router(router)

if __name__ == '__main__':
    ui.run(
        title="Nicediff - AI Image Generation Studio",
        port=8081,  # 포트 충돌 방지를 위해 8081로 변경
        dark=True,
        reload=False,
        show=True,
        favicon='🎨',
        storage_secret='nicediff-secret-key-2024'
    )