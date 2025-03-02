import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import queue
import datetime

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    root = TkinterDnD.Tk()
except ImportError:
    root = tk.Tk()
    DND_FILES = None

# 简单 ToolTip 实现


class ToolTip:
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id_ = getattr(self, 'id', None)
        if id_:
            self.widget.after_cancel(id_)
            self.id = None

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 1
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(tw, text=self.text,
                          style="info.TLabel", padding=5, wraplength=200)
        label.pack()

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None


class OCRGuiApp:
    def __init__(self, root):
        self.root = root
        root.title("OCRmyPDF 图形化前端✨")
        root.geometry("950x700")

        # 初始化日志队列，用于跨线程日志更新
        self.log_queue = queue.Queue()

        # 创建 Notebook 与各个标签页
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_basic = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_basic, text="📁基本设置")
        self.create_basic_tab()

        self.tab_image = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_image, text="🖼️图像预处理")
        self.create_image_tab()

        self.tab_advanced = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_advanced, text="⚙️高级选项")
        self.create_advanced_tab()

        self.tab_meta = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_meta, text="📝文档元数据")
        self.create_meta_tab()

        # 底部区域：生成命令与日志
        self.bottom_frame = ttk.Frame(root)
        self.bottom_frame.pack(fill='both', expand=False,
                               padx=10, pady=(0, 10))
        self.create_bottom_area()

        self.bind_update_events()
        self.update_command()

        # 定时任务，每100毫秒检测日志队列
        self.root.after(100, self._process_log_queue)

    # ----- 基本设置标签页 -----
    def create_basic_tab(self):
        frame = self.tab_basic
        # 输入文件
        lbl_in = ttk.Label(frame, text="📥输入文件：")
        lbl_in.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_input = ttk.Entry(frame, width=60)
        self.entry_input.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        btn_in = ttk.Button(
            frame, text="🔍浏览", style="info.TButton", command=self.select_input_file)
        btn_in.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_input, "点击浏览或拖入文件路径（支持拖拽）")
        if DND_FILES:
            self.entry_input.drop_target_register(DND_FILES)
            self.entry_input.dnd_bind("<<Drop>>", self.drop_input_file)

        # 输出文件
        lbl_out = ttk.Label(frame, text="📤输出文件：")
        lbl_out.grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_output = ttk.Entry(frame, width=60)
        self.entry_output.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        btn_out = ttk.Button(
            frame, text="🔍浏览", style="info.TButton", command=self.select_output_file)
        btn_out.grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_output, "请选择输出 PDF 文件路径；若未指定则自动生成“输入文件名+_ocr.pdf”")
        if DND_FILES:
            self.entry_output.drop_target_register(DND_FILES)
            self.entry_output.dnd_bind("<<Drop>>", self.drop_output_file)

        # 识别语言多选
        lbl_lang = ttk.Label(frame, text="🌐识别语言：")
        lbl_lang.grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        self.lang_frame = ttk.Frame(frame)
        self.lang_frame.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.languages = {
            "简体中文": "chi_sim",
            "英文": "eng",
            "繁体中文": "chi_tra",
            "日文": "jpn",
            "韩文": "kor",
            "法文": "fra",
            "德文": "deu",
            "西班牙文": "spa"
        }
        self.lang_vars = {}
        col = 0
        for lang in self.languages:
            var = tk.BooleanVar(value=True if lang == "简体中文" else False)
            self.lang_vars[lang] = var
            chk = ttk.Checkbutton(self.lang_frame, text=lang,
                                  variable=var, command=self.update_command)
            chk.grid(row=0, column=col, sticky=tk.W, padx=2, pady=2)
            ToolTip(chk, f"选择是否使用 {lang} 的OCR识别")
            col += 1

        # 输出类型
        lbl_outtype = ttk.Label(frame, text="📄输出类型：")
        lbl_outtype.grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.combo_outtype = ttk.Combobox(frame,
                                          values=["pdf", "pdfa", "pdfa-1",
                                                  "pdfa-2", "pdfa-3", "none"],
                                          state="readonly")
        self.combo_outtype.set("pdfa")
        self.combo_outtype.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.combo_outtype, "选择输出PDF类型")
        self.combo_outtype.bind("<<ComboboxSelected>>",
                                lambda e: self.update_command())

    # ----- 图像预处理标签页 -----
    def create_image_tab(self):
        frame = self.tab_image
        self.var_rotate = tk.BooleanVar()
        chk_rotate = ttk.Checkbutton(
            frame, text="↻自动旋转页面", variable=self.var_rotate, command=self.update_command)
        chk_rotate.grid(row=0, column=0, columnspan=2,
                        sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_rotate, "启用后根据文本方向自动旋转页面")

        self.var_remove_bg = tk.BooleanVar()
        chk_remove_bg = ttk.Checkbutton(
            frame, text="🚫移除背景", variable=self.var_remove_bg, command=self.update_command)
        chk_remove_bg.grid(row=1, column=0, columnspan=2,
                           sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_remove_bg, "尝试将页面背景设置为白色")

        self.var_deskew = tk.BooleanVar()
        chk_deskew = ttk.Checkbutton(
            frame, text="📐纠正页面倾斜", variable=self.var_deskew, command=self.update_command)
        chk_deskew.grid(row=2, column=0, columnspan=2,
                        sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_deskew, "对页面进行去斜处理")

        self.var_clean = tk.BooleanVar()
        chk_clean = ttk.Checkbutton(
            frame, text="🧹清理扫描伪影", variable=self.var_clean, command=self.update_command)
        chk_clean.grid(row=3, column=0, columnspan=2,
                       sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_clean, "清除页面中的扫描杂点，但不用于最终输出")

        self.var_clean_final = tk.BooleanVar()
        chk_clean_final = ttk.Checkbutton(
            frame, text="✅清理并使用处理后图像", variable=self.var_clean_final, command=self.update_command)
        chk_clean_final.grid(row=4, column=0, columnspan=2,
                             sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_clean_final, "清理页面后，生成PDF时使用处理后的图像")

    # ----- 高级选项标签页 -----
    def create_advanced_tab(self):
        frame = self.tab_advanced
        row = 0
        lbl_pdfopt = ttk.Label(frame, text="🔧PDF优化：")
        lbl_pdfopt.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.combo_pdfopt = ttk.Combobox(frame,
                                         values=["不优化", "安全无损优化",
                                                 "有损 JPEG 优化", "更激进的有损优化"],
                                         state="readonly")
        self.combo_pdfopt.set("安全无损优化")
        self.combo_pdfopt.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.combo_pdfopt, "选择PDF优化方式，对应-O选项（0～3）")
        self.combo_pdfopt.bind("<<ComboboxSelected>>",
                               lambda e: self.update_command())
        row += 1

        self.var_force_ocr = tk.BooleanVar()
        chk_force = ttk.Checkbutton(
            frame, text="💪强制OCR", variable=self.var_force_ocr, command=self.update_command)
        chk_force.grid(row=row, column=0, columnspan=2,
                       sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_force, "强制对所有页面进行OCR（对应-f）")
        row += 1

        self.var_skip_text = tk.BooleanVar()
        chk_skip = ttk.Checkbutton(
            frame, text="🚫跳过已有文本", variable=self.var_skip_text, command=self.update_command)
        chk_skip.grid(row=row, column=0, columnspan=2,
                      sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_skip, "遇到已有文本的页面则跳过OCR（对应-s）")
        row += 1

        self.var_redo = tk.BooleanVar()
        chk_redo = ttk.Checkbutton(
            frame, text="🔄重做OCR", variable=self.var_redo, command=self.update_command)
        chk_redo.grid(row=row, column=0, columnspan=2,
                      sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_redo, "对已有OCR结果的文件进行重做OCR（对应--redo-ocr）")
        row += 1

        self.var_sidecar = tk.BooleanVar()
        chk_sidecar = ttk.Checkbutton(
            frame, text="📑生成Sidecar文本文件", variable=self.var_sidecar, command=self.update_command)
        chk_sidecar.grid(row=row, column=0, columnspan=2,
                         sticky=tk.W, padx=5, pady=5)
        ToolTip(chk_sidecar, "生成包含OCR文本的Sidecar文件")
        row += 1

        lbl_sidecar = ttk.Label(frame, text="📝Sidecar文件名：")
        lbl_sidecar.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_sidecar = ttk.Entry(frame, width=30)
        self.entry_sidecar.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_sidecar, '例如输入“名称1”，命令中显示为 "<输入文件目录>/名称1.txt"')
        self.entry_sidecar.bind(
            "<KeyRelease>", lambda e: self.update_command())
        self.entry_sidecar.bind("<FocusOut>", lambda e: self.update_command())
        row += 1

        lbl_pages = ttk.Label(frame, text="📄处理页数：")
        lbl_pages.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_pages = ttk.Entry(frame, width=30)
        self.entry_pages.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_pages, "例如：1-3,5表示仅处理指定页")
        self.entry_pages.bind("<KeyRelease>", lambda e: self.update_command())
        row += 1

    # ----- 文档元数据标签页 -----
    def create_meta_tab(self):
        frame = self.tab_meta
        row = 0
        lbl_title = ttk.Label(frame, text="🏷️标题：")
        lbl_title.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_title = ttk.Entry(frame, width=30)
        self.entry_title.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_title, "设置PDF文档标题")
        self.entry_title.bind("<KeyRelease>", lambda e: self.update_command())
        row += 1

        lbl_author = ttk.Label(frame, text="👤作者：")
        lbl_author.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_author = ttk.Entry(frame, width=30)
        self.entry_author.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_author, "设置PDF文档作者")
        self.entry_author.bind("<KeyRelease>", lambda e: self.update_command())
        row += 1

        lbl_subject = ttk.Label(frame, text="📚主题：")
        lbl_subject.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_subject = ttk.Entry(frame, width=30)
        self.entry_subject.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_subject, "设置PDF文档主题")
        self.entry_subject.bind(
            "<KeyRelease>", lambda e: self.update_command())
        row += 1

        lbl_keywords = ttk.Label(frame, text="🔑关键字：")
        lbl_keywords.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_keywords = ttk.Entry(frame, width=30)
        self.entry_keywords.grid(
            row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ToolTip(self.entry_keywords, "设置PDF文档关键字，多个词请用逗号分隔")
        self.entry_keywords.bind(
            "<KeyRelease>", lambda e: self.update_command())
        row += 1

    # ----- 底部区域：生成命令与日志 -----
    def create_bottom_area(self):
        self.bottom_top = ttk.Frame(self.bottom_frame)
        self.bottom_top.pack(fill='x', padx=5, pady=5)
        lbl_cmd = ttk.Label(self.bottom_top, text="📝生成的命令：")
        lbl_cmd.pack(side=tk.LEFT, padx=5)
        # 命令文本区域保持可编辑状态，用户可以直接修改命令
        self.txt_command = tk.Text(self.bottom_top, height=2, width=80)
        self.txt_command.pack(side=tk.LEFT, padx=5)
        btn_run = ttk.Button(self.bottom_top, text="🚀运行命令",
                             style="success.TButton", command=self.run_command)
        btn_run.pack(side=tk.LEFT, padx=5)
        ToolTip(btn_run, "执行生成的命令")
        btn_clear_cmd = ttk.Button(
            self.bottom_top, text="🗑️清除命令", style="warning.TButton", command=self.clear_command)
        btn_clear_cmd.pack(side=tk.LEFT, padx=5)
        ToolTip(btn_clear_cmd, "清空生成的命令文本")

        self.bottom_bottom = ttk.Frame(self.bottom_frame)
        self.bottom_bottom.pack(fill='both', expand=True, padx=5, pady=5)
        lbl_log = ttk.Label(self.bottom_bottom, text="📃执行日志：")
        lbl_log.pack(anchor=tk.W, padx=5)
        self.log_text = scrolledtext.ScrolledText(
            self.bottom_bottom, height=10, state='disabled', wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        btn_frame = ttk.Frame(self.bottom_bottom)
        btn_frame.pack(fill='x', padx=5, pady=5)
        btn_clear = ttk.Button(btn_frame, text="❌清除日志",
                               style="danger.TButton", command=self._clear_log)
        btn_clear.pack(side=tk.RIGHT, padx=5)
        btn_save = ttk.Button(btn_frame, text="💾保存日志",
                              style="primary.TButton", command=self._save_log)
        btn_save.pack(side=tk.RIGHT, padx=5)
        self._create_log_tags()

    def _create_log_tags(self):
        self.log_text.tag_config("timestamp", foreground="blue")
        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("success", foreground="green")

    # 将日志消息压入队列，消息为 (message, level) 的元组
    def _log_message(self, message, level):
        self.log_queue.put((message, level))

    # 定时处理日志队列，将消息追加到日志文本区域
    def _process_log_queue(self):
        while not self.log_queue.empty():
            message, level = self.log_queue.get()
            self._append_log(message, level)
        self.root.after(100, self._process_log_queue)

    # 在日志区域进行追加，附加时间戳，并按日志级别设置颜色
    def _append_log(self, message, level):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, timestamp, "timestamp")
        self.log_text.insert(tk.END, message + "\n", level)
        self.log_text.configure(state='disabled')
        self.log_text.see(tk.END)

    def _clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state='disabled')
        self._log_message("日志已清空", "info")

    def _save_log(self):
        file_path = filedialog.asksaveasfilename(
            title="保存日志", defaultextension=".txt", filetypes=[("文本文件", "*.txt")])
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.get("1.0", tk.END))
                messagebox.showinfo("提示", "日志已保存")
            except Exception as e:
                messagebox.showerror("错误", f"保存日志失败：{e}")

    # 清除生成命令文本
    def clear_command(self):
        self.txt_command.delete("1.0", tk.END)

    # 绑定各输入控件事件，实时更新命令
    def bind_update_events(self):
        self.entry_input.bind("<KeyRelease>", lambda e: self.update_command())
        self.entry_output.bind("<KeyRelease>", lambda e: self.update_command())
        self.entry_sidecar.bind(
            "<KeyRelease>", lambda e: self.update_command())
        self.entry_sidecar.bind("<FocusOut>", lambda e: self.update_command())
        self.entry_pages.bind("<KeyRelease>", lambda e: self.update_command())
        self.entry_title.bind("<KeyRelease>", lambda e: self.update_command())
        self.entry_author.bind("<KeyRelease>", lambda e: self.update_command())
        self.entry_subject.bind(
            "<KeyRelease>", lambda e: self.update_command())
        self.entry_keywords.bind(
            "<KeyRelease>", lambda e: self.update_command())
        for var in self.lang_vars.values():
            var.trace_add("write", lambda *args: self.update_command())
        self.combo_outtype.bind("<<ComboboxSelected>>",
                                lambda e: self.update_command())
        self.combo_pdfopt.bind("<<ComboboxSelected>>",
                               lambda e: self.update_command())

    def update_command(self):
        cmd = self.generate_command(update_only=True)
        self.txt_command.delete("1.0", tk.END)
        self.txt_command.insert(tk.END, " ".join(cmd))

    def generate_command(self, update_only=False):
        cmd = ["ocrmypdf"]

        selected = [self.languages[lang]
                    for lang, var in self.lang_vars.items() if var.get()]
        if selected:
            cmd.extend(["-l", "+".join(selected)])
        if self.var_rotate.get():
            cmd.append("-r")
        if self.var_remove_bg.get():
            cmd.append("--remove-background")
        if self.var_deskew.get():
            cmd.append("-d")
        if self.var_clean.get():
            cmd.append("-c")
        if self.var_clean_final.get():
            cmd.append("-i")
        outtype = self.combo_outtype.get().strip()
        if outtype:
            cmd.extend(["--output-type", outtype])
        pdf_opt = self.combo_pdfopt.get().strip()
        pdf_map = {"不优化": "0", "安全无损优化": "1",
                   "有损 JPEG 优化": "2", "更激进的有损优化": "3"}
        if pdf_opt in pdf_map:
            cmd.extend(["-O", pdf_map[pdf_opt]])
        if self.var_force_ocr.get():
            cmd.append("-f")
        if self.var_skip_text.get():
            cmd.append("-s")
        if self.var_redo.get():
            cmd.append("--redo-ocr")
        if self.var_sidecar.get():
            input_path = self.entry_input.get().strip()
            sidecar = self.entry_sidecar.get().strip()
            if not sidecar:
                base, _ = os.path.splitext(input_path)
                sidecar = os.path.basename(base) + ".txt"
            else:
                if not os.path.splitext(sidecar)[1]:
                    sidecar += ".txt"
            dir_in = os.path.dirname(
                input_path) if os.path.dirname(input_path) else "."
            sidecar_full = os.path.join(dir_in, sidecar).replace("\\", "/")
            # 为防止 sidecar 路径中出现空格，套上双引号
            cmd.extend(["--sidecar", f'"{sidecar_full}"'])
        pages = self.entry_pages.get().strip()
        if pages:
            cmd.extend(["--pages", f'"{pages}"'])
        title = self.entry_title.get().strip() if hasattr(self, "entry_title") else ""
        if title:
            cmd.extend(["--title", f'"{title}"'])
        author = self.entry_author.get().strip() if hasattr(self, "entry_author") else ""
        if author:
            cmd.extend(["--author", f'"{author}"'])
        subject = self.entry_subject.get().strip() if hasattr(self, "entry_subject") else ""
        if subject:
            cmd.extend(["--subject", f'"{subject}"'])
        keywords = self.entry_keywords.get().strip(
        ) if hasattr(self, "entry_keywords") else ""
        if keywords:
            cmd.extend(["--keywords", f'"{keywords}"'])
        input_file = self.entry_input.get().strip() or "-"
        output_file = self.entry_output.get().strip() or "-"
        # 给文件路径也加上双引号
        cmd.append(f'"{input_file}"')
        cmd.append(f'"{output_file}"')
        if not update_only:
            self._log_message("命令生成成功", "success")
        return cmd

    def select_input_file(self):
        file_path = filedialog.askopenfilename(
            title="选择输入文件", filetypes=[("PDF 或图像", "*.pdf;*.png;*.jpg;*.jpeg;*.tif")])
        if file_path:
            self.entry_input.delete(0, tk.END)
            self.entry_input.insert(0, file_path)
            base, ext = os.path.splitext(file_path)
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, f"{base}_ocr{ext}")
            self.update_command()

    def select_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="选择输出文件", defaultextension=".pdf", filetypes=[("PDF 文件", "*.pdf")])
        if file_path:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, file_path)
            self.update_command()

    def drop_input_file(self, event):
        file_path = event.data
        if file_path.startswith("{") and file_path.endswith("}"):
            file_path = file_path[1:-1]
        self.entry_input.delete(0, tk.END)
        self.entry_input.insert(0, file_path)
        base, ext = os.path.splitext(file_path)
        self.entry_output.delete(0, tk.END)
        self.entry_output.insert(0, f"{base}_ocr{ext}")
        self.update_command()

    def drop_output_file(self, event):
        file_path = event.data
        if file_path.startswith("{") and file_path.endswith("}"):
            file_path = file_path[1:-1]
        self.entry_output.delete(0, tk.END)
        self.entry_output.insert(0, file_path)
        self.update_command()

    # 使用 shell=True 并从 txt_command 中读取命令执行，便于用户直接修改
    def run_command(self):
        cmd_str = self.txt_command.get("1.0", tk.END).strip()
        self._log_message("开始执行命令：" + cmd_str, "success")

        def run_thread():
            try:
                proc = subprocess.Popen(cmd_str,
                                        shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        bufsize=1,
                                        universal_newlines=True,
                                        encoding='utf-8',
                                        errors='replace')
                while True:
                    line = proc.stdout.readline()
                    if line == '' and proc.poll() is not None:
                        break
                    if line:
                        self._log_message(line.strip(), "success")
                ret_code = proc.poll()
                if ret_code == 0:
                    self._log_message("命令执行完毕", "success")
                else:
                    self._log_message(f"命令执行失败，返回码：{ret_code}", "error")
            except Exception as e:
                self._log_message("执行过程中出错：" + str(e), "error")
        threading.Thread(target=run_thread, daemon=True).start()


if __name__ == '__main__':
    style = ttk.Style(theme='minty')
    app = OCRGuiApp(root)
    root.mainloop()
