#!/usr/bin/env python3
"""
독립적인 이미지 패드 - Tkinter 기반
NiceGUI 없이 Python으로 직접 구현
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import threading
import queue
from typing import Optional, Callable
import numpy as np

class CustomImagePad:
    def __init__(self, callback_function: Optional[Callable] = None):
        """
        이미지 패드 초기화
        
        Args:
            callback_function: 이미지가 업로드되면 호출될 콜백 함수
                              (numpy array를 인자로 받음)
        """
        self.callback_function = callback_function
        self.image_queue = queue.Queue()
        
        # 메인 윈도우 생성
        self.root = tk.Tk()
        self.root.title("Image Pad - 드래그앤드롭 또는 클릭으로 이미지 업로드")
        self.root.geometry("800x600")
        self.root.configure(bg='#1a1a1a')
        
        # 이미지 관련 변수
        self.current_image = None
        self.current_photo = None
        self.image_path = None
        
        # UI 구성
        self._setup_ui()
        
        # 드래그앤드롭 이벤트 바인딩
        self._setup_drag_drop()
        
        # 이미지 처리 스레드 시작
        self._start_image_processor()
        
    def _setup_ui(self):
        """UI 구성"""
        # 메인 프레임
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 제목
        title_label = tk.Label(
            main_frame, 
            text="📁 이미지 패드", 
            font=("Arial", 16, "bold"),
            fg='white',
            bg='#1a1a1a'
        )
        title_label.pack(pady=(0, 10))
        
        # 이미지 표시 영역
        self.image_frame = tk.Frame(
            main_frame, 
            bg='#2a2a2a', 
            relief=tk.RAISED, 
            bd=2
        )
        self.image_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 이미지 라벨 (드래그앤드롭 영역)
        self.image_label = tk.Label(
            self.image_frame,
            text="이미지를 여기에 드래그앤드롭하세요\n또는 클릭하여 파일 선택",
            font=("Arial", 12),
            fg='#888888',
            bg='#2a2a2a',
            width=50,
            height=20,
            cursor="hand2"
        )
        self.image_label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 버튼 프레임
        button_frame = tk.Frame(main_frame, bg='#1a1a1a')
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 파일 선택 버튼
        self.select_button = tk.Button(
            button_frame,
            text="📁 파일 선택",
            command=self._select_file,
            font=("Arial", 10),
            bg='#4a4a4a',
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=5
        )
        self.select_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 캔버스 비우기 버튼
        self.clear_button = tk.Button(
            button_frame,
            text="🗑️ 캔버스 비우기",
            command=self._clear_canvas,
            font=("Arial", 10),
            bg='#8b0000',
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=5
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 상태 라벨
        self.status_label = tk.Label(
            button_frame,
            text="대기 중...",
            font=("Arial", 9),
            fg='#888888',
            bg='#1a1a1a'
        )
        self.status_label.pack(side=tk.RIGHT)
        
    def _setup_drag_drop(self):
        """이벤트 설정"""
        # 이미지 라벨에 클릭 이벤트
        self.image_label.bind("<Button-1>", self._on_click)
        
        # 더블클릭 이벤트
        self.image_label.bind("<Double-Button-1>", self._on_double_click)
        
        # 키보드 단축키
        self.root.bind('<Control-o>', lambda e: self._select_file())
        self.root.bind('<Control-O>', lambda e: self._select_file())
        
    def _on_click(self, event):
        """이미지 영역 클릭 시 파일 선택"""
        self._select_file()
        
    def _on_double_click(self, event):
        """더블클릭 시 이미지 전체화면 보기"""
        if self.current_image:
            self._show_fullscreen()
            
    def _show_fullscreen(self):
        """이미지 전체화면 보기"""
        if not self.current_image:
            return
            
        # 새 창 생성
        fullscreen_window = tk.Toplevel(self.root)
        fullscreen_window.title("이미지 전체화면 보기")
        fullscreen_window.geometry("1200x800")
        
        # 이미지 크기 조정
        display_width, display_height = 1200, 800
        image_width, image_height = self.current_image.size
        
        ratio = min(display_width / image_width, display_height / image_height)
        new_width = int(image_width * ratio)
        new_height = int(image_height * ratio)
        
        resized_image = self.current_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized_image)
        
        # 이미지 라벨
        image_label = tk.Label(fullscreen_window, image=photo)
        image_label.image = photo  # 참조 유지
        image_label.pack(fill=tk.BOTH, expand=True)
        
        # 닫기 버튼
        close_button = tk.Button(
            fullscreen_window,
            text="닫기",
            command=fullscreen_window.destroy,
            bg='#8b0000',
            fg='white'
        )
        close_button.pack(pady=10)
        
    def _select_file(self):
        """파일 선택 다이얼로그"""
        file_path = filedialog.askopenfilename(
            title="이미지 파일 선택",
            filetypes=[
                ("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("PNG 파일", "*.png"),
                ("JPEG 파일", "*.jpg *.jpeg"),
                ("모든 파일", "*.*")
            ]
        )
        if file_path:
            self._process_image_file(file_path)
            
    def _process_image_file(self, file_path: str):
        """이미지 파일 처리"""
        try:
            self.status_label.configure(text="이미지 처리 중...")
            
            # PIL로 이미지 로드
            image = Image.open(file_path)
            
            # RGB로 변환 (알파 채널 제거)
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
                
            # 이미지 크기 조정 (최대 800x600)
            max_width, max_height = 800, 600
            width, height = image.size
            
            if width > max_width or height > max_height:
                # 비율 유지하면서 크기 조정
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            # PhotoImage로 변환
            photo = ImageTk.PhotoImage(image)
            
            # UI 업데이트 (메인 스레드에서)
            self.root.after(0, self._update_ui_with_image, image, photo, file_path)
            
        except Exception as e:
            messagebox.showerror("오류", f"이미지 로드 실패: {str(e)}")
            self.status_label.configure(text="오류 발생")
            
    def _update_ui_with_image(self, image: Image.Image, photo: ImageTk.PhotoImage, file_path: str):
        """UI에 이미지 표시"""
        # 기존 이미지 제거
        if self.current_photo:
            self.image_label.configure(image="", text="")
            
        # 새 이미지 설정
        self.current_image = image
        self.current_photo = photo
        self.image_path = file_path
        
        # 이미지 라벨에 표시
        self.image_label.configure(image=photo, text="")
        
        # 상태 업데이트
        width, height = image.size
        self.status_label.configure(text=f"로드됨: {os.path.basename(file_path)} ({width}x{height})")
        
        # numpy array로 변환하여 콜백 호출
        np_image = np.array(image)
        if self.callback_function:
            # 별도 스레드에서 콜백 실행
            threading.Thread(target=self.callback_function, args=(np_image,), daemon=True).start()
            
    def _clear_canvas(self):
        """캔버스 비우기"""
        if self.current_photo:
            self.current_image = None
            self.current_photo = None
            self.image_path = None
            
            self.image_label.configure(
                image="",
                text="이미지를 여기에 드래그앤드롭하세요\n또는 클릭하여 파일 선택"
            )
            
            self.status_label.configure(text="캔버스 비워짐")
            
    def _start_image_processor(self):
        """이미지 처리 스레드 시작"""
        def process_queue():
            while True:
                try:
                    # 큐에서 이미지 가져오기
                    image_data = self.image_queue.get(timeout=1)
                    # 여기서 추가 이미지 처리 가능
                except queue.Empty:
                    continue
                    
        threading.Thread(target=process_queue, daemon=True).start()
        
    def get_current_image(self) -> Optional[np.ndarray]:
        """현재 이미지를 numpy array로 반환"""
        if self.current_image:
            return np.array(self.current_image)
        return None
        
    def get_current_image_path(self) -> Optional[str]:
        """현재 이미지 파일 경로 반환"""
        return self.image_path
        
    def run(self):
        """이미지 패드 실행"""
        self.root.mainloop()
        
    def close(self):
        """이미지 패드 종료"""
        self.root.quit()
        self.root.destroy()

# 테스트용
if __name__ == "__main__":
    def on_image_uploaded(np_image):
        print(f"이미지 업로드됨: {np_image.shape}")
        
    image_pad = CustomImagePad(callback_function=on_image_uploaded)
    image_pad.run() 