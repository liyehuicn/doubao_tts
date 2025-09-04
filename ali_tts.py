import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer
import json
import threading
import tempfile
import platform
import subprocess
from datetime import datetime
import re

class VoiceSynthesisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("阿里云CosyVoice语音合成应用")
        self.root.geometry("900x650")
        self.root.minsize(700, 600)
        
        # 配置中文字体
        self.font_config()
        
        # 应用状态变量
        self.api_key = ""
        self.voice_id = ""  # 保留内部使用，不显示在界面
        self.voice_ids = {}
        self.config_file = "config.json"
        self.temp_audio_file = None
        self.audio_data = None
        self.volume = 5.0  # 保留配置
        self.speech_rate = 1.0  # 保留配置
        self.synthesis_mode = tk.StringVar(value="text")
        
        # Voice ID相关变量（仅内部使用）
        self.voice_id_var = tk.StringVar()
        
        # 延迟初始化对话框
        self.api_dialog = None
        self.voice_dialog = None
        self.log_text = None
        
        # 加载配置
        self.load_config()
        
        # 创建UI
        self.create_widgets()
        
        # 绑定窗口大小变化事件
        self.root.bind("<Configure>", self.on_resize)
    
    def font_config(self):
        """配置中文字体支持"""
        default_font = ('SimHei', 10)
        self.root.option_add("*Font", default_font)
    
    def load_config(self):
        """从配置文件加载"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.api_key = config.get('api_key', '')
                    self.voice_id = config.get('voice_id', '')
                    self.voice_ids = config.get('voice_ids', {})
                    self.volume = max(0.1, min(10.0, config.get('volume', 5.0)))
                    self.speech_rate = max(0.5, min(2.0, config.get('speech_rate', 1.0)))
                    self.voice_id_var.set(self.voice_id)
            except Exception as e:
                messagebox.showerror("配置加载错误", f"加载配置文件失败: {str(e)}")
    
    def save_config(self):
        """保存配置（内部自动调用，不通过界面按钮）"""
        try:
            self.voice_id = self.voice_id_var.get().strip()
            config = {
                'api_key': self.api_key,
                'voice_id': self.voice_id,
                'voice_ids': self.voice_ids,
                'volume': self.volume,
                'speech_rate': self.speech_rate
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.log_message("配置已自动保存")
        except Exception as e:
            messagebox.showerror("配置保存错误", f"保存配置文件失败: {str(e)}")
    
    def create_widgets(self):
        """创建界面组件"""
        # 主容器使用grid布局
        self.main_frame = tk.Frame(self.root, padx=10, pady=10)
        self.main_frame.grid(sticky=tk.NSEW)
        
        # 配置主网格权重
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(4, weight=3)  # 文本输入区域
        self.main_frame.grid_rowconfigure(6, weight=1)  # 日志区域
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # 顶部框架（标题+设置按钮）
        self.top_frame = tk.Frame(self.main_frame)
        self.top_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))
        self.top_frame.grid_columnconfigure(0, weight=1)
        
        tk.Label(self.top_frame, text="阿里云CosyVoice语音合成应用", font=('SimHei', 14, 'bold')).grid(
            row=0, column=0, sticky=tk.W)
        
        self.settings_btn = tk.Menubutton(self.top_frame, text="设置", relief=tk.RAISED)
        self.settings_btn.grid(row=0, column=1, sticky=tk.E)
        
        self.settings_menu = tk.Menu(self.settings_btn, tearoff=0)
        self.settings_btn.config(menu=self.settings_menu)
        self.settings_menu.add_command(label="API 密钥设置", command=self.show_api_settings)
        self.settings_menu.add_command(label="语音复刻设置", command=self.show_voice_settings)
        
        # 1. 语音控制区域
        self.control_frame = tk.LabelFrame(self.main_frame, text="语音参数控制", padx=5, pady=5)
        self.control_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        self.control_frame.grid_columnconfigure(1, weight=1)
        self.control_frame.grid_columnconfigure(3, weight=1)
        
        # 音量控制
        tk.Label(self.control_frame, text="音量:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.volume_slider = ttk.Scale(
            self.control_frame, 
            from_=1,    
            to=100,     
            orient=tk.HORIZONTAL,
            command=self.update_volume
        )
        self.volume_slider.set(self.volume * 10)
        self.volume_slider.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        
        self.volume_label = tk.Label(self.control_frame, text=f"{int(self.volume*10)}% (暂不生效)")
        self.volume_label.grid(row=0, column=2, padx=5)
        
        # 语速控制
        tk.Label(self.control_frame, text="语速:").grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        self.rate_slider = ttk.Scale(
            self.control_frame, 
            from_=5,    
            to=20,      
            orient=tk.HORIZONTAL,
            command=self.update_rate,
            length=200
        )
        self.rate_slider.set(self.speech_rate * 10)
        self.rate_slider.grid(row=0, column=4, sticky=tk.EW, pady=5, padx=5)
        
        self.rate_label = tk.Label(self.control_frame, text=f"{self.speech_rate:.1f}x (暂不生效)")
        self.rate_label.grid(row=0, column=5, padx=5)
        
        # SDK参数提示
        tip_label = tk.Label(
            self.control_frame, 
            text="提示：当前SDK版本暂不支持音量/语速参数传递", 
            fg="red",
            font=('SimHei', 9)
        )
        tip_label.grid(row=1, column=0, columnspan=6, pady=5, padx=5, sticky=tk.W)
        
        # 2. 合成模式选择
        self.mode_frame = tk.LabelFrame(self.main_frame, text="合成模式选择", padx=5, pady=5)
        self.mode_frame.grid(row=2, column=0, sticky=tk.EW, pady=(0, 10))
        
        self.text_mode_radio = tk.Radiobutton(
            self.mode_frame, 
            text="文本合成", 
            variable=self.synthesis_mode, 
            value="text",
            command=self.update_mode_ui
        )
        self.text_mode_radio.grid(row=0, column=0, padx=20, pady=5, sticky=tk.W)
        
        self.subtitle_mode_radio = tk.Radiobutton(
            self.mode_frame, 
            text="字幕合成", 
            variable=self.synthesis_mode, 
            value="subtitle",
            command=self.update_mode_ui
        )
        self.subtitle_mode_radio.grid(row=0, column=1, padx=20, pady=5, sticky=tk.W)
        
        # 3. 字幕文件处理
        self.subtitle_frame = tk.LabelFrame(self.main_frame, text="字幕文件处理", padx=5, pady=5)
        self.subtitle_frame.grid_columnconfigure(1, weight=1)
        
        tk.Label(self.subtitle_frame, text="字幕文件:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.subtitle_path_entry = tk.Entry(self.subtitle_frame)
        self.subtitle_path_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        
        self.browse_subtitle_btn = tk.Button(
            self.subtitle_frame, 
            text="浏览字幕文件...", 
            command=self.browse_subtitle_file
        )
        self.browse_subtitle_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # 添加"加载字幕到文本框"按钮
        self.load_subtitle_btn = tk.Button(
            self.subtitle_frame, 
            text="加载字幕到文本框", 
            command=self.load_subtitle_to_textbox
        )
        self.load_subtitle_btn.grid(row=1, column=0, padx=5, pady=5)
        
        # 字幕处理状态提示
        self.subtitle_status = tk.Label(self.subtitle_frame, text="", fg="blue", font=('SimHei', 9))
        self.subtitle_status.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        
        # 4. 文本输入区域
        self.text_frame = tk.LabelFrame(self.main_frame, text="合成文本", padx=5, pady=5)
        self.text_frame.grid(row=4, column=0, sticky=tk.NSEW, pady=(0, 10))
        self.text_frame.grid_rowconfigure(0, weight=1)
        self.text_frame.grid_columnconfigure(0, weight=1)
        
        self.text_input = scrolledtext.ScrolledText(self.text_frame, wrap=tk.WORD)
        self.text_input.grid(row=0, column=0, sticky=tk.NSEW, pady=5, padx=5)
        self.text_input.insert(tk.END, "今天天气怎么样？")
        
        # 5. 输出设置与操作区域
        self.output_frame = tk.LabelFrame(self.main_frame, text="输出设置与操作", padx=10, pady=10)
        self.output_frame.grid(row=5, column=0, sticky=tk.EW, pady=(0, 10), ipady=5)
        self.output_frame.grid_columnconfigure(1, weight=1)
        self.output_frame.grid_columnconfigure(0, weight=0)
        self.output_frame.grid_columnconfigure(2, weight=0)
        self.output_frame.grid_columnconfigure(3, weight=0)
        
        # 保存文件夹设置
        tk.Label(self.output_frame, text="保存文件夹:", width=10).grid(
            row=0, column=0, sticky=tk.W, pady=5, padx=(5, 10))
        
        self.output_dir_entry = tk.Entry(self.output_frame)
        self.output_dir_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        self.output_dir_entry.insert(0, os.getcwd())
        
        self.browse_btn = tk.Button(self.output_frame, text="浏览...", width=8, command=self.browse_output_dir)
        self.browse_btn.grid(row=0, column=2, sticky=tk.W, pady=5, padx=(10, 5))
        
        # 操作按钮框架（合成、试听、保存）
        self.btn_frame = tk.Frame(self.output_frame)
        self.btn_frame.grid(row=0, column=3, sticky=tk.E, padx=5, pady=5)
        
        self.synthesize_btn = tk.Button(
            self.btn_frame, 
            text="合成语音", 
            command=self.start_synthesize_based_on_mode,
            width=10,
            bg="#4CAF50",
            fg="white"
        )
        self.synthesize_btn.pack(side=tk.LEFT, padx=3)
        
        self.play_btn = tk.Button(
            self.btn_frame, 
            text="试听语音", 
            command=self.play_audio,
            width=10,
            state=tk.DISABLED
        )
        self.play_btn.pack(side=tk.LEFT, padx=3)
        
        self.save_btn = tk.Button(
            self.btn_frame, 
            text="保存语音", 
            command=self.save_audio,
            width=10,
            state=tk.DISABLED
        )
        self.save_btn.pack(side=tk.LEFT, padx=3)
        
        # 6. 日志区域
        self.log_frame = tk.LabelFrame(self.main_frame, text="操作日志", padx=5, pady=5)
        self.log_frame.grid(row=6, column=0, sticky=tk.NSEW, pady=(0, 10))
        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, 
            wrap=tk.WORD, 
            state=tk.DISABLED,
            height=5
        )
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW, pady=5, padx=5)
        
        log_ctrl_frame = tk.Frame(self.log_frame)
        log_ctrl_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 5))
        log_ctrl_frame.grid_columnconfigure(0, weight=1)
        
        self.auto_scroll_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            log_ctrl_frame, 
            text="自动滚动到最新日志", 
            variable=self.auto_scroll_var
        ).grid(row=0, column=0, sticky=tk.W, padx=5)
        
        self.clear_log_btn = tk.Button(log_ctrl_frame, text="清空日志", command=self.clear_log)
        self.clear_log_btn.grid(row=0, column=1, sticky=tk.E, padx=5)
        
        # 初始化UI
        self.update_mode_ui()
        self.log_message("应用已启动")
        self.log_message("提示：当前SDK版本暂不支持音量/语速参数传递")
        if self.voice_id:
            self.log_message(f"已加载保存的Voice ID")
            self.log_message("提示：Voice ID通过'设置-语音复刻设置'管理")
    
    def update_mode_ui(self):
        """更新模式UI"""
        mode = self.synthesis_mode.get()
        
        try:
            self.subtitle_frame.grid_remove()
        except:
            pass
        
        if mode == "text":
            self.text_input.config(state=tk.NORMAL)
            self.subtitle_frame.grid_remove()
            self.log_message("切换到文本合成模式")
        else:
            self.text_input.config(state=tk.NORMAL)  # 允许在字幕模式下编辑文本
            self.subtitle_frame.grid(row=3, column=0, sticky=tk.EW, pady=(0, 10))
            self.log_message("切换到字幕合成模式")
    
    def update_volume(self, value):
        """更新音量配置"""
        try:
            slider_value = float(value)
            self.volume = round(slider_value / 10, 1)
            
            if hasattr(self, 'volume_label'):
                self.volume_label.config(
                    text=f"{int(slider_value)}% (暂不生效)"
                )
            self.save_config()  # 配置变更时自动保存
        except Exception as e:
            self.log_message(f"更新音量失败: {str(e)}")
    
    def update_rate(self, value):
        """更新语速配置"""
        try:
            slider_value = float(value)
            self.speech_rate = round(slider_value / 10, 1)
            
            if hasattr(self, 'rate_label'):
                self.rate_label.config(
                    text=f"{self.speech_rate:.1f}x (暂不生效)"
                )
            self.save_config()  # 配置变更时自动保存
        except Exception as e:
            self.log_message(f"更新语速失败: {str(e)}")
    
    def log_message(self, message):
        """日志显示"""
        if self.log_text is None:
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, full_message + "\n")
        
        # 限制日志行数
        line_count = int(self.log_text.index('end-1c').split('.')[0])
        if line_count > 50:
            self.log_text.delete(1.0, 2.0)
            
        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)
            
        self.log_text.config(state=tk.DISABLED)
    
    def create_api_settings_dialog(self):
        """创建API设置对话框"""
        self.api_dialog = tk.Toplevel(self.root)
        self.api_dialog.title("API 密钥设置")
        self.api_dialog.geometry("400x150")
        self.api_dialog.resizable(False, False)
        self.api_dialog.transient(self.root)
        self.api_dialog.protocol("WM_DELETE_WINDOW", self.api_dialog.withdraw)
        
        # 配置列权重，使输入框能够自适应宽度
        self.api_dialog.grid_columnconfigure(1, weight=1)
        
        tk.Label(self.api_dialog, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=15, padx=15)
        self.api_entry = tk.Entry(self.api_dialog, show="*", width=30)
        self.api_entry.grid(row=0, column=1, sticky=tk.EW, pady=15, padx=5)
        self.api_entry.insert(0, self.api_key)
        
        btn_frame = tk.Frame(self.api_dialog)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        self.save_api_btn = tk.Button(btn_frame, text="保存", command=self.save_api_key)
        self.save_api_btn.pack(side=tk.LEFT, padx=10)
        
        self.close_api_btn = tk.Button(btn_frame, text="关闭", command=self.api_dialog.withdraw)
        self.close_api_btn.pack(side=tk.LEFT, padx=10)
    
    def create_voice_settings_dialog(self):
        """创建语音复刻设置对话框（支持自适应宽度）"""
        self.voice_dialog = tk.Toplevel(self.root)
        self.voice_dialog.title("语音复刻设置")
        self.voice_dialog.geometry("600x500")  # 初始大小
        self.voice_dialog.minsize(550, 500)    # 最小尺寸限制
        self.voice_dialog.transient(self.root)
        self.voice_dialog.protocol("WM_DELETE_WINDOW", self.voice_dialog.withdraw)
        
        # 配置主框架权重，使内容能够自适应窗口大小
        main_frame = tk.Frame(self.voice_dialog, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(0, weight=1)  # 主框架自适应宽度
        
        # 创建Notebook选项卡
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 1. 创建语音选项卡（支持自适应宽度）
        create_frame = ttk.Frame(notebook, padding=10)
        notebook.add(create_frame, text="创建语音")
        
        # 配置创建语音选项卡的列权重
        create_frame.grid_columnconfigure(1, weight=1)  # 输入框列自适应宽度
        
        tk.Label(create_frame, text="音频文件URL或本地路径:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.audio_url_entry = tk.Entry(create_frame)
        self.audio_url_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        self.audio_url_entry.insert(0, "https://your-audio-file-url")
        
        # 添加浏览本地文件按钮
        browse_audio_btn = tk.Button(
            create_frame, 
            text="浏览本地文件", 
            command=self.browse_audio_file
        )
        browse_audio_btn.grid(row=0, column=3, padx=5, pady=5)
        
        tk.Label(create_frame, text="前缀:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.prefix_entry = tk.Entry(create_frame, width=20)
        self.prefix_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.prefix_entry.insert(0, "myvoice")
        
        tk.Label(create_frame, text="语音名称:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.voice_name_entry = tk.Entry(create_frame, width=20)
        self.voice_name_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.voice_name_entry.insert(0, "我的声音")
        
        self.reuse_voice_var = tk.BooleanVar(value=True if self.voice_id else False)
        self.reuse_checkbox = tk.Checkbutton(
            create_frame, 
            text="复用现有Voice ID（避免重复创建）", 
            variable=self.reuse_voice_var
        )
        self.reuse_checkbox.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        
        self.create_voice_btn = tk.Button(
            create_frame, 
            text="创建/更新语音", 
            command=self.start_create_voice_thread
        )
        self.create_voice_btn.grid(row=3, column=3, padx=5, pady=5)
        
        # 2. 管理语音选项卡（支持自适应宽度）
        manage_frame = ttk.Frame(notebook, padding=10)
        notebook.add(manage_frame, text="管理语音")
        
        # 配置管理语音选项卡的列权重
        manage_frame.grid_columnconfigure(1, weight=1)  # 输入框列自适应宽度
        
        # 当前Voice ID显示
        tk.Label(manage_frame, text="当前Voice ID:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.voice_id_dialog_entry = tk.Entry(manage_frame, textvariable=self.voice_id_var, state='readonly')
        self.voice_id_dialog_entry.grid(row=0, column=1, columnspan=3, sticky=tk.EW, pady=5, padx=5)
        
        # 手动输入Voice ID区域
        tk.Label(manage_frame, text="手动输入Voice ID:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.manual_voice_id_entry = tk.Entry(manage_frame)
        self.manual_voice_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
        
        tk.Label(manage_frame, text="语音名称:").grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)
        self.manual_voice_name_entry = tk.Entry(manage_frame, width=15)
        self.manual_voice_name_entry.grid(row=1, column=3, sticky=tk.W, pady=5, padx=5)
        
        self.add_manual_voice_btn = tk.Button(
            manage_frame, 
            text="添加Voice ID", 
            command=self.add_manual_voice
        )
        self.add_manual_voice_btn.grid(row=1, column=4, padx=5, pady=5)
        
        # 语音列表显示区域（自适应宽度和高度）
        tk.Label(manage_frame, text="已保存的语音列表:").grid(row=2, column=0, sticky=tk.W, pady=10, padx=5)
        
        # 创建列表框容器并配置权重
        list_frame = tk.Frame(manage_frame)
        list_frame.grid(row=3, column=0, columnspan=4, sticky=tk.NSEW, pady=5, padx=5)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        # 创建列表框
        self.voice_listbox = tk.Listbox(list_frame, height=8, width=50)
        self.voice_listbox.grid(row=0, column=0, sticky=tk.NSEW)
        
        # 添加滚动条
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.voice_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.voice_listbox.config(yscrollcommand=scrollbar.set)
        
        # 添加删除按钮
        self.delete_voice_btn = tk.Button(
            manage_frame, 
            text="删除选中语音", 
            command=self.delete_selected_voice
        )
        self.delete_voice_btn.grid(row=4, column=0, pady=10, padx=5, sticky=tk.W)
        
        # 配置行权重，使列表区域能够自适应高度
        manage_frame.grid_rowconfigure(3, weight=1)
        
        # 加载已有Voice ID到列表
        self.refresh_voice_list()
        
        # 绑定列表双击事件（切换选中Voice ID）
        self.voice_listbox.bind('<Double-1>', self.on_voice_select)
    
    def browse_audio_file(self):
        """浏览并选择本地音频文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("音频文件", "*.mp3;*.wav;*.flac;*.m4a"), ("所有文件", "*.*")]
        )
        if file_path:
            self.audio_url_entry.delete(0, tk.END)
            self.audio_url_entry.insert(0, file_path)
    
    def add_manual_voice(self):
        """处理手动添加Voice ID的逻辑"""
        # 获取输入的Voice ID和名称
        voice_id = self.manual_voice_id_entry.get().strip()
        voice_name = self.manual_voice_name_entry.get().strip()
        
        # 输入验证
        if not voice_id:
            messagebox.showerror("输入错误", "请输入Voice ID")
            return
            
        if not voice_name:
            messagebox.showerror("输入错误", "请输入语音名称")
            return
            
        # 检查是否已存在相同ID
        if voice_id in self.voice_ids.values():
            existing_name = next(k for k, v in self.voice_ids.items() if v == voice_id)
            messagebox.showwarning("已存在", f"该Voice ID已关联到语音名称: {existing_name}")
            return
            
        # 处理名称重复的情况
        if voice_name in self.voice_ids:
            if not messagebox.askyesno("名称重复", f"语音名称'{voice_name}'已存在，是否覆盖?"):
                return
            del self.voice_ids[voice_name]  # 先删除旧的关联
        
        # 添加到字典并更新状态
        self.voice_ids[voice_name] = voice_id
        self.voice_id_var.set(voice_id)  # 自动选中新添加的Voice ID
        self.save_config()  # 保存配置
        
        # 刷新列表显示
        self.refresh_voice_list()
        
        # 清空输入框并提示成功
        self.manual_voice_id_entry.delete(0, tk.END)
        self.manual_voice_name_entry.delete(0, tk.END)
        
        self.log_message(f"已添加Voice ID: {voice_id} (名称: {voice_name})")
        messagebox.showinfo("成功", f"已添加语音: {voice_name}")
    
    def refresh_voice_list(self):
        """刷新语音列表显示"""
        self.voice_listbox.delete(0, tk.END)  # 清空现有列表
        for name, voice_id in self.voice_ids.items():
            # 显示格式：名称 (ID前8位...)
            display_text = f"{name} ({voice_id[:8]}...)"
            self.voice_listbox.insert(tk.END, display_text)
            # 高亮当前选中的Voice ID
            if voice_id == self.voice_id_var.get():
                self.voice_listbox.selection_set(tk.END)
    
    def delete_selected_voice(self):
        """删除选中的Voice ID"""
        selected_index = self.voice_listbox.curselection()
        if not selected_index:
            messagebox.showinfo("提示", "请先选中要删除的语音")
            return
            
        # 获取选中的名称
        selected_text = self.voice_listbox.get(selected_index)
        voice_name = selected_text.split(" (")[0]  # 提取名称部分
        
        if messagebox.askyesno("确认删除", f"确定要删除语音'{voice_name}'吗?"):
            del self.voice_ids[voice_name]
            # 如果删除的是当前选中的ID，自动切换
            if self.voice_id_var.get() == self.voice_ids.get(voice_name, ""):
                if self.voice_ids:
                    # 切换到第一个语音
                    first_name = next(iter(self.voice_ids.keys()))
                    self.voice_id_var.set(self.voice_ids[first_name])
                else:
                    self.voice_id_var.set("")
            self.save_config()
            self.refresh_voice_list()
            self.log_message(f"已删除语音: {voice_name}")
    
    def on_voice_select(self, event):
        """双击列表项切换选中的Voice ID"""
        selected_index = self.voice_listbox.curselection()
        if not selected_index:
            return
            
        selected_text = self.voice_listbox.get(selected_index)
        voice_name = selected_text.split(" (")[0]  # 提取名称部分
        
        if voice_name in self.voice_ids:
            selected_voice_id = self.voice_ids[voice_name]
            self.voice_id_var.set(selected_voice_id)
            self.save_config()
            self.log_message(f"已切换到语音: {voice_name}")
    
    def show_api_settings(self):
        """显示API设置对话框"""
        if not self.api_dialog:
            self.create_api_settings_dialog()
        else:
            self.api_dialog.deiconify()
        self.api_dialog.lift()
    
    def show_voice_settings(self):
        """显示语音复刻设置对话框"""
        if not self.voice_dialog:
            self.create_voice_settings_dialog()
        else:
            self.voice_dialog.deiconify()
        self.voice_dialog.lift()
    
    def save_api_key(self):
        """保存API密钥"""
        new_api_key = self.api_entry.get().strip()
        if new_api_key:
            self.api_key = new_api_key
            self.save_config()
            self.log_message("API密钥已更新")
            messagebox.showinfo("成功", "API密钥已保存")
            self.api_dialog.withdraw()
        else:
            messagebox.showerror("输入错误", "API密钥不能为空")
    
    def browse_output_dir(self):
        """浏览输出目录"""
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, directory)
    
    def browse_subtitle_file(self):
        """浏览字幕文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("字幕文件", "*.srt;*.ass;*.ssa"), ("所有文件", "*.*")]
        )
        if file_path:
            self.subtitle_path_entry.delete(0, tk.END)
            self.subtitle_path_entry.insert(0, file_path)
            # 自动解析并显示字幕信息
            self.root.after(100, self.preview_subtitle)
    
    def preview_subtitle(self):
        """预览字幕文件信息"""
        subtitle_path = self.subtitle_path_entry.get().strip()
        if not subtitle_path or not os.path.exists(subtitle_path):
            return
            
        try:
            with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # 简单解析字幕内容
            clean_lines = []
            for line in lines:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.isdigit() or '-->' in stripped_line:
                    continue
                clean_lines.append(stripped_line)
            
            if clean_lines:
                self.subtitle_status.config(text=f"检测到 {len(clean_lines)} 行有效文本")
            else:
                self.subtitle_status.config(text="未检测到有效文本内容", fg="red")
                
        except Exception as e:
            self.subtitle_status.config(text=f"解析错误: {str(e)}", fg="red")
    
    def load_subtitle_to_textbox(self):
        """加载字幕到文本框，过滤时间戳和数字"""
        subtitle_path = self.subtitle_path_entry.get().strip()
        if not subtitle_path or not os.path.exists(subtitle_path):
            messagebox.showerror("错误", "请选择有效的字幕文件")
            return
        
        try:
            self.log_message(f"正在加载字幕文件: {subtitle_path}")
            
            # 读取字幕文件
            with open(subtitle_path, 'r', encoding='utf-8', errors='ignore') as f:
                subtitle_text = f.read()
            
            # 解析并过滤字幕内容
            clean_text = self.parse_and_clean_subtitle(subtitle_text)
            
            if not clean_text:
                self.log_message("未从字幕文件中提取到有效文本")
                messagebox.showwarning("警告", "未从字幕文件中提取到有效文本")
                return
            
            # 显示到文本框
            self.text_input.config(state=tk.NORMAL)
            self.text_input.delete(1.0, tk.END)
            self.text_input.insert(tk.END, clean_text)
            self.text_input.config(state=tk.NORMAL)  # 保持可编辑状态
            
            self.log_message(f"字幕加载完成，共提取 {len(clean_text.splitlines())} 行文本")
            self.subtitle_status.config(text=f"已加载 {len(clean_text.splitlines())} 行文本", fg="green")
            
        except Exception as e:
            error_msg = f"加载字幕失败: {str(e)}"
            self.log_message(error_msg)
            self.subtitle_status.config(text=error_msg, fg="red")
            messagebox.showerror("错误", error_msg)
    
    def parse_and_clean_subtitle(self, subtitle_text):
        """解析字幕并过滤时间戳和数字"""
        lines = subtitle_text.splitlines()
        clean_lines = []
        skip_next_empty = False  # 用于跳过字幕块之间的空行
        
        for line in lines:
            stripped_line = line.strip()
            
            # 过滤SRT格式的序号（纯数字）
            if stripped_line.isdigit():
                skip_next_empty = True
                continue
                
            # 过滤时间戳（包含 --> 标记）
            if '-->' in stripped_line:
                skip_next_empty = True
                continue
                
            # 跳过字幕块之间的空行
            if not stripped_line:
                if skip_next_empty:
                    skip_next_empty = False
                    continue
                else:
                    # 保留文本段落之间的空行
                    clean_lines.append('')
                    continue
            
            # 重置跳过标记
            skip_next_empty = False
            
            # 处理包含数字的行（只移除纯数字，保留包含数字的文本）
            if stripped_line.isdigit():
                continue
                
            # 保留有效文本行
            clean_lines.append(stripped_line)
        
        # 合并为极文，使用空行分隔段落
        return '\n'.join(clean_lines)
    
    def start_synthesize_based_on_mode(self):
        """根据当前模式启动合成"""
        if not self.api_key:
            messagebox.showwarning("提示", "请先在设置中配置API密钥")
            self.show_api_settings()
            return
            
        if not self.voice_id_var.get():
            messagebox.showwarning("提示", "请先在语音复刻设置中创建或添加Voice ID")
            self.show_voice_settings()
            return
        
        mode = self.synthesis_mode.get()
        
        # 禁用按钮防止重复点击
        self.synthesize_btn.config(state=tk.DISABLED)
        self.play_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        
        if mode == "text":
            text = self.text_input.get("1.0", tk.END).strip()
            if not text:
                messagebox.showerror("错误", "请输入要合成的文本")
                self.synthesize_btn.config(state=tk.NORMAL)
                return
            threading.Thread(target=self.synthesize_text, args=(text,), daemon=True).start()
        else:
            text = self.text_input.get("1.0", tk.END).strip()
            if not text:
                messagebox.showerror("错误", "请先加载字幕到文本框")
                self.synthesize_btn.config(state=tk.NORMAL)
                return
            threading.Thread(target=self.synthesize_subtitle, args=(text,), daemon=True).start()
    
    def synthesize_text(self, text):
        """合成文本语音"""
        try:
            self.log_message("开始文本语音合成...")
            dashscope.api_key = self.api_key
            
            synthesizer = SpeechSynthesizer(
                model='cosyvoice-v2',
                voice=self.voice_id_var.get()
            )
            
            # 执行合成
            self.log_message("正在调用API进行语音合成...")
            result = synthesizer.call(text=text)
            
            # 检查API返回结果类型
            if isinstance(result, bytes):
                # 如果返回的是字节流，直接作为音频数据处理
                self.audio_data = result
                
                # 创建临时文件存储合成结果
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                    f.write(self.audio_data)
                    self.temp_audio_file = f.name
                
                self.log_message("语音合成成功")
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
                self.log_message(f"合成语音已保存到临时文件: {self.temp_audio_file}")
                
            elif isinstance(result, dict):
                # 如果返回的是字典，按之前的方式处理
                if result.get('status_code') == 200:
                    self.audio_data = result.get('audio') or result.get('audio_data')
                    
                    if self.audio_data:
                        # 创建临时文件存储合成结果
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                            f.write(self.audio_data)
                            self.temp_audio_file = f.name
                        
                        self.log_message("语音合成成功")
                        self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                        self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
                        self.log_message(f"合成语音已保存到临时文件: {self.temp_audio_file}")
                    else:
                        error_msg = "合成成功但未获取到音频数据"
                        self.log_message(error_msg)
                        messagebox.showerror("合成失败", error_msg)
                else:
                    error_msg = f"合成失败: {result.get('message', '未知错误')}"
                    self.log_message(error_msg)
                    messagebox.showerror("合成失败", error_msg)
            else:
                error_msg = f"合成失败: 未知的API返回格式 {type(result)}"
                self.log_message(error_msg)
                messagebox.showerror("合成失败", error_msg)
                    
        except Exception as e:
            error_msg = f"合成过程出错: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
        finally:
            self.root.after(0, lambda: self.synthesize_btn.config(state=tk.NORMAL))
    
    def synthesize_subtitle(self, text):
        """合成长字幕语音（支持大文件分块处理）"""
        try:
            self.log_message("开始处理字幕文本...")
            
            # 将文本分成多个段落，每段不超过200字（避免API限制）
            paragraphs = []
            current_paragraph = []
            current_length = 0
            
            for line in text.splitlines():
                stripped_line = line.strip()
                if not stripped_line:  # 保留段落分隔
                    if current_paragraph:
                        paragraphs.append(" ".join(current_paragraph))
                        current_paragraph = []
                        current_length = 0
                    continue
                    
                if current_length + len(stripped_line) > 200:
                    paragraphs.append(" ".join(current_paragraph))
                    current_paragraph = [stripped_line]
                    current_length = len(stripped_line)
                else:
                    current_paragraph.append(stripped_line)
                    current_length += len(stripped_line)
            
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
            
            if not paragraphs:
                self.log_message("没有可合成的字幕文本")
                messagebox.showwarning("警告", "没有可合成的字幕文本")
                return
            
            self.log_message(f"字幕文本已分段，共分为 {len(paragraphs)} 段进行合成")
            
            # 处理所有段落并合并音频
            all_audio_data = []
            for i, para in enumerate(paragraphs):
                self.log_message(f"正在合成第 {i+1}/{len(paragraphs)} 段...")
                
                # 为每个段落合成语音，添加超时控制
                para_audio = self.synthesize_text_segment(para)
                if not para_audio:
                    self.log_message(f"第 {i+1} 段合成失败，中止处理")
                    return
                    
                all_audio_data.append(para_audio)
            
            # 合并所有音频片段（需要安装pydub库）
            try:
                from pydub import AudioSegment
                from io import BytesIO
                
                combined = AudioSegment.empty()
                for audio_data in all_audio_data:
                    segment = AudioSegment.from_file(BytesIO(audio_data), format="mp3")
                    combined += segment
                
                # 保存合并后的音频
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                    combined.export(f, format="mp3")
                    self.temp_audio_file = f.name
                
                # 保存原始数据用于后续保存
                self.audio_data = combined.export(BytesIO(), format="mp3").read()
                
                self.log_message("字幕语音合成成功")
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
                
            except ImportError:
                self.log_message("警告：未安装pydub库，无法合并音频，仅保存最后一段")
                self.audio_data = all_audio_data[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                    f.write(self.audio_data)
                    self.temp_audio_file = f.name
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
            except Exception as e:
                self.log_message(f"音频合并失败: {str(e)}")
                messagebox.showerror("错误", f"音频合并失败: {str(e)}")
                
        except Exception as e:
            error_msg = f"字幕处理出错: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
        finally:
            self.root.after(0, lambda: self.synthesize_btn.config(state=tk.NORMAL))

    def synthesize_text_segment(self, text, timeout=30):
        """合成文本片段，带超时控制"""
        try:
            # 设置超时机制
            import threading
            result = [None]
            error = [None]
            
            def synthesis_task():
                try:
                    dashscope.api_key = self.api_key
                    synthesizer = SpeechSynthesizer(
                        model='cosyvoice-v2',
                        voice=self.voice_id_var.get()
                    )
                    res = synthesizer.call(text=text)
                    result[0] = res
                except Exception as e:
                    error[0] = e
            
            thread = threading.Thread(target=synthesis_task)
            thread.start()
            thread.join(timeout)
            
            if thread.is_alive():
                self.log_message(f"合成超时（{timeout}秒）")
                return None
                
            if error[0]:
                self.log_message(f"合成片段出错: {str(error[0])}")
                return None
                
            res = result[0]
            if isinstance(res, bytes):
                return res
            elif isinstance(res, dict) and res.get('status_code') == 200:
                return res.get('audio') or res.get('audio_data')
            else:
                self.log_message(f"片段合成失败: {res.get('message', '未知错误') if isinstance(res, dict) else str(res)}")
                return None
                
        except Exception as e:
            self.log_message(f"处理片段时出错: {str(e)}")
            return None
    
    def start_create_voice_thread(self):
        """启动创建语音的线程"""
        if not self.api_key:
            messagebox.showwarning("提示", "请先在设置中配置API密钥")
            self.show_api_settings()
            return
            
        # 禁用按钮防止重复点击
        self.create_voice_btn.config(state=tk.DISABLED)
        
        # 启动创建语音线程
        threading.Thread(
            target=self.create_voice,
            daemon=True
        ).start()
    
    def create_voice(self):
        """创建语音复刻"""
        try:
            self.log_message("开始创建语音复刻...")
            
            # 检查API密钥
            if not self.api_key:
                messagebox.showerror("错误", "请先在设置中配置API密钥")
                self.log_message("创建失败：未设置API密钥")
                return
        
            # 检查是否复用现有voice_id
            if self.reuse_voice_var.get() and self.voice_id:
                self.log_message(f"复用现有Voice ID: {self.voice_id}")
                messagebox.showinfo("信息", f"已复用现有Voice ID: {self.voice_id}")
                return
        
            # 获取参数
            url_or_path = self.audio_url_entry.get().strip()
            prefix = self.prefix_entry.get().strip()
            target_model = "cosyvoice-v2"
            
            if not url_or_path or url_or_path == "https://your-audio-file-url":
                messagebox.showerror("错误", "请输入有效的音频文件URL或选择本地文件")
                self.log_message("创建失败：音频文件URL无效")
                return
            
            if not prefix:
                messagebox.showerror("错误", "请输入前缀")
                self.log_message("创建失败：未输入前缀")
                return
            
            # 设置API密钥
            dashscope.api_key = self.api_key
            
            # 创建语音注册服务实例
            service = VoiceEnrollmentService()
            
            # 判断是URL还是本地文件路径
            if os.path.exists(url_or_path):
                self.log_message("警告：使用本地文件路径，需要确保文件可公开访问")
                url = url_or_path
            else:
                url = url_or_path
            
            # 调用create_voice方法复刻声音，并生成voice_id
            self.log_message("正在创建语音，请稍候...")
            # 获取原始voice_id
            raw_voice_id = service.create_voice(
                target_model=target_model, 
                prefix=prefix, 
                url=url
            )
            
            # 构建完整的voice_id，确保包含模型前缀
            if not raw_voice_id.startswith(f"{target_model}-"):
                self.voice_id = f"{target_model}-{raw_voice_id}"
            else:
                self.voice_id = raw_voice_id
            
            # 更新界面显示
            self.root.after(0, lambda: self.voice_id_var.set(self.voice_id))
            
            # 自动保存到语音列表
            voice_name = self.voice_name_entry.get().strip() or f"语音_{datetime.now().strftime('%H%M%S')}"
            self.voice_ids[voice_name] = self.voice_id
            
            # 保存配置
            self.save_config()
            self.root.after(0, self.refresh_voice_list)
            
            self.log_message(f"语音创建成功，Voice ID: {self.voice_id}")
            self.log_message(f"Request ID: {service.get_last_request_id()}")
            messagebox.showinfo("成功", f"语音创建成功\nVoice ID: {self.voice_id}")
            
        except Exception as e:
            error_msg = f"创建语音失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
        finally:
            self.root.after(0, lambda: self.create_voice_btn.config(state=tk.NORMAL))
    
    def play_audio(self):
        """播放合成的语音"""
        if not self.temp_audio_file or not os.path.exists(self.temp_audio_file):
            messagebox.showerror("错误", "没有可播放的音频文件，请先合成语音")
            return
        
        try:
            self.log_message("开始播放音频...")
            # 根据操作系统选择播放命令
            if platform.system() == 'Windows':
                os.startfile(self.temp_audio_file)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', self.temp_audio_file])
            else:  # Linux
                subprocess.run(['xdg-open', self.temp_audio_file])
        except Exception as e:
            error_msg = f"播放音频失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def save_audio(self):
        """保存合成的语音"""
        if not self.audio_data:
            messagebox.showerror("错误", "没有可保存的音频文件，请先合成语音")
            return
        
        output_dir = self.output_dir_entry.get().strip()
        if not output_dir:
            output_dir = filedialog.askdirectory(title="选择保存目录")
            if not output_dir:
                return
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, output_dir)
        
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建目录: {str(e)}")
                return
        
        # 生成默认文件名
        default_filename = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        save_path = os.path.join(output_dir, default_filename)
        
        try:
            # 直接使用API返回的音频数据保存
            with open(save_path, 'wb') as f:
                f.write(self.audio_data)
            
            self.log_message(f"音频已保存到: {save_path}")
            messagebox.showinfo("成功", f"音频已保存到:\n{save_path}")
        except Exception as e:
            error_msg = f"保存音频失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_message("日志已清空")
    
    def on_resize(self, event):
        """窗口大小变化时调整布局"""
        # 响应式布局调整逻辑
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceSynthesisApp(root)
    root.mainloop()
