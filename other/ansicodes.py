#!/usr/bin/env python3

import sys
import os
import select
import re

if os.name == "nt":
    import msvcrt
else:
    import tty
    import termios
    import fcntl
    from array import array

    FIONREAD = getattr(termios, "FIONREAD", None)

sys.path.insert(0, os.path.expanduser("~/.local/lib/python3.13/site-packages"))
import ansi as a

version = "1.1.0"
csi  = "\x1b["                      # Control Sequence Introducer
dlm  = a.dr                         # delimiters in Bold Red
escl = a.dy + "Esc"                 # "Esc" label in Bold Yellow
val  = a.dc                         # values in Bold Cyan
in_true_color = False               # Flag for true color page
# Regex to match ANSI escape sequences for stripping them from input
ansi_re = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

prmpt = (
    f"{a.B} {a.dr}E{a.w}: EscSeq  "
    f" {a.dr}A{a.w}: Attr  "
    f" {a.dr}F{a.w}: FG256  "
    f" {a.dr}B{a.w}: BG256  "
    f" {a.dr}T{a.w}: TrueClr  "
    f" {a.dr}L{a.w}: LineDraw  "
    f" {a.dr}Q{a.w}: Quit {a.rst}"
)

# True color field definitions. Used by true_color() to print the "T" Page.
tc = {
    'bg1': {
        "hex": "000030",            # hex color code
        "r": 0,                     # RGB color codes
        "g": 0,
        "b": 48,
        "column": 18                # Field start column
    },
    'bg2': {
        "hex": "202060",            # hex color code
        "r": 32,                    # RGB color codes
        "g": 32,
        "b": 96,
        "column": 41                # Field start column
    },
    'fg': {
        "hex": "ff10f3",            # hex color code
        "r": 255,                   # RGB color codes
        "g": 16,
        "b": 243,
        "column": 64                # Field start column
    }
}


# ---------------------------------------------------------------------
#  Debug output
# ---------------------------------------------------------------------
def prt_debug(msg):
    setpos(26, 1)
    sys.stdout.write(f"{csi}KDEBUG: {msg}")
    sys.stdout.flush()


# ---------------------------------------------------------------------
#  Get the number of bytes waiting to be read on a file descriptor.
#  Called by read_key() to consume any pending bytes of an escape
#  sequence.
# ---------------------------------------------------------------------
def bytes_waiting(fd):
    """Return the number of bytes currently queued for this tty fd."""
    if os.name == "nt" or FIONREAD is None:
        return 0

    buf = array("I", [0])
    try:
        fcntl.ioctl(fd, FIONREAD, buf, True)
    except OSError:
        return 0
    return int(buf[0])


# ---------------------------------------------------------------------
#  Read a single keypress (raw mode, no echo) (Linux/Mac version)
# ---------------------------------------------------------------------
def read_key():
    sys.stdout.flush()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        # Use os.read() throughout so all bytes stay on the raw fd.
        # sys.stdin.read() feeds Python's buffer, making FIONREAD/select
        # return 0 even when more sequence bytes are present.
        ch = os.read(fd, 1).decode(errors="ignore")
        # Consume any trailing bytes of an escape sequence so they don't
        # bleed into the next read (e.g. Delete sends 3 bytes after ESC,
        # Shift+Tab sends 3 bytes after ESC).
        if ch == '\x1b':
            seq = []
            while True:
                pending = bytes_waiting(fd)
                if pending == 0:
                    ready, _, _ = select.select([fd], [], [], 0.05)
                    if not ready:
                        break
                    pending = max(bytes_waiting(fd), 1)

                seq.append(os.read(fd, pending).decode(errors="ignore"))
                if sum(len(part) for part in seq) >= 16:
                    break

            ch = "".join(seq)
#            prt_debug(f"Escape sequence read: {ch.encode()}")
        else:
            ch = ch.lower()
#            prt_debug(f"Character read: {ch.encode()}")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

    return ch


