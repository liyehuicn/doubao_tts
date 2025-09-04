import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import time
import json
import threading
import os
import sys
import uuid
import base64
import pygame
import re
from io import BytesIO
from cryptography.fernet import Fernet  # 需要安装cryptography库

class VolcanoTTS:
    def __init__(self, root):
        self.root = root
        self.root.title("火山引擎语音合成（双模式版）")
        self.root.geometry("850x800")  # 增加高度以容纳新控件
        self.root.resizable(False, False)  
        
        # 创建加密密钥
        self._create_crypto_key()
        
        # 创建主容器，用于更好地管理布局
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # 配置参数
        self.config = self._load_config()
        self.default_api_key = self.config.get("api_key", "")
        self.voice_id = self.config.get("voice_id", "")
        self.default_speed = self.config.get("speed", 1.0)  # 默认语速
        
        # 音频相关变量
        self.base64_audio = None
        self.raw_response = ""
        self.audio_data = None  # 单段音频数据
        self.audio_segments = []  # 字幕模式的多段音频
        self.is_playing = False
        self.current_segment = 0
        self.raw_responses = []  # 存储所有API响应
        self.playback_start_time = 0  # 播放开始的系统时间（毫秒）
        
        # 初始化音频播放器
        pygame.mixer.init()
        
        # 初始化界面
        self._init_ui()
    
    def _create_crypto_key(self):
        """创建加密密钥，用于加密敏感信息"""
        key_path = "crypto.key"
        if not os.path.exists(key_path):
            try:
                key = Fernet.generate_key()
                with open(key_path, "wb") as f:
                    f.write(key)
                # 限制密钥文件权限
                os.chmod(key_path, 0o600)
            except Exception as e:
                self._log(f"创建加密密钥失败: {str(e)}")
                raise
        
        try:
            with open(key_path, "rb") as f:
                self.cipher_suite = Fernet(f.read())
        except Exception as e:
            self._log(f"加载加密密钥失败: {str(e)}")
            raise
    
    def _encrypt_data(self, data):
        """加密数据"""
        if not data:
            return ""
        return self.cipher_suite.encrypt(data.encode()).decode()
    
    def _decrypt_data(self, data):
        """解密数据"""
        if not data:
            return ""
        try:
            return self.cipher_suite.decrypt(data.encode()).decode()
        except:
            return ""  # 解密失败返回空
    
    def _load_config(self):
        """加载外部配置文件（加密存储敏感信息）"""
        config_path = "config.json"
        default_config = {
            "api_key": "",
            "voice_id": "",
            "speed": 1.0  # 新增语速配置
        }
        
        # 如果配置文件不存在则创建
        if not os.path.exists(config_path):
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                # 限制配置文件权限
                os.chmod(config_path, 0o600)
                return default_config
            except Exception as e:
                self._log(f"创建配置文件失败: {str(e)}")
                return default_config
        
        # 读取配置文件
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # 解密配置信息
            return {
                "api_key": self._decrypt_data(config.get("api_key", "")),
                "voice_id": self._decrypt_data(config.get("voice_id", "")),
                "speed": float(config.get("speed", 1.0))  # 新增语速配置
            }
        except Exception as e:
            self._log(f"读取配置文件失败: {str(e)}")
            return default_config
    
    def _save_config(self):
        """保存配置到外部文件（加密存储敏感信息）"""
        config_path = "config.json"
        try:
            # 获取当前语速值
            current_speed = self.speed_scale.get()
            
            # 加密配置信息后保存
            encrypted_config = {
                "api_key": self._encrypt_data(self.api_key_entry.get().strip()),
                "voice_id": self._encrypt_data(self.voice_id_entry.get().strip()),
                "speed": current_speed  # 新增保存语速配置
            }
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(encrypted_config, f, ensure_ascii=False, indent=2)
            # 限制配置文件权限
            os.chmod(config_path, 0o600)
            self._log("配置已加密保存到config.json")
        except Exception as e:
            self._log(f"保存配置文件失败: {str(e)}")
    
    def _init_ui(self):
        # 1. API配置区域
        api_frame = ttk.LabelFrame(self.main_container, text="1. API 配置", padding=(15, 10))
        api_frame.pack(fill=tk.X, padx=20, pady=(15, 5))
        
        # 使用Frame包装API配置行
        api_row = ttk.Frame(api_frame)
        api_row.pack(fill=tk.X, pady=5)
        ttk.Label(api_row, text="api-key：").pack(side=tk.LEFT, padx=(0, 10))
        self.api_key_entry = ttk.Entry(api_row, width=50, show="*")  # 密码框显示方式
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.api_key_entry.insert(0, self.default_api_key)
        
        # 添加显示/隐藏密码按钮
        self.show_api_key = tk.BooleanVar(value=False)
        self.api_key_toggle = ttk.Checkbutton(
            api_row, 
            text="显示", 
            variable=self.show_api_key,
            command=self._toggle_api_key_visibility
        )
        self.api_key_toggle.pack(side=tk.LEFT, padx=(5, 10))
        
        # 2. 音色配置区域
        voice_frame = ttk.LabelFrame(self.main_container, text="2. 音色配置", padding=(15, 10))
        voice_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # 使用Frame包装音色配置行
        voice_row = ttk.Frame(voice_frame)
        voice_row.pack(fill=tk.X, pady=5)
        ttk.Label(voice_row, text="voice_type：").pack(side=tk.LEFT, padx=(0, 10))
        self.voice_id_entry = ttk.Entry(voice_row, width=50, show="*")  # 密码框显示方式
        self.voice_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.voice_id_entry.insert(0, self.voice_id)
        
        # 添加显示/隐藏按钮
        self.show_voice_id = tk.BooleanVar(value=False)
        self.voice_id_toggle = ttk.Checkbutton(
            voice_row, 
            text="显示", 
            variable=self.show_voice_id,
            command=self._toggle_voice_id_visibility
        )
        self.voice_id_toggle.pack(side=tk.LEFT, padx=(5, 10))
        
        config_btn = ttk.Button(voice_row, text="保存配置", command=self._save_config)
        config_btn.pack(side=tk.LEFT)
        
        # 新增：语速调节区域
        speed_frame = ttk.LabelFrame(self.main_container, text="3. 语速调节", padding=(15, 10))
        speed_frame.pack(fill=tk.X, padx=20, pady=5)
        
        speed_row = ttk.Frame(speed_frame)
        speed_row.pack(fill=tk.X, pady=5)
        ttk.Label(speed_row, text="语速：").pack(side=tk.LEFT, padx=(0, 10))
        
        # 语速滑块，范围0.5-1.5倍，步长0.1
        self.speed_scale = ttk.Scale(
            speed_row, 
            from_=0.5, 
            to=1.6, 
            orient="horizontal", 
            length=300,
            value=self.default_speed,
            command=self._update_speed_label
        )
        self.speed_scale.pack(side=tk.LEFT, padx=(0, 10))
        
        # 显示当前语速
        self.speed_label = ttk.Label(speed_row, text=f"{self.default_speed:.1f}x")
        self.speed_label.pack(side=tk.LEFT)
        
        # 3. 配音模式选择（原3改为4）
        mode_frame = ttk.LabelFrame(self.main_container, text="4. 配音模式", padding=(15, 10))
        mode_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # 使用Frame包装模式选择
        mode_row = ttk.Frame(mode_frame)
        mode_row.pack(fill=tk.X)
        self.mode_var = tk.StringVar(value="text")
        ttk.Radiobutton(mode_row, text="文本直接配音", variable=self.mode_var, value="text", 
                       command=self._switch_mode).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_row, text="字幕文件配音", variable=self.mode_var, value="subtitle",
                       command=self._switch_mode).pack(side=tk.LEFT, padx=10)
        
        # 内容区域容器（用于在切换模式时保持布局稳定性）
        self.content_container = ttk.Frame(self.main_container)
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        # 4. 文本输入区域（文本模式，原4改为5）
        self.text_frame = ttk.LabelFrame(self.content_container, text="5. 合成文本", padding=(15, 10))
        self.text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_input = tk.Text(self.text_frame, height=6, width=75)
        self.text_input.pack(fill=tk.BOTH, expand=True)
        self.text_input.insert(tk.END, "你是否也曾这样，心里很想和某个人聊天，却希望他先来找你，呆呆的看着他的头像一遍又一遍。")
        
        # 5. 字幕文件区域（字幕模式，默认隐藏，原5改为6）
        self.subtitle_frame = ttk.LabelFrame(self.content_container, text="5. 字幕文件", padding=(15, 10))
        # 默认不显示，通过模式切换显示
        
        # 使用Frame包装字幕文件选择行
        subtitle_row = ttk.Frame(self.subtitle_frame)
        subtitle_row.pack(fill=tk.X, pady=5)
        self.subtitle_path = tk.StringVar()
        ttk.Entry(subtitle_row, textvariable=self.subtitle_path, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(subtitle_row, text="选择SRT文件", command=self._select_subtitle).pack(side=tk.LEFT)
        
        # 字幕内容预览
        self.subtitle_preview = tk.Text(self.subtitle_frame, height=6, width=75)
        self.subtitle_preview.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 6. 按钮区域（原6改为7）
        btn_frame = ttk.Frame(self.main_container, padding=(15, 10))
        btn_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.gen_btn = ttk.Button(btn_frame, text="生成语音", command=self._start_generate)
        self.gen_btn.pack(side="left", padx=10)
        
        self.play_btn = ttk.Button(btn_frame, text="播放语音", command=self._play_audio, state="disabled")
        self.play_btn.pack(side="left", padx=10)
        
        self.stop_btn = ttk.Button(btn_frame, text="停止播放", command=self._stop_audio, state="disabled")
        self.stop_btn.pack(side="left", padx=10)
        
        self.save_btn = ttk.Button(btn_frame, text="保存音频", command=self._save_audio, state="disabled")
        self.save_btn.pack(side="left", padx=10)
        
        self.show_log_btn = ttk.Button(btn_frame, text="查看响应", command=self._show_raw, state="disabled")
        self.show_log_btn.pack(side="left", padx=10)
        
        # 7. 进度条（原7改为8）
        self.progress = ttk.Progressbar(self.main_container, orient="horizontal", length=100, mode="determinate")
        self.progress.pack(fill=tk.X, padx=20, pady=5)
        
        # 8. 操作日志区域（固定在最底部，原8改为9）
        log_frame = ttk.LabelFrame(root, text="9. 操作日志", padding=(15, 10))
        # 使用root作为父容器而不是main_container，确保它在最底部
        log_frame.pack(fill=tk.BOTH, expand=False, padx=20, pady=(5, 15), side=tk.BOTTOM)
        
        self.log_text = tk.Text(log_frame, height=6, state="disabled", font=("SimHei", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def _update_speed_label(self, value):
        """更新语速显示标签"""
        speed = round(float(value), 1)
        self.speed_label.config(text=f"{speed}x")
    
    def _toggle_api_key_visibility(self):
        """切换API Key显示/隐藏状态"""
        if self.show_api_key.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")
    
    def _toggle_voice_id_visibility(self):
        """切换Voice ID显示/隐藏状态"""
        if self.show_voice_id.get():
            self.voice_id_entry.config(show="")
        else:
            self.voice_id_entry.config(show="*")
    
    def _switch_mode(self):
        """切换配音模式"""
        mode = self.mode_var.get()
        if mode == "text":
            self.subtitle_frame.pack_forget()
            self.text_frame.pack(fill=tk.BOTH, expand=True)
            self._log("已切换到文本直接配音模式")
        else:
            self.text_frame.pack_forget()
            self.subtitle_frame.pack(fill=tk.BOTH, expand=True)
            self._log("已切换到字幕文件配音模式")
    
    def _select_subtitle(self):
        """选择SRT字幕文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("SRT字幕文件", "*.srt")],
            title="选择字幕文件"
        )
        if file_path:
            self.subtitle_path.set(file_path)
            self._load_subtitle(file_path)
    
    def _load_subtitle(self, file_path):
        """加载并解析SRT字幕文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 显示字幕内容
            self.subtitle_preview.delete(1.0, tk.END)
            self.subtitle_preview.insert(tk.END, content)
            
            # 解析字幕
            self.subtitles = self._parse_srt(content)
            if self.subtitles:
                self._log(f"成功加载字幕文件，共{len(self.subtitles)}条字幕")
            else:
                self._log("警告：未解析到有效字幕内容")
                
        except Exception as e:
            self._log(f"加载字幕失败：{str(e)}")
    
    def _parse_srt(self, content):
        """解析SRT格式字幕"""
        # SRT格式正则表达式
        pattern = re.compile(
            r'(\d+)\r?\n'
            r'(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)\r?\n'
            r'(.*?)\r?\n\r?\n',
            re.DOTALL
        )
        
        subtitles = []
        for match in pattern.finditer(content):
            index = match.group(1)
            start_time = self._time_to_ms(match.group(2))
            end_time = self._time_to_ms(match.group(3))
            text = match.group(4).strip()
            
            # 计算字幕时长(毫秒)
            duration = end_time - start_time
            subtitles.append({
                'index': index,
                'start': start_time,
                'end': end_time,
                'duration': duration,
                'text': text
            })
        
        return subtitles
    
    def _time_to_ms(self, time_str):
        """将SRT时间格式转换为毫秒"""
        # 处理逗号为点，统一格式
        time_str = time_str.replace(',', '.')
        h, m, s = time_str.split(':')
        s, ms = s.split('.')
        
        # 转换为总毫秒数
        total_ms = (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)
        return total_ms
    
    def _log(self, msg):
        """安全更新日志"""
        def _update():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(0, _update)
    
    def _show_raw(self):
        """显示API响应"""
        if not self.raw_responses and not self.raw_response:
            messagebox.showinfo("提示", "暂无响应数据")
            return
        
        win = tk.Toplevel(self.root)
        win.title("API原始响应")
        win.geometry("600x400")
        
        text = tk.Text(win, wrap=tk.WORD, font=("SimHei", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        if self.mode_var.get() == "text":
            text.insert(tk.END, self.raw_response[:2000] + "...")
        else:
            text.insert(tk.END, "\n\n".join(self.raw_responses))
    
    def _start_generate(self):
        """开始生成语音（根据模式选择不同处理）"""
        self.api_key = self.api_key_entry.get().strip()
        self.voice_id = self.voice_id_entry.get().strip()
        
        if not self.api_key:
            messagebox.showerror("错误", "请输入x-api-key！")
            return
        
        # 获取语速值（限制在0.5-1.5之间）
        self.speed_ratio = max(0.5, min(1.5, round(float(self.speed_scale.get()), 1)))
        
        # 停止可能的播放
        self._stop_audio()
        
        # 禁用按钮防止重复操作
        self.gen_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.play_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.show_log_btn.config(state="disabled")
        self.progress["value"] = 0
        
        # 根据模式处理
        mode = self.mode_var.get()
        if mode == "text":
            text = self.text_input.get("1.0", tk.END).strip()
            if not text:
                messagebox.showerror("错误", "请输入合成文本！")
                self.gen_btn.config(state="normal")
                return
            
            self._log(f"开始生成文本语音（语速：{self.speed_ratio}x）...")
            threading.Thread(
                target=self._generate_text_audio,
                args=(self.api_key, self.voice_id, text),
                daemon=True
            ).start()
        else:
            if not hasattr(self, 'subtitles') or not self.subtitles:
                messagebox.showerror("错误", "请先加载有效的字幕文件！")
                self.gen_btn.config(state="normal")
                return
            
            self._log(f"开始生成{len(self.subtitles)}条字幕配音（语速：{self.speed_ratio}x）...")
            self.progress["maximum"] = len(self.subtitles)
            self.raw_responses = []  # 重置响应列表
            threading.Thread(
                target=self._generate_subtitle_audio,
                args=(self.api_key, self.voice_id),
                daemon=True
            ).start()
    
    def _generate_text_audio(self, api_key, voice_id, text):
        """生成文本直接配音"""
        try:
            req_data = {
                "app": {"cluster": "volcano_icl"},
                "user": {"uid": "豆包语音"},
                "audio": {
                    "voice_type": voice_id,
                    "encoding": "mp3",
                    "speed_ratio": self.speed_ratio  # 使用选择的语速
                },
                "request": {
                    "reqid": str(uuid.uuid4()).replace("-", ""),
                    "text": text,
                    "operation": "query"
                }
            }
            
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            self._log(f"请求参数：{json.dumps(req_data, ensure_ascii=False)[:150]}...")
            
            # 发送请求
            response = requests.post(
                url="https://openspeech.bytedance.com/api/v1/tts",
                headers=headers,
                json=req_data,
                timeout=30
            )
            
            self.raw_response = response.text
            self.root.after(0, lambda: self.show_log_btn.config(state="normal"))
            
            self._log(f"API响应：状态码{response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    self._log("错误：API返回数据不是有效的JSON格式")
                    return
                    
                if result.get("code") == 3000 and result.get("message") == "Success":
                    self.base64_audio = result.get("data")
                    if self.base64_audio:
                        # 解码音频数据用于播放
                        try:
                            self.audio_data = base64.b64decode(self.base64_audio)
                            self._log(f"成功提取Base64音频！长度：{len(self.base64_audio)//1024}KB")
                            self.root.after(0, lambda: self.save_btn.config(state="normal"))
                            self.root.after(0, lambda: self.play_btn.config(state="normal"))
                        except base64.binascii.Error:
                            self._log("错误：Base64解码失败，音频数据格式错误")
                    else:
                        self._log("错误：response.data为空，无音频数据")
                else:
                    self._log(f"业务失败：code={result.get('code')}，message={result.get('message')}")
            else:
                self._log(f"API请求失败：状态码{response.status_code}")
        except Exception as e:
            self._log(f"生成语音失败：{str(e)}")
        finally:
            self.root.after(0, lambda: self.gen_btn.config(state="normal"))
    
    def _generate_subtitle_audio(self, api_key, voice_id):
        """生成字幕文件配音"""
        try:
            self.audio_segments = []  # 重置音频段列表
            
            for i, subtitle in enumerate(self.subtitles):
                # 更新进度条
                self.root.after(0, lambda val=i+1: self.progress.config(value=val))
                
                text = subtitle['text']
                if not text:
                    self._log(f"跳过空字幕 #{subtitle['index']}")
                    continue
                    
                self._log(f"正在处理字幕 #{subtitle['index']}: {text[:30]}...")
                
                req_data = {
                    "app": {"cluster": "volcano_icl"},
                    "user": {"uid": "豆包语音"},
                    "audio": {
                        "voice_type": voice_id,
                        "encoding": "mp3",
                        "speed_ratio": self.speed_ratio  # 使用选择的语速
                    },
                    "request": {
                        "reqid": str(uuid.uuid4()).replace("-", ""),
                        "text": text,
                        "operation": "query"
                    }
                }
                
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json"
                }
                
                try:
                    response = requests.post(
                        url="https://openspeech.bytedance.com/api/v1/tts",
                        headers=headers,
                        json=req_data,
                        timeout=30
                    )
                    
                    self.raw_responses.append(f"字幕 #{subtitle['index']} 响应:\n{response.text}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("code") == 3000 and result.get("message") == "Success":
                            base64_audio = result.get("data")
                            if base64_audio:
                                audio_data = base64.b64decode(base64_audio)
                                self.audio_segments.append({
                                    'data': audio_data,
                                    'subtitle': subtitle
                                })
                                self._log(f"成功生成字幕 #{subtitle['index']} 音频")
                            else:
                                self._log(f"字幕 #{subtitle['index']} 无音频数据")
                        else:
                            self._log(f"字幕 #{subtitle['index']} 业务失败: {result.get('message')}")
                    else:
                        self._log(f"字幕 #{subtitle['index']} 请求失败: 状态码{response.status_code}")
                        
                except Exception as e:
                    self._log(f"处理字幕 #{subtitle['index']} 出错: {str(e)}")
                
                # 避免请求过于频繁
                time.sleep(0.5)
            
            self._log(f"字幕配音生成完成，共成功生成 {len(self.audio_segments)}/{len(self.subtitles)} 段音频")
            self.root.after(0, lambda: self.show_log_btn.config(state="normal"))
            if self.audio_segments:
                self.root.after(0, lambda: self.play_btn.config(state="normal"))
                self.root.after(0, lambda: self.save_btn.config(state="normal"))
                
        except Exception as e:
            self._log(f"生成字幕配音失败：{str(e)}")
        finally:
            self.root.after(0, lambda: self.gen_btn.config(state="normal"))
    
    def _play_audio(self):
        """播放音频（根据模式选择不同播放方式）"""
        if self.mode_var.get() == "text":
            self._play_text_audio()
        else:
            self._play_subtitle_audio()
    
    def _play_text_audio(self):
        """播放文本生成的音频"""
        if not self.audio_data:
            messagebox.showinfo("提示", "没有可播放的音频数据")
            return
            
        try:
            # 停止当前播放
            pygame.mixer.stop()
            
            # 加载音频数据
            sound = pygame.mixer.Sound(BytesIO(self.audio_data))
            sound.play()
            
            # 更新状态
            self.is_playing = True
            self.play_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self._log("开始播放音频...")
            
            # 检查播放状态的定时器
            self._check_playback_status()
            
        except Exception as e:
            self._log(f"播放失败：{str(e)}")
            self.is_playing = False
    
    def _play_subtitle_audio(self):
        """播放字幕生成的分段音频"""
        if not self.audio_segments:
            messagebox.showinfo("提示", "没有可播放的音频段")
            return
            
        try:
            # 停止当前播放
            pygame.mixer.stop()
            
            self.current_segment = 0
            self.is_playing = True
            self.play_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.playback_start_time = time.time() * 1000  # 记录开始时间（毫秒）
            
            self._log("开始播放字幕音频...")
            self._play_next_segment()
            
        except Exception as e:
            self._log(f"播放失败：{str(e)}")
            self.is_playing = False
    
    def _play_next_segment(self):
        """播放下一段音频"""
        if not self.is_playing or self.current_segment >= len(self.audio_segments):
            self._stop_audio()
            self._log("字幕音频播放完成")
            return
            
        # 获取当前段
        segment = self.audio_segments[self.current_segment]
        subtitle = segment['subtitle']
        
        # 计算需要等待的时间（根据字幕时间戳）
        current_time = time.time() * 1000 - self.playback_start_time
        wait_time = max(0, subtitle['start'] - current_time)
        
        self._log(f"准备播放第 {self.current_segment + 1} 段字幕（等待 {wait_time:.0f}ms）")
        
        # 延迟播放当前段
        self.root.after(int(wait_time), self._play_current_segment)
    
    def _play_current_segment(self):
        """播放当前段音频"""
        if not self.is_playing:
            return
            
        segment = self.audio_segments[self.current_segment]
        subtitle = segment['subtitle']
        
        try:
            # 加载并播放音频
            sound = pygame.mixer.Sound(BytesIO(segment['data']))
            sound.play()
            self._log(f"正在播放第 {self.current_segment + 1} 段: {subtitle['text'][:30]}...")
            
            # 计算当前段播放时长（毫秒）
            play_length = int(len(segment['data']) / 3.5)  # 粗略估算，实际应根据音频本身计算
            
            # 准备播放下一段
            self.current_segment += 1
            self.root.after(play_length, self._play_next_segment)
            
        except Exception as e:
            self._log(f"播放第 {self.current_segment + 1} 段失败：{str(e)}")
            self.current_segment += 1
            self.root.after(100, self._play_next_segment)
    
    def _check_playback_status(self):
        """检查音频播放状态"""
        if not self.is_playing:
            return
            
        if not pygame.mixer.get_busy():
            self._log("音频播放完成")
            self.is_playing = False
            self.root.after(0, lambda: self.play_btn.config(state="normal"))
            self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
            return
            
        # 继续检查
        self.root.after(100, self._check_playback_status)
    
    def _stop_audio(self):
        """停止音频播放"""
        pygame.mixer.stop()
        self.is_playing = False
        self.root.after(0, lambda: self.play_btn.config(state="normal"))
        self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
        self._log("已停止播放")
    
    def _save_audio(self):
        """保存音频到文件"""
        if self.mode_var.get() == "text" and self.audio_data:
            self._save_text_audio()
        elif self.mode_var.get() == "subtitle" and self.audio_segments:
            self._save_subtitle_audio()
        else:
            messagebox.showinfo("提示", "没有可保存的音频数据")
    
    def _save_text_audio(self):
        """保存文本生成的音频"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3文件", "*.mp3"), ("所有文件", "*.*")],
            title="保存音频文件"
        )
        
        if file_path:
            try:
                with open(file_path, "wb") as f:
                    f.write(self.audio_data)
                self._log(f"音频已保存到：{file_path}")
                messagebox.showinfo("成功", f"音频已保存到：{file_path}")
            except Exception as e:
                self._log(f"保存音频失败：{str(e)}")
                messagebox.showerror("错误", f"保存音频失败：{str(e)}")
    
    def _save_subtitle_audio(self):
        """保存字幕生成的音频（合并为一个文件）"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3文件", "*.mp3"), ("所有文件", "*.*")],
            title="保存音频文件"
        )
        
        if file_path:
            try:
                # 简单合并（实际应用中可能需要更复杂的处理来保证间隙正确）
                with open(file_path, "wb") as f:
                    for segment in self.audio_segments:
                        f.write(segment['data'])
                
                self._log(f"合并音频已保存到：{file_path}")
                messagebox.showinfo("成功", f"合并音频已保存到：{file_path}")
            except Exception as e:
                self._log(f"保存音频失败：{str(e)}")
                messagebox.showerror("错误", f"保存音频失败：{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VolcanoTTS(root)
    root.mainloop()
