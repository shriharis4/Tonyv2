# Import agent first to prevent PyQt5 DLL collision crash
import sys
import os
import json
import math
import time
import socket
import asyncio
import logging
import subprocess
import traceback
from datetime import datetime

import random
import threading
import psutil

import numpy as np
from livekit import rtc
from livekit.rtc import VideoBufferType

# Patch rtc.MediaDevices.open_input to prevent QueueFull flood on Windows audio threads
try:
    from livekit.rtc import media_devices as _md
    _orig_open_input = _md.MediaDevices.open_input

    def _safe_open_input(self, *args, **kwargs):
        kwargs.setdefault('queue_capacity', 500)
        orig_queue_cls = asyncio.Queue

        class _SafeQueue(orig_queue_cls):
            def put_nowait(self, item):
                try:
                    return super().put_nowait(item)
                except asyncio.QueueFull:
                    pass

        asyncio.Queue = _SafeQueue
        try:
            return _orig_open_input(self, *args, **kwargs)
        finally:
            asyncio.Queue = orig_queue_cls

    _md.MediaDevices.open_input = _safe_open_input
except Exception:
    pass

import firebase_admin
from firebase_admin import credentials, db
# Import runtime_agent before PyQt5 to prevent DLL collision crash
from core.runtime_agent import entrypoint

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect, QMenu,
                            QMessageBox, QInputDialog, QDialog, QProgressBar, QDialogButtonBox,
                            QFrame, QScrollArea, QLineEdit)
from PyQt5.QtCore import (QTimer, Qt, QPoint, QPointF, QRectF, QPropertyAnimation, QSize,
                         QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup,
                         QObject, pyqtSignal, QThread)
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
                         QLinearGradient, QRadialGradient, QPainterPath)

logging.getLogger('asyncio').setLevel(logging.WARNING)

# ============================================
# STYLESHEET CONSTANTS (reduce duplication)
# ============================================
PROGRESSBAR_STYLESHEET = """
    QProgressBar {{
        background: rgba(255, 255, 255, 15);
        border: 1px solid rgba(255, 0, 0, 50);
        border-radius: 4px;
        height: 6px;
    }}
    QProgressBar::chunk {{
        background: {color};
        border-radius: 4px;
    }}
"""

LABEL_TITLE_STYLE = "color: #ff0000; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold; letter-spacing: 1.5px;"
LABEL_SECTION_STYLE = "color: #ff0000; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold;"
LABEL_STATUS_STYLE = "color: #ff0000; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;"
LABEL_VALUE_STYLE = "color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;"
DIVIDER_LINE_STYLE = "color: rgba(255, 0, 0, 80); background: rgba(255, 0, 0, 80); height: 1px;"

# Safe print wrapper to prevent UnicodeEncodeError on legacy Windows consoles
_original_print = print
def print(*args, **kwargs):
    enc = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
    new_args = []
    for arg in args:
        if isinstance(arg, str):
            try:
                arg.encode(enc)
                new_args.append(arg)
            except UnicodeEncodeError:
                new_args.append(arg.encode(enc, errors='replace').decode(enc))
        else:
            new_args.append(arg)
    _original_print(*new_args, **kwargs)

class PyQtSignalBridge(QObject):
    connection_changed = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    command_received = pyqtSignal(str)
    response_received = pyqtSignal(str)
    latency_changed = pyqtSignal(float, float)

    livekit_status_changed = pyqtSignal(str, str)  # text, style
    gemini_status_changed = pyqtSignal(str, str)   # text, style
    mic_status_changed = pyqtSignal(str, str)       # text, style

    # --- Streaming chat signals ---
    stream_start = pyqtSignal(str)   # sender name ("TONY" or "You")
    stream_chunk = pyqtSignal(str)   # partial text chunk (append)
    stream_end = pyqtSignal()        # finalize bubble
    stream_replace = pyqtSignal(str) # partial text (replace, not append) for live STT

    # --- Static bubble (history loading) ---
    add_static_bubble = pyqtSignal(str, str)  # sender, text

