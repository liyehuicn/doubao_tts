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
        self.root.geometry("850x750")
        self.root.resizable(False, False)  
        
        # 创建加密密钥
        self._create_crypto_key()
        
        # 创建主容器，用于更好地管理布局
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # 配置参数
        self.config = self._load_config()
        self.default_api_key = self.config.get("api_key", "11111")
        self.voice_id = self.config.get("voice_id", "22222")
        
        # 音频相关变量
        self.base64_audio = None
        self.raw_response = ""
        self.audio_data = None  # 单段音频数据
        self.audio_segments = []  # 字幕模式的多段音频
        self.is_playing = False
        self.current_segment = 0
        self.raw_responses = []  # 存储所有API响应
        
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
            "voice_id": ""
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
                "voice_id": self._decrypt_data(config.get("voice_id", ""))
            }
        except Exception as e:
            self._log(f"读取配置文件失败: {str(e)}")
            return default_config
    
    def _save_config(self):
        """保存配置到外部文件（加密存储敏感信息）"""
        config_path = "config.json"
        try:
            # 加密配置信息后保存
            encrypted_config = {
                "api_key": self._encrypt_data(self.api_key_entry.get().strip()),
                "voice_id": self._encrypt_data(self.voice_id_entry.get().strip())
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
        
        # 以下为其他原有代码，保持不变...
        # 3. 配音模式选择
        mode_frame = ttk.LabelFrame(self.main_container, text="3. 配音模式", padding=(15, 10))
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
        
        # 4. 文本输入区域（文本模式）
        self.text_frame = ttk.LabelFrame(self.content_container, text="4. 合成文本", padding=(15, 10))
        self.text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_input = tk.Text(self.text_frame, height=6, width=75)
        self.text_input.pack(fill=tk.BOTH, expand=True)
        self.text_input.insert(tk.END, "你是否也曾这样，心里很想和某个人聊天，却希望他先来找你，呆呆的看着他的头像一遍又一遍。")
        
        # 5. 字幕文件区域（字幕模式，默认隐藏）
        self.subtitle_frame = ttk.LabelFrame(self.content_container, text="4. 字幕文件", padding=(15, 10))
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
        
        # 6. 按钮区域
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
        
        # 7. 进度条
        self.progress = ttk.Progressbar(self.main_container, orient="horizontal", length=100, mode="determinate")
        self.progress.pack(fill=tk.X, padx=20, pady=5)
        
        # 8. 操作日志区域（固定在最底部）
        log_frame = ttk.LabelFrame(root, text="5. 操作日志", padding=(15, 10))
        # 使用root作为父容器而不是main_container，确保它在最底部
        log_frame.pack(fill=tk.BOTH, expand=False, padx=20, pady=(5, 15), side=tk.BOTTOM)
        
        self.log_text = tk.Text(log_frame, height=6, state="disabled", font=("SimHei", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
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
    
    # 以下为其他原有方法，保持不变...
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
            
            self._log("开始生成文本语音...")
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
            
            self._log(f"开始生成{len(self.subtitles)}条字幕配音...")
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
                    "speed_ratio": 1.0
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
                self._log(f"HTTP失败：状态码{response.status_code}")
        
        except requests.exceptions.RequestException as e:
            self._log(f"网络请求错误：{str(e)}")
        except Exception as e:
            self._log(f"处理错误：{str(e)}")
        finally:
            self.root.after(0, lambda: self.gen_btn.config(state="normal"))
    
    def _generate_subtitle_audio(self, api_key, voice_id):
        """生成字幕配音"""
        try:
            self.audio_segments = []  # 重置音频片段
            
            for i, subtitle in enumerate(self.subtitles):
                # 计算需要的语速
                text_length = len(subtitle['text'])
                if text_length == 0:
                    self._log(f"跳过空字幕 {subtitle['index']}")
                    self.progress["value"] = i + 1
                    continue
                    
                # 字幕时长(秒)
                subtitle_duration = subtitle['duration'] / 1000
                # 预估正常语速下的语音时长(秒)
                estimated_duration = text_length * 0.3
                # 计算语速比例(最大不超过2.0，最小不低于0.5)
                speed_ratio = min(max(estimated_duration / subtitle_duration, 0.5), 2.0)
                
                self._log(
                    f"处理字幕 {subtitle['index']}: 文本长度{text_length}，"
                    f"字幕时长{subtitle_duration:.2f}s，预估语速{speed_ratio:.2f}x"
                )
                
                # 生成当前片段语音
                audio_data = self._generate_single_segment(
                    api_key, voice_id, subtitle['text'], speed_ratio
                )
                
                if audio_data:
                    self.audio_segments.append({
                        'start': subtitle['start'],
                        'end': subtitle['end'],
                        'audio': audio_data,
                        'text': subtitle['text']
                    })
                
                # 更新进度条
                self.root.after(0, lambda v=i+1: self.progress.configure(value=v))
            
            self._log(f"全部字幕处理完成，成功生成{len(self.audio_segments)}段语音")
            
            # 启用相关按钮
            self.root.after(0, lambda: self.play_btn.config(state="normal"))
            self.root.after(0, lambda: self.save_btn.config(state="normal"))
            self.root.after(0, lambda: self.show_log_btn.config(state="normal"))
            
        except Exception as e:
            self._log(f"批量生成错误：{str(e)}")
        finally:
            self.root.after(0, lambda: self.gen_btn.config(state="normal"))
    
    def _generate_single_segment(self, api_key, voice_id, text, speed_ratio):
        """生成单个字幕片段的语音"""
        try:
            req_data = {
                "app": {"cluster": "volcano_icl"},
                "user": {"uid": "豆包语音"},
                "audio": {
                    "voice_type": voice_id,
                    "encoding": "mp3",
                    "speed_ratio": speed_ratio  # 使用计算出的语速
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
            
            response = requests.post(
                url="https://openspeech.bytedance.com/api/v1/tts",
                headers=headers,
                json=req_data,
                timeout=30
            )
            
            self.raw_responses.append(f"字幕 {text[:10]}...: {response.text[:200]}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 3000 and result.get("message") == "Success":
                    base64_audio = result.get("data")
                    if base64_audio:
                        return base64.b64decode(base64_audio)
                    else:
                        self._log("错误：response.data为空")
                else:
                    self._log(f"业务失败：code={result.get('code')}，message={result.get('message')}")
            else:
                self._log(f"HTTP失败：状态码{response.status_code}")
                
        except Exception as e:
            self._log(f"生成单段语音错误：{str(e)}")
        return None
    
    def _play_audio(self):
        """根据模式播放音频"""
        mode = self.mode_var.get()
        if mode == "text":
            self._play_text_audio()
        else:
            self._play_subtitle_audio()
    
    def _play_text_audio(self):
        """播放文本直接生成的音频"""
        if not self.audio_data:
            messagebox.showerror("错误", "无音频数据，请先生成！")
            return
        
        # 停止当前播放（如果有的话）
        if self.is_playing:
            self._stop_audio()
        
        try:
            # 从内存数据创建音频流
            audio_stream = BytesIO(self.audio_data)
            pygame.mixer.music.load(audio_stream)
            pygame.mixer.music.play()
            
            self.is_playing = True
            self.play_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self._log("开始播放音频...")
            
            # 启动播放状态检查线程
            threading.Thread(target=self._check_play_status, daemon=True).start()
            
        except Exception as e:
            self._log(f"播放失败：{str(e)}")
            self.is_playing = False
            self.play_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
    
    def _play_subtitle_audio(self):
        """按顺序播放所有字幕音频片段"""
        if not self.audio_segments:
            messagebox.showerror("错误", "无音频数据，请先生成！")
            return
        
        # 停止当前播放
        if self.is_playing:
            self._stop_audio()
        
        self.is_playing = True
        self.current_segment = 0
        self.play_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._log("开始播放配音...")
        
        # 启动播放线程
        threading.Thread(target=self._play_segments, daemon=True).start()
    
    def _play_segments(self):
        """按顺序播放音频片段"""
        try:
            start_time = time.time() * 1000  # 开始播放的毫秒时间
            
            for i, segment in enumerate(self.audio_segments):
                if not self.is_playing:
                    break
                    
                self.current_segment = i
                self._log(f"播放片段 {i+1}/{len(self.audio_segments)}: {segment['text'][:20]}...")
                
                # 计算需要等待的时间（确保按字幕时间戳播放）
                current_time = time.time() * 1000
                elapsed = current_time - start_time
                wait_time = (segment['start'] - elapsed) / 1000  # 转换为秒
                
                if wait_time > 0:
                    time.sleep(wait_time)
                
                # 播放当前片段
                audio_stream = BytesIO(segment['audio'])
                pygame.mixer.music.load(audio_stream)
                pygame.mixer.music.play()
                
                # 等待播放完成
                while pygame.mixer.music.get_busy() and self.is_playing:
                    time.sleep(0.1)
            
            if self.is_playing:
                self._log("所有片段播放完成")
                
        except Exception as e:
            self._log(f"播放错误：{str(e)}")
        finally:
            self.is_playing = False
            self.root.after(0, lambda: self.play_btn.config(state="normal"))
            self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
    
    def _check_play_status(self):
        """检查播放状态，播放结束后更新按钮状态"""
        while self.is_playing:
            if not pygame.mixer.music.get_busy():
                self.is_playing = False
                self.root.after(0, lambda: self.play_btn.config(state="normal"))
                self.root.after(0, lambda: self.stop_btn.config(state="disabled"))
                self._log("音频播放结束")
                break
            time.sleep(0.5)
    
    def _stop_audio(self):
        """停止播放音频"""
        if self.is_playing:
            pygame.mixer.music.stop()
            self.is_playing = False
            self._log("已停止播放")
        
        self.play_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
    
    def _save_audio(self):
        """根据模式保存音频"""
        mode = self.mode_var.get()
        if mode == "text":
            self._save_text_audio()
        else:
            self._save_subtitle_audio()
    
    def _save_text_audio(self):
        """保存文本生成的音频"""
        if not self.base64_audio:
            messagebox.showerror("错误", "无音频数据，请先生成！")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3文件", "*.mp3")],
            title="保存合成语音"
        )
        if not save_path:
            return
        
        self._log(f"开始保存MP3到：{save_path}")
        self.save_btn.config(state="disabled")
        
        threading.Thread(
            target=self._save_text_thread,
            args=(save_path,),
            daemon=True
        ).start()
    
    def _save_text_thread(self, save_path):
        """保存文本音频的线程"""
        try:
            audio_bytes = base64.b64decode(self.base64_audio)
            
            with open(save_path, "wb") as f:
                f.write(audio_bytes)
            
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                file_size = os.path.getsize(save_path) / 1024
                self._log(f"保存成功！文件大小：{file_size:.1f}KB")
                self.root.after(0, lambda: messagebox.showinfo("成功", f"MP3已保存至：\n{save_path}"))
            else:
                self._log("错误：保存的文件为空或不存在")
        
        except base64.binascii.Error:
            self._log("错误：Base64解码失败，音频数据格式错误")
        except IOError as e:
            self._log(f"文件写入错误：{str(e)}")
        except Exception as e:
            self._log(f"保存错误：{str(e)}")
        finally:
            self.root.after(0, lambda: self.save_btn.config(state="normal"))
    
    def _save_subtitle_audio(self):
        """保存字幕生成的所有音频片段"""
        if not self.audio_segments:
            messagebox.showerror("错误", "无音频数据，请先生成！")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3文件", "*.mp3")],
            title="保存全部配音"
        )
        if not save_path:
            return
        
        self._log(f"开始保存音频到：{save_path}")
        self.save_btn.config(state="disabled")
        
        threading.Thread(
            target=self._save_subtitle_thread,
            args=(save_path,),
            daemon=True
        ).start()
    
    def _save_subtitle_thread(self, save_path):
        """保存字幕音频的线程"""
        try:
            # 拼接所有音频片段
            with open(save_path, "wb") as f:
                for segment in self.audio_segments:
                    f.write(segment['audio'])
            
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                file_size = os.path.getsize(save_path) / 1024
                self._log(f"保存成功！文件大小：{file_size:.1f}KB")
                self.root.after(0, lambda: messagebox.showinfo("成功", f"音频已保存至：\n{save_path}"))
            else:
                self._log("错误：保存的文件为空或不存在")
        
        except IOError as e:
            self._log(f"文件写入错误：{str(e)}")
        except Exception as e:
            self._log(f"保存错误：{str(e)}")
        finally:
            self.root.after(0, lambda: self.save_btn.config(state="normal"))


# 程序入口
if __name__ == "__main__":
    try:
        # 检查Python版本
        if sys.version_info < (3, 6):
            raise Exception("Python版本过低，需要Python 3.6及以上版本")
        
        # 检查并安装必要的库
        def install(package):
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            install("cryptography")
        
        # 启动GUI
        root = tk.Tk()
        # 确保中文显示正常
        root.option_add("*Font", ("SimHei", 10))
        app = VolcanoTTS(root)
        root.mainloop()
    
    except Exception as e:
        error_msg = f"启动失败：{str(e)}\n\n请检查：\n1. Python版本是否为3.6及以上\n2. 是否已安装必要库（运行：pip install requests pygame cryptography）\n3. 代码是否完整复制"
        print(error_msg, file=sys.stderr)
        # 尝试显示图形化错误提示
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            messagebox.showerror("启动错误", error_msg)
            root.destroy()
        except:
            pass
