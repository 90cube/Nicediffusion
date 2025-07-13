@echo off
setlocal enabledelayedexpansion

echo ========================================
echo NiceDiffusion 자동 설치 스크립트 (Windows)
echo ========================================
echo.

:: Python 3.12 설치 확인
echo [1/6] Python 3.12 설치 확인 중...
python --version 2>nul
if errorlevel 1 (
    echo 오류: Python이 설치되지 않았습니다.
    echo https://www.python.org/downloads/ 에서 Python 3.12를 다운로드하여 설치해주세요.
    pause
    exit /b 1
)

python -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>nul
if errorlevel 1 (
    echo 오류: Python 3.12 이상이 필요합니다.
    echo 현재 설치된 Python 버전을 확인하고 업그레이드해주세요.
    pause
    exit /b 1
)

echo Python 3.12 확인 완료
echo.

:: 기존 가상환경 삭제
echo [2/6] 기존 가상환경 정리 중...
if exist "venv" (
    echo 기존 venv 폴더를 삭제합니다...
    rmdir /s /q venv
)

:: 새 가상환경 생성
echo [3/6] Python 3.12 가상환경 생성 중...
python -m venv venv
if errorlevel 1 (
    echo 오류: 가상환경 생성에 실패했습니다.
    pause
    exit /b 1
)

:: 가상환경 활성화
echo [4/6] 가상환경 활성화 중...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo 오류: 가상환경 활성화에 실패했습니다.
    pause
    exit /b 1
)

:: pip 업그레이드
echo pip 업그레이드 중...
python -m pip install --upgrade pip

:: CUDA 확인
echo [5/6] CUDA 환경 확인 중...
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo CUDA가 설치되지 않았거나 NVIDIA 드라이버가 없습니다.
    echo CPU 전용 PyTorch를 설치합니다.
    set CUDA_AVAILABLE=0
) else (
    echo CUDA가 감지되었습니다.
    set CUDA_AVAILABLE=1
)

:: PyTorch 설치 (CUDA 여부에 따라)
echo [6/6] PyTorch 및 의존성 설치 중...
if "%CUDA_AVAILABLE%"=="1" (
    echo CUDA 지원 PyTorch 설치 중...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
) else (
    echo CPU 전용 PyTorch 설치 중...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
)

:: 나머지 requirements 설치
echo 나머지 패키지 설치 중...
pip install -r requirements_win.txt

echo.
echo ========================================
echo 설치 완료!
echo ========================================
echo.
echo 가상환경을 활성화하려면:
echo   venv\Scripts\activate.bat
echo.
echo 프로그램을 실행하려면:
echo   python main.py
echo.
echo 가상환경을 비활성화하려면:
echo   deactivate
echo.
pause 