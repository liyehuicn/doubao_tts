import os
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
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
        self.root.title("语音合成应用")
        self.root.geometry("800x700")
        self.root.minsize(600, 600)  # 设置最小窗口尺寸
        
        # 配置中文字体
        self.font_config()
        
        # 应用状态变量
        self.api_key = ""
        self.voice_id = ""
        self.config_file = "config.json"
        self.temp_audio_file = None  # 用于存储临时音频文件路径
        self.audio_data = None  # 存储合成的音频数据
        
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
        """从配置文件加载API密钥和voice_id"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.api_key = config.get('api_key', '')
                    self.voice_id = config.get('voice_id', '')
            except Exception as e:
                messagebox.showerror("配置加载错误", f"加载配置文件失败: {str(e)}")
    
    def save_config(self):
        """保存配置到文件"""
        try:
            config = {
                'api_key': self.api_key,
                'voice_id': self.voice_id
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.log_message("配置已保存")
        except Exception as e:
            messagebox.showerror("配置保存错误", f"保存配置文件失败: {str(e)}")
    
    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架，使用网格布局
        self.main_frame = tk.Frame(self.root, padx=10, pady=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 设置网格权重，使组件能够自适应拉伸
        self.main_frame.grid_rowconfigure(4, weight=1)  # 文本输入区域
        self.main_frame.grid_rowconfigure(6, weight=1)  # 日志区域
        self.main_frame.grid_columnconfigure(1, weight=1)  # 输入框列
        
        # 1. API密钥区域
        self.api_frame = tk.LabelFrame(self.main_frame, text="API 密钥设置", padx=5, pady=5)
        self.api_frame.grid(row=0, column=0, columnspan=4, sticky=tk.EW, pady=(0, 10))
        self.api_frame.grid_columnconfigure(1, weight=1)
        
        tk.Label(self.api_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.api_entry = tk.Entry(self.api_frame, show="*")
        self.api_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        self.api_entry.insert(0, self.api_key)
        
        self.save_api_btn = tk.Button(self.api_frame, text="保存API密钥", command=self.save_api_key)
        self.save_api_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # 2. 语音复刻区域
        self.voice_clone_frame = tk.LabelFrame(self.main_frame, text="语音复刻设置", padx=5, pady=5)
        self.voice_clone_frame.grid(row=1, column=0, columnspan=4, sticky=tk.EW, pady=(0, 10))
        self.voice_clone_frame.grid_columnconfigure(1, weight=1)
        
        tk.Label(self.voice_clone_frame, text="音频文件URL:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.audio_url_entry = tk.Entry(self.voice_clone_frame)
        self.audio_url_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        self.audio_url_entry.insert(0, "https://your-audio-file-url")
        
        tk.Label(self.voice_clone_frame, text="前缀:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.prefix_entry = tk.Entry(self.voice_clone_frame, width=20)
        self.prefix_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.prefix_entry.insert(0, "myvoice")
        
        tk.Label(self.voice_clone_frame, text="当前Voice ID:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.voice_id_entry = tk.Entry(self.voice_clone_frame)
        self.voice_id_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, pady=5, padx=5)
        self.voice_id_entry.insert(0, self.voice_id)
        
        self.reuse_voice_var = tk.BooleanVar(value=True if self.voice_id else False)
        self.reuse_checkbox = tk.Checkbutton(
            self.voice_clone_frame, 
            text="复用现有Voice ID（避免重复创建）", 
            variable=self.reuse_voice_var
        )
        self.reuse_checkbox.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        
        self.create_voice_btn = tk.Button(
            self.voice_clone_frame, 
            text="创建/更新语音", 
            command=self.start_create_voice_thread
        )
        self.create_voice_btn.grid(row=3, column=2, padx=5, pady=5)
        
        # 3. 文本输入区域
        self.text_frame = tk.LabelFrame(self.main_frame, text="合成文本", padx=5, pady=5)
        self.text_frame.grid(row=4, column=0, columnspan=4, sticky=tk.NSEW, pady=(0, 10))
        self.text_frame.grid_rowconfigure(0, weight=1)
        self.text_frame.grid_columnconfigure(0, weight=1)
        
        self.text_input = scrolledtext.ScrolledText(self.text_frame, wrap=tk.WORD)
        self.text_input.grid(row=0, column=0, sticky=tk.NSEW, pady=5, padx=5)
        self.text_input.insert(tk.END, "今天天气怎么样？")
        
        # 4. 输出设置和操作区域
        self.output_frame = tk.LabelFrame(self.main_frame, text="操作与输出", padx=5, pady=5)
        self.output_frame.grid(row=5, column=0, columnspan=4, sticky=tk.EW, pady=(0, 10))
        self.output_frame.grid_columnconfigure(1, weight=1)
        
        tk.Label(self.output_frame, text="保存文件夹:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.output_dir_entry = tk.Entry(self.output_frame)
        self.output_dir_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        self.output_dir_entry.insert(0, os.getcwd())  # 默认使用当前工作目录
        
        self.browse_btn = tk.Button(self.output_frame, text="浏览文件夹...", command=self.browse_output_dir)
        self.browse_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # 操作按钮框架
        self.btn_frame = tk.Frame(self.output_frame)
        self.btn_frame.grid(row=0, column=3, padx=5, pady=5)
        
        self.synthesize_btn = tk.Button(
            self.btn_frame, 
            text="合成语音", 
            command=self.start_synthesize_thread,
            width=12,
            bg="#4CAF50",
            fg="white"
        )
        self.synthesize_btn.pack(side=tk.LEFT, padx=5)
        
        self.play_btn = tk.Button(
            self.btn_frame, 
            text="试听语音", 
            command=self.play_audio,
            width=12,
            state=tk.DISABLED  # 初始禁用，合成后启用
        )
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = tk.Button(
            self.btn_frame, 
            text="保存语音", 
            command=self.save_audio,
            width=12,
            state=tk.DISABLED  # 初始禁用，合成后启用
        )
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        # 5. 日志区域
        self.log_frame = tk.LabelFrame(self.main_frame, text="操作日志", padx=5, pady=5)
        self.log_frame.grid(row=6, column=0, columnspan=4, sticky=tk.NSEW, pady=(0, 10))
        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky=tk.NSEW, pady=5, padx=5)
        
        # 添加清空日志按钮
        self.clear_log_btn = tk.Button(self.log_frame, text="清空日志", command=self.clear_log)
        self.clear_log_btn.grid(row=1, column=0, sticky=tk.E, pady=(0, 5), padx=5)
        
        # 初始日志
        self.log_message("应用已启动")
        if self.voice_id:
            self.log_message(f"已加载保存的Voice ID: {self.voice_id}")
    
    def on_resize(self, event):
        """窗口大小变化时调整组件"""
        # 这里可以根据需要添加更复杂的布局调整逻辑
        pass
    
    def save_api_key(self):
        """保存API密钥"""
        self.api_key = self.api_entry.get().strip()
        if self.api_key:
            self.save_config()
            messagebox.showinfo("成功", "API密钥已保存")
        else:
            messagebox.showwarning("警告", "API密钥不能为空")
    
    def browse_output_dir(self):
        """浏览输出文件夹"""
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, directory)
    
    def log_message(self, message):
        """在日志区域显示消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_message("日志已清空")
    
    def start_create_voice_thread(self):
        """启动创建语音的线程"""
        threading.Thread(target=self.create_voice, daemon=True).start()
    
    def create_voice(self):
        """创建语音复刻"""
        self.log_message("开始创建语音复刻...")
        
        # 检查API密钥
        self.api_key = self.api_entry.get().strip()
        if not self.api_key:
            messagebox.showerror("错误", "请先设置API密钥")
            self.log_message("创建失败：未设置API密钥")
            return
        
        # 检查是否复用现有voice_id
        if self.reuse_voice_var.get() and self.voice_id:
            self.log_message(f"复用现有Voice ID: {self.voice_id}")
            messagebox.showinfo("信息", f"已复用现有Voice ID: {self.voice_id}")
            return
        
        # 获取参数
        url = self.audio_url_entry.get().strip()
        prefix = self.prefix_entry.get().strip()
        target_model = "cosyvoice-v2"
        
        if not url or url == "https://your-audio-file-url":
            messagebox.showerror("错误", "请输入有效的音频文件URL")
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
            
            # 调用create_voice方法复刻声音，并生成voice_id
            self.log_message("正在创建语音，请稍候...")
            self.voice_id = service.create_voice(
                target_model=target_model, 
                prefix=prefix, 
                url=url
            )
            
            # 更新界面
            self.root.after(0, lambda: self.voice_id_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.voice_id_entry.insert(0, self.voice_id))
            
            # 保存配置
            self.save_config()
            
            self.log_message(f"语音创建成功，Voice ID: {self.voice_id}")
            self.log_message(f"Request ID: {service.get_last_request_id()}")
            messagebox.showinfo("成功", f"语音创建成功，Voice ID: {self.voice_id}")
            
        except Exception as e:
            error_msg = f"创建语音失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def start_synthesize_thread(self):
        """启动语音合成的线程"""
        threading.Thread(target=self.synthesize_speech, daemon=True).start()
    
    def synthesize_speech(self):
        """合成语音"""
        self.log_message("开始语音合成...")
        
        # 检查API密钥
        self.api_key = self.api_entry.get().strip()
        if not self.api_key:
            messagebox.showerror("错误", "请先设置API密钥")
            self.log_message("合成失败：未设置API密钥")
            return
        
        # 检查voice_id
        current_voice_id = self.voice_id_entry.get().strip()
        if not current_voice_id:
            messagebox.showerror("错误", "请先创建语音复刻获取Voice ID")
            self.log_message("合成失败：未获取Voice ID")
            return
        
        # 检查文本
        text = self.text_input.get(1.0, tk.END).strip()
        if not text:
            messagebox.showerror("错误", "请输入要合成的文本")
            self.log_message("合成失败：未输入文本")
            return
        
        try:
            # 设置API密钥
            dashscope.api_key = self.api_key
            
            # 使用复刻的声音进行语音合成
            self.log_message("正在合成语音，请稍候...")
            synthesizer = SpeechSynthesizer(
                model="cosyvoice-v2", 
                voice=current_voice_id
            )
            self.audio_data = synthesizer.call(text)
            
            # 保存到临时文件，用于试听
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
            self.log_message("可以点击'试听语音'按钮播放，或'保存语音'按钮保存到文件")
            
        except Exception as e:
            error_msg = f"语音合成失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def play_audio(self):
        """播放合成的语音"""
        if not self.temp_audio_file or not os.path.exists(self.temp_audio_file):
            messagebox.showerror("错误", "没有可播放的音频文件，请先合成语音")
            return
        
        try:
            self.log_message("开始播放音频...")
            
            # 根据操作系统选择合适的播放器
            system = platform.system()
            if system == 'Windows':
                os.startfile(self.temp_audio_file)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', self.temp_audio_file])
            elif system == 'Linux':  # Linux
                subprocess.run(['xdg-open', self.temp_audio_file])
            else:
                raise Exception(f"不支持的操作系统: {system}")
                
            self.log_message("音频播放已启动")
            
        except Exception as e:
            error_msg = f"播放音频失败: {str(e)}"
            self.log_message(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def save_audio(self):
        """保存合成的语音到指定文件夹，文件名自动生成"""
        if not self.audio_data:
            messagebox.showerror("错误", "没有可保存的音频文件，请先合成语音")
            return
        
        # 获取用户指定的保存文件夹
        output_dir = self.output_dir_entry.get().strip()
        if not output_dir:
            # 如果未指定文件夹，使用浏览对话框
            output_dir = filedialog.askdirectory()
            if not output_dir:  # 用户取消选择
                return
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, output_dir)
        
        try:
            # 生成唯一文件名（基于时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"voice_synthesis_{timestamp}.mp3"
            output_path = os.path.join(output_dir, filename)
            
            # 保存音频数据
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
    