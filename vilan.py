#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, Menu, colorchooser
import time
import threading
import configparser
import os

class NetworkSpeedWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Скорость интернета")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        
        # Конфигурация
        self.config_file = os.path.expanduser("~/.netspeed_config")
        self.load_config()
        
        # Цвета по умолчанию
        self.bg_color = self.config.get('colors', 'bg', fallback='#2d2d2d')
        self.download_color = self.config.get('colors', 'download', fallback='#4CAF50')
        self.upload_color = self.config.get('colors', 'upload', fallback='#2196F3')
        self.grid_color = self.config.get('colors', 'grid', fallback='#444444')
        self.text_color = self.config.get('colors', 'text', fallback='white')
        
        # Размеры
        self.width = int(self.config.get('size', 'width', fallback='200'))
        self.height = int(self.config.get('size', 'height', fallback='150'))
        self.font_size = int(self.config.get('font', 'size', fallback='9'))
        
        # Прозрачность
        self.transparency = float(self.config.get('display', 'transparency', fallback='0.9'))
        
        # Интерфейс
        self.selected_interface = tk.StringVar()
        self.interfaces = self.get_network_interfaces()
        if self.interfaces:
            saved_interface = self.config.get('network', 'interface', fallback='')
            if saved_interface in self.interfaces:
                self.selected_interface.set(saved_interface)
            else:
                self.selected_interface.set(self.interfaces[0])
        
        # Данные
        self.download_data = [0] * 20
        self.upload_data = [0] * 20
        self.max_value = 100
        self.prev_stats = {}
        self.is_running = True
        self.x = 0
        self.y = 0
        self.resize_start_x = 0
        self.resize_start_y = 0
        self.start_width = 0
        self.start_height = 0
        
        # Создаем интерфейс
        self.create_widgets()
        
        # Контекстное меню
        self.create_context_menu()
        
        # Применяем настройки
        self.apply_config()
        
        # Запуск потока мониторинга
        self.thread = threading.Thread(target=self.monitor_network, daemon=True)
        self.thread.start()

    def load_config(self):
        """Загрузка конфигурации"""
        self.config = configparser.ConfigParser()
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)

    def save_config(self):
        """Сохранение конфигурации"""
        sections = ['colors', 'size', 'font', 'network', 'display']
        for section in sections:
            if not self.config.has_section(section):
                self.config.add_section(section)
            
        self.config.set('colors', 'bg', self.bg_color)
        self.config.set('colors', 'download', self.download_color)
        self.config.set('colors', 'upload', self.upload_color)
        self.config.set('colors', 'grid', self.grid_color)
        self.config.set('colors', 'text', self.text_color)
        self.config.set('size', 'width', str(self.width))
        self.config.set('size', 'height', str(self.height))
        self.config.set('font', 'size', str(self.font_size))
        self.config.set('network', 'interface', self.selected_interface.get())
        self.config.set('display', 'transparency', str(self.transparency))
        
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def get_network_interfaces(self):
        """Получить список сетевых интерфейсов"""
        interfaces = []
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]
                for line in lines:
                    interface = line.split(':')[0].strip()
                    if not interface.startswith(('lo', 'virbr', 'docker')):
                        interfaces.append(interface)
        except Exception as e:
            print(f"Ошибка получения интерфейсов: {e}")
        return interfaces if interfaces else ['lo']

    def get_network_stats(self, interface):
        """Получить статистику по интерфейсу"""
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]
                for line in lines:
                    if interface in line:
                        parts = line.split(':')
                        if len(parts) == 2:
                            stats = parts[1].split()
                            if len(stats) >= 10:
                                rx_bytes = int(stats[0])
                                tx_bytes = int(stats[8])
                                return rx_bytes, tx_bytes
        except Exception as e:
            print(f"Ошибка чтения статистики: {e}")
        return 0, 0

    def create_widgets(self):
        """Создание виджетов"""
        self.root.configure(bg=self.bg_color)
        
        # Верхняя панель
        self.top_frame = tk.Frame(self.root, bg=self.bg_color, height=20)
        self.top_frame.pack(fill="x", padx=2, pady=2)
        self.top_frame.pack_propagate(False)
        
        # Кнопка настроек
        self.settings_btn = tk.Button(self.top_frame, text="⚙", bg="#555", fg="white", 
                                    font=("Arial", 8), width=2, height=1, bd=0,
                                    command=self.show_context_menu)
        self.settings_btn.pack(side="left")
        
        # Область ресайза (правый нижний угол)
        self.resize_handle = tk.Label(self.root, text="⇲", bg=self.bg_color, 
                                     fg="#777", cursor="bottom_right_corner")
        self.resize_handle.place(relx=1.0, rely=1.0, anchor="se")
        self.resize_handle.bind('<Button-1>', self.start_resize)
        self.resize_handle.bind('<B1-Motion>', self.do_resize)

        # Заголовок
        self.title = tk.Label(self.root, text="Сеть", font=("Arial", 10), 
                             fg=self.text_color, bg=self.bg_color, cursor="fleur")
        self.title.pack()

        # Холст для графика
        self.canvas_width = self.width - 20
        self.canvas_height = self.height - 80
        self.canvas = tk.Canvas(self.root, width=self.canvas_width, 
                               height=self.canvas_height, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(padx=5, pady=2)
        
        # Метки скорости
        self.speed_label = tk.Label(self.root, text="D: 0 KB/s  U: 0 KB/s", 
                                   font=("Arial", self.font_size), fg=self.text_color, bg=self.bg_color)
        self.speed_label.pack(pady=2)

        # Биндинги для перемещения
        self.bind_movement()

    def bind_movement(self):
        """Настройка перемещения окна"""
        widgets = [self.root, self.title, self.speed_label, self.canvas, self.top_frame]
        for widget in widgets:
            widget.bind('<Button-1>', self.start_move)
            widget.bind('<B1-Motion>', self.do_move)
            widget.bind('<Button-3>', self.show_context_menu_right_click)

    def start_move(self, event):
        if event.widget != self.resize_handle and event.widget != self.settings_btn:
            self.x = event.x
            self.y = event.y

    def do_move(self, event):
        if event.widget != self.resize_handle and event.widget != self.settings_btn:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")

    def start_resize(self, event):
        """Начало изменения размера"""
        self.resize_start_x = event.x_root
        self.resize_start_y = event.y_root
        self.start_width = self.width
        self.start_height = self.height

    def do_resize(self, event):
        """Изменение размера"""
        delta_x = event.x_root - self.resize_start_x
        delta_y = event.y_root - self.resize_start_y
        
        new_width = max(150, self.start_width + delta_x)
        new_height = max(120, self.start_height + delta_y)
        
        self.width = int(new_width)
        self.height = int(new_height)
        
        self.root.geometry(f"{self.width}x{self.height}")
        self.update_canvas_size()

    def update_canvas_size(self):
        """Обновление размера холста"""
        canvas_new_width = self.width - 20
        canvas_new_height = self.height - 80
        self.canvas.configure(width=canvas_new_width, height=canvas_new_height)
        self.canvas_width = canvas_new_width
        self.canvas_height = canvas_new_height

    def create_context_menu(self):
        """Создание контекстного меню"""
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Настройки", command=self.show_main_settings)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Цвета", command=self.show_color_settings)
        self.context_menu.add_command(label="Размер шрифта", command=self.show_font_settings)
        self.context_menu.add_command(label="Прозрачность", command=self.show_transparency_settings)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Выбрать интерфейс", command=self.show_interface_dialog)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Сброс настроек", command=self.reset_settings)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Выход", command=self.quit_app)

    def show_context_menu_right_click(self, event):
        """Показ контекстного меню по правой кнопке"""
        self.context_menu.post(event.x_root, event.y_root)

    def show_context_menu(self, event=None):
        """Показ контекстного меню"""
        x = self.root.winfo_x() + 20
        y = self.root.winfo_y() + 20
        self.context_menu.post(x, y)

    def show_main_settings(self):
        """Главные настройки"""
        SettingsWindow(self.root, self)

    def show_color_settings(self):
        """Настройки цветов"""
        ColorSettingsWindow(self.root, self)

    def show_font_settings(self):
        """Настройки шрифта"""
        FontSettingsWindow(self.root, self)

    def show_transparency_settings(self):
        """Настройки прозрачности"""
        TransparencySettingsWindow(self.root, self)

    def show_interface_dialog(self):
        """Диалог выбора интерфейса"""
        InterfaceDialog(self.root, self)

    def reset_settings(self):
        """Сброс настроек"""
        # Удаляем конфиг файл
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        # Перезапускаем приложение
        self.root.quit()
        os.execv(__file__, [__file__])

    def quit_app(self):
        """Выход из приложения"""
        self.save_config()
        self.root.quit()

    def apply_config(self):
        """Применение конфигурации"""
        self.root.configure(bg=self.bg_color)
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.wm_attributes("-alpha", self.transparency)
        self.title.configure(bg=self.bg_color, fg=self.text_color)
        self.speed_label.configure(bg=self.bg_color, fg=self.text_color, font=("Arial", self.font_size))
        self.settings_btn.configure(bg="#555", fg="white")
        self.resize_handle.configure(bg=self.bg_color)
        self.update_canvas_size()

    def set_color(self, color_type, color):
        """Установка цвета"""
        setattr(self, f"{color_type}_color", color)
        self.apply_config()
        self.save_config()

    def set_font_size(self, size):
        """Установка размера шрифта"""
        self.font_size = size
        self.speed_label.configure(font=("Arial", self.font_size))
        self.save_config()

    def set_transparency(self, value):
        """Установка прозрачности"""
        self.transparency = float(value)
        self.root.wm_attributes("-alpha", self.transparency)
        self.save_config()

    def monitor_network(self):
        """Мониторинг сетевой активности"""
        while self.is_running:
            interface = self.selected_interface.get()
            current_rx, current_tx = self.get_network_stats(interface)
            
            if interface in self.prev_stats:
                prev_rx, prev_tx = self.prev_stats[interface]
                
                rx_speed = max(0, current_rx - prev_rx)
                tx_speed = max(0, current_tx - prev_tx)
                
                download_kbps = rx_speed / 1024
                upload_kbps = tx_speed / 1024
                
                self.download_data.append(download_kbps)
                self.upload_data.append(upload_kbps)
                
                if len(self.download_data) > 20:
                    self.download_data.pop(0)
                if len(self.upload_data) > 20:
                    self.upload_data.pop(0)
                
                current_max = max(max(self.download_data + self.upload_data) * 1.2, 10)
                self.max_value = max(current_max, self.max_value * 0.9)
                
                self.root.after(0, self.update_display, download_kbps, upload_kbps)
            
            self.prev_stats[interface] = (current_rx, current_tx)
            time.sleep(1)

    def update_display(self, download, upload):
        """Обновление отображения"""
        self.speed_label.config(text=f"D: {download:.1f} KB/s  U: {upload:.1f} KB/s")
        self.canvas.delete("all")
        
        # Рисуем сетку
        for i in range(1, 5):
            y = i * self.canvas_height / 5
            self.canvas.create_line(0, y, self.canvas_width, y, fill=self.grid_color, dash=(2, 2))
        
        # Рисуем данные
        if len(self.download_data) > 0:
            bar_width = self.canvas_width / len(self.download_data)
            
            for i in range(len(self.download_data)):
                x = i * bar_width
                
                if self.max_value > 0:
                    download_height = (self.download_data[i] / self.max_value) * self.canvas_height
                    self.canvas.create_rectangle(
                        x, self.canvas_height - download_height,
                        x + bar_width/2 - 1, self.canvas_height,
                        fill=self.download_color, outline=""
                    )
                    
                    upload_height = (self.upload_data[i] / self.max_value) * self.canvas_height
                    self.canvas.create_rectangle(
                        x + bar_width/2 + 1, self.canvas_height - upload_height,
                        x + bar_width - 1, self.canvas_height,
                        fill=self.upload_color, outline=""
                    )

    def run(self):
        self.root.mainloop()

