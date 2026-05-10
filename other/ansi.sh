#!/bin/bash

PATH="${HOME}/.local/lib/bash:${PATH}"
. Ansi

version="1.0.3"

dlm="${_dr}"
# ds="${dlm};"
escl="${_dy}Esc"
val="${_dc}"
printf -v col2 "\e[2G"

prmpt="${_B} ${_dr}E${_w}: Esc Seqs  "
prmpt="${prmpt}${_dr}A${_w}: Attrib  "
prmpt="${prmpt}${_dr}F${_w}: 256 Clr FG  "
prmpt="${prmpt}${_dr}B${_w}: 256 Clr BG  "
prmpt="${prmpt}${_dr}L${_w}: Line-draw  "
prmpt="${prmpt}${_dr}Q${_w}: Quit ${_rst}"

_setpos()
{
    printf "\e[%s;%sH" "$1" "$2"
}

_prt_seq1()
{
	_setpos "$1" "$2"
	printf "%s%s[%s%s %s" \
		"${escl}" "${dlm}" "$3" "${_rst}" "$4"
}

_prt_seq2()
{
	_setpos "$1" "$2"
	printf "%s%s[%s%s%s%s %s" \
		"${escl}" "${dlm}" "${val}" "${dlm}" "$3" "${_rst}" "$4"
}

_prt_seq3()
{
	_setpos "$1" "$2"
	printf "%s%s[${val}%s%s;%s%s%s%s%s" \
		"${escl}" "${dlm}" "$3" "${dlm}" "${val}" "$4" "${dlm}" "$5" "${_rst}"
	_setpos "$1" "$(( $2 + 17 ))"
	printf "%s" "$6"
}

_esc_seq()
{
	printf "%s" "${_cls}"
	_setpos 1 30
	printf "%s ANSI Escape Sequences %s" "${_vdbW}" "${_rst}"

	_setpos 5 1
	printf " %s%s is \\\\033 or \\\\x1b        " "${escl}" "${_rst}"
	printf "Delimeters in %sRed%s        " "${dlm}" "${_rst}"
	printf "Numbers in %sCyan%s" "${val}" "${_rst}"

	_prt_seq2  7  2 "@" "Insert Chars"
	_prt_seq2  7 29 A "Crsr Up"
	_prt_seq2  7 54 B "Crsr Down"
	_prt_seq2  8  2 C "Crsr Forward"
	_prt_seq2  8 29 D "Crsr Backward"
	_prt_seq2  8 54 E "Crsr next line"
	_prt_seq2  9  2 F "Crsr prev line"
	_prt_seq2  9 29 G "Crsr to col"
	_prt_seq2  9 54 J "Erase Display*"
	_prt_seq2 10  2 K "Erase Line*"
	_prt_seq2 10 29 L "Insert Lines"
	_prt_seq2 10 54 M "Delete Lines"
	_prt_seq2 11  2 P "Delete Chars"
	_prt_seq2 11 29 S "Scroll Up"
	_prt_seq2 11 54 T "Scroll Down"
	_prt_seq2 12  2 d "Crsr to Row"
	_setpos 12 29
	printf "%s%s[%s?25%sl%s Cursor Off" "${escl}" "${dlm}" "${val}" "${dlm}" "${_rst}"
	_setpos 12 54
	printf "%s%s[%s?25%sh%s Cursor On" "${escl}" "${dlm}" "${val}" "${dlm}" "${_rst}"
	_prt_seq1 13  2 s "Save Crsr Pos"
	_prt_seq1 13 29 u "Rstr Crsr Pos"

	_prt_seq3 15  2 Row Col H "Set Crsr Pos"
	_prt_seq2 15 45 b "Repeat Prev Char n times"
	_setpos 16 2
	printf "%s%s[%sVal%s;%s...%s;%sVal%sm%s" \
		"${escl}" "${dlm}" "${val}" "${dlm}" "${val}" "${dlm}" "${val}" "${dlm}" "${_rst}"
	printf " Attr & colors %s(Menu A)%s" "${_dB}" "${_rst}"

	_setpos 19 5
	printf "%s* %sVal%s for Erase Disp/Line - " "${_d}" "${val}" "${_rst}"
	printf "%s0%s or none: to end   %s1%s: to beginning" "${val}" "${_rst}" "${val}" "${_rst}"
	printf "   %s2%s: all" "${val}" "${_rst}"
}

_prt_attr1()
{
	_setpos "$1" "$2"
	printf "%s%s%s: \e[%sm%s${_rst}" "${val}" "${3}" "${_rst}" "${3}" "${4}"
}