# ---------------------------------------------------------------------
#  Read a single keypress (Windows version). Translates special keys
#  into the same escape sequences as the Linux/Mac version for
#  consistency.
# ---------------------------------------------------------------------
def read_key_nt():
    ch = msvcrt.getwch()        # type: ignore
    ch = ch.lower()

    # On Windows consoles, special keys are two-part sequences:
    # prefix (\x00 or \xe0) + a key code.
    if ch in ("\x00", "\xe0"):
        code = msvcrt.getwch()  # type: ignore
        mapping = {
            "K": "[D",          # Left arrow
            "M": "[C",          # Right arrow
            "H": "[A",          # Up arrow
            "P": "[B",          # Down arrow
            "G": "[1~",         # Home
            "O": "[4~",         # End
            "Z": "[Z",          # Shift+Tab (some terminals)
            "\x0f": "[Z",       # Shift+Tab (Windows console code)
            "S": "[3~",         # Delete
            "\x08": "\x7f",     # Backspace (some terminals)
        }
        ch = mapping.get(code, code)
#        prt_debug(f"Special key read: {ch.encode()}") # type: ignore
        return ch

#    prt_debug(f"Character read: {ch.encode()}")
    return ch


# ---------------------------------------------------------------------
#  Set the cursor position
# ---------------------------------------------------------------------
def setpos(row, col):
    sys.stdout.write(f"{csi}{row};{col}H")


# ---------------------------------------------------------------------
#  Return text centered within a field of the given width.
# ---------------------------------------------------------------------
def center_text(row, text, width):
    setpos(row, 1)
    sys.stdout.write(a.el)                  # Clear the line

    visible = ansi_re.sub("", text)         # Number of visible chars in text
    extra = width - len(visible)
    if extra > 1:                           # Calculate left position
        col = extra // 2
    else:
        col = 1

    setpos(row, col)
    sys.stdout.write(text)                  # Write the text


# ---------------------------------------------------------------------
#  Print the header
# ---------------------------------------------------------------------
def print_header():
    val = f"{a.vdbW} ANSI Escape Sequences - version {version} {a.rst}"
    center_text(1, val, 80)


# ---------------------------------------------------------------------
#  Functions to print escape sequences with different numbers of
#  values. Called by esc_seq() to print the "E" Page.
# ---------------------------------------------------------------------
def prt_seq1(row, col, code, label):
    setpos(row, col)
    sys.stdout.write(f"{escl}{dlm}[{val}{code}{a.rst} {label}")


def prt_seq2(row, col, code1, code2, label):
    setpos(row, col)
    sys.stdout.write(f"{escl}{dlm}[{val}{code1}{dlm}{code2}{a.rst} {label}")


def prt_seq3(row, col, code1, code2, code3, label):
    setpos(row, col)
    sys.stdout.write(
        f"{escl}{dlm}[{val}{code1}{dlm};{val}{code2}{dlm}{code3}{a.rst} {label}"
    )