class BaseSettingsWindow:
    def __init__(self, parent, main_app):
        self.parent = parent
        self.main_app = main_app
        self.window = None
    
    def create_window(self, title, width=250, height=200):
        self.window = tk.Toplevel(self.parent)
        self.window.title(title)
        self.window.geometry(f"{width}x{height}")
        self.window.configure(bg=self.main_app.bg_color)
        self.window.transient(self.parent)
        
        # Центрирование
        x = self.parent.winfo_x() + 50
        y = self.parent.winfo_y() + 50
        self.window.geometry(f"+{x}+{y}")
        
        return self.window
    
    def close_window(self):
        if self.window:
            self.window.destroy()
            self.window = None

class SettingsWindow(BaseSettingsWindow):
    def __init__(self, parent, main_app):
        super().__init__(parent, main_app)
        self.show()
    
    def show(self):
        if self.window is not None:
            self.window.lift()
            return
            
        self.create_window("Настройки", 250, 150)
        
        # Прозрачность
        tk.Label(self.window, text="Прозрачность:", bg=self.main_app.bg_color, fg=self.main_app.text_color).pack(pady=5)
        transparency_var = tk.DoubleVar(value=self.main_app.transparency)
        transparency_scale = ttk.Scale(self.window, from_=0.3, to=1.0, 
                                      variable=transparency_var, orient="horizontal", length=200,
                                      command=lambda v: self.main_app.root.wm_attributes("-alpha", float(v)))
        transparency_scale.pack(pady=5)
        
        tk.Button(self.window, text="Сохранить", 
                 command=lambda: self.save_settings(transparency_var)).pack(pady=10)
        
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

    def save_settings(self, transparency_var):
        self.main_app.set_transparency(transparency_var.get())
        self.close_window()

