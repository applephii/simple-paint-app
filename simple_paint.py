import tkinter as tk
from tkinter import colorchooser, filedialog
from PIL import Image, ImageDraw, ImageTk
import copy

class PaintApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Paint")

        self.canvas_width = 650
        self.canvas_height = 650

        self.pen_color = "black"
        self.pen_size = 5
        self.tool = "pencil"

        self.image = Image.new("RGB", (self.canvas_width, self.canvas_height), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.undo_stack = []

        self.canvas_frame = tk.Frame(self.root, width=self.canvas_width, height=self.canvas_height)
        self.canvas_frame.pack(side=tk.RIGHT, expand=True)
        self.canvas_frame.pack_propagate(False)

        self.canvas = tk.Canvas(self.canvas_frame, bg="white",
                                width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack(expand=True)

        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.show_pointer)

        self.last_x, self.last_y = None, None
        self.start_x, self.start_y = None, None

        self.image_tk = None
        self.temp_shape = None
        self.pointer = None
        self.tool_buttons = {}

        self.current_tool = "pencil"
        self.drag_data = {"x": 0, "y": 0}
        self.selection_rect = None
        self.select_start = None
        self.selected_items = []
        self.selection_active = False

        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)

        self.cursor_button = tk.Button(self.toolbar, text="Cursor", width=12,
                                       command=lambda: self.set_tool("cursor"))
        self.cursor_button.grid(row=0, column=0, padx=2, pady=2)
        self.tool_buttons["cursor"] = self.cursor_button

        self.selectAndmove_button = tk.Button(self.toolbar, text="Select", width=12,
                                              command=lambda: self.set_tool("selectAndmove"))
        self.selectAndmove_button.grid(row=0, column=1, padx=2, pady=2)
        self.tool_buttons["selectAndmove"] = self.selectAndmove_button

        self.tool_row = 1
        self.tool_col = 0

        self.selection_box = None
        self.selection_image = None
        self.selection_position = None
        self.preview_image = None

        self.setup_ui()
        self.update_canvas_image()

    def setup_ui(self):
        frame = self.toolbar

        def add_button(text, command, tool_name=None):
            nonlocal frame
            btn = tk.Button(frame, text=text, width=12, 
                            command=lambda: command(tool_name) if tool_name else command())
            btn.grid(row=self.tool_row, column=self.tool_col, padx=2, pady=2, sticky="ew")
            if tool_name:
                self.tool_buttons[tool_name] = btn
            self.tool_col += 1
            if self.tool_col > 1:
                self.tool_col = 0
                self.tool_row += 1

        add_button("Color", self.choose_color)
        add_button("Clear", self.clear_canvas)
        add_button("Save", self.save_image)
        add_button("Undo", self.undo)
        add_button("Rotate", self.rotate_image)
        add_button("Rotate Selection", self.rotate_selection)
        add_button("Flip H", self.flip_horizontal)
        add_button("Flip V", self.flip_vertical)

        tools = ["pencil", "eraser", "line", "line_bresenham", "rectangle", "oval", 
                 "circle_midpoint", "circle", "triangle", "fill", 
                 "rectangle3d", "circle3d", "triangle3d"]
        for t in tools:
            add_button(t.capitalize(), self.set_tool, t)

        self.tool_row += 1
        self.tool_col = 0
        tk.Label(frame, text="Ukuran Pena").grid(row=self.tool_row, column=0, columnspan=2, pady=(10, 0))
        self.tool_row += 1
        self.size_var = tk.IntVar(value=self.pen_size)
        tk.Spinbox(frame, from_=1, to=50, textvariable=self.size_var, width=5, 
                   command=self.update_pen_size).grid(row=self.tool_row, column=0, columnspan=2, pady=5)

        self.update_tool_highlight()

    def on_canvas_resize(self, event):
        new_width = max(event.width, 1)
        new_height = max(event.height, 1)
        if new_width > self.canvas_width or new_height > self.canvas_height:
            old_image = self.image
            self.canvas_width = new_width
            self.canvas_height = new_height
            self.image = Image.new("RGB", (self.canvas_width, self.canvas_height), "white")
            self.image.paste(old_image, (0, 0))
            self.draw = ImageDraw.Draw(self.image)
            self.update_canvas_image()

    def set_tool(self, tool):
        self.tool = tool
        self.current_tool = tool
        self.update_tool_highlight()

    def update_tool_highlight(self):
        for name, btn in self.tool_buttons.items():
            btn.config(bg="lightgray" if name == self.tool else "SystemButtonFace")

    def choose_color(self):
        color = colorchooser.askcolor()[1]
        if color:
            self.pen_color = color
            if self.tool == "eraser":
                self.set_tool("pencil")

    def update_pen_size(self):
        self.pen_size = self.size_var.get()

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.save_state()
        if self.tool == "fill":
            self.flood_fill(event.x, event.y)
        elif self.tool in ["pencil", "eraser"]:
            self.last_x, self.last_y = event.x, event.y
        elif self.tool in ["selectAndmove", "cursor"]:
            self.select_start = (event.x, event.y)
            self.selection_rect = self.canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                                outline="blue", dash=(2, 2))
            self.selected_items = []
            self.canvas.bind("<B1-Motion>", self.on_drag)

    def on_drag(self, event):
        if self.tool == "selectAndmove":
            if self.selection_box and self.selection_image:
                dx = event.x - self.selection_position[0]
                dy = event.y - self.selection_position[1]
                self.update_canvas_image()
                self.preview_image = ImageTk.PhotoImage(self.selection_image)
                self.canvas.create_image(event.x, event.y, image=self.preview_image, anchor=tk.NW)
                self.drag_data["dx"] = dx
                self.drag_data["dy"] = dy
        elif self.tool == "cursor":
            if self.selection_rect:
                x0, y0 = self.select_start
                self.canvas.coords(self.selection_rect, x0, y0, event.x, event.y)
            elif self.selected_items:
                dx = event.x - self.drag_data["x"]
                dy = event.y - self.drag_data["y"]
                for item in self.selected_items:
                    self.canvas.move(item, dx, dy)
                self.drag_data["x"] = event.x
                self.drag_data["y"] = event.y

    def on_release(self, event):
        if self.tool == "cursor":
            if self.selection_rect:
                x0, y0, x1, y1 = self.canvas.coords(self.selection_rect)
                self.selected_items = self.canvas.find_enclosed(min(x0, x1), min(y0, y1),
                                                                 max(x0, x1), max(y0, y1))
                self.canvas.delete(self.selection_rect)
                self.selection_rect = None
                self.select_start = None
                if self.selected_items:
                    self.drag_data["x"] = event.x
                    self.drag_data["y"] = event.y
        elif self.temp_shape:
            self.canvas.delete(self.temp_shape)
            self.temp_shape = None

        if self.tool == "selectAndmove":
            if self.selection_rect and not self.selection_box:
                x0, y0 = self.select_start
                x1, y1 = event.x, event.y
                self.canvas.coords(self.selection_rect, x0, y0, x1, y1)
                self.selection_box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                self.selection_image = self.image.crop(self.selection_box)
                self.selection_position = (self.selection_box[0], self.selection_box[1])
                self.selection_active = True
            elif self.selection_box and self.selection_image:
                dx = event.x - self.selection_position[0]
                dy = event.y - self.selection_position[1]
                self.update_canvas_image()
                self.preview_image = ImageTk.PhotoImage(self.selection_image)
                self.canvas.create_image(event.x, event.y, image=self.preview_image, anchor=tk.NW)
                self.drag_data["dx"] = dx
                self.drag_data["dy"] = dy

            if self.selection_image and ("dx" in self.drag_data or "dy" in self.drag_data):
                self.save_state()
                dx, dy = self.drag_data["dx"], self.drag_data["dy"]
                x0 = self.selection_box[0] + dx
                y0 = self.selection_box[1] + dy
                x_old0, y_old0, x_old1, y_old1 = self.selection_box
                self.draw.rectangle([x_old0, y_old0, x_old1, y_old1], fill="white")
                self.image.paste(self.selection_image, (x0, y0))
                self.draw = ImageDraw.Draw(self.image)
                self.update_canvas_image()
                self.selection_box = None
                self.selection_image = None
                self.selection_position = None
                self.preview_image = None
                self.drag_data.clear()
                self.selection_active = False

        if self.tool in ["line", "line_bresenham", "rectangle", "oval", "circle_midpoint",
                         "circle", "triangle", "rectangle3d", "circle3d", "triangle3d"]:
            x0, y0 = self.start_x, self.start_y
            x1, y1 = event.x, event.y

            if self.tool == "line":
                self.draw.line((x0, y0, x1, y1), fill=self.pen_color, width=self.pen_size)  
            elif self.tool == "line_bresenham":
                self.draw_line_bresenham(x0, y0, x1, y1, self.pen_color)
            elif self.tool == "rectangle":
                self.draw.rectangle((x0, y0, x1, y1), outline=self.pen_color, width=self.pen_size)
            elif self.tool == "oval":
                self.draw.ellipse((x0, y0, x1, y1), outline=self.pen_color, width=self.pen_size)
            elif self.tool == "circle_midpoint":
                xc = (x0 + x1) // 2
                yc = (y0 + y1) // 2
                r = max(abs(x1 - x0), abs(y1 - y0)) // 2
                self.draw_circle_midpoint(xc, yc, r, self.pen_color)
            elif self.tool == "circle":
                r = max(abs(x1 - x0), abs(y1 - y0))
                self.draw.ellipse((x0 - r, y0 - r, x0 + r, y0 + r), outline=self.pen_color, width=self.pen_size)
            elif self.tool == "triangle":
                points = [x0, y1, (x0 + x1) // 2, y0, x1, y1]
                self.draw.polygon(points, outline=self.pen_color, width=self.pen_size)
            elif self.tool == "rectangle3d":
                offset = 10
                self.draw.rectangle((x0, y0, x1, y1), fill=self.pen_color,
                                    outline=self.pen_color, width=self.pen_size)
                shadow_color = "gray"
                self.draw.rectangle((x0 + offset, y0 - offset, x1 + offset, y1 - offset),
                                    fill=shadow_color, outline=shadow_color)
                self.draw.polygon([(x0, y0), (x0 + offset, y0 - offset),
                                   (x0 + offset, y1 - offset), (x0, y1)],
                                  fill="darkgray")
                self.draw.polygon([(x1, y0), (x1 + offset, y0 - offset),
                                   (x1 + offset, y1 - offset), (x1, y1)],
                                  fill="darkgray")
            elif self.tool == "circle3d":
                r = max(abs(x1 - x0), abs(y1 - y0))
                self.draw.ellipse((x0 - r, y0 - r, x0 + r, y0 + r), fill=self.pen_color,
                                  outline=self.pen_color, width=self.pen_size)
                self.draw.ellipse((x0 - r + 5, y0 - r - 5, x0 + r + 5, y0 + r - 5),
                                  fill="gray", outline="gray", width=1)
            elif self.tool == "triangle3d":
                base_points = [x0, y1, (x0 + x1) // 2, y0, x1, y1]
                shadow_offset = 10
                shadow_points = [
                    x0 + shadow_offset, y1 - shadow_offset,
                    (x0 + x1) // 2 + shadow_offset, y0 - shadow_offset,
                    x1 + shadow_offset, y1 - shadow_offset
                ]
                self.draw.polygon(base_points, fill=self.pen_color, outline=self.pen_color)
                self.draw.polygon(shadow_points, fill="gray", outline="gray")
                for (x_base, y_base), (x_shadow, y_shadow) in zip(
                    [(x0, y1), ((x0 + x1) // 2, y0), (x1, y1)],
                    [(x0 + shadow_offset, y1 - shadow_offset),
                     ((x0 + x1) // 2 + shadow_offset, y0 - shadow_offset),
                     (x1 + shadow_offset, y1 - shadow_offset)]
                ):
                    self.draw.line((x_base, y_base, x_shadow, y_shadow), fill="darkgray")

            self.update_canvas_image()
        self.canvas.bind("<B1-Motion>", self.paint)

    def paint(self, event):
        if self.tool in ["pencil", "eraser"]:
            x, y = event.x, event.y
            color = "white" if self.tool == "eraser" else self.pen_color
            self.canvas.create_line(self.last_x, self.last_y, x, y, fill=color, width=self.pen_size)
            self.draw.line([self.last_x, self.last_y, x, y], fill=color, width=self.pen_size)
            self.last_x, self.last_y = x, y
        elif self.tool in ["line", "rectangle", "oval", "circle", "triangle"]:
            if self.temp_shape:
                self.canvas.delete(self.temp_shape)
            x0, y0 = self.start_x, self.start_y
            x1, y1 = event.x, event.y
            if self.tool == "line":
                self.temp_shape = self.canvas.create_line(x0, y0, x1, y1, fill="gray", dash=(4, 2))
            elif self.tool == "rectangle":
                self.temp_shape = self.canvas.create_rectangle(x0, y0, x1, y1, outline="gray", dash=(4, 2))
            elif self.tool == "oval":
                self.temp_shape = self.canvas.create_oval(x0, y0, x1, y1, outline="gray", dash=(4, 2))
            elif self.tool == "circle":
                r = max(abs(x1 - x0), abs(y1 - y0))
                self.temp_shape = self.canvas.create_oval(x0 - r, y0 - r, x0 + r, y0 + r, outline="gray", dash=(4, 2))
            elif self.tool == "triangle":
                points = [x0, y1, (x0 + x1) // 2, y0, x1, y1]
                self.temp_shape = self.canvas.create_polygon(points, outline="gray", dash=(4, 2), fill="")

    def flood_fill(self, x, y):
        if not (0 <= x < self.canvas_width and 0 <= y < self.canvas_height):
            return
        target_color = self.image.getpixel((x, y))
        replacement_color = self.hex_to_rgb(self.pen_color)
        if target_color == replacement_color:
            return
        pixel = self.image.load()
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            try:
                if pixel[cx, cy] == target_color:
                    pixel[cx, cy] = replacement_color
                    stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])
            except IndexError:
                continue
        self.update_canvas_image()

    def rotate_image(self):
        self.save_state()
        rotated = self.image.rotate(-90, expand=True)
        new_canvas = Image.new("RGB", (self.canvas_width, self.canvas_height), "white")
        rotated_width, rotated_height = rotated.size
        center_x = (self.canvas_width - rotated_width) // 2
        center_y = (self.canvas_height - rotated_height) // 2
        new_canvas.paste(rotated, (center_x, center_y))
        self.image = new_canvas
        self.draw = ImageDraw.Draw(self.image)
        self.update_canvas_image()
        
    def rotate_selection(self):
        if not self.selection_active or not self.selection_box or not self.selection_image:
            print("Tidak ada seleksi aktif untuk diputar.")
            return
        
        self.save_state()
        rotated_image = self.selection_image.rotate(-90, expand=True)
        w, h = rotated_image.size
        x0, y0 = self.selection_box[0], self.selection_box[1]

        x_old0, y_old0, x_old1, y_old1 = self.selection_box
        self.draw.rectangle([x_old0, y_old0, x_old1, y_old1], fill="white")
        self.image.paste(rotated_image, (x0, y0))
        self.draw = ImageDraw.Draw(self.image)

        self.selection_box = None
        self.selection_image = None
        self.selection_position = None
        self.preview_image = None
        self.selection_active = False
        self.update_canvas_image()

    def flip_horizontal(self):
        self.save_state()
        self.image = self.image.transpose(Image.FLIP_LEFT_RIGHT)
        self.draw = ImageDraw.Draw(self.image)
        self.update_canvas_image()

    def flip_vertical(self):
        self.save_state()
        self.image = self.image.transpose(Image.FLIP_TOP_BOTTOM)
        self.draw = ImageDraw.Draw(self.image)
        self.update_canvas_image()

    def show_pointer(self, event):
        if self.pointer:
            self.canvas.delete(self.pointer)
        if self.tool in ["pencil", "eraser"]:
            r = self.pen_size // 2
            self.pointer = self.canvas.create_oval(event.x - r, event.y - r,
                                                   event.x + r, event.y + r,
                                                   outline="gray", width=1)

    def update_canvas_image(self):
        self.canvas.delete("all")
        self.image_tk = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_tk)
        self.preview_image = None

    def clear_canvas(self):
        self.save_state()
        self.canvas.delete("all")
        self.image = Image.new("RGB", (self.canvas_width, self.canvas_height), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.update_canvas_image()

    def save_image(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                   filetypes=[("PNG files", "*.png"),
                                                              ("JPEG files", "*.jpg;*.jpeg"),
                                                              ("All files", "*.*")])
        if file_path:
            ext = file_path.lower().split('.')[-1]
            if ext in ["jpg", "jpeg"]:
                rgb_image = self.image.convert("RGB")
                rgb_image.save(file_path, format="JPEG")
            else:
                self.image.save(file_path)

    def save_state(self):
        self.undo_stack.append(copy.deepcopy(self.image))

    def undo(self):
        if self.undo_stack:
            self.image = self.undo_stack.pop()
            self.draw = ImageDraw.Draw(self.image)
            self.update_canvas_image()

    def hex_to_rgb(self, color):
        if color.startswith('#'):
            color = color.lstrip('#')
            return tuple(int(color[i:i+2], 16) for i in (0,2,4))
        else:
            r, g, b = self.root.winfo_rgb(color)
            return (r//256, g//256, b//256)

    def draw_line_bresenham(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.image.putpixel((x0, y0), self.hex_to_rgb(color))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_circle_midpoint(self, xc, yc, r, color):
        x = 0
        y = r
        p = 1 - r
        self._plot_circle_points(xc, yc, x, y, color)
        while x < y:
            x += 1
            if p < 0:
                p += 2 * x + 1
            else:
                y -= 1
                p += 2 * (x - y) + 1
            self._plot_circle_points(xc, yc, x, y, color)

    def _plot_circle_points(self, xc, yc, x, y, color):
        points = [
            (xc+x, yc+y), (xc-x, yc+y), (xc+x, yc-y), (xc-x, yc-y),
            (xc+y, yc+x), (xc-y, yc+x), (xc+y, yc-x), (xc-y, yc-x)
        ]
        for px, py in points:
            if 0 <= px < self.canvas_width and 0 <= py < self.canvas_height:
                self.image.putpixel((px, py), self.hex_to_rgb(color))


if __name__ == "__main__":
    root = tk.Tk()
    app = PaintApp(root)
    root.geometry("900x700")
    root.mainloop()