# ---------------------------------------------------------------------
#  Print the escape sequences Page
# ---------------------------------------------------------------------
def esc_seq():
    sys.stdout.write(a.cls)
    print_header()

    setpos(3, 1)
    sys.stdout.write(f" {escl}{a.rst} is \\033 or \\x1b        ")
    sys.stdout.write(f"Delimeters in {dlm}Red{a.rst}        ")
    sys.stdout.write(f"Values in {val}Cyan{a.rst}")

    prt_seq1( 5,  2, "@", "Insert Chars")
    prt_seq1( 5, 29, "A", "Crsr Up")
    prt_seq1( 5, 54, "B", "Crsr Down")
    prt_seq1( 6,  2, "C", "Crsr Forward")
    prt_seq1( 6, 29, "D", "Crsr Backward")
    prt_seq1( 6, 54, "E", "Crsr next line")
    prt_seq1( 7,  2, "F", "Crsr prev line")
    prt_seq1( 7, 29, "G", "Crsr to col")
    prt_seq1( 7, 54, "J", f"Erase Display {a.dm}*{a.rst}")
    prt_seq1( 8,  2, "K", f"Erase Line {a.dm}*{a.rst}")
    prt_seq1( 8, 29, "L", "Insert Lines")
    prt_seq1( 8, 54, "M", "Delete Lines")
    prt_seq1( 9,  2, "P", "Delete Chars")
    prt_seq1( 9, 29, "S", "Scroll Up")
    prt_seq1( 9, 54, "T", "Scroll Down")
    prt_seq1(10,  2, "d", "Crsr to Row")

    setpos(10, 29)
    sys.stdout.write(f"{escl}{dlm}[{val}?25{dlm}l{a.rst} Cursor Off")
    setpos(10, 54)
    sys.stdout.write(f"{escl}{dlm}[{val}?25{dlm}h{a.rst} Cursor On")

    prt_seq1(12,  2, "s", "Save Crsr Pos")
    prt_seq1(12, 29, "u", "Rstr Crsr Pos")
    prt_seq3(12, 54, "Row", "Col", "H", "Set Pos")

    prt_seq2(14,  2, "N", "b", f"Repeat Prev Char {val}N{a.rst} times")
    setpos(14, 35)
    sys.stdout.write(
        f"{escl}{dlm}[{val}Val{dlm};{val}...{dlm};{val}Val{dlm}m{a.rst}"
    )
    sys.stdout.write(f" Attr & colors {a.dB}(Menu A){a.rst}")

    setpos(16, 2)
    sys.stdout.write(f"{a.dm}* {val}Val{a.rst} for Erase Disp/Line - ")
    sys.stdout.write(f"{val}0{a.rst} or none: to end   {val}1{a.rst}: to beginning")
    sys.stdout.write(f"   {val}2{a.rst}: all")

    sys.stdout.flush()


# ---------------------------------------------------------------------
#  Functions to print the attribute & color sequeces. Called by
#  attributes() to print the "A" Page.
# ---------------------------------------------------------------------
def print_attr1(row, col, code, label):
    setpos(row, col)
    sys.stdout.write(f"{val}{code}{a.rst}: {csi}{code}m{label}{a.rst}")

def print_attr2(value, label, attr):
    sys.stdout.write(f"{val}{value}{a.rst} {attr}{label}{a.rst} ")


# ---------------------------------------------------------------------
#  Print the escape sequences Page
# ---------------------------------------------------------------------
def attributes():
    sys.stdout.write(a.cls)
    print_header()

    setpos(4, 19)
    sys.stdout.write(f"{a.dc}Set Attributers & Colors:{a.rst} ")
    sys.stdout.write(f"{escl}{dlm}[{val}Val{dlm};{val}...{dlm};{val}Val{dlm}m{a.rst}")

    setpos(6, 2)
    sys.stdout.write(f"{a.dc}{a.u}Text attributes:{a.rst}")
    print_attr1( 8,  2, 0, "All off")
    print_attr1( 8, 17, 1, "Bold")
    print_attr1( 8, 32, 2, "Dim")
    print_attr1( 8, 46, 3, "Italic")
    print_attr1( 8, 61, 4, "Underscore")
    print_attr1( 9,  2, 5, "Blink")
    print_attr1( 9, 17, 7, "Reverse")
    print_attr1( 9, 32, 8, "Hidden")
    print_attr1( 9, 46, 9, "Strike")
    print_attr1( 9, 60, 21, "Dbl Underline")

    subheader = f"{a.dc}{a.u}16 Color Sequences:{a.rst}"
    center_text(11, subheader, 80)

    setpos(12, 2)
    sys.stdout.write(f"{a.dc}{a.u}Foreground Colors:{a.rst}")

    setpos(14, 2)
    print_attr2("30", "Black", f"{a.d}{a.v}")
    print_attr2("31", "Red", a.r)
    print_attr2("32", "Green", a.g)
    print_attr2("33", "Yellow", a.y)
    print_attr2("34", "Blue", f"{a.db}{a.W}")
    print_attr2("35", "Magenta", a.m)
    print_attr2("36", "Cyan", a.c)
    print_attr2("37", "White", a.w)

    setpos(16, 13)
    sys.stdout.write(f"{escl}{dlm}[{a.rst}38;5;{val}xxx{dlm}m{a.rst} - ")
    sys.stdout.write(f"xxx = Foreground 256 color code {a.dB}(Menu F){a.rst}")

    setpos(18, 2)
    sys.stdout.write(f"{a.dc}{a.u}Background Colors:{a.rst}")

    setpos(20, 2)
    print_attr2("40", "Black", a.K)
    print_attr2("41", "Red", a.R)
    print_attr2("42", "Green", f"{a.G}{a.k}")
    print_attr2("43", "Yellow", f"{a.Y}{a.k}")
    print_attr2("44", "Blue", a.B)
    print_attr2("45", "Magenta", a.M)
    print_attr2("46", "Cyan", f"{a.C}{a.k}")
    print_attr2("47", "White", f"{a.W}{a.k}")

    setpos(22, 13)
    sys.stdout.write(f"{escl}{dlm}[{a.rst}48;5;{val}xxx{dlm}m{a.rst} - ")
    sys.stdout.write(f"xxx = Background 256 color code {a.dB}(Menu B){a.rst}")

    sys.stdout.flush()


