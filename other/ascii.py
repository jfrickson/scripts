#!/usr/bin/env python3.13

from marshal import version
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import font

ascii_version = "2.0.1"

# Extended ASCII sets with their Python codec names and value ranges
extended_sets = {
    'ISO-8859-1 Extended': {'range': list(range(128, 256)), 'codec': 'latin1'},
    'CP437 Extended': {'range': list(range(128, 256)), 'codec': 'cp437'},
    'CP1252 Extended': {'range': list(range(128, 256)), 'codec': 'cp1252'},
    'MacRoman Extended': {'range': list(range(128, 256)), 'codec': 'mac_roman'},
}

class AsciiTableApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ASCII Table: Decimal')
        self.geometry('460x790')
        self.mono_font = font.Font(family='Courier', size=10)
        self.number_format = 'dec'  # dec, oct, hex
        self.selected_set = None
        self.highlighted = None
        self.highlighted_ext = None
        self.create_widgets()
        self.bind('<Control-q>', lambda e: self.quit())
        self.bind('<Escape>', self.process_escape)
        self.bind('<Right>', self.next_format)
        self.bind('<Left>', self.prev_format)
        self.bind('<Key>', self.key_press)

    def create_widgets(self):
        # Standard ASCII table (always shown)
        ascii_label = tk.Label(self, text="Standard ASCII (32-127)",
                               font=('Arial', 11, 'bold'))
        ascii_label.pack(pady=(10, 0))

        self.ascii_frame = tk.Frame(self)
        self.ascii_frame.pack(pady=5)
        self.ascii_labels = []
        self.ascii_codes = list(range(32, 128))

        # Create ASCII labels once
        rows = [self.ascii_codes[i:i+8] for i in range(0, len(self.ascii_codes), 8)]
        for r, row in enumerate(rows):
            for c, n in enumerate(row):
                label = tk.Label(self.ascii_frame, text='', width=6,
                                  font=self.mono_font, anchor='center',
                                  relief='solid', borderwidth=1)
                label.grid(row=r, column=c, padx=2, pady=2)
                self.ascii_labels.append(label)

        hint_label = tk.Label(
            self,
            text='Press a key to highlight it in the table. Use ⇽/⇾ to switch Decimal, Octal, and Hex.',
            font=('Arial', 8),
            justify='center',
            anchor='center',
        )
        hint_label.pack(pady=(2, 5))

        # Dropdown for extended sets
        self.dropdown_var = tk.StringVar()
        dropdown_width = max(len(key) for key in extended_sets.keys())
        self.dropdown = ttk.Combobox(self, textvariable=self.dropdown_var,
                                     state='readonly', width=dropdown_width)
        self.dropdown['values'] = list(extended_sets.keys())
        self.dropdown.current(0)
        self.dropdown.pack(pady=(10, 5))
        self.dropdown.bind('<<ComboboxSelected>>', self.update_extended_table)

        # Extended ASCII table frame (shown when selected)
        self.extended_frame = tk.Frame(self)
        self.extended_frame.pack(pady=5)
        self.extended_labels = []
        self.extended_codes = list(range(128, 256))

        # Create extended labels once
        rows = [self.extended_codes[i:i+8] for i in range(0, len(self.extended_codes), 8)]
        for r, row in enumerate(rows):
            for c, n in enumerate(row):
                label = tk.Label(self.extended_frame, text='', width=6,
                                  font=self.mono_font, anchor='w',
                                  relief='solid', borderwidth=1)
                label.grid(row=r, column=c, padx=2, pady=2)
                self.extended_labels.append(label)

        self.update_ascii_table()
        self.update_extended_table()

    def process_escape(self, s):
        if self.highlighted is None and self.highlighted_ext is None:
            self.quit()
        self.highlighted = None
        self.highlighted_ext = None
        self.highlight_entry(None, is_extended=False)
        self.highlight_entry(None, is_extended=True)

    def format_number(self, n):
        if self.number_format == 'dec':
            return f'{n:3d}'
        elif self.number_format == 'oct':
            return f'{n:03o}'
        elif self.number_format == 'hex':
            return f'{n:02X}'

    def update_ascii_table(self, event=None):
        if self.number_format == 'dec':
            self.title('ASCII Table: Decimal')
        elif self.number_format == 'oct':
            self.title('ASCII Table: Octal')
        elif self.number_format == 'hex':
            self.title('ASCII Table: Hexadecimal')

        for idx, n in enumerate(self.ascii_codes):
            char = chr(n) if 32 <= n < 128 else ''
            text = f'{self.format_number(n)} {char}'
            if self.highlighted == idx:
                bg = 'yellow'
            else:
                bg = self.cget('bg')
            self.ascii_labels[idx].config(text=text, bg=bg)

    def update_extended_table(self, event=None):
        set_info = extended_sets[self.dropdown_var.get()]
        codec = set_info['codec']

        def get_char(n):
            try:
                return bytes([n]).decode(codec)
            except Exception:
                return '?'

        for idx, n in enumerate(self.extended_codes):
            char = get_char(n)
            text = f'{self.format_number(n)} {char}'
            if self.highlighted_ext == idx:
                bg = 'yellow'
            else:
                bg = self.cget('bg')
            self.extended_labels[idx].config(text=text, bg=bg)

    def next_format(self, event=None):
        formats = ['dec', 'oct', 'hex']
        idx = formats.index(self.number_format)
        self.number_format = formats[(idx + 1) % 3]
        self.update_ascii_table()
        self.update_extended_table()

    def prev_format(self, event=None):
        formats = ['dec', 'oct', 'hex']
        idx = formats.index(self.number_format)
        self.number_format = formats[(idx - 1) % 3]
        self.update_ascii_table()
        self.update_extended_table()

    def key_press(self, event):
        char = event.char
        if not char:
            return
        code = ord(char)

        # Check if in standard ASCII range
        if 32 <= code < 128:
            self.highlight_entry(code, is_extended=False)

        # Check if in extended range (if an extended table is displayed)
        if self.dropdown_var.get() in extended_sets:
            set_info = extended_sets[self.dropdown_var.get()]
            valid_range = set_info['range']
            if code in valid_range:
                self.highlight_entry(code, is_extended=True)

    def highlight_entry(self, code, is_extended=False):
        if is_extended:
            # Clear extended highlights
            for label in self.extended_labels:
                label.config(bg=self.cget('bg'))
            if code is None:
                return
            try:
                set_info = extended_sets[self.dropdown_var.get()]
                idx = set_info['range'].index(code)
                if 0 <= idx < len(self.extended_labels):
                    self.extended_labels[idx].config(bg='yellow')
                    self.highlighted_ext = idx
            except (ValueError, KeyError):
                return
        else:
            # Clear ASCII highlights
            for label in self.ascii_labels:
                label.config(bg=self.cget('bg'))
            if code is None:
                return
            idx = code - 32
            if 0 <= idx < len(self.ascii_labels):
                self.ascii_labels[idx].config(bg='yellow')
                self.highlighted = idx

if __name__ == '__main__':
    if len(sys.argv) > 1:
        sys.argv = sys.argv[1:]  # Remove script name from arguments
        for arg in sys.argv:
            if arg in ('-V', '--version'):
                print(f'\nASCII Table App - Version {ascii_version}\n')
                sys.exit(0)
            else:
                print(f'Unknown argument: {arg}')
                print('Usage: ascii.py [-V|--version]')
                sys.exit(1)

    app = AsciiTableApp()
    app.mainloop()
