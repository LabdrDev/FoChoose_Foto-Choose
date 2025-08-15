import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import shutil

# Konstanta
MAX_IMAGE_SIZE = (800, 600)
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')


class ToolTip:
    """Tooltip sederhana untuk widget Tkinter."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _e):
        if self.tw or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.geometry(f"+{x}+{y}")
        lbl = tk.Label(self.tw, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        lbl.pack(ipadx=6, ipady=3)

    def hide(self, _e):
        if self.tw:
            self.tw.destroy()
            self.tw = None


class PhotoSorterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Aplikasi Pemilah Foto 📸 — By LabdrDev | linktr.ee/LabdrDev")
        self.root.geometry("980x860")

        # State
        self.source_dir = ""
        self.dest_dirs = []   # list of dict: {path, name, button}
        self.image_list = []
        self.current_index = 0
        self.image_cache = {}  # path -> PhotoImage
        self.copy_mode = tk.BooleanVar(value=False)

        # UI
        self.create_widgets()
        self.bind_shortcuts()

    # ---------- UI ----------
    def create_widgets(self):
        # Bar pilih folder
        top = tk.Frame(self.root, pady=8)
        top.pack(fill="x")

        tk.Button(top, text="1. Pilih Folder Sumber Foto", command=self.select_source_folder)\
            .pack(side="left", padx=10)

        self.source_label = tk.Label(top, text="Belum ada folder sumber yang dipilih", fg="gray")
        self.source_label.pack(side="left")
        self.source_tooltip = None  # diisi saat pilih folder

        # Area daftar folder tujuan + tombol tambah
        self.dest_frame = tk.Frame(self.root, pady=6)
        self.dest_frame.pack(fill="x", padx=10)

        tk.Button(self.dest_frame, text="2. Tambah Folder Tujuan (+)", command=self.add_dest_folder)\
            .pack(anchor="w")

        # Bar tombol tujuan (pakai grid, agar semua tombol nampak >2)
        self.dest_buttons_frame = tk.Frame(self.root)
        self.dest_buttons_frame.pack(fill="x", padx=10, pady=6)

        # Area gambar
        self.image_frame = tk.Frame(self.root, relief="sunken", borderwidth=2,
                                    width=MAX_IMAGE_SIZE[0], height=MAX_IMAGE_SIZE[1])
        self.image_frame.pack(pady=10, padx=10, expand=True)
        self.image_label = tk.Label(self.image_frame)
        self.image_label.pack(expand=True)

        # Navigasi + opsi
        nav = tk.Frame(self.root, pady=6)
        nav.pack(fill="x")

        self.back_button = tk.Button(nav, text="⬅️ Kembali", command=self.go_back, state="disabled")
        self.back_button.pack(side="left", expand=True, padx=10)

        self.copy_checkbox = tk.Checkbutton(nav, text="Salin file (Copy) — bukan pindah", variable=self.copy_mode,
                                            command=self.update_status_bar)
        self.copy_checkbox.pack(side="left", expand=True)

        self.next_button = tk.Button(nav, text="Berikutnya ➡️", command=self.go_next, state="disabled")
        self.next_button.pack(side="left", expand=True, padx=10)

        # Status bar
        self.status_label = tk.Label(self.root, text="Selamat datang! Pilih folder sumber.",
                                     bd=1, relief="sunken", anchor="w")
        self.status_label.pack(side="bottom", fill="x")

        # Awal: render container tombol (kosong)
        self.render_dest_buttons()

    def bind_shortcuts(self):
        # Navigasi
        self.root.bind("<Left>", lambda e: self.go_back())
        self.root.bind("<Right>", lambda e: self.go_next())
        # Toggle copy mode
        self.root.bind("<c>", lambda e: self.toggle_copy_mode())
        self.root.bind("<C>", lambda e: self.toggle_copy_mode())
        # Angka 1-5 untuk kirim ke folder
        for i in range(1, 6):
            self.root.bind(str(i), self.make_hotkey_handler(i))

    def make_hotkey_handler(self, idx1):
        def handler(_e):
            if 1 <= idx1 <= len(self.dest_dirs) and self.image_list:
                self.process_file(self.dest_dirs[idx1-1]['path'])
        return handler

    def toggle_copy_mode(self):
        self.copy_mode.set(not self.copy_mode.get())
        self.update_status_bar()

    # ---------- Folder selection ----------
    def select_source_folder(self):
        folder_path = filedialog.askdirectory(title="Pilih Folder Sumber Foto")
        if folder_path:
            self.source_dir = folder_path
            self.source_label.config(text=f"Sumber: {os.path.basename(folder_path)}", fg="black")
            if self.source_tooltip:
                self.source_tooltip.hide(None)
            self.source_tooltip = ToolTip(self.source_label, folder_path)
            self.load_images()

    def add_dest_folder(self):
        if len(self.dest_dirs) >= 5:
            messagebox.showwarning("Batas Tercapai", "Anda hanya bisa menambahkan maksimal 5 folder tujuan.")
            return

        folder_path = filedialog.askdirectory(title=f"Pilih Folder Tujuan #{len(self.dest_dirs) + 1}")
        if not folder_path:
            return

        if folder_path in [d['path'] for d in self.dest_dirs]:
            messagebox.showwarning("Folder Duplikat", "Folder ini sudah ditambahkan.")
            return

        folder_name = os.path.basename(folder_path) or folder_path
        self.dest_dirs.append({'path': folder_path, 'name': folder_name, 'button': None})
        self.render_dest_buttons()
        self.update_buttons_state()

    def render_dest_buttons(self):
        # Bersihkan isi frame
        for w in self.dest_buttons_frame.winfo_children():
            w.destroy()

        # Grid config: hingga 5 kolom, merata
        max_cols = 5
        for c in range(max_cols):
            self.dest_buttons_frame.grid_columnconfigure(c, weight=1, uniform="btns")

        # Pasang tombol
        for i, d in enumerate(self.dest_dirs):
            r, c = divmod(i, max_cols)  # kalau lebih dari 5, otomatis baris ke-2 (aman & jelas)
            btn = tk.Button(self.dest_buttons_frame,
                            text=f"{i+1}. Proses ke '{d['name']}'",
                            state="disabled",
                            command=lambda p=d['path']: self.process_file(p))
            btn.grid(row=r, column=c, padx=6, pady=6, sticky="ew")
            d['button'] = btn

    # ---------- Image loading/display ----------
    def load_images(self):
        try:
            self.image_list = sorted([
                f for f in os.listdir(self.source_dir)
                if f.lower().endswith(SUPPORTED_EXTENSIONS)
            ])
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membaca folder sumber: {e}")
            return

        self.current_index = 0
        self.image_cache.clear()

        if not self.image_list:
            messagebox.showinfo("Kosong", "Tidak ada file foto yang ditemukan di folder ini.")
            self.image_label.config(image='', text="Tidak ada foto.")
            self.update_buttons_state()
            self.update_status_bar()
            return

        self.display_current_image()

    def display_current_image(self):
        if 0 <= self.current_index < len(self.image_list):
            image_path = os.path.join(self.source_dir, self.image_list[self.current_index])

            if image_path not in self.image_cache:
                try:
                    img = Image.open(image_path)
                    img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
                    self.image_cache[image_path] = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f"[Skip] Gagal buka {image_path}: {e}")
                    # Hapus dari list dan coba lagi
                    self.image_list.pop(self.current_index)
                    if not self.image_list:
                        self.image_label.config(image='', text="Tidak ada foto valid.")
                        self.update_buttons_state()
                        self.update_status_bar()
                        return
                    if self.current_index >= len(self.image_list):
                        self.current_index = len(self.image_list) - 1
                    self.display_current_image()
                    return

            self.image_label.config(image=self.image_cache[image_path], text="")
            self.image_label.image = self.image_cache[image_path]
        else:
            # Selesai
            self.image_label.config(
                image='', text="✅\n\nSemua foto telah dipilah!\n\nAnda bisa memilih folder sumber baru atau menutup aplikasi."
            )

        self.update_buttons_state()
        self.update_status_bar()

    # ---------- File ops ----------
    def process_file(self, dest_path):
        """Salin atau pindah file saat ini ke dest_path, dengan nama aman (no overwrite)."""
        if not (0 <= self.current_index < len(self.image_list)):
            return

        src_name = self.image_list[self.current_index]
        src_path = os.path.join(self.source_dir, src_name)

        try:
            # Pastikan nama unik di tujuan
            target_path = self.make_unique_path(dest_path, src_name)

            if self.copy_mode.get():
                shutil.copy2(src_path, target_path)  # copy2 biar metadata ikut
            else:
                # Jika dest di drive berbeda atau nama bentrok, move aman juga via make_unique_path
                shutil.move(src_path, target_path)

            # Hapus dari daftar & tampilkan berikutnya
            self.image_list.pop(self.current_index)
            if self.current_index >= len(self.image_list) and self.image_list:
                self.current_index -= 1
            self.display_current_image()

        except Exception as e:
            messagebox.showerror("Error", f"Gagal memproses file:\n{e}")

    def make_unique_path(self, dest_dir, filename):
        """Kembalikan path unik di dest_dir (file (2).ext, dst.) tanpa overwrite."""
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(dest_dir, filename)
        n = 2
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{base} ({n}){ext}")
            n += 1
        return candidate

    # ---------- Navigation ----------
    def go_next(self):
        if self.current_index < len(self.image_list) - 1:
            self.current_index += 1
            self.display_current_image()

    def go_back(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_image()

    # ---------- State/UI helpers ----------
    def update_buttons_state(self):
        has_photos = bool(self.image_list)
        # Tombol tujuan
        state = "normal" if has_photos else "disabled"
        for d in self.dest_dirs:
            if d['button'] is not None:
                d['button'].config(state=state)
        # Navigasi
        self.back_button.config(state="normal" if has_photos and self.current_index > 0 else "disabled")
        self.next_button.config(state="normal" if has_photos and self.current_index < len(self.image_list) - 1 else "disabled")

    def update_status_bar(self):
        mode = "COPY" if self.copy_mode.get() else "MOVE"
        if self.image_list and (0 <= self.current_index < len(self.image_list)):
            self.status_label.config(
                text=f"[{mode}]  Foto {self.current_index + 1} / {len(self.image_list)}  |  "
                     f"Nama: {self.image_list[self.current_index]}"
            )
        else:
            self.status_label.config(text=f"[{mode}]  Tidak ada foto aktif.")

# ---- Main ----
if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoSorterApp(root)
    root.mainloop()