# ---------------------------------------------------------------------
#  Print the 256 color foreground codes
# ---------------------------------------------------------------------
def fg_256_color():
    fg  = "\x1b[38;5;"
    c = 16
    n = 0

    sys.stdout.write(a.cls)
    print_header()

    setpos(5, 1)
    sys.stdout.write(f" {a.u}{a.dc}256 Foreground Colors{a.rst}   ")
    sys.stdout.write(f"{escl}{dlm}[{val}38;5;xxx{dlm}m{a.rst} - xxx = 256 color code{a.rst}")
    sys.stdout.write("\n\n\n")

    while c <= 255:
        if c < 24:
            sys.stdout.write(a.W)
        elif c < 52:
            sys.stdout.write(a.K)
        elif c < 58:
            sys.stdout.write(a.W)
        elif c < 232:
            sys.stdout.write(a.K)
        elif c < 242:
            sys.stdout.write(a.W)
        else:
            sys.stdout.write(a.K)

        sys.stdout.write(f"{fg}{c}m{c:3d} {a.rst}")
        c += 1
        n += 1
        if n == 20:
            sys.stdout.write(a.rst + "\n")
            n = 0

        sys.stdout.write(a.rst)

    sys.stdout.flush()


# ---------------------------------------------------------------------
#  Print the 256 color background codes
# ---------------------------------------------------------------------
def bg_256_color():
    c = 16
    n = 0

    sys.stdout.write(a.cls)
    print_header()

    setpos(5, 1)
    sys.stdout.write(f" {a.u}{a.dc}256 Background Colors{a.rst}   ")
    sys.stdout.write(f"{escl}{dlm}[{val}48;5;xxx{dlm}m{a.rst} - xxx = 256 color code{a.rst}")
    sys.stdout.write("\n\n\n")

    while c <= 255:
        if c < 32:
            sys.stdout.write(a.W)
        elif c < 52:
            sys.stdout.write(a.K)
        elif c < 60:
            sys.stdout.write(a.W)
        elif c < 88:
            sys.stdout.write(a.K)
        elif c < 95:
            sys.stdout.write(a.W)
        elif c < 232:
            sys.stdout.write(a.K)
        elif c < 242:
            sys.stdout.write(a.W)
        else:
            sys.stdout.write(a.K)

        sys.stdout.write(f"{csi}48;5;{c}m{c:3d} {a.rst}")
        c += 1
        n += 1
        if n == 20:
            sys.stdout.write(a.rst + "\n")
            n = 0

    sys.stdout.flush()


