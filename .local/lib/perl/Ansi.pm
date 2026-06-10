# vim: set ft=bash ts=4 sw=4 sts=4 noet ai eol:

package Ansi;
use Exporter;
our @ISA = qw(Exporter);
our @EXPORT = qw(
    $_rst  $_cls  $_hom  $_el   $_scp  $_rcp  $_d    $_u    $_f    $_v
    $_k    $_r    $_g    $_y    $_b    $_m    $_c    $_w    $_dk   $_dr
    $_dg   $_dy   $_db   $_dm   $_dc   $_dw   $_K    $_R    $_G    $_Y
    $_B    $_M    $_C    $_W    $_dK   $_dR   $_dG   $_dY   $_dB   $_dM
    $_dC   $_dW   $_vdkW $_vdrW $_vdbW $_vdmW $_dwR  $_dwB  $_dwC  $_dur
	$_dug  $_duy  $_dub  $_dum  $_duc  $_duw  $_err  $_wrn
	@_fg256 @_bg256 @_fg256d @_bg256d @_fg256v @_bg256v @_fg256dv @_bg256dv
	_a
);

# =====================
#  Reset, Clear, Home
# =====================
our $_rst = "\e[0m";			# Reset to normal attributes
our $_cls = "\e[H\e[J";			# Clear Screen & Home
our $_hom = "\e[0;0H";			# Cursor to Home R0C0
our $_el = "\e[2K";				# Erase Line
our $_scp = "\e[s";				# Save cursor pos
our $_rcp = "\e[u";				# Restore cursor pos

# =====================
#      Attributes
# =====================
our $_d = "\e[1m";				# Bold
our $_u = "\e[4m";				# Underscore
our $_f = "\e[5m";				# Blink (flash)
our $_v = "\e[7m";				# Reverse

# =====================
#   Foreground Colors
# =====================
our $_k = "\e[30m";				# Black
our $_r = "\e[31m";				# Red
our $_g = "\e[32m";				# Green
our $_y = "\e[33m";				# Yellow
our $_b = "\e[34m";				# Blue
our $_m = "\e[35m";				# Magenta
our $_c = "\e[36m";				# Cyan
our $_w = "\e[37m";				# White

our $_dk = "\e[1;30m";			# Bold Black
our $_dr = "\e[1;31m";			# Bold Red
our $_dg = "\e[1;32m";			# Bold Green
our $_dy = "\e[1;33m";			# Bold Yellow
our $_db = "\e[1;34m";			# Bold Blue
our $_dm = "\e[1;35m";			# Bold Magenta
our $_dc = "\e[1;36m";			# Bold Cyan
our $_dw = "\e[1;37m";			# Bold White

# =====================
#   Background Colors
# =====================
our $_K = "\e[40m";				# Black
our $_R = "\e[41m";				# Red
our $_G = "\e[42m";				# Green
our $_Y = "\e[43m";				# Yellow
our $_B = "\e[44m";				# Blue
our $_M = "\e[45m";				# Magenta
our $_C = "\e[46m";				# Cyan
our $_W = "\e[47m";				# White

our $_dK = "\e[1;40m";			# Bold Black
our $_dR = "\e[1;41m";			# Bold Red
our $_dG = "\e[1;42m";			# Bold Green
our $_dY = "\e[1;43m";			# Bold Yellow
our $_dB = "\e[1;44m";			# Bold Blue
our $_dM = "\e[1;45m";			# Bold Magenta
our $_dC = "\e[1;46m";			# Bold Cyan
our $_dW = "\e[1;47m";			# Bold White

# =====================
#  Common Combinations
# =====================

our $_vdkW = "\e[1;7;37;40m";		# Reverse Bold Black on White
our $_vdrW = "\e[1;7;37;41m";		# Reverse Bold Red on White
our $_vdbW = "\e[1;7;37;44m";		# Reverse Bold Blue on White
our $_vdmW = "\e[1;7;37;45m";		# Reverse Bold Magenta on White
our $_vdwC = "\e[1;7;36;41m";		# Reverse Bold White on Cyan
our $_dwR = "\e[1;41;37m";			# Bold White on Red
our $_dwB = "\e[1;44;37m";			# Bold White on Blue
our $_dwC = "\e[1;46;37m";			# Bold White on Cyan
our $_dur = "\e[1;4;31m";			# Bold Underline Red
our $_dug = "\e[1;4;32m";			# Bold Underline Green
our $_duy = "\e[1;4;33m";			# Bold Underline Yellow
our $_dub = "\e[1;4;34m";			# Bold Underline Blue
our $_dum = "\e[1;4;35m";			# Bold Underline Magenta
our $_duc = "\e[1;4;36m";			# Bold Underline Cyan
our $_duw = "\e[1;4;37m";			# Bold Underline White

our $_err = "$_dwR";;				# Errors
our $_wrn = "\e[30;43m";			# Warnings

# =====================
#   256 color Colors
# =====================

our (@_fg256, @_bg256, @_fg256d, @_bg256d, @_fg256v, @_bg256v, @_fg256dv, @_bg256dv);

for (my $i = 16; $i < 257; $i++) {
	$_fg256[$i] = "\e[38;5;${i}m";
	$_bg256[$i] = "\e[48;5;${i}m";
	$_fg256d[$i] = "\e[1;38;5;${i}m";
	$_bg256d[$i] = "\e[1;48;5;${i}m";
	$_fg256v[$i] = "\e[7;38;5;${i}m";
	$_bg256v[$i] = "\e[7;48;5;${i}m";
	$_fg256dv[$i] = "\e[1;7;38;5;${i}m";
	$_bg256dv[$i] = "\e[1;7;48;5;${i}m";
}

sub _a()
{
    my ($var) = @_;
	$var = '$' . $var unless ref $$var;
	print "$$var";
}

1;
