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
        
        self.upload_subtitle_audio_btn = tk.Button(
            self.subtitle_frame, 
            text="上传参考音频...", 
            command=self.upload_subtitle_audio
        )
        self.upload_subtitle_audio_btn.grid(row=1, column=0, padx=5, pady=5)
        
        self.subtitle_audio_path = tk.Entry(self.subtitle_frame)
        self.subtitle_audio_path.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
        
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
            self.text_input.config(state=tk.DISABLED)
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
        
        tk.Label(self.api_dialog, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=15, padx=15)
        self.api_entry = tk.Entry(self.api_dialog, show="*", width=30)
        self.api_entry.grid(row=0, column=1, sticky=tk.W, pady=15, padx=5)
        self.api_entry.insert(0, self.api_key)
        
        btn_frame = tk.Frame(self.api_dialog)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        self.save_api_btn = tk.Button(btn_frame, text="保存", command=self.save_api_key)
        self.save_api_btn.pack(side=tk.LEFT, padx=10)
        
        self.close_api_btn = tk.Button(btn_frame, text="关闭", command=self.api_dialog.withdraw)
        self.close_api_btn.pack(side=tk.LEFT, padx=10)
    
    def create_voice_settings_dialog(self):
        """创建语音复刻设置对话框（内部管理Voice ID）"""
        self.voice_dialog = tk.Toplevel(self.root)
        self.voice_dialog.title("语音复刻设置")
        self.voice_dialog.geometry("600x400")
        self.voice_dialog.transient(self.root)
        self.voice_dialog.protocol("WM_DELETE_WINDOW", self.voice_dialog.withdraw)
        
        frame = tk.Frame(self.voice_dialog, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="音频文件URL或本地路径:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.audio_url_entry = tk.Entry(frame)
        self.audio_url_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        self.audio_url_entry.insert(0, "https://your-audio-file-url")
        frame.grid_columnconfigure(1, weight=1)
        
        tk.Label(frame, text="前缀:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.prefix_entry = tk.Entry(frame, width=20)
        self.prefix_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.prefix_entry.insert(0, "myvoice")
        
        tk.Label(frame, text="语音名称:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.voice_name_entry = tk.Entry(frame, width=20)
        self.voice_name_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.voice_name_entry.insert(0, "我的声音")
        
        # Voice ID管理（仅在设置对话框中显示）
        tk.Label(frame, text="当前Voice ID:").grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        self.voice_id_dialog_entry = tk.Entry(frame, textvariable=self.voice_id_var)
        self.voice_id_dialog_entry.grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        
        self.save_voice_id_btn = tk.Button(
            frame, 
            text="保存当前Voice ID", 
            command=self.save_current_voice_id
        )
        self.save_voice_id_btn.grid(row=3, column=3, padx=5, pady=5)
        
        tk.Label(frame, text="选择保存的Voice ID:").grid(row=4, column=0, sticky=tk.W, pady=5, padx=5)
        self.voice_id_combobox = ttk.Combobox(frame, state="readonly")
        self.voice_id_combobox.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)
        self.update_voice_combobox()
        self.voice_id_combobox.bind("<<ComboboxSelected>>", self.on_voice_selected)
        
        self.delete_voice_btn = tk.Button(
            frame, 
            text="删除选中Voice ID", 
            command=self.delete_selected_voice
        )
        self.delete_voice_btn.grid(row=4, column=2, padx=5, pady=5)
        
        self.reuse_voice_var = tk.BooleanVar(value=True if self.voice_id else False)
        self.reuse_checkbox = tk.Checkbutton(
            frame, 
            text="复用现有Voice ID（避免重复创建）", 
            variable=self.reuse_voice_var
        )
        self.reuse_checkbox.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        
        self.create_voice_btn = tk.Button(
            frame, 
            text="创建/更新语音", 
            command=self.start_create_voice_thread
        )
        self.create_voice_btn.grid(row=5, column=2, padx=5, pady=5)
        
        self.close_voice_btn = tk.Button(frame, text="关闭", command=self.voice_dialog.withdraw)
        self.close_voice_btn.grid(row=6, column=3, pady=15)
    
    def show_api_settings(self):
        """显示API设置对话框"""
        if not self.api_dialog:
            self.create_api_settings_dialog()
        self.api_dialog.deiconify()
        self.api_dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + self.root.winfo_width()//2 - 200,
            self.root.winfo_rooty() + self.root.winfo_height()//2 - 75
        ))
    
    def show_voice_settings(self):
        """显示语音复刻设置对话框"""
        if not self.voice_dialog:
            self.create_voice_settings_dialog()
        self.voice_dialog.deiconify()
        self.voice_dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + self.root.winfo_width()//2 - 300,
            self.root.winfo_rooty() + self.root.winfo_height()//2 - 200
        ))
    
    def on_resize(self, event):
        """窗口大小变化时调整组件"""
        pass
    
    def save_api_key(self):
        """保存API密钥"""
        self.api_key = self.api_entry.get().strip()
        if self.api_key:
            self.save_config()
            messagebox.showinfo("成功", "API密钥已保存")
            self.api_dialog.withdraw()
        else:
            messagebox.showwarning("警告", "API密钥不能为空")
    
    def browse_output_dir(self):
        """浏览输出文件夹"""
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, directory)
    
    def clear_log(self):
        """清空日志"""
        if self.log_text is None:
            return
            
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_message("日志已清空")
    
    # Voice ID管理功能（仅在设置对话框中可用）
    def save_current_voice_id(self):
        """保存当前Voice ID到配置中"""
        voice_name = self.voice_name_entry.get().strip()
        voice_id = self.voice_id_var.get().strip()
        
        if not voice_name:
            messagebox.showwarning("警告", "请输入语音名称")
            return
        
        if not voice_id:
            messagebox.showwarning("警告", "请输入有效的Voice ID")
            return
        
        self.voice_ids[voice_name] = voice_id
        self.voice_id = voice_id
        self.save_config()
        self.update_voice_combobox()
        self.log_message(f"已保存语音: {voice_name}")
        messagebox.showinfo("成功", f"已保存语音: {voice_name}")
    
    def update_voice_combobox(self):
        """更新语音选择下拉框"""
        self.voice_id_combobox['values'] = list(self.voice_ids.keys())
        if self.voice_ids:
            self.voice_id_combobox.current(0)
    
    def on_voice_selected(self, event):
        """选择语音时更新输入框"""
        selected_name = self.voice_id_combobox.get()
        if selected_name in self.voice_ids:
            selected_id = self.voice_ids[selected_name]
            self.voice_id_var.set(selected_id)
            self.voice_id = selected_id
            self.log_message(f"已选择语音: {selected_name}")
    
    def delete_selected_voice(self):
        """删除选中的Voice ID"""
        selected_name = self.voice_id_combobox.get()
        if not selected_name or selected_name not in self.voice_ids:
            messagebox.showwarning("警告", "请先选择要删除的语音")
            return
        
        if messagebox.askyesno("确认", f"确定要删除语音 '{selected_name}' 吗？"):
            del self.voice_ids[selected_name]
            self.save_config()
            self.update_voice_combobox()
            self.log_message(f"已删除语音: {selected_name}")
    
    # 字幕文件处理
    def browse_subtitle_file(self):
        """浏览字幕文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("字幕文件", "*.srt *.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            self.subtitle_path_entry.delete(0, tk.END)
            self.subtitle_path_entry.insert(0, file_path)
            self.load_subtitle_content(file_path)
    
    def upload_subtitle_audio(self):
        """上传用于字幕合成的参考音频文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("音频文件", "*.wav *.mp3 *.ogg *.flac"), ("所有文件", "*.*")]
        )
        if file_path:
            self.subtitle_audio_path.delete(0, tk.END)
            self.subtitle_audio_path.insert(0, file_path)
            self.log_message(f"已上传字幕参考音频: {os.path.basename(file_path)}")
    
    def load_subtitle_content(self, file_path):
        """加载字幕内容到文本框"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 处理SRT格式，提取文本内容
                if file_path.endswith('.srt'):
                    lines = content.split('\n')
                    text_lines = []
                    for line in lines:
                        # 跳过序号和时间戳
                        if not line.strip().isdigit() and '-->' not in line:
                            if line.strip():
                                text_lines.append(line.strip())
                    content = '\n'.join(text_lines)
                
                # 更新文本框内容
                self.text_input.config(state=tk.NORMAL)
                self.text_input.delete(1.0, tk.END)
                self.text_input.insert(tk.END, content)
                self.text_input.config(state=tk.DISABLED)
                self.log_message(f"已加载字幕内容: {os.path.basename(file_path)}")
        except Exception as e:
            error_msg = f"加载字幕文件失败: {str(e)}"
            self.log_message(error_msg)
    
    def start_subtitle_synth_thread(self):
        """启动字幕语音合成线程"""
        threading.Thread(target=self.synthesize_from_subtitle, daemon=True).start()
    
    def synthesize_from_subtitle(self):
        """从字幕文件合成语音"""
        subtitle_path = self.subtitle_path_entry.get().strip()
        if not subtitle_path or not os.path.exists(subtitle_path):
            messagebox.showerror("错误", "请选择有效的字幕文件")
            self.log_message("字幕合成失败：未选择有效的字幕文件")
            return
        
        # 检查API密钥
        if not self.api_key:
            messagebox.showerror("错误", "请先在设置中配置API密钥")
            self.log_message("合成失败：未设置API密钥")
            return
        
        # 检查voice_id
        current_voice_id = self.voice_id_var.get().strip()
        if not current_voice_id:
            messagebox.showerror("错误", "请先在设置中创建语音复刻获取Voice ID")
            self.log_message("合成失败：未获取Voice ID")
            return
        
        try:
            # 读取字幕内容
            with open(subtitle_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 处理字幕内容
            if subtitle_path.endswith('.srt'):
                lines = content.split('\n')
                text_lines = []
                for line in lines:
                    if not line.strip().isdigit() and '-->' not in line and line.strip():
                        text_lines.append(line.strip())
                text = ' '.join(text_lines)
            else:  # 普通文本文件
                text = content.strip()
            
            if not text:
                messagebox.showerror("错误", "字幕文件中没有可合成的文本")
                self.log_message("合成失败：字幕文件中没有可合成的文本")
                return
            
            # 调用合成方法
            self.synthesize_text(text)
            
        except Exception as e:
            error_msg = f"字幕语音合成失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def start_create_voice_thread(self):
        """启动创建语音的线程"""
        threading.Thread(target=self.create_voice, daemon=True).start()
    
    def create_voice(self):
        """创建语音复刻"""
        self.log_message("开始创建语音复刻...")
        
        # 检查API密钥
        if not self.api_key:
            messagebox.showerror("错误", "请先在设置中配置API密钥")
            self.log_message("创建失败：未设置API密钥")
            return
        
        # 检查是否复用现有voice_id
        if self.reuse_voice_var.get() and self.voice_id:
            self.log_message(f"复用现有Voice ID")
            messagebox.showinfo("信息", f"已复用现有Voice ID")
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
        
        try:
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
            self.voice_id = service.create_voice(
                target_model=target_model, 
                prefix=prefix, 
                url=url
            )
            
            # 更新界面
            self.root.after(0, lambda: self.voice_id_var.set(self.voice_id))
            
            # 保存配置
            self.save_config()
            
            self.log_message(f"语音创建成功")
            self.log_message(f"Request ID: {service.get_last_request_id()}")
            messagebox.showinfo("成功", f"语音创建成功")
            
        except Exception as e:
            error_msg = f"创建语音失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def start_synthesize_thread(self):
        """启动语音合成的线程"""
        text = self.text_input.get(1.0, tk.END).strip()
        if text:
            threading.Thread(target=lambda: self.synthesize_text(text), daemon=True).start()
        else:
            messagebox.showerror("错误", "请输入要合成的文本")
    
    def start_synthesize_based_on_mode(self):
        """根据选择的模式启动相应的合成线程"""
        mode = self.synthesis_mode.get()
        if mode == "text":
            self.start_synthesize_thread()
        else:
            self.start_subtitle_synth_thread()
    
    def synthesize_text(self, text):
        """合成指定文本的语音"""
        self.log_message("开始语音合成...")
        
        # 检查API密钥
        if not self.api_key:
            messagebox.showerror("错误", "请先在设置中配置API密钥")
            self.log_message("合成失败：未设置API密钥")
            return
        
        # 检查voice_id
        current_voice_id = self.voice_id_var.get().strip()
        if not current_voice_id:
            messagebox.showerror("错误", "请先在设置中创建语音复刻获取Voice ID")
            self.log_message("合成失败：未获取Voice ID")
            return
        
        if not text:
            messagebox.showerror("错误", "请输入要合成的文本")
            self.log_message("合成失败：未输入文本")
            return
        
        try:
            # 设置API密钥
            dashscope.api_key = self.api_key
            
            # 创建语音合成器实例
            synthesizer = SpeechSynthesizer(
                model="cosyvoice-v2", 
                voice=current_voice_id
            )
            
            # 调用合成方法
            self.log_message(f"正在合成语音，请稍候...")
            self.audio_data = synthesizer.call(text)
            
            # 保存到临时文件
            if self.temp_audio_file and os.path.exists(self.temp_audio_file):
                os.remove(self.temp_audio_file)
                
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(self.audio_data)
                self.temp_audio_file = f.name
            
            # 启用试听和保存按钮
            self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
            
            self.log_message("语音合成成功")
            self.log_message(f"Request ID: {synthesizer.get_last_request_id()}")
            
        except Exception as e:
            error_msg = f"语音合成失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def play_audio(self):
        """播放合成的语音 - 使用系统默认播放器"""
        if not self.temp_audio_file or not os.path.exists(self.temp_audio_file):
            messagebox.showerror("错误", "没有可播放的音频文件，请先合成语音")
            return
        
        try:
            self.log_message("开始播放音频（使用系统默认播放器）...")
            
            # 根据操作系统选择合适的方式调用默认播放器
            system = platform.system()
            if system == 'Windows':
                # Windows使用start命令打开默认播放器
                os.startfile(self.temp_audio_file)
            elif system == 'Darwin':  # macOS
                # macOS使用open命令打开默认播放器
                subprocess.run(['open', self.temp_audio_file])
            elif system == 'Linux':  # Linux
                # Linux使用xdg-open打开默认播放器
                subprocess.run(['xdg-open', self.temp_audio_file])
            else:
                raise Exception(f"不支持的操作系统: {system}")
                
            self.log_message("已启动系统默认播放器播放音频")
            
        except Exception as e:
            error_msg = f"播放音频失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def save_audio(self):
        """保存合成的语音到指定文件夹"""
        if not self.audio_data:
            messagebox.showerror("错误", "没有可保存的音频文件，请先合成语音")
            return
        
        output_dir = self.output_dir_entry.get().strip()
        if not output_dir:
            output_dir = filedialog.askdirectory()
            if not output_dir:
                return
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, output_dir)
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"voice_synthesis_{timestamp}.mp3"
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, 'wb') as f:
                f.write(self.audio_data)
            
            self.log_message(f"语音已保存至: {output_path}")
            messagebox.showinfo("成功", f"语音已保存至:\n{output_path}")
            
        except Exception as e:
            error_msg = f"保存音频失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceSynthesisApp(root)
    root.mainloop()
    