# ---------------------------------------------------------------------
#  Print the line-drawing characters
# ---------------------------------------------------------------------
def line_draw():
    ent_grp = "\x1b(0"              # Enter line-drawing mode
    ext_grp = "\x1b(B"              # Exit line-drawing mode

    sys.stdout.write(a.cls)
    print_header()

    subheader = f"{a.dc}{a.u}Line-Drawing Characters{a.rst} - " \
                f"{escl}{dlm}(0{a.rst} <characters> {escl}{dlm}(B{a.rst}"
    center_text(4, subheader, 80)

    # Top row
    setpos(6, 31)
    sys.stdout.write(f"{val}l  q  q  w  q  q  k{a.rst}")

    setpos(7, 31)
    sys.stdout.write(f"{ent_grp}l  q  q  w  q  q  k{ext_grp}")

    # Empty row
    setpos(9, 29)
    sys.stdout.write(f"{val}x{a.rst} {ent_grp}x{ext_grp}      "
                    f"{val}x{a.rst} {ent_grp}x{ext_grp}        "
                    f"{ent_grp}x{ext_grp} {val}x{a.rst}")

    # Line across row
    setpos(10, 34)
    sys.stdout.write(f"{val}q  q  n  q  q{a.rst}")
    setpos(11, 29)
    sys.stdout.write(f"{val}t{a.rst} {ent_grp}t  q  q  "
                     f"q  q  q  u{ext_grp} {val}u{a.rst}")

    # Empty row
    setpos(13, 29)
    sys.stdout.write(f"{val}x{a.rst} {ent_grp}x{ext_grp}      "
                    f"{val}x{a.rst} {ent_grp}x{ext_grp}        "
                    f"{ent_grp}x{ext_grp} {val}x{a.rst}")

    # Bottom row
    setpos(15, 29)
    sys.stdout.write(f"{val}m{a.rst} {ent_grp}m  q  q  "
                     f"v  q  q  j{ext_grp} {val}j{a.rst}")
    setpos(16, 34)
    sys.stdout.write(f"{val}q  q  v  q  q{a.rst}")

    # Other chars
    setpos(20, 26)
    sys.stdout.write(f"{val}a{a.rst} {ent_grp}a{ext_grp}"
                     f"  {val}d{a.rst} {ent_grp}d{ext_grp}"
                     f"  {val}o{a.rst} {ent_grp}o{ext_grp}"
                     f"  {val}q{a.rst} {ent_grp}q{ext_grp}"
                     f"  {val}r{a.rst} {ent_grp}r{ext_grp}"
                     f"  {val}s{a.rst} {ent_grp}s{ext_grp}")

    sys.stdout.write(a.rst)


