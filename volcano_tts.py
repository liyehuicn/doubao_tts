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
import pygame  # 用于音频播放
from io import BytesIO  # 内存文件操作

class VolcanoTTS:
    def __init__(self, root):
        self.root = root
        self.root.title("火山引擎语音合成（语音克隆版）")
        self.root.geometry("650x600")
        self.root.resizable(False, False)  
        
        # 配置参数 - 从外部文件加载
        self.config = self._load_config()
        self.default_api_key = self.config.get("api_key", "11111")
        self.voice_id = self.config.get("voice_id", "22222")
        
        # 音频相关变量
        self.base64_audio = None
        self.raw_response = ""
        self.audio_data = None  # 二进制音频数据
        self.is_playing = False  # 播放状态标记
        
        # 初始化音频播放器
        pygame.mixer.init()
        
        # 初始化界面
        self._init_ui()
    
    def _load_config(self):
        """加载外部配置文件"""
        config_path = "config.json"
        default_config = {
            "api_key": "11111",
            "voice_id": "22222"
        }
        
        # 如果配置文件不存在则创建
        if not os.path.exists(config_path):
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                return default_config
            except Exception as e:
                self._log(f"创建配置文件失败: {str(e)}")
                return default_config
        
        # 读取配置文件
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self._log(f"读取配置文件失败: {str(e)}")
            return default_config
    
    def _save_config(self):
        """保存配置到外部文件"""
        config_path = "config.json"
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "api_key": self.api_key_entry.get().strip(),
                    "voice_id": self.voice_id_entry.get().strip()
                }, f, ensure_ascii=False, indent=2)
            self._log("配置已保存到config.json")
        except Exception as e:
            self._log(f"保存配置文件失败: {str(e)}")
    
    def _init_ui(self):
        # 1. API配置区域
        api_frame = ttk.LabelFrame(self.root, text="1. API 配置", padding=(15, 10))
        api_frame.pack(fill=tk.X, padx=20, pady=(15, 5))
        
        ttk.Label(api_frame, text="api-key：").grid(row=0, column=0, sticky="w", pady=5)
        self.api_key_entry = ttk.Entry(api_frame, width=50)
        self.api_key_entry.grid(row=0, column=1, pady=5)
        self.api_key_entry.insert(0, self.default_api_key)
        
        # 2. 音色配置区域
        voice_frame = ttk.LabelFrame(self.root, text="2. 音色配置", padding=(15, 10))
        voice_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(voice_frame, text="voice_type：").grid(row=0, column=0, sticky="w", pady=5)
        self.voice_id_entry = ttk.Entry(voice_frame, width=50)
        self.voice_id_entry.grid(row=0, column=1, pady=5)
        self.voice_id_entry.insert(0, self.voice_id)
        
        # 保存配置按钮
        config_btn = ttk.Button(voice_frame, text="保存配置", command=self._save_config)
        config_btn.grid(row=0, column=2, padx=10)
        
        # 3. 文本输入区域
        text_frame = ttk.LabelFrame(self.root, text="3. 合成文本", padding=(15, 10))
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        self.text_input = tk.Text(text_frame, height=6, width=65)
        self.text_input.pack(fill=tk.BOTH, expand=True)
        self.text_input.insert(tk.END, "你是否也曾这样，心里很想和某个人聊天，却希望他先来找你， 呆呆的看着他的头像一遍又一遍。")
        
        # 4. 按钮区域（增加播放控制按钮）
        btn_frame = ttk.Frame(self.root, padding=(15, 10))
        btn_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.gen_btn = ttk.Button(btn_frame, text="生成语音", command=self._start_generate)
        self.gen_btn.pack(side="left", padx=10)
        
        self.play_btn = ttk.Button(btn_frame, text="播放语音", command=self._play_audio, state="disabled")
        self.play_btn.pack(side="left", padx=10)
        
        self.stop_btn = ttk.Button(btn_frame, text="停止播放", command=self._stop_audio, state="disabled")
        self.stop_btn.pack(side="left", padx=10)
        
        self.save_btn = ttk.Button(btn_frame, text="保存MP3", command=self._save_mp3, state="disabled")
        self.save_btn.pack(side="left", padx=10)
        
        self.show_log_btn = ttk.Button(btn_frame, text="查看响应", command=self._show_raw, state="disabled")
        self.show_log_btn.pack(side="left", padx=10)
        
        # 5. 日志区域
        log_frame = ttk.LabelFrame(self.root, text="4. 操作日志", padding=(15, 10))
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        self.log_text = tk.Text(log_frame, height=8, state="disabled", font=("SimHei", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
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
        if not self.raw_response:
            messagebox.showinfo("提示", "暂无响应数据")
            return
        
        win = tk.Toplevel(self.root)
        win.title("API原始响应")
        win.geometry("600x400")
        
        text = tk.Text(win, wrap=tk.WORD, font=("SimHei", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, self.raw_response[:2000] + "...")
    
    def _start_generate(self):
        """开始生成语音"""
        self.api_key = self.api_key_entry.get().strip()
        self.voice_id = self.voice_id_entry.get().strip()
        text = self.text_input.get("1.0", tk.END).strip()
        
        if not self.api_key:
            messagebox.showerror("错误", "请输入x-api-key！")
            return
        if not text:
            messagebox.showerror("错误", "请输入合成文本！")
            return
        
        # 停止可能的播放
        self._stop_audio()
        
        # 禁用按钮防止重复操作
        self.gen_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.play_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self._log("开始发送生成请求...")
        
        threading.Thread(
            target=self._generate_thread,
            args=(self.api_key, self.voice_id, text),
            daemon=True
        ).start()
    
    def _generate_thread(self, api_key, voice_id, text):
        """生成语音的线程"""
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
    
    def _play_audio(self):
        """播放音频预览"""
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
    
    def _stop_audio(self):
        """停止播放音频"""
        if self.is_playing:
            pygame.mixer.music.stop()
            self.is_playing = False
            self._log("已停止播放")
        
        self.play_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
    
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
    
    def _save_mp3(self):
        """保存MP3文件"""
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
            target=self._save_thread,
            args=(save_path,),
            daemon=True
        ).start()
    
    def _save_thread(self, save_path):
        """保存文件的线程"""
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


# 程序入口
if __name__ == "__main__":
    try:
        # 检查Python版本
        if sys.version_info < (3, 6):
            raise Exception("Python版本过低，需要Python 3.6及以上版本")
        
        # 启动GUI
        root = tk.Tk()
        # 确保中文显示正常
        root.option_add("*Font", ("SimHei", 10))
        app = VolcanoTTS(root)
        root.mainloop()
    
    except Exception as e:
        error_msg = f"启动失败：{str(e)}\n\n请检查：\n1. Python版本是否为3.6及以上\n2. 是否已安装必要库（运行：pip install requests pygame）\n3. 代码是否完整复制"
        print(error_msg, file=sys.stderr)
        # 尝试显示图形化错误提示
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            messagebox.showerror("启动错误", error_msg)
            root.destroy()
        except:
            pass
