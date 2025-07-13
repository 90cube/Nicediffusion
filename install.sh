#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수 정의
print_header() {
    echo -e "${BLUE}========================================"
    echo -e "NiceDiffusion 자동 설치 스크립트 (Linux)"
    echo -e "========================================${NC}"
    echo
}

print_step() {
    echo -e "${YELLOW}[$1] $2${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# 헤더 출력
print_header

# Python 3.12 설치 확인
print_step "1/6" "Python 3.12 설치 확인 중..."

if ! command -v python3 &> /dev/null; then
    print_error "Python3가 설치되지 않았습니다."
    echo "다음 명령어로 Python 3.12를 설치해주세요:"
    echo "sudo apt update && sudo apt install python3.12 python3.12-venv python3.12-pip"
    exit 1
fi

# Python 버전 확인
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.12"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Python 3.12 이상이 필요합니다. 현재 버전: $PYTHON_VERSION"
    echo "다음 명령어로 Python 3.12를 설치해주세요:"
    echo "sudo apt update && sudo apt install python3.12 python3.12-venv python3.12-pip"
    exit 1
fi

print_success "Python $PYTHON_VERSION 확인 완료"
echo

# 기존 가상환경 삭제
print_step "2/6" "기존 가상환경 정리 중..."
if [ -d "venv" ]; then
    echo "기존 venv 폴더를 삭제합니다..."
    rm -rf venv
fi

# 새 가상환경 생성
print_step "3/6" "Python 3.12 가상환경 생성 중..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    print_error "가상환경 생성에 실패했습니다."
    echo "python3-venv 패키지가 설치되어 있는지 확인해주세요:"
    echo "sudo apt install python3.12-venv"
    exit 1
fi

# 가상환경 활성화
print_step "4/6" "가상환경 활성화 중..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    print_error "가상환경 활성화에 실패했습니다."
    exit 1
fi

# pip 업그레이드
echo "pip 업그레이드 중..."
python -m pip install --upgrade pip

# CUDA 확인
print_step "5/6" "CUDA 환경 확인 중..."
if command -v nvidia-smi &> /dev/null; then
    echo "CUDA가 감지되었습니다."
    CUDA_AVAILABLE=1
else
    echo "CUDA가 설치되지 않았거나 NVIDIA 드라이버가 없습니다."
    echo "CPU 전용 PyTorch를 설치합니다."
    CUDA_AVAILABLE=0
fi

# PyTorch 설치 (CUDA 여부에 따라)
print_step "6/6" "PyTorch 및 의존성 설치 중..."
if [ $CUDA_AVAILABLE -eq 1 ]; then
    echo "CUDA 지원 PyTorch 설치 중..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
else
    echo "CPU 전용 PyTorch 설치 중..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

# 나머지 requirements 설치
echo "나머지 패키지 설치 중..."
pip install -r requirements_linux.txt

echo
print_header
print_success "설치 완료!"
echo
echo "가상환경을 활성화하려면:"
echo "  source venv/bin/activate"
echo
echo "프로그램을 실행하려면:"
echo "  python main.py"
echo
echo "가상환경을 비활성화하려면:"
echo "  deactivate"
echo 