class ScanningAnimation(QWidget):
    """ULTRA PREMIUM scanning animation for TONY AI - FULL SCREEN"""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Get screen dimensions for full screen
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        self.setGeometry(screen_geometry)
        
        # Animation state
        self.scan_position = 0
        self.opacity = 1.0
        self.pulse_phase = 0.0
        self.glow_intensity = 0.0
        self.particle_phase = 0.0
        self.hologram_phase = 0.0
        
        # Setup animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)  # 60 FPS
        
        # Auto-close after 3 seconds
        QTimer.singleShot(3000, self.fade_out)
        
    def update_animation(self):
        self.scan_position = (self.scan_position + 8) % (self.height() + 400)
        self.pulse_phase += 0.12
        self.particle_phase += 0.15
        self.hologram_phase += 0.08
        self.glow_intensity = 0.6 + 0.4 * math.sin(self.pulse_phase * 2)
        self.update()
        
    def fade_out(self):
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(800)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.close)
        self.anim.start()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Premium dark background with deep space gradient
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(8, 8, 25, 255))
        gradient.setColorAt(0.3, QColor(5, 5, 18, 250))
        gradient.setColorAt(0.7, QColor(3, 3, 12, 245))
        gradient.setColorAt(1, QColor(1, 1, 8, 250))
        painter.fillRect(self.rect(), QBrush(gradient))
        
        # Draw premium effects
        self.draw_nebula_effect(painter)
        self.draw_scanning_effect(painter)
        self.draw_hologram_grid(painter)
        self.draw_tony_text_premium(painter)
        self.draw_particles_premium(painter)
        self.draw_circuit_pattern(painter)
        
    def draw_nebula_effect(self, painter):
        """Draw nebula-like background effect"""
        for i in range(3):
            radius = 300 + i * 150
            center_x = self.width() * (0.3 + i * 0.2)
            center_y = self.height() * (0.4 + math.sin(self.pulse_phase + i) * 0.1)
            
            gradient = QRadialGradient(center_x, center_y, radius)
            gradient.setColorAt(0, QColor(255, 182, 193, 30))  # Light Pink
            gradient.setColorAt(0.5, QColor(255, 215, 0, 20))   # Gold
            gradient.setColorAt(1, QColor(255, 182, 193, 0))    # Light Pink
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

    def draw_scanning_effect(self, painter):
        """ULTRA PREMIUM scanning lines with holographic effect"""
        for i in range(7):
            scan_y = (self.scan_position + i * 60) % (self.height() + 400)
            scan_height = 120 - i * 12
            
            # Multi-layer gradient for premium look
            gradient = QLinearGradient(0, scan_y, 0, scan_y + scan_height)
            alpha = 150 - i * 15
            gradient.setColorAt(0, QColor(255, 182, 193, 0))    # Light Pink
            gradient.setColorAt(0.1, QColor(255, 182, 255, int(alpha)//2))  # Pink
            gradient.setColorAt(0.3, QColor(255, 182, 193, int(alpha)))     # Light Pink
            gradient.setColorAt(0.5, QColor(255, 255, 182, int(alpha)))     # Light Gold
            gradient.setColorAt(0.7, QColor(255, 215, 0, int(alpha)))       # Gold
            gradient.setColorAt(0.9, QColor(255, 182, 255, int(alpha)//2))  # Pink
            gradient.setColorAt(1, QColor(255, 182, 193, 0))
            
            # Add glow effect
            glow_gradient = QLinearGradient(0, scan_y - 10, 0, scan_y + scan_height + 10)
            glow_gradient.setColorAt(0, QColor(255, 182, 193, 30))  # Light Pink
            glow_gradient.setColorAt(0.5, QColor(255, 215, 0, 60))   # Gold
            glow_gradient.setColorAt(1, QColor(255, 182, 193, 30))   # Light Pink
            
            painter.fillRect(0, scan_y - 10, self.width(), scan_height + 20, QBrush(glow_gradient))
            painter.fillRect(0, scan_y, self.width(), scan_height, QBrush(gradient))
            
    def draw_hologram_grid(self, painter):
        """Premium holographic grid effect"""
        
        # Vertical lines
        for x in range(0, self.width(), 40):
            alpha = 30 + 20 * math.sin(self.hologram_phase + x * 0.01)
            # CHANGE: float alpha ko int me convert karo
            painter.setPen(QPen(QColor(255, 215, 0, int(alpha)), 1))
            painter.drawLine(x, 0, x, self.height())
            
        # Horizontal lines
        for y in range(0, self.height(), 40):
            alpha = 30 + 20 * math.sin(self.hologram_phase + y * 0.01)
            # CHANGE: yahan bhi float alpha ko int me convert karo
            painter.setPen(QPen(QColor(255, 182, 193, int(alpha)), 1))  # Light Pink
            painter.drawLine(0, y, self.width(), y)
            
    def draw_tony_text_premium(self, painter):
        """ULTRA PREMIUM text with holographic effects"""
        # Main TONY AI text
        font = QFont("Segoe UI", 56, QFont.Black)
        painter.setFont(font)
        
        text = "TONY AI"
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(text)
        
        text_x = (self.width() - text_width) // 2
        text_y = self.height() // 2 - 60
        
        # Enhanced multi-layer glow effect
        glow_size = 20 + 12 * self.glow_intensity
        for i in range(int(glow_size), 0, -2):
            alpha = 50 - i * 1.5
            color = QColor(255, 192, 203,int(alpha))
            if i % 3 == 0:
                color = QColor(255, 182, 193, int(alpha))  # Light Pink glow
            
            painter.setPen(QPen(color, i))
            painter.drawText(text_x, text_y, text)
        
        # Main text with ULTRA PREMIUM gradient
        text_gradient = QLinearGradient(text_x, text_y, text_x + text_width, text_y + 60)
        text_gradient.setColorAt(0, QColor(255, 182, 193))    # Light Pink
        text_gradient.setColorAt(0.2, QColor(255, 200, 220))  # Pink
        text_gradient.setColorAt(0.4, QColor(255, 255, 255))  # White
        text_gradient.setColorAt(0.6, QColor(255, 240, 220))  # Light Gold
        text_gradient.setColorAt(0.8, QColor(255, 215, 0))    # Gold
        text_gradient.setColorAt(1, QColor(255, 182, 193))    # Light Pink
        
        painter.setPen(QPen(QBrush(text_gradient), 4))
        painter.drawText(text_x, text_y, text)
        
        # Premium subtitle with enhanced effects
        sub_font = QFont("Segoe UI", 20, QFont.DemiBold)
        painter.setFont(sub_font)
        sub_text = "LOVELY INITIALIZATION"
        sub_width = QFontMetrics(sub_font).horizontalAdvance(sub_text)
        sub_x = (self.width() - sub_width) // 2
        sub_y = text_y + 85
        
        # Subtitle glow
        for i in range(8, 0, -1):
            alpha = 40 - i * 3
            painter.setPen(QPen(QColor(100, 255, 255,int(alpha)), i))
            painter.drawText(sub_x, sub_y, sub_text)
        
        # Subtitle main text
        sub_gradient = QLinearGradient(sub_x, sub_y, sub_x + sub_width, sub_y + 10)
        sub_gradient.setColorAt(0, QColor(255, 240, 245))  # Very Light Pink
        sub_gradient.setColorAt(1, QColor(255, 215, 0))    # Gold
        painter.setPen(QPen(QBrush(sub_gradient), 2))
        painter.drawText(sub_x, sub_y, sub_text)
        
        # Enhanced loading animation
        dots = "." * (int(self.pulse_phase * 3) % 4)
        loading_text = f"SYSTEM BOOTING{dots}"
        loading_font = QFont("Segoe UI", 16, QFont.Normal)
        painter.setFont(loading_font)
        loading_width = QFontMetrics(loading_font).horizontalAdvance(loading_text)
        loading_x = (self.width() - loading_width) // 2
        loading_y = sub_y + 45
        
        sub_gradient.setColorAt(0, QColor(255, 240, 245))  # Very Light Pink
        painter.drawText(loading_x, loading_y, loading_text)
        
        # Progress bar
        bar_width = 300
        bar_height = 6
        bar_x = (self.width() - bar_width) // 2
        bar_y = loading_y + 30
        
        # Progress bar background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 182, 193, 100)))  # Light Pink
        painter.drawRoundedRect(bar_x, bar_y, bar_width, bar_height, 3, 3)
        
        # Animated progress
        progress = (self.pulse_phase * 50) % bar_width
        progress_gradient = QLinearGradient(bar_x, bar_y, bar_x + progress, bar_y + bar_height)
        progress_gradient.setColorAt(0, QColor(0, 255, 255))
        progress_gradient.setColorAt(1, QColor(0, 200, 255))
        painter.setBrush(QBrush(progress_gradient))
        painter.drawRoundedRect(bar_x, bar_y, int(progress), bar_height, 3, 3)
        
    def draw_particles_premium(self, painter):
        """ULTRA PREMIUM particle system"""
        for i in range(300):
            x = (i * 67 + self.particle_phase * 50) % self.width()
            y = (i * 43 + self.scan_position * 0.4) % self.height()
            size = 2 + math.sin(self.pulse_phase + i * 0.5) * 2
            alpha = 80 + int(50 * math.sin(self.particle_phase + i * 0.3))
            
            # Multi-color premium particles
            if i % 7 == 0:
                color = QColor(255, 182, 193, int(alpha))  # Light Pink
            elif i % 5 == 0:
                color = QColor(255, 215, 0, int(alpha))    # Gold
            elif i % 3 == 0:
                color = QColor(255, 105, 180, int(alpha))  # Hot Pink
            else:
                color = QColor(255, 228, 196, int(alpha))  # Bisque
                
            painter.setPen(QPen(color, size))
            painter.drawPoint(int(x), int(y))
            
            # Some particles as small circles
            if i % 13 == 0:
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x, y), size/2, size/2)

    def draw_circuit_pattern(self, painter):
        """Premium circuit board pattern effect"""
        painter.setPen(QPen(QColor(255, 192, 203, 25), 1))
        
        # Circuit lines
        for i in range(0, self.width(), 60):
            for j in range(0, self.height(), 60):
                if (i + j) % 120 == 0:
                    alpha = 20 + 15 * math.sin(self.hologram_phase + i * 0.02 + j * 0.02)
                    painter.setPen(QPen(QColor(255, 182, 193, int(alpha)), 1))  # Light Pink
                    
                    if i < self.width() - 60 and j < self.height() - 60:
                        painter.drawLine(i, j, i + 30, j)
                        painter.drawLine(i + 30, j, i + 30, j + 30)
                        painter.drawLine(i + 30, j + 30, i + 60, j + 30)

class VoiceVisualizer(QWidget):
    """Voice engine visualization circle and waveform"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 170)
        self.pulse_phase = 0.0
        self.state = "idle"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_anim)
        self.timer.start(30)
        self.waveform_data = [0.0] * 20
        
    def update_anim(self):
        self.pulse_phase += 0.1
        if self.state == "listening":
            self.waveform_data = [random.uniform(0.1, 0.4) for _ in range(20)]
        elif self.state == "speaking":
            self.waveform_data = [random.uniform(0.2, 0.9) for _ in range(20)]
        elif self.state == "processing":
            self.waveform_data = [0.1 + 0.2 * math.sin(self.pulse_phase + i) for i in range(20)]
        else:
            self.waveform_data = [0.05] * 20
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        pulse_val = math.sin(self.pulse_phase) * 5
        outer_radius = 65 + pulse_val
        
        gradient = QRadialGradient(cx, cy, outer_radius)
        gradient.setColorAt(0, QColor(255, 0, 0, 40))
        gradient.setColorAt(0.7, QColor(255, 0, 0, 15))
        gradient.setColorAt(1, QColor(255, 0, 0, 0))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), outer_radius, outer_radius)
        
        pen = QPen(QColor(255, 0, 0, 180))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(cx, cy), 60, 60)
        
        core_radius = 25 + pulse_val * 0.5
        core_gradient = QRadialGradient(cx, cy, core_radius)
        core_gradient.setColorAt(0, QColor(255, 0, 0, 255))
        core_gradient.setColorAt(0.5, QColor(255, 0, 85, 180))
        core_gradient.setColorAt(1, QColor(15, 9, 19, 0))
        painter.setBrush(QBrush(core_gradient))
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)
        
        for i in range(36):
            angle = i * 10 * math.pi / 180
            data_val = self.waveform_data[i % len(self.waveform_data)]
            length = 5 + data_val * 15
            x1 = cx + (60) * math.cos(angle)
            y1 = cy + (60) * math.sin(angle)
            x2 = cx + (60 + length) * math.cos(angle)
            y2 = cy + (60 + length) * math.sin(angle)
            
            pen = QPen(QColor(255, 0, 0, 200))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

class SystemMonitorWidget(QWidget):
    """Left side top panel for CPU/GPU monitoring"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self.cpu_usage = 0.0
        self.ram_usage = 0.0
        self.gpu_load = 0.0
        self.gpu_temp = 42
        self.gpu_clock = 300
        
        self.init_ui()
        
        self.worker = SystemMonitorWorker()
        self.worker.stats_updated.connect(self._on_stats_updated)
        self.worker.start()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(8)
        
        title = QLabel("SYSTEM MONITOR")
        title.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold; letter-spacing: 1.5px;")
        layout.addWidget(title)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(255, 0, 0, 80); background: rgba(255, 0, 0, 80); height: 1px;")
        layout.addWidget(line)
        
        gpu_detail_layout = QHBoxLayout()
        self.gpu_clock_lbl = QLabel("GPU CLOCK\n300 MHz")
        self.gpu_temp_lbl = QLabel("TEMP\n42 C")
        self.gpu_load_lbl = QLabel("LOAD\n8%")
        for lbl in [self.gpu_clock_lbl, self.gpu_temp_lbl, self.gpu_load_lbl]:
            lbl.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;")
            lbl.setAlignment(Qt.AlignCenter)
            gpu_detail_layout.addWidget(lbl)
        
        gpu_detail_widget = QWidget()
        gpu_detail_widget.setLayout(gpu_detail_layout)
        gpu_detail_widget.setStyleSheet("background: rgba(255, 0, 0, 15); border: 1px solid rgba(255, 0, 0, 60); border-radius: 8px; padding: 5px;")
        layout.addWidget(gpu_detail_widget)
        
        gpu_bar_title = QHBoxLayout()
        gpu_bar_lbl = QLabel("GPU USAGE")
        gpu_bar_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold;")
        self.gpu_val_lbl = QLabel("0.0%")
        self.gpu_val_lbl.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;")
        gpu_bar_title.addWidget(gpu_bar_lbl)
        gpu_bar_title.addStretch()
        gpu_bar_title.addWidget(self.gpu_val_lbl)
        layout.addLayout(gpu_bar_title)
        
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setRange(0, 100)
        self.gpu_bar.setTextVisible(False)
        self.gpu_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 15);
                border: 1px solid rgba(255, 0, 0, 50);
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background: #ff0000;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.gpu_bar)
        
        cpu_bar_title = QHBoxLayout()
        cpu_bar_lbl = QLabel("CPU USAGE")
        cpu_bar_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold;")
        self.cpu_val_lbl = QLabel("0.0%")
        self.cpu_val_lbl.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;")
        cpu_bar_title.addWidget(cpu_bar_lbl)
        cpu_bar_title.addStretch()
        cpu_bar_title.addWidget(self.cpu_val_lbl)
        layout.addLayout(cpu_bar_title)
        
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 15);
                border: 1px solid rgba(255, 0, 0, 50);
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background: #ff0055;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.cpu_bar)
        
        ram_bar_title = QHBoxLayout()
        ram_bar_lbl = QLabel("RAM USAGE")
        ram_bar_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold;")
        self.ram_val_lbl = QLabel("0.0%")
        self.ram_val_lbl.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;")
        ram_bar_title.addWidget(ram_bar_lbl)
        ram_bar_title.addStretch()
        ram_bar_title.addWidget(self.ram_val_lbl)
        layout.addLayout(ram_bar_title)
        
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255, 255, 255, 15);
                border: 1px solid rgba(255, 0, 0, 50);
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background: #b000b0;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.ram_bar)

    def _on_stats_updated(self, cpu_usage, ram_usage, gpu_load, gpu_temp, gpu_clock):
        self.cpu_usage = cpu_usage
        self.ram_usage = ram_usage
        self.gpu_load = gpu_load
        self.gpu_temp = gpu_temp
        self.gpu_clock = gpu_clock
        
        self.cpu_bar.setValue(int(cpu_usage))
        self.cpu_val_lbl.setText(f"{cpu_usage:.1f}%")
        
        self.ram_bar.setValue(int(ram_usage))
        self.ram_val_lbl.setText(f"{ram_usage:.1f}%")
        
        self.gpu_bar.setValue(int(gpu_load))
        self.gpu_val_lbl.setText(f"{gpu_load:.1f}%")
        
        self.gpu_clock_lbl.setText(f"GPU CLOCK\n{gpu_clock} MHz")
        self.gpu_temp_lbl.setText(f"TEMP\n{gpu_temp}°C")
        self.gpu_load_lbl.setText(f"LOAD\n{int(gpu_load)}%")