_attributes()
{
	printf "%s" "${_cls}"
	_setpos 2 30
	printf "%s ANSI Escape Sequences %s" "${_vdbW}" "${_rst}"

	_setpos 4 18
	printf "%sSet Attributers & Colors:%s " "${_dc}" "${_rst}"
	printf "%s%s[%sVal%s;%s...%s;%sVal%sm%s" \
		"${escl}" "${dlm}" "${val}" "${dlm}" "${val}" "${dlm}" "${val}" "${dlm}" "${_rst}"

	_setpos 6 2
	printf "%s%sText attributes%s\n" "${_dc}" "${_u}" "${_rst}"
	_prt_attr1  8  2 0 "All off"
	_prt_attr1  8 17 1 Bold
	_prt_attr1  8 32 2 Dim
	_prt_attr1  8 46 3 Italic
	_prt_attr1  8 61 4 Underscore
	_prt_attr1  9  2 5 Blink
	_prt_attr1  9 17 7 Reverse
	_prt_attr1  9 32 8 Hidden
	_prt_attr1  9 46 9 Strike
	_prt_attr1  9 60 21 "Dbl Underline"

	_setpos 11 30
	printf "%s%s16 Color Sequences%s" "${_dc}" "${_u}" "${_rst}"

	_setpos 12 2
	printf "%s%sForeground Colors%s" "${_dc}" "${_u}" "${_rst}"
	_setpos 14 2
	printf "%s30%s %s%sBlack%s" "${val}" "${_rst}" "${_d}" "${_v}" "${_rst}"
	printf " %s31%s %sRed%s" "${val}" "${_rst}" "${_r}" "${_rst}"
	printf " %s32%s %sGreen%s" "${val}" "${_rst}" "${_g}" "${_rst}"
	printf " %s33%s %sYellow%s" "${val}" "${_rst}" "${_y}" "${_rst}"
	printf " %s34%s %s%sBlue%s" "${val}" "${_rst}" "${_db}" "${_W}" "${_rst}"
	printf " %s35%s %sMagenta%s" "${val}" "${_rst}" "${_m}" "${_rst}"
	printf " %s36%s %sCyan%s" "${val}" "${_rst}" "${_c}" "${_rst}"
	printf " %s37%s White" "${val}" "${_rst}"

	_setpos 16 13
	printf "%s%s[%s48;5;%sxxx%sm%s - xxx = foreground 256 color code %s(Menu F)%s" \
		"${escl}" "${dlm}" "${_rst}" "${val}" "${dlm}" "${_rst}" "${_dB}" "${_rst}"

	_setpos 18 2
	printf "%s%sBackground Colors%s" "${_dc}" "${_u}" "${_rst}"
	_setpos 20 2
	printf "%s40%s Black" "${val}" "${_rst}"
	printf " %s41%s %sRed%s" "${val}" "${_rst}" "${_R}" "${_rst}"
	printf " %s42%s %s%sGreen%s" "${val}" "${_rst}" "${_G}" "${_k}" "${_rst}"
	printf " %s43%s %s%sYellow%s" "${val}" "${_rst}" "${_Y}" "${_k}" "${_rst}"
	printf " %s44%s %sBlue%s" "${val}" "${_rst}" "${_B}" "${_rst}"
	printf " %s45%s %sMagenta%s" "${val}" "${_rst}" "${_M}" "${_rst}"
	printf " %s46%s %s%sCyan%s" "${val}" "${_rst}" "${_C}" "${_k}" "${_rst}"
	printf " %s47%s %s%sWhite%s\n" "${val}" "${_rst}" "${_W}" "${_k}" "${_rst}"
	_setpos 22 13
	printf "%s%s[%s38;5;%sxxx%sm%s - xxx = background 256 color code %s(Menu B)%s" \
		"${escl}" "${dlm}" "${_rst}" "${val}" "${dlm}" "${_rst}" "${_dB}" "${_rst}"
}

_line_draw()
{
	local ent_grp, ext_grp
	printf -v ent_grp "\e(0"
	printf -v ext_grp "\e(B"

	printf "%s" "${_cls}"
	_setpos 2 28
	printf "%s ANSI Escape Sequences %s" "${_vdbW}" "${_rst}"

	_setpos 6 1
	printf "  %s%sLine-Drawing Characters%s - " "${_dc}" "${_u}" "${_rst}"
	printf "%s%s(0%s <characters> %s%s(B%s" \
		"${escl}" "${dlm}" "${_rst}" "${escl}" "${dlm}" "${_rst}"

	# Top row
	_setpos 8 17
	printf "%sl  q  q  w  q  q  k%s" "${val}" "${_rst}"

	_setpos 9 17
	printf "%sl  q  q  w  q  q  k%s" "${ent_grp}" "${ext_grp}"

	# Empty row
	_setpos 11 15
	printf "%sx%s %sx%s      %sx%s %sx%s        %sx%s %sx%s" \
		"${val}" "${_rst}" "${ent_grp}" "${ext_grp}" "${val}" "${_rst}" \
		"${ent_grp}" "${ext_grp}" "${ent_grp}" "${ext_grp}" "${val}" "${_rst}"

	# Line across row
	_setpos 12 20
	printf "%sq  q  n  q  q%s" "${val}" "${_rst}"
	_setpos 13 15
	printf "%st%s %st" "${val}" "${_rst}" "${ent_grp}"
	printf "  q  q  n  q  q  u%s %su%s" "${ext_grp}" "${val}" "${_rst}"

	# Empty row
	_setpos 15 15
	printf "%sx%s %sx%s      %sx%s %sx%s        %sx%s %sx%s" \
		"${val}" "${_rst}" "${ent_grp}" "${ext_grp}" "${val}" "${_rst}" \
		"${ent_grp}" "${ext_grp}" "${ent_grp}" "${ext_grp}" "${val}" "${_rst}"

	# Bottom row
	_setpos 17 15
	printf "%sm%s %sm" "${val}" "${_rst}" "${ent_grp}"
	printf "  q  q  v  q  q  j%s %sj%s" "${ext_grp}" "${val}" "${_rst}"
	_setpos 18 20
	printf "%sq  q  v  q  q%s" "${val}" "${_rst}"

	# Other chars
	_setpos 21 13
	printf "%sa%s %sa%s" "${val}" "${_rst}" "${ent_grp}" "${ext_grp}"
	printf "  %sd%s %sd%s" "${val}" "${_rst}" "${ent_grp}" "${ext_grp}"
	printf "  %so%s %so%s" "${val}" "${_rst}" "${ent_grp}" "${ext_grp}"
	printf "  %sq%s %sq%s" "${val}" "${_rst}" "${ent_grp}" "${ext_grp}"
	printf "  %sr%s %sr%s" "${val}" "${_rst}" "${ent_grp}" "${ext_grp}"
	printf "  %ss%s %ss%s" "${val}" "${_rst}" "${ent_grp}" "${ext_grp}"
}