# ---------------------------------------------------------------------
#  Print the true color demo page
# ---------------------------------------------------------------------
def true_color():
    sys.stdout.write(a.cls)
    print_header()

    setpos(3, 10)
    txt = f"{a.u}{a.dc}True Color Sequences{a.rst} - R, G, B = color values"
    center_text(3, txt, 80)
    txt = f"{escl}{dlm}[{val}XX{dlm};{val}2{dlm};" \
          f"{val}R{dlm};{val}G{dlm};{val}B{dlm}m{a.rst}" \
          " - xx: FG=38  BG=48"
    center_text(4, txt, 80)

    setpos(7, 12)
    sys.stdout.write(f"{a.dc}{a.u}B/G Colors 1{a.rst}")
    setpos(8, 12)
    sys.stdout.write(f"Hex   {a.dB}      {a.rst}")
    setpos(9, 12)
    sys.stdout.write(f"Red   {a.dB}   {a.rst}")
    setpos(10, 12)
    sys.stdout.write(f"Green {a.dB}   {a.rst}")
    setpos(11, 12)
    sys.stdout.write(f"Blue  {a.dB}   {a.rst}")

    setpos(7, 35)
    sys.stdout.write(f"{a.dc}{a.u}B/G Colors 2{a.rst}")
    setpos(8, 35)
    sys.stdout.write(f"Hex   {a.dB}      {a.rst}")
    setpos(9, 35)
    sys.stdout.write(f"Red   {a.dB}   {a.rst}")
    setpos(10, 35)
    sys.stdout.write(f"Green {a.dB}   {a.rst}")
    setpos(11, 35)
    sys.stdout.write(f"Blue  {a.dB}   {a.rst}")

    setpos(7, 58)
    sys.stdout.write(f"{a.dc}{a.u}F/G Colors{a.rst}")
    setpos(8, 58)
    sys.stdout.write(f"Hex   {a.dB}      {a.rst}")
    setpos(9, 58)
    sys.stdout.write(f"Red   {a.dB}   {a.rst}")
    setpos(10, 58)
    sys.stdout.write(f"Green {a.dB}   {a.rst}")
    setpos(11, 58)
    sys.stdout.write(f"Blue  {a.dB}   {a.rst}")

    edit_prompt = f"{a.dg}Press {a.dr}C{a.dg} to edit colors{a.rst}"
    center_text(13, edit_prompt, 80)

    setpos(13, 19)
    sys.stdout.write(f"{a.dw}{a.K}")
    sys.stdout.write("┌────────────────────────────────────────┐")
    setpos(14, 19)
    sys.stdout.write("│                                        │")
    setpos(15, 19)
    sys.stdout.write("│                                        │")
    setpos(16, 19)
    sys.stdout.write("│                                        │")
    setpos(17, 19)
    sys.stdout.write("│                                        │")
    setpos(18, 19)
    sys.stdout.write("│                                        │")
    setpos(19, 19)
    sys.stdout.write("│                                        │")
    setpos(20, 19)
    sys.stdout.write(f"└────────────────────────────────────────┘{a.rst}")

    fill_colors()


# ---------------------------------------------------------------------
#  Fill the color fields with the current values and draw the
#  gradient box
# ---------------------------------------------------------------------
def fill_colors():
    for key in tc:
        col = tc[key]["column"]
        r = tc[key]["r"]
        g = tc[key]["g"]
        b = tc[key]["b"]
        hex_color = tc[key]["hex"]

        setpos(8, col)
        sys.stdout.write(f"{a.dB}{hex_color:<6}{a.rst}")
        setpos(9, col)
        sys.stdout.write(f"{a.dB}{r:<3}{a.rst}")
        setpos(10, col)
        sys.stdout.write(f"{a.dB}{g:<3}{a.rst}")
        setpos(11, col)
        sys.stdout.write(f"{a.dB}{b:<3}{a.rst}")

    draw_interior()


# ---------------------------------------------------------------------
#  Draw the interior gradient box
# ---------------------------------------------------------------------
def draw_interior():
    # Diagonal gradient: top-left = bg1, bottom-right = bg2.
    # Use float interpolation to avoid integer-truncation
    # killing the gradient on small color ranges.
    bg1 = tc['bg1']
    bg2 = tc['bg2']
    fg  = tc['fg']
    fr = fg['r']; fg_g = fg['g']; fb = fg['b']

    # (row, col, text) using 1-based row/col inside the 6x40 interior.
    overlay = {
        2: (14, "At the beach,"),
        3: (11, "the Real Programmer"),
        4: (13, "draws flowcharts"),
        5: (7, "where the tide can't commit."),
    }

    buf = []
    for row in range(6):
        t_v = row / 5           # 0.0 (top) → 1.0 (bottom)
        buf.append(f"{csi}{14 + row};20H")
        text_start = -1
        text = ""
        if (row + 1) in overlay:
            text_start, text = overlay[row + 1]
            text_start -= 1

        for col in range(40):
            t_h = col / 39      # 0.0 (left) → 1.0 (right)
            t = (t_v + t_h) / 2
            r = round(bg1['r'] + t * (bg2['r'] - bg1['r']))
            g = round(bg1['g'] + t * (bg2['g'] - bg1['g']))
            b = round(bg1['b'] + t * (bg2['b'] - bg1['b']))
            ch = " "
            if text and text_start <= col < text_start + len(text):
                ch = text[col - text_start]

            buf.append(f"\x1b[38;2;{fr};{fg_g};{fb}m\x1b[48;2;{r};{g};{b}m{ch}")

    sys.stdout.write("".join(buf) + a.rst)
    sys.stdout.flush()