class SystemMonitorWorker(QThread):
    stats_updated = pyqtSignal(float, float, float, int, int)

    def run(self):
        while True:
            cpu_usage = psutil.cpu_percent()
            ram_usage = psutil.virtual_memory().percent
            gpu_load, gpu_temp, gpu_clock = 0.0, 42, 300
            
            try:
                # Provide creationflags to hide the subprocess window on Windows
                import subprocess
                res = subprocess.run(
                    ['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu,clocks.gr', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=0.5, creationflags=subprocess.CREATE_NO_WINDOW
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = res.stdout.strip().split(',')
                    if len(parts) >= 3:
                        gpu_load = float(parts[0].strip())
                        gpu_temp = int(parts[1].strip())
                        gpu_clock = int(parts[2].strip())
                else:
                    gpu_load = random.randint(5, 15)
                    gpu_temp = 42 + random.randint(-1, 1)
                    gpu_clock = 300
            except:
                gpu_load = random.randint(5, 15)
                gpu_temp = 42 + random.randint(-1, 1)
                gpu_clock = 300
                
            self.stats_updated.emit(cpu_usage, ram_usage, gpu_load, gpu_temp, gpu_clock)
            time.sleep(2.0)

class VoiceEngineWidget(QWidget):
    """Left side bottom panel for Voice Engine monitoring"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self.noise_floor = 0.0
        self.mic_boost = 1.2
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(6)
        
        title = QLabel("VOICE ENGINE")
        title.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold; letter-spacing: 1.5px;")
        layout.addWidget(title)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(255, 0, 0, 80); background: rgba(255, 0, 0, 80); height: 1px;")
        layout.addWidget(line)
        
        self.visualizer = VoiceVisualizer()
        layout.addWidget(self.visualizer, 0, Qt.AlignCenter)
        layout.addSpacing(6)

        waveform_layout = QHBoxLayout()
        waveform_layout.setSpacing(2)
        waveform_layout.addStretch()
        self.waveform_bars = []
        for i in range(15):
            bar = QFrame()
            bar.setFixedWidth(3)
            bar.setFixedHeight(8)
            bar.setStyleSheet("background: rgba(255, 0, 0, 100); border-radius: 1px;")
            waveform_layout.addWidget(bar)
            self.waveform_bars.append(bar)
        waveform_layout.addStretch()
        layout.addLayout(waveform_layout)
        layout.addSpacing(6)

        self.live_lbl = QLabel("● LIVE")
        self.live_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
        self.live_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.live_lbl)
        
        noise_title = QHBoxLayout()
        noise_lbl = QLabel("NOISE FLOOR")
        noise_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold;")
        self.noise_val = QLabel("0.0 RMS")
        self.noise_val.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;")
        noise_title.addWidget(noise_lbl)
        noise_title.addStretch()
        noise_title.addWidget(self.noise_val)
        layout.addLayout(noise_title)
        
        self.noise_bar = QProgressBar()
        self.noise_bar.setRange(0, 100)
        self.noise_bar.setValue(5)
        self.noise_bar.setTextVisible(False)
        self.noise_bar.setStyleSheet(PROGRESSBAR_STYLESHEET.format(color="#ff0000"))
        layout.addWidget(self.noise_bar)
        
        boost_title = QHBoxLayout()
        boost_lbl = QLabel("MIC BOOST")
        boost_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold;")
        self.boost_val = QLabel("1.2x")
        self.boost_val.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;")
        boost_title.addWidget(boost_lbl)
        boost_title.addStretch()
        boost_title.addWidget(self.boost_val)
        layout.addLayout(boost_title)
        
        self.boost_bar = QProgressBar()
        self.boost_bar.setRange(0, 100)
        self.boost_bar.setValue(35)
        self.boost_bar.setTextVisible(False)
        self.boost_bar.setStyleSheet(PROGRESSBAR_STYLESHEET.format(color="#ff0055"))
        layout.addWidget(self.boost_bar)
        
        self.wave_timer = QTimer(self)
        self.wave_timer.timeout.connect(self.animate_waveform)
        self.wave_timer.start(100)
        
    def animate_waveform(self):
        state = self.visualizer.state
        for bar in self.waveform_bars:
            if state in ["listening", "speaking"]:
                h = random.randint(6, 18)
                bar.setFixedHeight(h)
                bar.setStyleSheet("background: #ff0000; border-radius: 1px;")
            else:
                bar.setFixedHeight(8)
                bar.setStyleSheet("background: rgba(255, 0, 0, 100); border-radius: 1px;")
                
    def set_state(self, state):
        self.visualizer.state = state
        if state == "listening":
            self.live_lbl.setText("● LISTENING")
            self.live_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
        elif state == "speaking":
            self.live_lbl.setText("● SPEAKING")
            self.live_lbl.setStyleSheet("color: #00ffff; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
        elif state == "processing":
            self.live_lbl.setText("● PROCESSING")
            self.live_lbl.setStyleSheet("color: #ffff00; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
        else:
            self.live_lbl.setText("● LIVE")
            self.live_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")

class SystemStatusWidget(QWidget):
    """Left side bottom panel for general system and latency status"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(300)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(6)
        
        title = QLabel("SYSTEM STATUS")
        title.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold; letter-spacing: 1.5px;")
        layout.addWidget(title)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(255, 0, 0, 80); background: rgba(255, 0, 0, 80); height: 1px;")
        layout.addWidget(line)
        
        grid = QHBoxLayout()
        self.last_latency_lbl = QLabel("LAST COMMAND\n0.00 SEC")
        self.avg_latency_lbl = QLabel("AVERAGE\n0.00 SEC")
        for lbl in [self.last_latency_lbl, self.avg_latency_lbl]:
            lbl.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 10px; font-weight: bold;")
            lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl)
            
        layout.addLayout(grid)

class LiveSessionWidget(QWidget):
    """Right-side chat history and command entry panel - STREAMING CAPABLE"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(350)
        self._active_bubble_label = None   # QLabel being streamed into
        self._active_bubble_text = ""      # accumulated text so far
        self._streaming = False
        self._cursor_visible = True
        self._cursor_timer = None
        self._bubble_count = 0
        self.MAX_BUBBLES = 50              # cap for 2-hour session stability
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(12)
        
        header = QHBoxLayout()
        title = QLabel("TONY - LIVE SESSION")
        title.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold; letter-spacing: 1.5px;")
        header.addWidget(title)
        header.addStretch()
        
        live_badge = QLabel("● LIVE")
        live_badge.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold;")
        header.addWidget(live_badge)
        layout.addLayout(header)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: rgba(255, 0, 0, 80); background: rgba(255, 0, 0, 80); height: 1px;")
        layout.addWidget(line)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(255, 255, 255, 5);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 0, 0, 80);
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.scroll_widget)
        self.chat_layout.setContentsMargins(0, 5, 0, 5)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area)
        
        input_container = QHBoxLayout()
        input_container.setSpacing(8)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Kuch likhkar bhejo TONY ko...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 0, 0, 10);
                border: 1px solid rgba(255, 0, 0, 80);
                border-radius: 15px;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 12px;
                padding: 6px 15px;
            }
            QLineEdit:focus {
                border: 1px solid #ff0000;
                background: rgba(255, 0, 0, 20);
            }
        """)
        self.input_field.returnPressed.connect(self.send_text)
        input_container.addWidget(self.input_field)
        
        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #ff0000;
                border: none;
                border-radius: 16px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #ff3399;
            }
            QPushButton:pressed {
                background: #cc0066;
            }
        """)
        self.send_btn.clicked.connect(self.send_text)
        input_container.addWidget(self.send_btn)
        
        layout.addLayout(input_container)
        
        # Cursor blink timer
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        
        # Show initial greeting bubble
        self.add_bubble("TONY", "Swagat hai Boss! Kuch bhi bolo, main sun raha hoon.")
        
    # ----------------------------------------------------------------
    # STREAMING API — called via Qt signals from the agent thread
    # ----------------------------------------------------------------
    def start_stream_bubble(self, sender: str):
        """Create a new streaming bubble. Called from agent via Qt signal."""
        # Close any previous unclosed stream
        if self._streaming:
            self.end_stream()
        self._streaming = True
        self._active_bubble_text = ""
        self._cursor_visible = True

        bubble = QFrame()
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(4)

        sender_lbl = QLabel(sender)
        if sender == "You":
            sender_lbl.setStyleSheet("color: #ffb6c1; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
            bubble.setStyleSheet("""
                QFrame {
                    background: rgba(255, 0, 0, 30);
                    border: 1px solid rgba(255, 0, 0, 120);
                    border-radius: 10px;
                    margin-left: 50px;
                }
            """)
        else:
            sender_lbl.setStyleSheet("color: #00ffff; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
            bubble.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 10);
                    border: 1px solid rgba(255, 255, 255, 30);
                    border-radius: 10px;
                    margin-right: 50px;
                }
            """)
        bubble_layout.addWidget(sender_lbl)

        from datetime import datetime as _dt
        time_lbl = QLabel(_dt.now().strftime("%H:%M"))
        time_lbl.setStyleSheet("color: rgba(255,255,255,40); font-family: 'Segoe UI'; font-size: 8px; border: none; background: transparent;")
        bubble_layout.addWidget(time_lbl)

        text_lbl = QLabel("\u258c")  # blinking cursor placeholder
        text_lbl.setWordWrap(True)
        text_lbl.setMinimumHeight(20)
        text_lbl.setStyleSheet("color: #ffffff; font-family: 'Segoe UI'; font-size: 11px; border: none; background: transparent;")
        bubble_layout.addWidget(text_lbl)
        self._active_bubble_label = text_lbl

        self._enforce_bubble_cap()
        self.chat_layout.takeAt(self.chat_layout.count() - 1)
        self.chat_layout.addWidget(bubble)
        self.chat_layout.addStretch()
        self._bubble_count += 1

        self._cursor_timer.start(500)
        self._auto_scroll()

    def stream_chunk(self, chunk: str):
        """Append text chunk to the active streaming bubble."""
        if self._active_bubble_label is None:
            return
        self._active_bubble_text += chunk
        self._active_bubble_label.setText(self._active_bubble_text + "\u258c")
        self._auto_scroll()

    def stream_replace(self, text: str):
        """Replace (not append) the active streaming bubble text — used for live STT partial transcripts."""
        if self._active_bubble_label is None:
            return
        self._active_bubble_text = text   # REPLACE, not append
        self._active_bubble_label.setText(self._active_bubble_text + "\u258c")
        self._auto_scroll()

    def end_stream(self):
        """Finalize the streaming bubble - remove cursor, lock text."""
        self._cursor_timer.stop()
        if self._active_bubble_label is not None:
            self._active_bubble_label.setText(self._active_bubble_text)
        self._active_bubble_label = None
        self._active_bubble_text = ""
        self._streaming = False
        self._auto_scroll()

    def _blink_cursor(self):
        """Toggle blinking cursor character."""
        if self._active_bubble_label is None:
            self._cursor_timer.stop()
            return
        self._cursor_visible = not self._cursor_visible
        cursor_char = "\u258c" if self._cursor_visible else " "
        self._active_bubble_label.setText(self._active_bubble_text + cursor_char)

    def _enforce_bubble_cap(self):
        """Keep at most MAX_BUBBLES in memory for long sessions."""
        while self._bubble_count >= self.MAX_BUBBLES:
            removed = False
            for i in range(self.chat_layout.count()):
                item = self.chat_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QFrame):
                    widget = item.widget()
                    self.chat_layout.removeWidget(widget)
                    widget.deleteLater()
                    self._bubble_count -= 1
                    removed = True
                    break
            if not removed:
                break

    def _auto_scroll(self):
        """Scroll chat to bottom."""
        QTimer.singleShot(30, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    # ----------------------------------------------------------------
    # STATIC BUBBLE (initial greeting / legacy fallback)
    # ----------------------------------------------------------------
    def add_bubble(self, sender, text):
        bubble = QFrame()
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(4)

        sender_lbl = QLabel(sender)
        if sender == "You":
            sender_lbl.setStyleSheet("color: #ffb6c1; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
            bubble.setStyleSheet("""
                QFrame {
                    background: rgba(255, 0, 0, 30);
                    border: 1px solid rgba(255, 0, 0, 120);
                    border-radius: 10px;
                    margin-left: 50px;
                }
            """)
        else:
            sender_lbl.setStyleSheet("color: #00ffff; font-family: 'Segoe UI'; font-size: 9px; font-weight: bold;")
            bubble.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 10);
                    border: 1px solid rgba(255, 255, 255, 30);
                    border-radius: 10px;
                    margin-right: 50px;
                }
            """)
        bubble_layout.addWidget(sender_lbl)

        from datetime import datetime as _dt
        time_lbl = QLabel(_dt.now().strftime("%H:%M"))
        time_lbl.setStyleSheet("color: rgba(255,255,255,40); font-family: 'Segoe UI'; font-size: 8px; border: none; background: transparent;")
        bubble_layout.addWidget(time_lbl)

        text_lbl = QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("color: #ffffff; font-family: 'Segoe UI'; font-size: 11px; border: none; background: transparent;")
        bubble_layout.addWidget(text_lbl)

        self._enforce_bubble_cap()
        self.chat_layout.takeAt(self.chat_layout.count() - 1)
        self.chat_layout.addWidget(bubble)
        self.chat_layout.addStretch()
        self._bubble_count += 1
        self._auto_scroll()

    def send_text(self):
        text = self.input_field.text().strip()
        if text:
            self.add_bubble("You", text)
            self.input_field.clear()
            from core import runtime_agent
            runtime_agent.send_text_command(text)

class CentralVisualizerCore(QWidget):
    """The central pulsing TONY core visualizer widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.pulse_phase = 0.0
        self.state = "idle"
        
        # Pre-allocate cached objects to avoid allocation on every frame
        self._cached_ring_path = QPainterPath()
        self._cached_inner_ring_path = QPainterPath()
        self._cached_inner_ring_path.addEllipse(QPointF(0, 0), 120, 120)
        
        # Precompute math
        self._math_sin = [math.sin(i) for i in range(12)]
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_anim)
        self.timer.start(33)  # 30 FPS is plenty for smooth pulsing, saves 50% CPU over 16ms
        
    def set_state(self, state):
        self.state = state.lower()
        
    def update_anim(self):
        self.pulse_phase += 0.05
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        
        state = self.state
        if "listening" in state:
            c_r, c_g, c_b = 255, 0, 0
            p_r, p_g, p_b = 255, 215, 0
            rot_speed = 15.0
            pulse_amp = 8.0
        elif "speaking" in state:
            c_r, c_g, c_b = 0, 255, 255
            p_r, p_g, p_b = 255, 255, 255
            rot_speed = 10.0
            pulse_amp = 12.0 * math.sin(self.pulse_phase * 2)
        elif "processing" in state or "thinking" in state:
            c_r, c_g, c_b = 255, 255, 0
            p_r, p_g, p_b = 255, 170, 0
            rot_speed = 35.0
            pulse_amp = 4.0
        elif "executing" in state:
            c_r, c_g, c_b = 255, 170, 0
            p_r, p_g, p_b = 255, 0, 0
            rot_speed = 25.0
            pulse_amp = 10.0
        elif "error" in state:
            c_r, c_g, c_b = 255, 0, 0
            p_r, p_g, p_b = 255, 255, 255
            rot_speed = 5.0
            pulse_amp = 15.0 if int(self.pulse_phase * 2) % 2 == 0 else 0.0
        else:
            c_r, c_g, c_b = 255, 182, 193
            p_r, p_g, p_b = 255, 0, 0
            rot_speed = 5.0
            pulse_amp = 3.0
            
        outer_gradient = QRadialGradient(cx, cy, 220)
        outer_gradient.setColorAt(0, QColor(c_r, c_g, c_b, 30))
        outer_gradient.setColorAt(0.6, QColor(c_r, c_g, c_b, 8))
        outer_gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(outer_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 220, 220)
        
        self._cached_ring_path.clear()
        ring_radius = 160 + pulse_amp
        self._cached_ring_path.addEllipse(QPointF(cx, cy), ring_radius, ring_radius)
        
        pen = QPen(QColor(c_r, c_g, c_b, 80))
        pen.setWidth(1)
        pen.setDashPattern([10, 15, 2, 15])
        painter.setPen(pen)
        painter.drawPath(self._cached_ring_path)
        
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.pulse_phase * rot_speed)
        
        pen = QPen(QColor(c_r, c_g, c_b, 120))
        pen.setWidth(2)
        pen.setDashPattern([30, 20])
        painter.setPen(pen)
        painter.drawPath(self._cached_inner_ring_path)
        
        for i in range(12):
            painter.rotate(30)
            painter.drawLine(115, 0, 125, 0)
            
        painter.restore()
        
        for i in range(12):
            angle = (self.pulse_phase * 0.5 + i * math.pi / 6) % (2 * math.pi)
            r = 140 + 10 * math.sin(self.pulse_phase + i)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            
            p_size = 3 + 2 * math.sin(self.pulse_phase * 2 + i)
            alpha = 150 + int(100 * math.sin(self.pulse_phase * 3 + i))
            color = QColor(p_r, p_g, p_b, max(0, min(255, alpha)))
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(px, py), p_size, p_size)
            
        core_gradient = QRadialGradient(cx, cy, 70)
        core_gradient.setColorAt(0, QColor(255, 255, 255, 180))
        core_gradient.setColorAt(0.3, QColor(c_r, c_g, c_b, 120))
        core_gradient.setColorAt(0.8, QColor(25, 9, 19, 100))
        core_gradient.setColorAt(1, QColor(0, 0, 0, 255))
        
        painter.setBrush(QBrush(core_gradient))
        pen = QPen(QColor(c_r, c_g, c_b, 200))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(cx, cy), 65, 65)
        
        bg_glow = QRadialGradient(cx, cy, 30)
        bg_glow.setColorAt(0, QColor(c_r, c_g, c_b, 150))
        bg_glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(bg_glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 30, 30)
        
        painter.setFont(QFont("Segoe UI", 24, QFont.Bold))
        
        for i in range(4, 0, -1):
            alpha = 60 - i * 12
            painter.setPen(QPen(QColor(c_r, c_g, c_b, alpha), i))
            painter.drawText(int(cx - 80), int(cy - 50), 160, 100, Qt.AlignCenter, "TONY")
            
        txt_grad = QLinearGradient(cx - 30, cy - 30, cx + 30, cy + 30)
        txt_grad.setColorAt(0, QColor(255, 255, 255))
        txt_grad.setColorAt(0.5, QColor(255, 182, 193))
        txt_grad.setColorAt(1, QColor(c_r, c_g, c_b))
        painter.setPen(QPen(QBrush(txt_grad), 2))
        painter.drawText(int(cx - 80), int(cy - 50), 160, 100, Qt.AlignCenter, "TONY")

