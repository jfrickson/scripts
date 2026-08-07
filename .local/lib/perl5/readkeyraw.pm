# vim: set ft=perl ts=4 sw=4 sts=4 noet ai eol:

package readkeyraw;

use strict;
use warnings;
use Exporter 'import';
use POSIX qw(:termios_h);
use Time::HiRes qw(time usleep);
use Encode qw(decode FB_CROAK);

our @EXPORT_OK = qw(read_key_raw set_debug);

my %ESCAPE_MAP = (
	# Function keys
	"OP" => "#f1", "OQ" => "#f2", "OR" => "#f3", "OS" => "#f4",
	"[15~" => "#f5", "[17~" => "#f6", "[18~" => "#f7", "[19~" => "#f8",
	"[20~" => "#f9", "[21~" => "#f10", "[23~" => "#f11", "[24~" => "#f12",
	# Shifted function keys
	"[1;2P" => "#F1", "[1;2Q" => "#F2", "[1;2R" => "#F3", "[1;2S" => "#F4",
	"[15;2~" => "#F5", "[17;2~" => "#F6", "[18;2~" => "#F7", "[19;2~" => "#F8",
	"[20;2~" => "#F9", "[21;2~" => "#F10", "[23;2~" => "#F11", "[24;2~" => "#F12",
	# Control function keys
	"[1;5P" => "#C-f1", "[1;5Q" => "#C-f2", "[1;5R" => "#C-f3", "[1;5S" => "#C-f4",
	"[15;5~" => "#C-f5", "[17;5~" => "#C-f6", "[18;5~" => "#C-f7", "[19;5~" => "#C-f8",
	"[20;5~" => "#C-f9", "[21;5~" => "#C-f10", "[23;5~" => "#C-f11", "[24;5~" => "#C-f12",
	# Control+Shift function keys
	"[1;6P" => "#C-F1", "[1;6Q" => "#C-F2", "[1;6R" => "#C-F3", "[1;6S" => "#C-F4",
	"[15;6~" => "#C-F5", "[17;6~" => "#C-F6", "[18;6~" => "#C-F7", "[19;6~" => "#C-F8",
	"[20;6~" => "#C-F9", "[21;6~" => "#C-F10", "[23;6~" => "#C-F11", "[24;6~" => "#C-F12",
	# Alt function keys
	"[1;3P" => "#A-f1", "[1;3Q" => "#A-f2", "[1;3R" => "#A-f3", "[1;3S" => "#A-f4",
	"[15;3~" => "#A-f5", "[17;3~" => "#A-f6", "[18;3~" => "#A-f7", "[19;3~" => "#A-f8",
	"[20;3~" => "#A-f9", "[21;3~" => "#A-f10", "[23;3~" => "#A-f11", "[24;3~" => "#A-f12",
	# Alt+Shift function keys
	"[1;4P" => "#A-F1", "[1;4Q" => "#A-F2", "[1;4R" => "#A-F3", "[1;4S" => "#A-F4",
	"[15;4~" => "#A-F5", "[17;4~" => "#A-F6", "[18;4~" => "#A-F7", "[19;4~" => "#A-F8",
	"[20;4~" => "#A-F9", "[21;4~" => "#A-F10", "[23;4~" => "#A-F11", "[24;4~" => "#A-F12",
	# Alt+Control function keys
	"[1;7P" => "#AC-f1", "[1;7Q" => "#AC-f2", "[1;7R" => "#AC-f3", "[1;7S" => "#AC-f4",
	"[15;7~" => "#AC-f5", "[17;7~" => "#AC-f6", "[18;7~" => "#AC-f7", "[19;7~" => "#AC-f8",
	"[20;7~" => "#AC-f9", "[21;7~" => "#AC-f10", "[23;7~" => "#AC-f11", "[24;7~" => "#AC-f12",
	# Alt+Control+Shift function keys
	"[1;8P" => "#AC-F1", "[1;8Q" => "#AC-F2", "[1;8R" => "#AC-F3", "[1;8S" => "#AC-F4",
	"[15;8~" => "#AC-F5", "[17;8~" => "#AC-F6", "[18;8~" => "#AC-F7", "[19;8~" => "#AC-F8",
	"[20;8~" => "#AC-F9", "[21;8~" => "#AC-F10", "[23;8~" => "#AC-F11", "[24;8~" => "#AC-F12",
	# Cursor keys
	"[A" => "#UP", "[B" => "#DN", "[C" => "#RT", "[D" => "#LT", "[H" => "#HOM",
	"[F" => "#END", "[2~" => "#INS", "[3~" => "#DEL", "[5~" => "#PUP", "[6~" => "#PDN",
	# macOS differences
	"OH" => "#HOM", "OF" => "#END",
	# Alt cursor keys
	"[1;3A" => "#A-UP", "[1;3B" => "#A-DN", "[1;3C" => "#A-RT", "[1;3D" => "#A-LT",
	"[1;3H" => "#A-HOM", "[1;3F" => "#A-END", "[2;3~" => "#A-INS", "[3;3~" => "#A-DEL",
	"[5;3~" => "#A-PUP", "[6;3~" => "#A-PDN",
	# Control cursor keys
	"[1;5A" => "#C-UP", "[1;5B" => "#C-DN", "[1;5C" => "#C-RT", "[1;5D" => "#C-LT",
	"[1;5H" => "#C-HOM", "[1;5F" => "#C-END", "[2;5~" => "#C-INS", "[3;5~" => "#C-DEL",
	"[5;5~" => "#C-PUP", "[6;5~" => "#C-PDN",
);