# ---------------------------------------------------------------------
#  Input colors for the true color page. Allows editing the hex
#  and RGB values
# ---------------------------------------------------------------------
def input_colors():
    edit_prompt = f"{a.dg}Press {a.dr}Enter{a.dg} when finished," \
                 f" {a.dr}Tab{a.dg} to switch fields{a.rst}"
    center_text(13, edit_prompt, 80)

    row = 8
    grp = 'bg1'
    col = tc[grp]["column"]
    fld_ndx = 0
    is_err = False
    cur_value = ''
    color = ''

    while True:
        if is_err:                          # Set the error color if needed
            number_error(row, col, grp, True)
        setpos(row, col + fld_ndx)          # Set cursor position for input

        # Get a keypress. Windows and Linux/Mac versions return the
        # same escape sequences for special keys for consistency.
        if os.name == "nt":
            char = read_key_nt()
        else:
            char = read_key()

        if is_err:                          # Clear the error color if needed
            number_error(row, col, grp, False)
            is_err = False
        setpos(row, col + fld_ndx)

        # Get the current value and field info for the field being edited
        if row == 8:
            cur_value = tc[grp]["hex"]
            color = "hex"
        else:
            if row == 9:color = "r"
            elif row == 10: color = "g"
            else: color = "b"
            cur_value = str(tc[grp][color])

        # -------------------- Handle the keypress --------------------

        if char in ("\r", "\n"):            # Enter key - finish editing
            edit_prompt = f"{a.dg}Press {a.dr}C{a.dg} to edit colors{a.rst}"
            center_text(13, edit_prompt, 80)
            break

        elif char in ("\t","[B"):           # Tab key/DN - move to next field
            # Move to next field
            if row == 8:          row = 9
            elif row == 9:        row = 10
            elif row == 10:       row = 11
            elif grp == 'bg1':
                grp = 'bg2'
                row = 8
            elif grp == 'bg2':
                grp = 'fg'
                row = 8
            elif grp == 'fg':
                grp = 'bg1'
                row = 8
            col = tc[grp]["column"]
            fld_ndx = 0

        elif char in ("[Z", "[A"):          # Shift+Tab/UP - move to previous field
            # Move to previous field
            if row == 11:     row = 10
            elif row == 10:   row = 9
            elif row == 9:    row = 8
            elif row == 8:
                if grp == 'fg':
                    grp = 'bg2'
                    row = 11
                elif grp == 'bg2':
                    grp = 'bg1'
                    row = 11
                elif grp == 'bg1':
                    grp = 'fg'
                    row = 11
            col = tc[grp]["column"]
            fld_ndx = 0

        elif char == "[C":                  # Right arrow
            if  row == 8 and fld_ndx < 5:   # Move within fields
                fld_ndx += 1
            elif fld_ndx < 2 and fld_ndx < len(cur_value):
                fld_ndx += 1

        elif char == "[D":                  # Left arrow
            if fld_ndx > 0:                 # Move within fields
                fld_ndx -= 1

        elif char == "[1~":                 # Home key
            fld_ndx = 0

        elif char == "[4~":                 # End key
            if row == 8:                    # Move to end of hex fields
                fld_ndx = 5
            else:
                fld_ndx = min(len(cur_value), 2)

        elif char == "[3~":                 # Delete key
            if row != 8 and fld_ndx < len(cur_value):
                cur_value = cur_value[:fld_ndx] + cur_value[fld_ndx + 1:]
                value = int(cur_value) if cur_value else 0
                tc[grp][color] = value

                hex_value = f"{tc[grp]['r']:02x}{tc[grp]['g']:02x}{tc[grp]['b']:02x}"
                tc[grp]["hex"] = hex_value
                fill_colors()

        elif char in ("\x7f", "\b"):        # Backspace key
            if row != 8 and fld_ndx > 0:
                cur_value = cur_value[:fld_ndx - 1] + cur_value[fld_ndx:]
                value = int(cur_value) if cur_value else 0
                tc[grp][color] = value
                fld_ndx -= 1

                hex_value = f"{tc[grp]['r']:02x}{tc[grp]['g']:02x}{tc[grp]['b']:02x}"
                tc[grp]["hex"] = hex_value
                fill_colors()

        elif row == 8 and char in ("abcdef0123456789"):  # Valid hex digit
            # Update the value in tc and the display
            cur_value = cur_value[:fld_ndx] + char + cur_value[fld_ndx + 1:]
            tc[grp]["hex"] = cur_value
            r = int(cur_value[0:2], 16)
            g = int(cur_value[2:4], 16)
            b = int(cur_value[4:6], 16)
            tc[grp]["r"] = r
            tc[grp]["g"] = g
            tc[grp]["b"] = b

            if fld_ndx < 5: fld_ndx += 1    # Move to next hex digit
            fill_colors()                   # Update the display with new colors

        elif row > 8 and char in "0123456789":   # Valid decimal digit
            cur_value = cur_value[:fld_ndx] + char + cur_value[fld_ndx + 1:]
            value = int(cur_value)
            if value < 0: value = 0
            elif value > 255:
                is_err = True
                continue

            tc[grp][color] = value
            hex_value = f"{tc[grp]['r']:02x}{tc[grp]['g']:02x}{tc[grp]['b']:02x}"
            tc[grp]["hex"] = hex_value

            tmp = str(value)
            tmp2 = len(tmp)
            fld_ndx = len(str(value))       # Move to next digit
            if fld_ndx > 2: fld_ndx = 2
            fill_colors()                   # Update the display with new colors