class ModernFloatingWindow(QMainWindow):
    """ULTRA PREMIUM HUD window matching the cyberpunk visual style"""
    
    def __init__(self):
        super().__init__()
        print("🎯 ModernFloatingWindow INITIALIZED")
        self.setup_window()
        self.init_ui()
        
        # Instantiate signal bridge
        self.bridge = PyQtSignalBridge()
        self.bridge.connection_changed.connect(self.set_connection_label)
        self.bridge.status_changed.connect(self.set_status_label)
        # Legacy signals — kept for backward compat (streaming now primary)
        self.bridge.command_received.connect(lambda c: None)
        self.bridge.response_received.connect(lambda r: None)
        self.bridge.latency_changed.connect(self.set_latency_values)
        self.bridge.livekit_status_changed.connect(self.update_livekit_status)
        self.bridge.gemini_status_changed.connect(self.update_gemini_status)
        self.bridge.mic_status_changed.connect(self.update_mic_status)
        # Streaming chat signals
        self.bridge.stream_start.connect(self.live_session.start_stream_bubble)
        self.bridge.stream_chunk.connect(self.live_session.stream_chunk)
        self.bridge.stream_end.connect(self.live_session.end_stream)
        self.bridge.stream_replace.connect(self.live_session.stream_replace)
        self.bridge.add_static_bubble.connect(self.live_session.add_bubble)
        
        self.agent_thread = None
        self.setup_gui_bindings()
        self._start_agent_background()

    def update_livekit_status(self, text, style):
        self.livekit_status_lbl.setText(text)
        self.livekit_status_lbl.setStyleSheet(style)
        
    def update_gemini_status(self, text, style):
        self.gemini_status_lbl.setText(text)
        self.gemini_status_lbl.setStyleSheet(style)
        
    def update_mic_status(self, text, style):
        self.mic_status_lbl.setText(text)
        self.mic_status_lbl.setStyleSheet(style)
        
    def setup_window(self):
        self.setWindowTitle("TONY — Assistant")
        self.setMinimumSize(1000, 700)
        self.resize(1280, 800)

    def init_ui(self):
        bg_widget = QWidget(self)
        self.setCentralWidget(bg_widget)
        bg_widget.setObjectName("bg_widget")
        bg_widget.setStyleSheet("""
            QWidget#bg_widget {
                background-color: #050206;
                border: 2px solid rgba(255, 0, 0, 100);
            }
        """)
        
        main_layout = QVBoxLayout(bg_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 5, 10, 5)
        top_bar.setSpacing(15)
        
        logo_lbl = QLabel("TONY")
        logo_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        top_bar.addWidget(logo_lbl)
        
        sub_brand = QLabel("VOICE ASSISTANT")
        sub_brand.setStyleSheet("color: #888888; font-family: 'Segoe UI'; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        top_bar.addWidget(sub_brand)
        
        top_bar.addSpacing(30)
        
        settings_btn = QPushButton("SETTINGS")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 0, 0, 20);
                border: 1px solid #ff0000;
                border-radius: 12px;
                color: #ff0000;
                font-family: 'Segoe UI';
                font-size: 10px;
                font-weight: bold;
                padding: 4px 15px;
            }
            QPushButton:hover {
                background: rgba(255, 0, 0, 40);
                color: white;
            }
        """)
        top_bar.addWidget(settings_btn)
        
        top_bar.addStretch()
        
        self.status_title_lbl = QLabel("• READY")
        self.status_title_lbl.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        top_bar.addWidget(self.status_title_lbl)
        
        self.livekit_status_lbl = QLabel("LIVEKIT: OFFLINE")
        self.livekit_status_lbl.setStyleSheet("color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        top_bar.addWidget(self.livekit_status_lbl)
        
        self.gemini_status_lbl = QLabel("GEMINI: OFFLINE")
        self.gemini_status_lbl.setStyleSheet("color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        top_bar.addWidget(self.gemini_status_lbl)
        
        self.mic_status_lbl = QLabel("MIC: OFFLINE")
        self.mic_status_lbl.setStyleSheet("color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        top_bar.addWidget(self.mic_status_lbl)
        
        top_bar.addStretch()
        
        self.clock_lbl = QLabel("14:12:58")
        self.clock_lbl.setStyleSheet("color: #ffffff; font-family: 'Courier New'; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        top_bar.addWidget(self.clock_lbl)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        
        elite_lbl = QLabel("ELITE")
        elite_lbl.setStyleSheet("""
            QLabel {
                border: 1px solid #ff0000;
                border-radius: 10px;
                color: #ff0000;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: bold;
                padding: 2px 10px;
                background: transparent;
            }
        """)
        top_bar.addWidget(elite_lbl)
        
        boss_lbl = QLabel("BOSS")
        boss_lbl.setStyleSheet("""
            QLabel {
                border: 1px solid #ff0055;
                border-radius: 10px;
                color: #ffffff;
                font-family: 'Segoe UI';
                font-size: 9px;
                font-weight: bold;
                padding: 2px 10px;
                background: #ff0055;
            }
        """)
        top_bar.addWidget(boss_lbl)
        
        main_layout.addLayout(top_bar)
        
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        left_container = QWidget()
        left_container.setStyleSheet("background: transparent; border: none;")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        self.sys_monitor = SystemMonitorWidget()
        self.sys_monitor.setStyleSheet("background: rgba(15, 9, 19, 150); border: 1px solid rgba(255, 0, 0, 40); border-radius: 15px;")
        left_layout.addWidget(self.sys_monitor)
        
        self.voice_engine = VoiceEngineWidget()
        self.voice_engine.setStyleSheet("background: rgba(15, 9, 19, 150); border: 1px solid rgba(255, 0, 0, 40); border-radius: 15px;")
        left_layout.addWidget(self.voice_engine)
        
        self.sys_status = SystemStatusWidget()
        self.sys_status.setStyleSheet("background: rgba(15, 9, 19, 150); border: 1px solid rgba(255, 0, 0, 40); border-radius: 15px;")
        left_layout.addWidget(self.sys_status)
        
        content_layout.addWidget(left_container)
        
        center_container = QWidget()
        center_container.setStyleSheet("background: transparent; border: none;")
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)
        
        center_branding = QVBoxLayout()
        center_branding.setSpacing(2)
        tony_title = QLabel("T O N Y")
        tony_title.setStyleSheet("color: #ff0000; font-family: 'Segoe UI'; font-size: 48px; font-weight: bold; background: transparent; border: none;")
        tony_title.setAlignment(Qt.AlignCenter)
        center_branding.addWidget(tony_title)
        
        tony_subtitle = QLabel("TONY VOICE ASSISTANT  ·  AI CORE ACTIVE")
        tony_subtitle.setStyleSheet("color: #888888; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        tony_subtitle.setAlignment(Qt.AlignCenter)
        center_branding.addWidget(tony_subtitle)
        center_layout.addLayout(center_branding)
        
        max_status_lbl = QLabel("ALL SYSTEMS MAXIMUM - TURBO ENGAGED")
        max_status_lbl.setStyleSheet("""
            QLabel {
                background: rgba(255, 0, 0, 10);
                border: 1px solid rgba(255, 0, 0, 80);
                border-radius: 10px;
                color: #ff0000;
                font-family: 'Segoe UI';
                font-size: 10px;
                font-weight: bold;
                padding: 4px;
            }
        """)
        max_status_lbl.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(max_status_lbl)
        
        self.central_core = CentralVisualizerCore()
        center_layout.addWidget(self.central_core, 0, Qt.AlignCenter)
        
        content_layout.addWidget(center_container)
        
        self.live_session = LiveSessionWidget()
        self.live_session.setStyleSheet("background: rgba(15, 9, 19, 150); border: 1px solid rgba(255, 0, 0, 40); border-radius: 15px;")
        content_layout.addWidget(self.live_session)
        
        main_layout.addLayout(content_layout)
        


    def update_clock(self):
        self.clock_lbl.setText(datetime.now().strftime("%H:%M:%S"))

    def show_settings(self):
        print("⚙️ Settings clicked")
        
    def closeEvent(self, event):
        print("🛑 Close event triggered - Shutting down...")
        self.close_application()
        event.accept()

    def close_application(self):
        print("🔄 Shutting down TONY AI...")
        QApplication.quit()
        
    def set_latency_values(self, last_sec, avg_sec):
        self.sys_status.last_latency_lbl.setText(f"LAST COMMAND\n{last_sec:.2f} SEC")
        self.sys_status.avg_latency_lbl.setText(f"AVERAGE\n{avg_sec:.2f} SEC")
        
    def setup_gui_bindings(self):
        from core import runtime_agent
        from PyQt5.sip import isdeleted
        
        def safe_emit(signal, *args):
            try:
                if not isdeleted(self) and not isdeleted(self.bridge):
                    signal.emit(*args)
            except RuntimeError:
                pass
                
        runtime_agent.register_gui_callbacks(
            update_status=lambda s: safe_emit(self.bridge.status_changed, s),
            update_command=lambda c: safe_emit(self.bridge.command_received, c),
            update_response=lambda r: safe_emit(self.bridge.response_received, r),
            update_connection=lambda conn: safe_emit(self.bridge.connection_changed, conn),
            update_latency=lambda last, avg: safe_emit(self.bridge.latency_changed, last, avg),
            update_mic_status=lambda mic_text: safe_emit(
                self.bridge.mic_status_changed,
                mic_text,
                "color: #00ff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;"
            ),
            # Streaming callbacks — routed through Qt signals for thread safety
            stream_start=lambda sender: safe_emit(self.bridge.stream_start, sender),
            stream_chunk=lambda chunk: safe_emit(self.bridge.stream_chunk, chunk),
            stream_end=lambda: safe_emit(self.bridge.stream_end),
            # Partial transcript (replace, not append)
            stream_replace=lambda text: safe_emit(self.bridge.stream_replace, text),
            # History loading
            add_static_bubble=lambda sender, text: safe_emit(self.bridge.add_static_bubble, sender, text),
        )
        
    def set_connection_label(self, text):
        text_lower = text.lower()
        
        # Parse LiveKit
        if "livekit: online" in text_lower or "livekit: connected" in text_lower or "connected" in text_lower:
            self.livekit_status_lbl.setText("LIVEKIT: ONLINE")
            self.livekit_status_lbl.setStyleSheet("color: #00ff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        elif "livekit: connecting" in text_lower or "connecting" in text_lower:
            self.livekit_status_lbl.setText("LIVEKIT: CONNECTING")
            self.livekit_status_lbl.setStyleSheet("color: #ffff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        elif "livekit: reconnecting" in text_lower or "reconnecting" in text_lower:
            self.livekit_status_lbl.setText("LIVEKIT: RECONNECTING")
            self.livekit_status_lbl.setStyleSheet("color: #ffaa00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        else:
            self.livekit_status_lbl.setText("LIVEKIT: OFFLINE")
            self.livekit_status_lbl.setStyleSheet("color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
            
        # Parse Gemini
        if "gemini: online" in text_lower or "gemini: active" in text_lower or "active" in text_lower:
            self.gemini_status_lbl.setText("GEMINI: ONLINE")
            self.gemini_status_lbl.setStyleSheet("color: #00ff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        elif "gemini: connecting" in text_lower:
            self.gemini_status_lbl.setText("GEMINI: CONNECTING")
            self.gemini_status_lbl.setStyleSheet("color: #ffff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        else:
            self.gemini_status_lbl.setText("GEMINI: OFFLINE")
            self.gemini_status_lbl.setStyleSheet("color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
        
    def set_status_label(self, text):
        text_lower = text.lower()
        # ---- Label text
        if "listening" in text_lower:
            self.status_title_lbl.setText("TONY: LISTENING")
        elif "speaking" in text_lower:
            self.status_title_lbl.setText("TONY: SPEAKING")
        elif "thinking" in text_lower or "processing" in text_lower:
            self.status_title_lbl.setText("TONY: THINKING")
        elif "executing" in text_lower:
            self.status_title_lbl.setText("TONY: EXECUTING")
        elif "speech detected" in text_lower or "speech_detected" in text_lower:
            self.status_title_lbl.setText("TONY: SPEECH DETECTED")
        elif "transcrib" in text_lower:
            self.status_title_lbl.setText("TONY: TRANSCRIBING")
        elif "interrupt" in text_lower:
            self.status_title_lbl.setText("TONY: INTERRUPTED")
        elif "error" in text_lower:
            self.status_title_lbl.setText("TONY: ERROR")
        elif "offline" in text_lower:
            self.status_title_lbl.setText("TONY: OFFLINE")
        elif "idle" in text_lower or "ready" in text_lower:
            self.status_title_lbl.setText("TONY: READY")
        else:
            self.status_title_lbl.setText(f"TONY: {text.upper()}")

        self.voice_engine.set_state(text.lower())
        self.central_core.set_state(text.lower())

        # ---- Status color
        if "listening" in text_lower:
            col = "#ff0000"
        elif "speech detected" in text_lower:
            col = "#ff5500"
        elif "transcrib" in text_lower:
            col = "#ffaa00"
        elif "thinking" in text_lower or "processing" in text_lower:
            col = "#ffff00"
        elif "executing" in text_lower:
            col = "#ffaa00"
        elif "speaking" in text_lower:
            col = "#00ffff"
        elif "interrupt" in text_lower:
            col = "#ff5500"
        elif "error" in text_lower or "offline" in text_lower:
            col = "#ff0000"
        else:
            col = "#888888"

        self.status_title_lbl.setStyleSheet(
            f"color: {col}; font-family: 'Segoe UI'; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )

    def _start_agent_background(self):
        def run_agent():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                print("🟡 Starting TONY agent in background thread...")
                
                # Emit initial statuses
                self.bridge.livekit_status_changed.emit("LIVEKIT: CONNECTING", "color: #ffff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                self.bridge.gemini_status_changed.emit("GEMINI: CONNECTING", "color: #ffff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                self.bridge.mic_status_changed.emit("MIC: CONNECTING", "color: #ffff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                self.bridge.status_changed.emit("connecting")
                
                async def handshake():
                    import os
                    from pathlib import Path
                    from dotenv import load_dotenv
                    
                    # 1. LOAD ENV
                    print("[BOOT] Loading environment...")
                    dir_path = Path(__file__).resolve().parent
                    env_path = dir_path / ".env"
                    load_dotenv(dotenv_path=env_path)
                    
                    lk_url = os.getenv("LIVEKIT_URL")
                    lk_key = os.getenv("LIVEKIT_API_KEY")
                    lk_secret = os.getenv("LIVEKIT_API_SECRET")
                    google_key = os.getenv("GOOGLE_API_KEY")
                    
                    print("[ENV] Checking credentials:")
                    print("LIVEKIT_URL:", "PRESENT" if lk_url else "MISSING")
                    print("LIVEKIT_API_KEY:", "PRESENT" if lk_key else "MISSING")
                    print("LIVEKIT_API_SECRET:", "PRESENT" if lk_secret else "MISSING")
                    print("GOOGLE_API_KEY:", "PRESENT" if google_key else "MISSING")
                    
                    livekit_ok = False
                    gemini_ok = False
                    mic_ok = False
                    
                    # 2. CONNECT LIVEKIT (Client)
                    if not lk_url or not lk_key or not lk_secret:
                        print("[LIVEKIT ERROR] Missing LiveKit credentials in .env")
                        self.bridge.livekit_status_changed.emit("LIVEKIT: OFFLINE", "color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                    else:
                        print("[LIVEKIT] Connecting...")
                        try:
                            from livekit import rtc, api
                            import time
                            client_id = f"tony-desktop-client-{int(time.time())}"
                            room_name = f"tony-voice-room-{int(time.time())}"
                            token = api.AccessToken(lk_key, lk_secret)\
                                .with_identity(client_id)\
                                .with_grants(api.VideoGrants(room_join=True, room=room_name))\
                                .to_jwt()
                            self.client_room = rtc.Room()
                            
                            self.devices = rtc.MediaDevices()
                            self.player = self.devices.open_output()
                            await self.player.start()
                            
                            @self.client_room.on("track_subscribed")
                            def on_track_subscribed(track: rtc.Track, publication, participant):
                                if track.kind == rtc.TrackKind.KIND_AUDIO:
                                    print(f"[AUDIO] Subscribed to agent audio track: {track.sid}")
                                    asyncio.create_task(self.player.add_track(track))
                            
                            @self.client_room.on("data_received")
                            def on_data_received(dp: rtc.DataPacket):
                                if dp.topic == "tony_gui_rpc":
                                    try:
                                        import json
                                        payload = json.loads(dp.data.decode("utf-8"))
                                        cb_name = payload.get("callback")
                                        args = payload.get("args", [])
                                        if cb_name == 'update_status':
                                            self.bridge.status_changed.emit(*args)
                                        elif cb_name == 'update_command':
                                            self.bridge.command_received.emit(*args)
                                        elif cb_name == 'update_response':
                                            self.bridge.response_received.emit(*args)
                                        elif cb_name == 'update_connection':
                                            self.bridge.connection_changed.emit(*args)
                                        elif cb_name == 'update_latency':
                                            self.bridge.latency_changed.emit(*args)
                                        elif cb_name == 'update_mic_status':
                                            self.bridge.mic_status_changed.emit(
                                                args[0],
                                                "color: #00ff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;"
                                            )
                                        elif cb_name == 'stream_start':
                                            self.bridge.stream_start.emit(*args)
                                        elif cb_name == 'stream_chunk':
                                            self.bridge.stream_chunk.emit(*args)
                                        elif cb_name == 'stream_end':
                                            self.bridge.stream_end.emit()
                                        elif cb_name == 'stream_replace':
                                            self.bridge.stream_replace.emit(*args)
                                        elif cb_name == 'add_static_bubble':
                                            self.bridge.add_static_bubble.emit(*args)
                                    except Exception as e:
                                        print(f"⚠️ Error handling GUI RPC: {e}")
                                    
                            await self.client_room.connect(lk_url, token)
                            print("[LIVEKIT] Connected")
                            print(f"[LIVEKIT] Room: {room_name}")
                            self.bridge.livekit_status_changed.emit("LIVEKIT: ONLINE | STT: READY", "color: #00ff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                            livekit_ok = True
                        except Exception as e:
                            print(f"[LIVEKIT ERROR] {e}")
                            self.bridge.livekit_status_changed.emit("LIVEKIT: OFFLINE", "color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")

                    # 3. INITIALIZE GEMINI
                    if not google_key:
                        print("[GEMINI ERROR] GOOGLE_API_KEY is missing.")
                        self.bridge.gemini_status_changed.emit("GEMINI: OFFLINE", "color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                    else:
                        print("[GEMINI] Initializing...")
                        try:
                            os.environ["GEMINI_API_KEY"] = google_key
                            from core.runtime_agent import _init_global_llm
                            llm = _init_global_llm()
                            if not llm:
                                raise ValueError("Gemini Realtime LLM initialization failed")
                            print("[GEMINI] Model initialized")
                            print("[GEMINI] Realtime session ready")
                            print("[GEMINI] ONLINE")
                            self.bridge.gemini_status_changed.emit("GEMINI: ONLINE | TTS: READY", "color: #00ff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                            gemini_ok = True
                        except Exception as e:
                            print(f"[GEMINI ERROR] {e}")
                            self.bridge.gemini_status_changed.emit("GEMINI: OFFLINE", "color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")

                    # 4. INITIALIZE MICROPHONE
                    print("[MIC] Enumerating devices...")
                    try:
                        if not hasattr(self, "devices"):
                            from livekit import rtc
                            self.devices = rtc.MediaDevices()
                            
                        inputs = self.devices.list_input_devices()
                        if not inputs:
                            raise ValueError("No input devices found")
                        
                        default_in = self.devices.default_input_device()
                        selected_idx = None
                        selected_name = None
                        
                        if default_in:
                            selected_idx = default_in['index']
                            selected_name = default_in['name']
                        else:
                            # If default is None, find the first device with "microphone" or "mic" in its name
                            for inp in inputs:
                                name_lower = inp.get('name', '').lower()
                                if "microphone" in name_lower or "mic" in name_lower:
                                    # Prefer HostAPI 2 (WASAPI) or 1 (DirectSound)
                                    if inp.get('hostapi') in [2, 1]:
                                        selected_idx = inp['index']
                                        selected_name = inp['name']
                                        break
                            
                            # Fallback if no preferred HostAPI microphone found
                            if selected_idx is None:
                                for inp in inputs:
                                    name_lower = inp.get('name', '').lower()
                                    if "microphone" in name_lower or "mic" in name_lower:
                                        selected_idx = inp['index']
                                        selected_name = inp['name']
                                        break
                                        
                            # Absolute fallback
                            if selected_idx is None:
                                selected_idx = inputs[0]['index']
                                selected_name = inputs[0]['name']

                        print(f"[MIC] Selected device: {selected_name}")
                        print(f"[MIC] Device index: {selected_idx}")
                        print("[MIC] Sample rate: 16000")
                        
                        self.mic = self.devices.open_input(input_device=selected_idx, enable_aec=True, noise_suppression=True, queue_capacity=500)
                        print("[MIC] READY")
                        print("[AUDIO] input stream opened")
                        self.bridge.mic_status_changed.emit("MIC: ONLINE", "color: #00ff00; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")
                        mic_ok = True
                        
                        if livekit_ok:
                            from livekit import rtc
                            self.mic_track = rtc.LocalAudioTrack.create_audio_track("microphone", self.mic.source)
                            print("[LIVEKIT AUDIO] microphone track created")
                            pub_opts = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
                            await self.client_room.local_participant.publish_track(self.mic_track, pub_opts)
                            print("[LIVEKIT AUDIO] microphone track published")
                    except Exception as e:
                        print(f"[MIC ERROR] {e}")
                        self.bridge.mic_status_changed.emit("MIC: OFFLINE", "color: #ff0055; font-family: 'Segoe UI'; font-size: 10px; font-weight: bold; background: transparent; border: none;")

                    if livekit_ok and gemini_ok and mic_ok:
                        print("[SESSION] Starting agent session...")
                        print("[VOICE] VOICE PIPELINE READY")
                        self.bridge.status_changed.emit("listening")
                        return True
                    else:
                        errors = []
                        if not livekit_ok: errors.append("LIVEKIT")
                        if not gemini_ok: errors.append("GEMINI")
                        if not mic_ok: errors.append("MIC")
                        raise ValueError(f"Failed components: {', '.join(errors)}")
                
                try:
                    loop.run_until_complete(handshake())
                    handshake_success = True
                except Exception as ex:
                    print(f"❌ Handshake startup error: {ex}")
                    import traceback
                    traceback.print_exc()
                    err_msg = str(ex).split('\n')[0].upper()
                    self.bridge.status_changed.emit(f"offline (error: {err_msg})")
                    handshake_success = False
                
                if handshake_success:
                    import sys
                    if "client" in sys.argv:
                        print("🟢 Starting TONY client-only loop...")
                        loop.run_forever()
                    else:
                        print("🟢 Starting TONY client loop and worker...")
                        async def start_worker():
                            try:
                                from livekit.agents.worker import AgentServer
                                from livekit.agents import WorkerOptions, JobExecutorType
                                opts = WorkerOptions(entrypoint_fnc=entrypoint, job_executor_type=JobExecutorType.THREAD)
                                server = AgentServer.from_server_options(opts)
                                await server.run(devmode=True)
                            except Exception as w_err:
                                print(f"❌ Failed to start integrated worker: {w_err}")
                        loop.create_task(start_worker())
                        loop.run_forever()
            except Exception as e:
                print(f"❌ Background agent error: {e}")
                
        self.agent_thread = threading.Thread(target=run_agent, daemon=True)
        self.agent_thread.start()






        
# ---------- firebase init (service.json bundled inside exe) ----------
def get_service_json_path():
    """
    Returns the path to service.json whether running from source or PyInstaller exe.
    Checks FIREBASE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS first.
    If bundled, loads from _MEIPASS (internal temp folder).
    """
    env_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and os.path.exists(env_path):
        return env_path

    if getattr(sys, 'frozen', False):  # Running from PyInstaller bundle
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    json_path = os.path.join(base_path, "service.json")
    return json_path


def init_firebase_from_embedded(database_url=None):
    """
    Initializes Firebase from service.json (bundled inside exe or local dir).
    """
    path = get_service_json_path()
    
    if not os.path.exists(path):
        # Don't show message box here - we'll handle it in main after QApplication is created
        raise FileNotFoundError(f"Firebase service file not found: {path}")
    
    cred = credentials.Certificate(path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': database_url or 'https://Tony-Tony-default-rtdb.firebaseio.com/'
    })


# ---------- rest of your original app code (unchanged) ----------
def set_env_variable(key, value):
    """Permanently set a system environment variable"""
    try:
        subprocess.run(["setx", key, value], shell=True, check=True)
    except Exception as e:
        print(f"Failed to set environment variable: {e}")

def get_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return False

def prompt_access_key():
    key, ok = QInputDialog.getText(None, "Activation Required", "Enter your Access Key:")
    if ok and key.strip():
        return key.strip()
    return None

def prompt_user_name():
    while True:
        name, ok = QInputDialog.getText(
            None,
            "User Setup - Tony AI",
            "Enter your name (for personalized greeting):"
        )
        if not ok:
            reply = QMessageBox.question(
                None,
                "Confirm",
                "No name entered. Use default 'User'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                return "User"
            continue
        if name.strip():
            return name.strip()
        QMessageBox.warning(None, "Invalid", "Name cannot be empty.")

def prompt_lan():
    while True:
        name, ok = QInputDialog.getText(
            None,
            "Language Setup - Tony AI", 
            "Enter the language you want to use:"
        )
        if not ok:
            reply = QMessageBox.question(
                None,
                "Confirm",
                "No Language Entered. Use default 'Hindi'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                return "Hindi"
            continue
        if name.strip():
            return name.strip()
        QMessageBox.warning(None, "Invalid", "Language cannot be empty.")

def ensure_user_name():
    current = os.getenv("USER_NAME", "").strip()
    if current:
        return current
    
    # Show name prompt FIRST
    user_name = prompt_user_name()
    
    # Show language prompt SECOND
    mother_tongue = prompt_lan()
    
    # Set environment variables
    set_env_variable("USER_NAME", user_name)
    set_env_variable("LAN", mother_tongue)
    os.environ["USER_NAME"] = user_name
    os.environ["LAN"] = mother_tongue
    
    print(f"✅ User profile set: {user_name}, Language: {mother_tongue}")
    return user_name

BASE_SECRET = (
    "R7d9cQvPZ5mK2tYxW3nB8aJ4uH6sL1eT0gV9rC2pN7qD5fM8hK3zX1yU6jA4bS0i"
    "G7lE2oV9wQ5tR3nD8mC1kH6pJ4xZ0aY7"
)
PREMIUM_SECRET = (
    "N4kM8qS1vH6cL2xT9eR5jU3pA7zY0wD8fG2bC6nV4mK1tQ9rJ5hX3lS7oE0iP8aZ2"
    "Y6uW3dR9"
)
ELITE_SECRET = (
    "Z8xC1vB5nM2kL7jH3gF9dS4aA0pQ6wE2rT8yU1iO7lK3mN9cV5bX2zJ6hD4eR0tY8"
    "W3qP6uI1"
)

VARIANT_SECRET_MAP = {
    "base": BASE_SECRET,
    "premium": PREMIUM_SECRET,
    "elite": ELITE_SECRET,
}

VARIANT_NAMES = {
    "base": "Base",
    "premium": "Premium", 
    "elite": "Elite"
}

UPGRADE_PATHS = {
    "base": "premium",
    "premium": "elite",
    "elite": None  # No upgrade from elite
}

def detect_variant_and_ref(access_key):
    for variant in ["base", "premium", "elite"]:
        ref = db.reference(f"Tony{variant}/{access_key}")
        record = ref.get()
        if record is not None:
            return variant, ref, record
    return None, None, None

def prompt_upgrade(current_variant):
    """Ask user if they want to upgrade to next tier"""
    next_variant = UPGRADE_PATHS.get(current_variant)
    
    if not next_variant:
        return False  # No upgrade available
    
    current_name = VARIANT_NAMES.get(current_variant, current_variant)
    next_name = VARIANT_NAMES.get(next_variant, next_variant)
    
    msg = QMessageBox()
    msg.setWindowTitle("Upgrade Available")
    msg.setText(f"You are currently using {current_name} version.\n\nWould you like to upgrade to {next_name} version?")
    msg.setIcon(QMessageBox.Question)
    
    upgrade_btn = QPushButton(f"Upgrade to {next_name}")
    no_btn = QPushButton("Continue with Current")
    
    msg.addButton(upgrade_btn, QMessageBox.AcceptRole)
    msg.addButton(no_btn, QMessageBox.RejectRole)
    
    msg.exec_()
    
    if msg.clickedButton() == upgrade_btn:
        return True
    return False

def process_upgrade(current_variant):
    """Handle the upgrade process"""
    next_variant = UPGRADE_PATHS.get(current_variant)
    if not next_variant:
        return False
    
    next_name = VARIANT_NAMES.get(next_variant, next_variant)
    
    # Prompt for upgrade key
    upgrade_key, ok = QInputDialog.getText(
        None, 
        f"Upgrade to {next_name}", 
        f"Enter your {next_name} Access Key:"
    )
    
    if not ok or not upgrade_key.strip():
        return False
    
    upgrade_key = upgrade_key.strip()
    
    # Verify upgrade key
    variant, ref, record = detect_variant_and_ref(upgrade_key)
    
    if not variant:
        QMessageBox.critical(None, "Error", f"Key '{upgrade_key}' not found in any variant.")
        return False
    
    if variant != next_variant:
        QMessageBox.critical(
            None, 
            "Error", 
            f"This key is for {VARIANT_NAMES.get(variant, variant)} version.\n"
            f"You need a {VARIANT_NAMES.get(next_variant, next_variant)} key for upgrade."
        )
        return False
    
    if get_bool(record.get("isUsed")):
        QMessageBox.critical(None, "Error", f"Key '{upgrade_key}' is already used on another device.")
        return False
    
    # Mark upgrade key as used
    try:
        ref.update({"isUsed": True})
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Failed to update key on server: {e}")
        return False
    
    # Update environment variables for new variant
    set_env_variable("ACCESS_KEY", upgrade_key)
    set_env_variable("IS_ACTIVATED", "true")
    set_env_variable("ACTIVATION_COUNT", "1")
    set_env_variable("TONY_VARIANT", next_variant)
    set_env_variable("SYSTEM_CONST_32", VARIANT_SECRET_MAP[next_variant])
    
    os.environ["ACCESS_KEY"] = upgrade_key
    os.environ["IS_ACTIVATED"] = "true"
    os.environ["ACTIVATION_COUNT"] = "1"
    os.environ["TONY_VARIANT"] = next_variant
    os.environ["SYSTEM_CONST_32"] = VARIANT_SECRET_MAP[next_variant]
    
    QMessageBox.information(
        None, 
        "Upgrade Successful", 
        f"Successfully upgraded to {next_name} version!\n"
        f"All features of {next_name} are now available."
    )
    
    return True

def activation_gate():
    access_key = os.getenv("ACCESS_KEY")
    is_activated = os.getenv("IS_ACTIVATED", "").strip().lower() == "true"
    current_variant = os.getenv("TONY_VARIANT", "")
    
    try:
        activation_count = int(os.getenv("ACTIVATION_COUNT", "0").strip() or "0")
    except ValueError:
        activation_count = 0

    # Check if already activated and valid
    if is_activated and access_key and activation_count >= 1:
        secret = os.getenv("SYSTEM_CONST_32", "")
        if current_variant in VARIANT_SECRET_MAP and secret == VARIANT_SECRET_MAP[current_variant]:
            # Check if upgrade is available and prompt user
            if UPGRADE_PATHS.get(current_variant):
                if prompt_upgrade(current_variant):
                    if process_upgrade(current_variant):
                        # Successfully upgraded, continue with new variant
                        return True
                    else:
                        # Upgrade failed, continue with current variant
                        QMessageBox.information(
                            None,
                            "Upgrade Cancelled",
                            "Continuing with your current version."
                        )
            return True
        else:
            QMessageBox.critical(None, "Error", "This is incompatible version.")
            return False

    # New activation flow (existing code)
    if not access_key:
        access_key = prompt_access_key()
        if not access_key:
            QMessageBox.critical(None, "Error", "Access Key not provided. Exiting.")
            return False

    variant, ref, record = detect_variant_and_ref(access_key)
    if not variant:
        QMessageBox.critical(None, "Error", f"Key '{access_key}' not found in any variant.")
        return False

    if get_bool(record.get("isUsed")):
        QMessageBox.critical(None, "Error", f"Key '{access_key}' is already used on another device.")
        return False

    try:
        ref.update({"isUsed": True})
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Failed to update key on server: {e}")
        return False

    set_env_variable("ACCESS_KEY", access_key)
    set_env_variable("IS_ACTIVATED", "true")
    set_env_variable("ACTIVATION_COUNT", "1")
    set_env_variable("TONY_VARIANT", variant)
    set_env_variable("SYSTEM_CONST_32", VARIANT_SECRET_MAP[variant])

    os.environ["ACCESS_KEY"] = access_key
    os.environ["IS_ACTIVATED"] = "true"
    os.environ["ACTIVATION_COUNT"] = "1"
    os.environ["TONY_VARIANT"] = variant
    os.environ["SYSTEM_CONST_32"] = VARIANT_SECRET_MAP[variant]

    return True

def safe_activation_gate():
    try:
        if activation_gate():
            return True, "activated"
        else:
            return False, "failed"
    except Exception as e:
        print("Unexpected Activation Error:", e)
        print(traceback.format_exc())
        QMessageBox.warning(None, "Warning",
                            "Firebase se connect karte time error aaya.\n"
                            "App fallback mode me start ho raha hai.")
        return False, "fallback"




class WaitForInternetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TONY - Waiting for Internet")
        self.setFixedSize(400, 150)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout()
        
        self.message_label = QLabel("🔍 Checking internet connection...\nTONY requires internet to start")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Infinite progress
        layout.addWidget(self.progress_bar)
        
        self.timer_label = QLabel("Next check in: 10 seconds")
        self.timer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_label)
        
        button_box = QDialogButtonBox()
        self.cancel_button = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        self.cancel_button.clicked.connect(self.reject)
        
        # Setup timer
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_internet)
        self.seconds_remaining = 10
        
        # Start first check immediately
        QTimer.singleShot(1000, self.check_internet)
        
    def check_internet(self):
        """Check if internet is available"""
        if self.is_internet_available():
            self.message_label.setText("✅ Internet connected!\nStarting TONY...")
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(1)
            QTimer.singleShot(1000, self.accept)  # Close after 1 second
        else:
            self.seconds_remaining = 10
            self.message_label.setText("❌ No internet connection\nRetrying automatically...")
            self.start_countdown()
            
    def start_countdown(self):
        """Start 10 second countdown for next check"""
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # Update every second
        
    def update_countdown(self):
        """Update countdown timer"""
        self.seconds_remaining -= 1
        self.timer_label.setText(f"Next check in: {self.seconds_remaining} seconds")
        
        if self.seconds_remaining <= 0:
            self.countdown_timer.stop()
            self.check_internet()  # Check again
            
    def is_internet_available(self):
        """Simple internet connectivity check"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            return True
        except:
            try:
                socket.create_connection(("google.com", 80), timeout=5)
                return True
            except:
                return False

