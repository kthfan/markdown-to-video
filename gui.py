#!/usr/bin/env python3
"""
Markdown to Video Generator - GUI
繁體中文圖形介面
Supports both pyttsx3 and edge-tts
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import os
import sys
import pyttsx3
import asyncio
from generate_video import (
    generate_video_from_markdown, 
    get_available_voices_pyttsx3,
    get_available_voices_edge_tts,
    EDGE_TTS_AVAILABLE
)
import subprocess
import tempfile
import time

# Try to import edge-tts for voice testing
try:
    import edge_tts
    EDGE_TTS_FOR_TEST = True
except ImportError:
    EDGE_TTS_FOR_TEST = False


class MarkdownVideoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown 轉影片工具")
        self.root.geometry("950x850")
        
        # Variables
        self.markdown_content = tk.StringVar()
        self.output_file = tk.StringVar(value="output.mp4")
        self.media_dir = tk.StringVar()
        self.media_duration = tk.DoubleVar(value=8.0)
        self.max_chars = tk.IntVar(value=80)
        self.resolution = tk.StringVar(value="720x480")
        self.voice_index = tk.IntVar(value=0)
        self.speech_rate = tk.IntVar(value=150)
        self.tts_engine = tk.StringVar(value="pyttsx3")
        
        # Voice data
        self.pyttsx3_voices = []
        self.edge_tts_voices = []
        self.current_voices = []
        
        # Load available voices
        self.load_voices()
        
        # Create UI
        self.create_widgets()
        
    def load_voices(self):
        """Load available voices for both engines"""
        # Load pyttsx3 voices
        self.pyttsx3_voices = get_available_voices_pyttsx3()
        
        # Load edge-tts voices
        if EDGE_TTS_AVAILABLE:
            try:
                self.edge_tts_voices = get_available_voices_edge_tts()
            except Exception as e:
                print(f"Failed to load edge-tts voices: {e}")
                self.edge_tts_voices = []
        
        # Set current voices based on default engine
        self.update_voice_list()
        
    def update_voice_list(self):
        """Update current voice list based on selected engine"""
        engine = self.tts_engine.get()
        
        if engine == "edge-tts":
            self.current_voices = self.edge_tts_voices
        else:
            self.current_voices = self.pyttsx3_voices
        
    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="📹 Markdown 轉影片生成器", 
                                font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Tab 1: Basic Settings
        basic_frame = ttk.Frame(notebook, padding="10")
        notebook.add(basic_frame, text="基本設定")
        self.create_basic_tab(basic_frame)
        
        # Tab 2: Advanced Settings
        advanced_frame = ttk.Frame(notebook, padding="10")
        notebook.add(advanced_frame, text="進階設定")
        self.create_advanced_tab(advanced_frame)
        
        # Log output
        log_frame = ttk.LabelFrame(main_frame, text="輸出日誌", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, width=80, font=("Consolas", 10))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        self.generate_btn = ttk.Button(button_frame, text="🎬 開始生成影片", 
                                       command=self.start_generation)
        self.generate_btn.grid(row=0, column=0, padx=5)
        
        self.cancel_btn = ttk.Button(button_frame, text="❌ 取消", 
                                     command=self.cancel_generation, state=tk.DISABLED)
        self.cancel_btn.grid(row=0, column=1, padx=5)
        
        clear_btn = ttk.Button(button_frame, text="🗑️ 清除日誌", 
                              command=self.clear_log)
        clear_btn.grid(row=0, column=2, padx=5)
        
    def create_basic_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        
        row = 0
        
        # Markdown input section
        md_label = ttk.Label(parent, text="Markdown 內容:", font=('Arial', 10, 'bold'))
        md_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        row += 1
        
        # Markdown text area
        self.markdown_text = scrolledtext.ScrolledText(parent, height=12, width=70)
        self.markdown_text.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        row += 1
        
        # File upload buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        upload_btn = ttk.Button(btn_frame, text="📁 載入 Markdown 檔案", 
                               command=self.load_markdown_file)
        upload_btn.grid(row=0, column=0, padx=(0, 5))
        
        clear_md_btn = ttk.Button(btn_frame, text="🗑️ 清除內容", 
                                 command=self.clear_markdown)
        clear_md_btn.grid(row=0, column=1)
        row += 1
        
        # Separator
        ttk.Separator(parent, orient='horizontal').grid(row=row, column=0, columnspan=2, 
                                                        sticky=(tk.W, tk.E), pady=15)
        row += 1
        
        # Media directory
        ttk.Label(parent, text="媒體目錄 (圖片/影片):").grid(row=row, column=0, sticky=tk.W, pady=5)
        media_frame = ttk.Frame(parent)
        media_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        media_frame.columnconfigure(0, weight=1)
        
        media_entry = ttk.Entry(media_frame, textvariable=self.media_dir)
        media_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        media_btn = ttk.Button(media_frame, text="瀏覽...", command=self.browse_media_dir)
        media_btn.grid(row=0, column=1)
        row += 1
        
        # Output file
        ttk.Label(parent, text="輸出檔案:").grid(row=row, column=0, sticky=tk.W, pady=5)
        output_frame = ttk.Frame(parent)
        output_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        output_frame.columnconfigure(0, weight=1)
        
        output_entry = ttk.Entry(output_frame, textvariable=self.output_file)
        output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        output_btn = ttk.Button(output_frame, text="瀏覽...", command=self.browse_output_file)
        output_btn.grid(row=0, column=1)
        row += 1
        
        # TTS Engine selection
        ttk.Label(parent, text="TTS 引擎:").grid(row=row, column=0, sticky=tk.W, pady=5)
        
        engine_frame = ttk.Frame(parent)
        engine_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        
        engines = ["pyttsx3 (離線)"]
        if EDGE_TTS_AVAILABLE:
            engines.append("edge-tts (線上，高品質)")
        
        self.engine_combo = ttk.Combobox(engine_frame, values=engines, state='readonly', width=30)
        self.engine_combo.grid(row=0, column=0, sticky=tk.W)
        self.engine_combo.current(0)
        self.engine_combo.bind('<<ComboboxSelected>>', self.on_engine_changed)
        row += 1
        
        # Voice selection
        ttk.Label(parent, text="語音選擇:").grid(row=row, column=0, sticky=tk.W, pady=5)
        
        voice_frame = ttk.Frame(parent)
        voice_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        voice_frame.columnconfigure(0, weight=1)
        
        self.voice_combo = ttk.Combobox(voice_frame, state='readonly')
        self.voice_combo.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        test_voice_btn = ttk.Button(voice_frame, text="🔊 測試", command=self.test_voice)
        test_voice_btn.grid(row=0, column=1, padx=(0, 5))
        
        refresh_voice_btn = ttk.Button(voice_frame, text="🔄", command=self.refresh_voices, width=3)
        refresh_voice_btn.grid(row=0, column=2)
        
        # Populate voice combo
        self.populate_voice_combo()
        row += 1
        
    def create_advanced_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        
        row = 0
        
        # Resolution
        ttk.Label(parent, text="影片解析度:").grid(row=row, column=0, sticky=tk.W, pady=5)
        resolution_values = ["720x480 (SD)", "1920x1080 (Full HD)", "1280x720 (HD)", "3840x2160 (4K)"]
        resolution_combo = ttk.Combobox(parent, textvariable=self.resolution, 
                                       values=resolution_values, width=30)
        resolution_combo.grid(row=row, column=1, sticky=tk.W, pady=5)
        row += 1
        
        # Media duration
        ttk.Label(parent, text="每個媒體顯示時長 (秒):").grid(row=row, column=0, sticky=tk.W, pady=5)
        duration_frame = ttk.Frame(parent)
        duration_frame.grid(row=row, column=1, sticky=tk.W, pady=5)
        
        duration_spinbox = ttk.Spinbox(duration_frame, from_=1, to=60, 
                                       textvariable=self.media_duration, width=10)
        duration_spinbox.grid(row=0, column=0)
        ttk.Label(duration_frame, text="秒").grid(row=0, column=1, padx=(5, 0))
        row += 1
        
        # Max chars per subtitle
        ttk.Label(parent, text="每個字幕最大字元數:").grid(row=row, column=0, sticky=tk.W, pady=5)
        chars_frame = ttk.Frame(parent)
        chars_frame.grid(row=row, column=1, sticky=tk.W, pady=5)
        
        chars_spinbox = ttk.Spinbox(chars_frame, from_=20, to=200, 
                                    textvariable=self.max_chars, width=10)
        chars_spinbox.grid(row=0, column=0)
        ttk.Label(chars_frame, text="字元").grid(row=0, column=1, padx=(5, 0))
        row += 1
        
        # Speech rate
        ttk.Label(parent, text="語音速度:").grid(row=row, column=0, sticky=tk.W, pady=5)
        rate_frame = ttk.Frame(parent)
        rate_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        rate_frame.columnconfigure(0, weight=1)
        
        self.rate_scale = ttk.Scale(rate_frame, from_=50, to=300, 
                              variable=self.speech_rate, orient=tk.HORIZONTAL)
        self.rate_scale.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.rate_label = ttk.Label(rate_frame, text="150")
        self.rate_label.grid(row=0, column=1)
        
        def update_rate_label(val):
            rate = int(float(val))
            engine = self.tts_engine.get()
            if engine == "edge-tts":
                # Show as percentage for edge-tts
                rate_percent = int((rate - 150) / 150 * 100)
                self.rate_label.config(text=f"{rate_percent:+d}%")
            else:
                self.rate_label.config(text=f"{rate}")
        
        self.rate_scale.config(command=update_rate_label)
        row += 1
        
        # Info
        info_text = """