# ---------------------------------------------------------------------
#  Display an error background color for invalid number input
# ---------------------------------------------------------------------
def number_error(row, col, grp, set):
    setpos(row, col)
    nc = 6 if row == 8 else 3
    if row == 8:    fld = 'hex'
    elif row == 9:  fld = 'r'
    elif row == 10: fld = 'g'
    else: fld = 'b'
    value_str = str(tc[grp][fld])
    value_str += " " * (nc - len(value_str))
    clr = a.err if set else a.dB
    sys.stdout.write(f"{clr}{value_str}{a.rst}")



# ---------------------------------------------------------------------
#  Main loop
# ---------------------------------------------------------------------
def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-V", "--version"):
        print(f"\n{a.dg}ANSI Escape Sequences - Version {version}{a.rst}\n")
        sys.exit(0)

    opt = sys.argv[1] if len(sys.argv) > 1 else "e"
    in_true_color = False

    while True:
        if   opt != "c": in_true_color = False
        if   opt == "e": esc_seq()
        elif opt == "a":  attributes()
        elif opt == "f":  fg_256_color()
        elif opt == "b":  bg_256_color()
        elif opt == "l":  line_draw()
        elif opt == "t":
            in_true_color = True
            true_color()
        elif opt == "c":
            if in_true_color: input_colors()

        # "ansi.py e q" — show one screen and quit
        if len(sys.argv) > 2 and sys.argv[2] == "q":
            print("\n")
            sys.exit(0)

        setpos(24, 1)
        sys.stdout.write(prmpt)

        opt = read_key()
        if opt == "q":
            print("\n")
            sys.exit(0)

if __name__ == "__main__":
    main()