def wait_for_internet():
    """Wait for internet connection with auto-retry"""
    dialog = WaitForInternetDialog()
    result = dialog.exec_()
    return result == QDialog.Accepted





def main():
    """URGENT FIX - Firebase Verification BEFORE UI Launch"""
    app = None
    
    try:
        # Initialize QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("TONY AI")
        app.setApplicationVersion("4.0")
        
        # Prevent app from quitting when last window closes (Set to True to quit properly on exit)
        app.setQuitOnLastWindowClosed(False)
        
        print("🚀 STARTING TONY AI - PREMIUM EDITION")
        
        # Bypass Firebase & Activation Gate - Run in Elite mode locally
        os.environ["ACCESS_KEY"] = "LOCAL_DEV_KEY"
        os.environ["IS_ACTIVATED"] = "true"
        os.environ["ACTIVATION_COUNT"] = "1"
        os.environ["TONY_VARIANT"] = "elite"
        os.environ["SYSTEM_CONST_32"] = VARIANT_SECRET_MAP["elite"]
        os.environ["USER_NAME"] = "BOSS"
        os.environ["LAN"] = "English"
        
        # Ensure user name is set BEFORE UI
        print("👤 Setting up user profile...")
        user_name = ensure_user_name()
        print(f"✅ User profile set: {user_name}")
        
        # STEP 6: ONLY AFTER ALL VERIFICATIONS - Show UI
        print("🎨 Launching premium UI...")
        
        # Show ULTRA PREMIUM scanning animation
        scanning_window = ScanningAnimation()
        scanning_window.show()
        
        # Create premium main window
        main_window = ModernFloatingWindow()
        
        def show_main_and_keep_alive():
            print("🔄 Transitioning to premium main window...")
            scanning_window.close()
            
            # Show and activate premium main window maximized
            main_window.showMaximized()
            main_window.raise_()
            main_window.activateWindow()
            main_window.setFocus()
            
            print("✅ PREMIUM MAIN WINDOW SHOULD BE VISIBLE NOW!")
            print(f"👤 Welcome, {user_name}!")
            app.setQuitOnLastWindowClosed(True)
        
        # Show main window after scanning with delay
        QTimer.singleShot(3500, show_main_and_keep_alive)
        
        print("🔄 Starting LOVELY EVENT LOOP...")
        result = app.exec_()
        print(f"🔚 Application properly exited: {result}")
        return result
        
    except Exception as e:
        print(f"❌ LOVELY ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if app:
            app.processEvents()

if __name__ == "__main__":
    # Let Qt exit normally instead of terminating the process immediately
    sys.exit(main())


