from __future__ import annotations

import os
import mimetypes
import tempfile
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTextEdit,
    QScrollArea,
    QSizePolicy,
    QProgressBar,
    QMessageBox,
)
from PyQt6.QtGui import QFont, QPixmap, QImage, QImageReader, QIcon, QTextDocument
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog


class AttachmentPreviewDialog(QDialog):
    """附件预览对话框"""

    def __init__(self, file_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.file_type = (
            mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        )
        self.file_category = self.file_type.split("/")[0]

        self._setup_ui()
        self._load_file()

    def _setup_ui(self):
        self.setWindowTitle(f"预览: {self.file_name}")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)

        # 标题栏
        title_frame = QFrame()
        title_frame.setFrameStyle(QFrame.Shape.Box)
        title_frame.setStyleSheet("""
            QFrame {
                background: #313244;
                border: 1px solid #45475a;
                border-bottom: none;
                padding: 12px;
            }
        """)
        title_layout = QVBoxLayout(title_frame)
        title_layout.setSpacing(4)

        name_label = QLabel(self.file_name)
        name_label.setFont(QFont("", 13, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #cdd6f4;")
        title_layout.addWidget(name_label)

        info_label = QLabel(f"类型: {self.file_type} | 大小: {self._get_file_size()}")
        info_label.setStyleSheet("font-size: 11px; color: #a6adc8;")
        title_layout.addWidget(info_label)

        layout.addWidget(title_frame)

        # 工具栏
        toolbar_frame = QFrame()
        toolbar_frame.setFrameStyle(QFrame.Shape.Box)
        toolbar_frame.setStyleSheet("""
            QFrame {
                background: #45475a;
                border: 1px solid #585b70;
                border-bottom: none;
                padding: 8px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        self.open_btn = QPushButton("打开")
        self.open_btn.clicked.connect(self._open_file)
        toolbar_layout.addWidget(self.open_btn)

        self.save_btn = QPushButton("另存为...")
        self.save_btn.clicked.connect(self._save_as)
        toolbar_layout.addWidget(self.save_btn)

        if self.file_type == "application/pdf":
            self.print_btn = QPushButton("打印")
            self.print_btn.clicked.connect(self._print_file)
            toolbar_layout.addWidget(self.print_btn)

        toolbar_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        toolbar_layout.addWidget(close_btn)

        layout.addWidget(toolbar_frame)

        # 内容区域
        self.content_widget = QFrame()
        self.content_widget.setFrameStyle(QFrame.Shape.Box)
        self.content_widget.setStyleSheet("""
            QFrame {
                background: #1e1e2e;
                border: 1px solid #585b70;
                border-top: none;
            }
        """)

        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.progress_bar.setTextVisible(False)
        self.content_layout.addWidget(self.progress_bar)

        # 预览容器（后续由_load_file填充）
        self.preview_container = QFrame()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.addWidget(self.preview_container)

        layout.addWidget(self.content_widget)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                background: #313244;
                color: #a6adc8;
                padding: 4px 12px;
                font-size: 11px;
                border: 1px solid #45475a;
                border-top: none;
            }
        """)
        layout.addWidget(self.status_label)

    def _get_file_size(self) -> str:
        """获取文件大小"""
        try:
            size = os.path.getsize(self.file_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            elif size < 1024 * 1024 * 1024:
                return f"{size / (1024 * 1024):.1f} MB"
            else:
                return f"{size / (1024 * 1024 * 1024):.1f} GB"
        except:
            return "未知大小"

    def _load_file(self):
        """根据文件类型加载预览"""
        # 根据文件类别选择预览方式
        if self.file_category == "image":
            self._preview_image()
        elif self.file_type == "application/pdf":
            self._preview_pdf()
        elif self.file_category == "text":
            self._preview_text()
        else:
            self._preview_generic()

    def _preview_image(self):
        """预览图片文件"""
        try:
            # 加载图片
            image = QImage(self.file_path)
            if image.isNull():
                raise ValueError("无法加载图片")

            # 缩放以适合窗口
            max_width = self.width() - 100
            max_height = self.height() - 200

            if image.width() > max_width or image.height() > max_height:
                image = image.scaled(
                    max_width,
                    max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            pixmap = QPixmap.fromImage(image)

            # 创建图片标签
            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self.preview_layout.addWidget(image_label)

            self.status_label.setText(f"图片: {image.width()}×{image.height()}像素")

        except Exception as e:
            self._show_error(f"无法预览图片: {str(e)}")

        finally:
            self.progress_bar.hide()

    def _preview_pdf(self):
        """预览PDF文件"""
        try:
            # 使用Qt的WebEngine来预览PDF
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            from PyQt6.QtCore import QUrl

            # 将PDF文件转换为file:// URL
            pdf_url = QUrl.fromLocalFile(self.file_path)

            web_view = QWebEngineView()
            web_view.load(pdf_url)
            web_view.setZoomFactor(1.2)

            self.preview_layout.addWidget(web_view)
            self.status_label.setText("PDF预览 - 使用浏览器引擎")

        except ImportError:
            # 如果没有WebEngine，显示警告信息
            warning_label = QLabel("⚠️ PDF预览需要PyQt6-WebEngine模块")
            warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warning_label.setStyleSheet(
                "font-size: 14px; color: #f38ba8; padding: 20px;"
            )
            self.preview_layout.addWidget(warning_label)

            # 显示替代信息
            info_label = QLabel(
                "要预览PDF文件，请安装PyQt6-WebEngine模块：\n"
                "pip install PyQt6-WebEngine"
            )
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setStyleSheet("color: #a6adc8; padding: 10px;")
            self.preview_layout.addWidget(info_label)

            self.status_label.setText("PDF预览不可用")

        finally:
            self.progress_bar.hide()

    def _preview_text(self):
        """预览文本文件"""
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            text_edit = QTextEdit()
            text_edit.setPlainText(content)
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Monospace", 10))
            text_edit.setStyleSheet("""
                QTextEdit {
                    background: #11111b;
                    color: #cdd6f4;
                    border: 1px solid #585b70;
                    border-radius: 4px;
                }
            """)

            self.preview_layout.addWidget(text_edit)

            # 统计信息
            lines = content.count("\n") + 1
            chars = len(content)
            self.status_label.setText(f"文本文件: {lines}行, {chars}字符, UTF-8编码")

        except Exception as e:
            self._show_error(f"无法读取文本文件: {str(e)}")

        finally:
            self.progress_bar.hide()

    def _preview_generic(self):
        """通用文件预览"""
        info_label = QLabel(
            f"📄 文件类型: {self.file_type}\n\n"
            f"此文件类型无法直接预览。\n"
            f"您可以选择:\n"
            f"• 点击「打开」使用系统默认程序打开\n"
            f"• 点击「另存为」保存到其他位置\n"
        )
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #cdd6f4;
                line-height: 1.5;
                padding: 40px;
            }
        """)
        info_label.setWordWrap(True)

        self.preview_layout.addWidget(info_label)

        # 显示十六进制预览（仅用于小文件）
        try:
            if os.path.getsize(self.file_path) < 1024 * 1024:  # 小于1MB的文件
                hex_text = self._get_hex_preview()
                if hex_text:
                    hex_label = QLabel()
                    hex_label.setTextFormat(Qt.TextFormat.PlainText)
                    hex_label.setFont(QFont("Monospace", 9))
                    hex_label.setText(hex_text)
                    hex_label.setStyleSheet("color: #585b70;")

                    hex_scroll = QScrollArea()
                    hex_scroll.setWidget(hex_label)
                    hex_scroll.setMaximumHeight(200)
                    hex_scroll.setWidgetResizable(True)

                    self.preview_layout.addWidget(hex_scroll)
        except:
            pass

        self.progress_bar.hide()
        self.status_label.setText(f"通用文件类型: {self.file_type}")

    def _get_hex_preview(self) -> str:
        """获取十六进制预览"""
        try:
            with open(self.file_path, "rb") as f:
                data = f.read(512)  # 只读取前512字节

            if not data:
                return ""

            # 生成十六进制显示
            hex_lines = []
            for i in range(0, len(data), 16):
                chunk = data[i : i + 16]

                # 十六进制部分
                hex_part = " ".join(f"{b:02x}" for b in chunk)
                hex_part = hex_part.ljust(47)  # 对齐

                # ASCII部分
                ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

                hex_lines.append(f"{i:08x}: {hex_part}  |{ascii_part}|")

            return "\n".join(hex_lines)
        except:
            return ""

    def _show_error(self, message: str):
        """显示错误信息"""
        error_label = QLabel(f"❌ {message}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("font-size: 14px; color: #f38ba8; padding: 30px;")
        self.preview_layout.addWidget(error_label)

    def _open_file(self):
        """用系统默认程序打开文件"""
        try:
            import subprocess
            import sys

            if sys.platform == "win32":
                os.startfile(self.file_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", self.file_path])
            else:
                subprocess.call(["xdg-open", self.file_path])

            self.status_label.setText("文件已发送到系统默认程序")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开文件: {str(e)}")

    def _save_as(self):
        """另存为文件"""
        from PyQt6.QtWidgets import QFileDialog

        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("另存为")
        file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        file_dialog.selectFile(self.file_name)

        if file_dialog.exec():
            save_path = file_dialog.selectedFiles()[0]
            try:
                import shutil

                shutil.copy2(self.file_path, save_path)
                QMessageBox.information(self, "成功", f"文件已保存到:\n{save_path}")
                self.status_label.setText(f"文件已保存")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法保存文件: {str(e)}")

    def _print_file(self):
        """打印文件"""
        if self.file_type != "application/pdf":
            return

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            print_dialog = QPrintDialog(printer, self)

            if print_dialog.exec() == QPrintDialog.DialogCode.Accepted:
                # 这里可以添加PDF打印逻辑
                self.status_label.setText("打印任务已发送")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打印失败: {str(e)}")
