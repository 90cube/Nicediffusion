import sys
import os
try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

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

#!/usr/bin/env python3
"""
Nicediff - Modular AI Image Generation UI
Main entry point
"""

import sys
from pathlib import Path

# Windows/Linux 호환 경로 설정
ROOT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

from nicegui import app, ui
from src.nicediff.pages.inference_page import InferencePage
from src.nicediff.core.state_manager import StateManager

# 전역 상태 관리자 초기화
state_manager = StateManager()

@ui.page('/')
async def main_page():
    """메인 페이지 라우터"""
    ui.colors(primary='#3b82f6', dark='#1e293b')
    
    # Inference 페이지 렌더링
    inference_page = InferencePage(state_manager)
    await inference_page.render()

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

if __name__ == '__main__':
    ui.run(
        title="Nicediff",
        port=8080,
        dark=True,
        reload=False,
        show=True
    )