class ColorSettingsWindow(BaseSettingsWindow):
    def __init__(self, parent, main_app):
        super().__init__(parent, main_app)
        self.show()
    
    def show(self):
        if self.window is not None:
            self.window.lift()
            return
            
        self.create_window("Цвета", 250, 250)
        
        colors = [
            ("Фон", "bg"),
            ("Download", "download"),
            ("Upload", "upload"),
            ("Сетка", "grid"),
            ("Текст", "text")
        ]
        
        self.color_vars = {}
        
        for name, key in colors:
            frame = tk.Frame(self.window, bg=self.main_app.bg_color)
            frame.pack(fill="x", padx=10, pady=2)
            
            tk.Label(frame, text=name, bg=self.main_app.bg_color, fg=self.main_app.text_color).pack(side="left")
            
            color_btn = tk.Button(frame, text="●", width=3, 
                                 command=lambda k=key: self.choose_color(k))
            color_btn.pack(side="right")
            self.color_vars[key] = color_btn
            
            # Устанавливаем начальный цвет
            current_color = getattr(self.main_app, f"{key}_color")
            color_btn.configure(bg=current_color)
        
        # Кнопка сохранения
        tk.Button(self.window, text="Сохранить все", command=self.save_colors).pack(pady=10)
        
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

    def choose_color(self, key):
        color = colorchooser.askcolor(title=f"Выберите цвет {key}")[1]
        if color:
            self.color_vars[key].configure(bg=color)
            setattr(self.main_app, f"{key}_color", color)

    def save_colors(self):
        self.main_app.save_config()
        self.main_app.apply_config()
        self.close_window()