ℹ️ 提示:
• TTS 引擎:
  - pyttsx3: 離線，免費，但語音品質較低
  - edge-tts: 線上，免費，使用微軟神經語音，品質高
• 支援的圖片格式: PNG, JPG, JPEG, BMP, GIF, WEBP
• 支援的影片格式: MP4, AVI, MOV, MKV, FLV, WMV
• 語音速度: 50 (很慢) ~ 300 (很快)
• 字幕會自動與語音同步
• edge-tts 推薦中文語音:
  - zh-CN-XiaoxiaoNeural (女聲)
  - zh-CN-YunxiNeural (男聲)
        """
        info_label = ttk.Label(parent, text=info_text, justify=tk.LEFT, 
                              foreground='gray', font=('Arial', 9))
        info_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=20)
        
    def on_engine_changed(self, event=None):
        """Handle TTS engine change"""
        selected = self.engine_combo.get()
        if "edge-tts" in selected:
            self.tts_engine.set("edge-tts")
        else:
            self.tts_engine.set("pyttsx3")
        
        self.update_voice_list()
        self.populate_voice_combo()
        
        # Update rate label format
        rate = self.speech_rate.get()
        if self.tts_engine.get() == "edge-tts":
            rate_percent = int((rate - 150) / 150 * 100)
            self.rate_label.config(text=f"{rate_percent:+d}%")
        else:
            self.rate_label.config(text=f"{rate}")
    
    def populate_voice_combo(self):
        """Populate voice combobox based on current engine"""
        engine = self.tts_engine.get()
        
        if engine == "edge-tts":
            if self.edge_tts_voices:
                # Group by language and show popular Chinese voices first
                popular_chinese = [
                    "zh-CN-XiaoxiaoNeural",
                    "zh-CN-YunxiNeural", 
                    "zh-CN-YunyangNeural",
                    "zh-CN-XiaoyiNeural",
                    "zh-TW-HsiaoChenNeural",
                    "zh-TW-YunJheNeural",
                ]
                
                voice_names = []
                
                # Add popular voices first
                for short_name in popular_chinese:
                    for v in self.edge_tts_voices:
                        if v["ShortName"] == short_name:
                            gender = v.get("Gender", "Unknown")
                            voice_names.append(f"⭐ {short_name} ({gender})")
                            break
                
                # Add separator
                if voice_names:
                    voice_names.append("─" * 40)
                
                # Add all voices grouped by locale
                current_locale = None
                for v in self.edge_tts_voices:
                    locale = v["Locale"]
                    short_name = v["ShortName"]
                    
                    # Skip if already in popular list
                    if short_name in popular_chinese:
                        continue
                    
                    # Add locale header
                    if locale != current_locale:
                        if current_locale is not None:
                            voice_names.append("─" * 40)
                        current_locale = locale
                    
                    gender = v.get("Gender", "Unknown")
                    voice_names.append(f"{short_name} ({gender})")
                
                self.voice_combo['values'] = voice_names
                if voice_names:
                    self.voice_combo.current(0)
            else:
                self.voice_combo['values'] = ["zh-CN-XiaoxiaoNeural (預設)"]
                self.voice_combo.current(0)
        else:  # pyttsx3
            if self.pyttsx3_voices:
                voice_names = [f"{i}: {v.name}" for i, v in enumerate(self.pyttsx3_voices)]
                self.voice_combo['values'] = voice_names
                if voice_names:
                    self.voice_combo.current(0)
            else:
                self.voice_combo['values'] = ["預設語音"]
                self.voice_combo.current(0)
    
    def refresh_voices(self):
        """Reload voice list"""
        self.log("🔄 重新載入語音列表...")
        self.load_voices()
        self.populate_voice_combo()
        self.log("✓ 語音列表已更新")
        
    def get_selected_voice_id(self):
        """Get the ID of currently selected voice"""
        engine = self.tts_engine.get()
        selected_text = self.voice_combo.get()
        
        if not selected_text or "─" in selected_text:
            return None
        
        if engine == "edge-tts":
            # Extract voice name from combo text
            # Format: "⭐ zh-CN-XiaoxiaoNeural (Female)" or "zh-CN-YunxiNeural (Male)"
            parts = selected_text.split("(")
            if parts:
                voice_name = parts[0].strip()
                # Remove star emoji if present
                voice_name = voice_name.replace("⭐", "").strip()
                return voice_name
            return None
        else:  # pyttsx3
            selected_idx = self.voice_combo.current()
            if selected_idx >= 0 and selected_idx < len(self.pyttsx3_voices):
                return self.pyttsx3_voices[selected_idx].id
            return None
    
    def test_voice(self):
        """Test the selected voice"""
        engine = self.tts_engine.get()
        voice_id = self.get_selected_voice_id()
        
        if not voice_id:
            messagebox.showwarning("警告", "請選擇一個語音")
            return
        
        test_text = "您好，這是語音測試。Hello, this is a voice test."
        
        try:
            if engine == "edge-tts":
                if not EDGE_TTS_FOR_TEST:
                    messagebox.showerror("錯誤", "edge-tts 未安裝")
                    return
                
                # Test edge-tts voice
                self.log(f"🔊 測試 edge-tts 語音: {voice_id}")
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                    audio_path = temp_audio.name
                
                # Generate speech asynchronously
                async def generate_test_audio():
                    rate_percent = int((self.speech_rate.get() - 150) / 150 * 100)
                    rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
                    
                    communicate = edge_tts.Communicate(test_text, voice_id, rate=rate_str)
                    await communicate.save(audio_path)
                
                asyncio.run(generate_test_audio())
                
                # Play audio file
                if sys.platform == "win32":
                    os.startfile(audio_path)
                elif sys.platform == "darwin":
                    os.system(f"afplay {audio_path}")
                else:
                    os.system(f"mpg123 {audio_path}")
                
                # Schedule cleanup
                def cleanup():
                    try:
                        time.sleep(5)
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                    except:
                        pass
                
                threading.Thread(target=cleanup, daemon=True).start()
                
            else:  # pyttsx3
                self.log(f"🔊 測試 pyttsx3 語音")
                engine_obj = pyttsx3.init()
                engine_obj.setProperty('voice', voice_id)
                engine_obj.setProperty('rate', self.speech_rate.get())
                engine_obj.say(test_text)
                engine_obj.runAndWait()
                
        except Exception as e:
            messagebox.showerror("錯誤", f"無法測試語音: {e}")
            import traceback
            traceback.print_exc()
            
    def load_markdown_file(self):
        filename = filedialog.askopenfilename(
            title="選擇 Markdown 檔案",
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.markdown_text.delete(1.0, tk.END)
                self.markdown_text.insert(1.0, content)
                self.log(f"✓ 已載入檔案: {filename}")
            except Exception as e:
                messagebox.showerror("錯誤", f"無法載入檔案: {e}")
                
    def clear_markdown(self):
        self.markdown_text.delete(1.0, tk.END)
        
    def browse_media_dir(self):
        directory = filedialog.askdirectory(title="選擇媒體目錄")
        if directory:
            self.media_dir.set(directory)
            
    def browse_output_file(self):
        filename = filedialog.asksaveasfilename(
            title="選擇輸出檔案",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if filename:
            self.output_file.set(filename)
            
    def log(self, message):
        """Add message to log"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
        
    def clear_log(self):
        """Clear log"""
        self.log_text.delete(1.0, tk.END)
        
    def start_generation(self):
        """Start video generation in a separate thread"""
        # Get markdown content
        markdown_content = self.markdown_text.get(1.0, tk.END).strip()
        if not markdown_content:
            messagebox.showwarning("警告", "請輸入 Markdown 內容")
            return
            
        # Get output file
        output = self.output_file.get()
        if not output:
            messagebox.showwarning("警告", "請指定輸出檔案")
            return
            
        # Disable generate button
        self.generate_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        # Clear log
        self.clear_log()
        self.log("=" * 60)
        self.log("開始生成影片...")
        self.log("=" * 60)
        
        # Start generation thread
        self.generate_video_from_cmd(markdown_content)
    
    def generate_video_from_cmd(self, markdown_content):
        """Generate video using command line (runs in separate thread)"""
        
        def run_generation():
            try:
                # Parse resolution
                resolution_str = self.resolution.get().split()[0]  # Get "1920x1080" part
                
                # Get voice ID
                voice_id = self.get_selected_voice_id()
                
                # Get media directory
                media_dir = self.media_dir.get() if self.media_dir.get() else None
                
                # Create temporary markdown file
                tmp_path = None
                with tempfile.NamedTemporaryFile(mode='w+t', delete=False, suffix='.md', encoding='utf-8') as temp:
                    temp.write(markdown_content)
                    temp.flush()
                    tmp_path = temp.name
                
                # Get engine
                engine = self.tts_engine.get()
                
                # Build command
                cmds = [
                    sys.executable, "generate_video.py", 
                    tmp_path,
                    "-o", self.output_file.get(),
                    "-d", str(self.media_duration.get()),
                    "-r", resolution_str,
                    "-m", str(self.max_chars.get()),
                    "--engine", engine,
                ]
                
                # Add media directory if specified
                if media_dir:
                    cmds += ["-i", media_dir]
                
                # Add voice if specified
                if voice_id:
                    cmds += ["--voice", voice_id]
                
                # Add rate
                rate = self.speech_rate.get()
                if engine == "edge-tts":
                    # Convert to percentage
                    rate_percent = int((rate - 150) / 150 * 100)
                    rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"
                    cmds += ["--rate", rate_str]
                else:
                    cmds += ["--rate", str(rate)]
                
                self.log(f"\n執行命令: {' '.join(cmds)}\n")
                
                # Run command
                if sys.platform == "win32":
                    # On Windows, use subprocess to capture output
                    process = subprocess.Popen(
                        cmds,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        shell=True, creationflags=0x00000008, close_fds=True
                    )
                    
                    # Read output in real-time
                    for line in process.stdout:
                        self.log(line.rstrip())
                    
                    process.wait()
                    
                    if process.returncode == 0:
                        self.log("\n" + "=" * 60)
                        self.log("✅ 影片生成成功！")
                        self.log("=" * 60)
                        self.root.after(0, lambda: messagebox.showinfo("成功", 
                            f"影片已成功生成！\n\n輸出: {self.output_file.get()}"))
                    else:
                        self.log("\n" + "=" * 60)
                        self.log("❌ 影片生成失敗")
                        self.log("=" * 60)
                        self.root.after(0, lambda: messagebox.showerror("錯誤", "影片生成失敗，請查看日誌"))
                else:
                    # On Unix-like systems
                    os.system(" ".join(cmds))
                    self.log("\n" + "=" * 60)
                    self.log("✅ 影片生成完成！")
                    self.log("=" * 60)
                    self.root.after(0, lambda: messagebox.showinfo("完成", 
                        f"影片生成完成！\n\n輸出: {self.output_file.get()}"))
                
                # Cleanup temp file
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except:
                    pass
                    
            except Exception as e:
                import traceback
                error_msg = traceback.format_exc()
                self.log(f"\n❌ 錯誤: {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("錯誤", f"發生錯誤:\n{str(e)}"))
            finally:
                # Re-enable button
                self.root.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.cancel_btn.config(state=tk.DISABLED))
        
        # Run in thread
        thread = threading.Thread(target=run_generation, daemon=True)
        thread.start()
            
    def cancel_generation(self):
        """Cancel video generation (currently just a placeholder)"""
        messagebox.showinfo("資訊", "取消功能尚未完全實作")
        

def main():
    root = tk.Tk()
    app = MarkdownVideoGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()