_256_color_fg()
{
	_fg=$(echo -en "\e[38;5;")

	c=16
	n=0

	printf "%s" "${_cls}"
	_setpos 2 28
	printf "%s ANSI Escape Sequences %s" "${_vdbW}" "${_rst}"

	_setpos 5 1
	printf " %s%s256 Foreground Colors%s" "${_u}" "${_dc}" "${_rst}"
	printf "   %s%s[%s38;5;%sx%sm%s - x = 256 color code%s" \
		"${escl}" "${dlm}" "${_rst}" "${val}" "${dlm}" "${_dw}" "${_rst}"
	printf "\n\n\n"
	while [[ ${c} -le 255 ]]; do
		if (( c<24 )); then printf "%s" "${_W}"
		elif (( c<52 )); then printf "%s" "${_K}"
		elif (( c<58 )); then printf "%s" "${_W}"
		elif (( c<232 )); then printf "%s" "${_K}"
		elif (( c<242 )); then printf "%s" "${_W}"
		else printf "%s" "${_K}"
		fi

		printf "%s%sm%3d " "${_fg}" "${c}" "${c}"
		((c++))
		((n++))
		if [[ ${n} -eq 20 ]]; then
			printf "%s\n" "${_rst}"
			n=0
		fi
	done

	printf "%s" "${_rst}"
}

_256_color_bg()
{
	_bg=$(echo -en "\e[48;5;")

	c=16
	n=0

	printf "%s" "${_cls}"
	_setpos 2 26
	printf "%s ANSI Escape Sequences %s" "${_vdbW}" "${_rst}"

	_setpos 5 1

	printf " %s%s256 Background Colors%s" "${_u}" "${_dc}" "${_rst}"
	printf "   %s%s[%s48;5;%sx%sm%s - x = 256 color code%s" \
		"${escl}" "${dlm}" "${_rst}" "${val}" "${dlm}" "${_dw}" "${_rst}"
	printf "\n\n\n"
	while [[ ${c} -le 255 ]]; do
		if (( c<32 )); then printf "%s" "${_w}"
		elif (( c<52 )); then printf "%s" "${_k}"
		elif (( c<60 )); then printf "%s" "${_w}"
		elif (( c<88 )); then printf "%s" "${_k}"
		elif (( c<95 )); then printf "%s" "${_w}"
		elif (( c<232 )); then printf "%s" "${_k}"
		elif (( c<242 )); then printf "%s" "${_w}"
		else printf "%s" "${_k}"
		fi

		printf "%s%sm%3d " "${_bg}" "${c}" "${c}"
		((c++))
		((n++))
		if [[ ${n} -eq 20 ]]; then
			printf "%s\n" "${_rst}"
			n=0
		fi
	done

	printf "%s" "${_rst}"
}

if [[ "${1}" = "-V" || "${1}" = "--version" ]]; then
	printf "\n%sANSI Escape Sequences - Version %s%s\n\n" "${_dg}" "${version}" "${_rst}"
	exit 0
fi

if [[ -n "${1}" ]]; then opt="$1"; else opt=e; fi

while true; do
	case ${opt} in
		e|E) _esc_seq ;;
		a|A) _attributes ;;
		l|L) _line_draw ;;
		f|F) _256_color_fg ;;
		b|B) _256_color_bg ;;
		q|Q) echo; exit 0 ;;
	esac

	if [[ "$2" = q ]]; then _setpos 28 1; exit 0; fi
	_setpos 24 2
	read -r -n 1 -p "${prmpt}" opt
done