my $DEFAULT = __PACKAGE__->new();

sub new {
	my ($class) = @_;
	my $self = {
		debug => 0,
	};
	return bless $self, $class;
}

sub set_debug {
	my ($self, $debug) = @_;
	if (ref $self) {
		$self->{debug} = $debug ? 1 : 0;
		return;
	}
	$DEFAULT->{debug} = $_[0] ? 1 : 0;
}

sub read_key {
	my ($self, @args) = @_;
	return $self->read_key_raw(@args);
}

sub read_key_raw {
	my ($self, @args) = @_;
	if (!ref $self) {
		unshift @args, $self if defined $self;
		$self = $DEFAULT;
	}

	my $timeout = _parse_timeout(@args);
	my $fd = fileno(STDIN);
	return '#ERROR' if !defined $fd;

	my $saved = _stty_save($fd);
	return '#ERROR' if !$saved;

	my $cleanup = sub {
		_stty_restore($fd, $saved);
	};

	local $SIG{INT} = sub {
		$cleanup->();
		$SIG{INT} = 'DEFAULT';
		kill 'INT', $$;
	};
	local $SIG{TERM} = sub {
		$cleanup->();
		$SIG{TERM} = 'DEFAULT';
		kill 'TERM', $$;
	};

	my $out;
	eval {
		_stty_raw($fd, $saved);
		$out = _read_key_impl($self, $fd, $timeout);
		1;
	} or do {
		$out = '#ERROR';
	};

	$cleanup->();
	return $out;
}

sub _parse_timeout {
	my (@args) = @_;
	return undef if !@args;
	if (@args == 1 && !ref $args[0]) {
		return $args[0];
	}
	if (@args % 2 == 0) {
		my %opts = @args;
		return $opts{timeout};
	}
	return undef;
}

sub _read_key_impl {
	my ($self, $fd, $timeout) = @_;

	my $first = _read_one_byte($fd, $timeout);
	return '#TIMEOUT' if !defined $first;

	return '#BS' if $first == 0x08 || $first == 0x7F;
	return '#LF' if $first == 0x0A;
	return '#TAB' if $first == 0x09;

	if ($first == 0x1B) {
		my $seq = _collect_escape_suffix($fd);
		return '#ESC' if $seq eq '';
		my $translated = _translate_escape($seq);
		if ($self->{debug}) {
			printf "Escape sequence read: %s => %s\n", _repr_bytes($seq), $translated;
		}
		return $translated;
	}

	if ($first >= 0xC2 && $first <= 0xF4) {
		my $expected = $first <= 0xDF ? 1 : $first <= 0xEF ? 2 : 3;
		my $raw = pack('C', $first) . _read_following_bytes($fd, $expected);
		my $decoded = eval { _decode_utf8($raw) };
		return defined($decoded) ? $decoded : $raw;
	}

	if ($first >= 1 && $first <= 26) {
		return '#C-' . chr($first + 64);
	}

	return chr($first);
}