class FontSettingsWindow(BaseSettingsWindow):
    def __init__(self, parent, main_app):
        super().__init__(parent, main_app)
        self.show()
    
    def show(self):
        if self.window is not None:
            self.window.lift()
            return
            
        self.create_window("Размер шрифта", 200, 120)
        
        tk.Label(self.window, text="Размер шрифта:", bg=self.main_app.bg_color, fg=self.main_app.text_color).pack(pady=5)
        
        font_var = tk.IntVar(value=self.main_app.font_size)
        font_spinbox = tk.Spinbox(self.window, from_=6, to=20, textvariable=font_var, width=10)
        font_spinbox.pack(pady=5)
        
        tk.Button(self.window, text="Применить", 
                 command=lambda: self.apply_font_size(font_var)).pack(pady=10)
        
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
    
    def apply_font_size(self, font_var):
        self.main_app.set_font_size(font_var.get())
        self.close_window()

class TransparencySettingsWindow(BaseSettingsWindow):
    def __init__(self, parent, main_app):
        super().__init__(parent, main_app)
        self.show()
    
    def show(self):
        if self.window is not None:
            self.window.lift()
            return
            
        self.create_window("Прозрачность", 250, 120)
        
        tk.Label(self.window, text="Прозрачность:", bg=self.main_app.bg_color, fg=self.main_app.text_color).pack(pady=5)
        transparency_var = tk.DoubleVar(value=self.main_app.transparency)
        transparency_scale = ttk.Scale(self.window, from_=0.3, to=1.0, 
                                      variable=transparency_var, orient="horizontal", length=200,
                                      command=lambda v: self.main_app.root.wm_attributes("-alpha", float(v)))
        transparency_scale.pack(pady=5)
        
        tk.Button(self.window, text="Сохранить", 
                 command=lambda: self.apply_transparency(transparency_var)).pack(pady=10)
        
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
    
    def apply_transparency(self, transparency_var):
        self.main_app.set_transparency(transparency_var.get())
        self.close_window()

class InterfaceDialog(BaseSettingsWindow):
    def __init__(self, parent, main_app):
        super().__init__(parent, main_app)
        self.show()
    
    def show(self):
        if self.window is not None:
            self.window.lift()
            return
            
        self.create_window("Интерфейс", 200, 150)
        
        self.main_app.interfaces = self.main_app.get_network_interfaces()
        
        tk.Label(self.window, text="Интерфейс:", bg=self.main_app.bg_color, fg=self.main_app.text_color).pack(pady=5)
        
        interface_var = tk.StringVar(value=self.main_app.selected_interface.get())
        interface_combo = ttk.Combobox(self.window, textvariable=interface_var, 
                                      values=self.main_app.interfaces, state="readonly", width=20)
        interface_combo.pack(pady=5)
        
        def apply_interface():
            self.main_app.selected_interface.set(interface_var.get())
            self.main_app.save_config()
            self.close_window()
        
        tk.Button(self.window, text="Применить", command=apply_interface).pack(pady=10)
        
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

if __name__ == "__main__":
    app = NetworkSpeedWidget()
    app.run()
