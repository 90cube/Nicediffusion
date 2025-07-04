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