sub _read_one_byte {
	my ($fd, $timeout) = @_;
	if (defined $timeout) {
		my $ready = _wait_readable($fd, $timeout);
		return undef if !$ready;
	}
	my $buf = '';
	my $n = sysread(STDIN, $buf, 1);
	return undef if !defined($n) || $n == 0;
	return unpack('C', $buf);
}

sub _read_following_bytes {
	my ($fd, $count) = @_;
	my $out = '';
	for (1 .. $count) {
		my $ready = _wait_readable($fd, 0.01);
		last if !$ready;
		my $buf = '';
		my $n = sysread(STDIN, $buf, 1);
		last if !defined($n) || $n == 0;
		$out .= $buf;
	}
	return $out;
}

sub _collect_escape_suffix {
	my ($fd) = @_;
	my $out = '';
	while (length($out) < 32) {
		my $ready = _wait_readable($fd, 0.02);
		last if !$ready;

		my $buf = '';
		my $n = sysread(STDIN, $buf, 1);
		last if !defined($n) || $n == 0;

		my $b = unpack('C', $buf);
		if ($b == 0x1B) {
			# Another escape started; drain a little and discard like the Bash version.
			while (_wait_readable($fd, 0.01)) {
				my $tmp = '';
				last if !defined(sysread(STDIN, $tmp, 1));
			}
			last;
		}
		$out .= $buf;
	}
	return $out;
}

sub _translate_escape {
	my ($seq) = @_;
	return $ESCAPE_MAP{$seq} if exists $ESCAPE_MAP{$seq};
	if (length($seq) == 1) {
		my $ord = ord($seq);
		if ($ord >= 33 && $ord <= 126) {
			return '#A-' . $seq;
		}
	}
	return $seq;
}

sub _wait_readable {
	my ($fd, $timeout) = @_;
	my $rin = '';
	vec($rin, $fd, 1) = 1;
	my $n = select(my $rout = $rin, undef, undef, $timeout);
	return $n && vec($rout, $fd, 1);
}

sub _decode_utf8 {
	my ($bytes) = @_;
	return decode('UTF-8', $bytes, FB_CROAK);
}

sub _repr_bytes {
	my ($s) = @_;
	return join('', map { sprintf('\\x%02x', ord($_)) } split(//, $s));
}

sub _stty_save {
	my ($fd) = @_;
	my $t = POSIX::Termios->new();
	return undef if !$t->getattr($fd);
	return {
		iflag => $t->getiflag,
		oflag => $t->getoflag,
		cflag => $t->getcflag,
		lflag => $t->getlflag,
		ispeed => $t->getispeed,
		ospeed => $t->getospeed,
		cc => [ map { $t->getcc($_) } 0 .. NCCS - 1 ],
	};
}

sub _stty_restore {
	my ($fd, $saved) = @_;
	my $t = POSIX::Termios->new();
	$t->getattr($fd);
	$t->setiflag($saved->{iflag});
	$t->setoflag($saved->{oflag});
	$t->setcflag($saved->{cflag});
	$t->setlflag($saved->{lflag});
	$t->setispeed($saved->{ispeed});
	$t->setospeed($saved->{ospeed});
	for my $i (0 .. NCCS - 1) {
		$t->setcc($i, $saved->{cc}->[$i]);
	}
	$t->setattr($fd, TCSANOW);
}

sub _stty_raw {
	my ($fd, $saved) = @_;
	my $t = POSIX::Termios->new();
	$t->getattr($fd);
	$t->setlflag($saved->{lflag} & ~(ICANON | ECHO));
	$t->setcc(VMIN, 1);
	$t->setcc(VTIME, 0);
	$t->setattr($fd, TCSANOW);
}

1;
