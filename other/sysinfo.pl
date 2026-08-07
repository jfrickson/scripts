#!/usr/bin/env perl

use strict;
use warnings;
use lib glob("~/.local/lib/perl5");
use Ansi qw(:DEFAULT);
use List::Util qw(first);
use Term::ReadKey;

my $version = "2.0.1";

my $header = "  ${_vdbW}                           System Information                             ${_rst}\n\n";
my $footer = "\n  ${_dwB}                  Press Q to quit, Up/Down to scroll                      ${_rst}";


sub multi_line
{
	my ($val, $l1) = @_;
	my @result = ();

	# Default color prefix if not provided
	$l1 = defined $l1 ? $l1 : $_dw;
	my @lines = split /\n/, $val;
	if (@lines < 2) {
		$val =~ s/\n//g;
		push @result, "$l1$val$_rst";
		return \@result;
	} else {
		# Prefix all but the first line with spaces and color
		my $first = shift @lines;
		push @result, "$l1$first$_rst";
		$l1 = $_dw;  # reset to default color for subsequent lines
		foreach my $line (@lines) {
			push @result, "                 $l1$line$_rst";
		}
		return \@result;
	}
}


sub format_size
{
	my ($size, $unit) = @_;
	my @units = ('B', 'KB', 'MB', 'GB', 'TB');
	my $unit_index = first { $units[$_] eq $unit } 0..$#units;

	while ($size >= 1024 && $unit_index < $#units) {
		$size /= 1024;
		$unit_index++;
	}
	return sprintf("%.2f%s", $size, $units[$unit_index]);
}


sub get_basic
{
	my %info;

	$info{hn} = $ENV{HOSTNAME} // `hostname`;
	chomp $info{hn};

	my $uptime = '';
	if (open my $fh, '<', '/proc/uptime') {
		my $work = <$fh>;
		close $fh;
		$work =~ s/\..*//;
		my $days = int($work / 86400);
		my $hours = int(($work % 86400) / 3600);
		my $mins = int(($work % 3600) / 60);
		$uptime = sprintf("%02d:%02d", $hours, $mins);
		if ($days > 0) {
			my $d = $days == 1 ? 'day' : 'days';
			$uptime = "$days $d $uptime";
		}
	}
	$info{uptime} = $uptime;

	if (open my $fh, '<', '/proc/loadavg') {
		my $line = <$fh>;
		close $fh;
		my ($m1, $m5, $m15) = split /\s+/, $line;
		$info{m1} = $m1; $info{m5} = $m5; $info{m15} = $m15;
	}

	# Distribution
	my $dist = '';
	my $id = '';
	my $eol = '';
	my $rel = '';
	if (-f '/etc/redhat-release') {
		if (open my $fh, '<', '/etc/redhat-release') {
			$dist = <$fh>;
			close $fh;
			$dist =~ s/release | \(Core\)//g;
			chomp $dist;
		}
	} elsif (-f '/etc/os-release') {
		if (open my $fh, '<', '/etc/os-release') {
			while (<$fh>) {
				$id = $1 if /^ID=["']?([^"']+)["']?/;
				$dist = $1 if /^PRETTY_NAME="?([^"]+)"?/;
			}
			close $fh;
		}
	}
	$info{dist} = $dist;

	if ($id eq "opensuse-leap") {
		if (open my $fh, '<', '/etc/products.d/baseproduct') {
			while (<$fh>) {
				chomp;
				$eol = $1 if (m{<endoflife>(\d{4}-\d{2}-\d{2})</endoflife>});
				$rel = $1 if (m{<releasepackage[^>]*release="([^\"]+)"});
			}
			close $fh;
		}
	}

	$info{eol} = $eol;
	$info{rel} = $rel;

	# Desktop info
	my $sess_type = $ENV{XDG_SESSION_TYPE} // '';
	my $sess_dt = $ENV{DESKTOP_SESSION} // '';
	my $display = $ENV{DISPLAY} // '';

	$info{sess_type} = $sess_type if $display;
	$info{sess_dt} = $sess_dt if $display;

	return \%info;
}


sub get_cpu_mem
{
	my (@lines, $line, $key, $val, %cpu_info, %mem_info);
	my ($mem_total, $mem_free, $mem_avail, $swap_total, $swap_free);

	@lines = `lscpu 2>/dev/null`;
	foreach $line (@lines) {
		chomp $line;
		($key, $val) = split /:\s+/, $line, 2;
		next unless defined $val;
		$cpu_info{cpu_mod} = $val if $key eq 'Model name';
		$cpu_info{cpu_sockets} = $val if $key eq 'Socket(s)';
		$cpu_info{cpu_cores} = $val if $key eq 'Core(s) per socket';
		$cpu_info{cpu_thrds} = $val if $key eq 'Thread(s) per core';
		$cpu_info{machine} = $val if $key eq 'Architecture';
		if ($key eq 'CPU max MHz') {
			$val = sprintf("%.2f", $val / 1000);
			$cpu_info{cpu_speed} = $val;
		}
	}

	if (open my $fh, '<', '/proc/meminfo') {
		while (<$fh>) {
			$mem_total = $1 if /^MemTotal:\s+(\d+)/;
			$mem_free = $1 if /^MemFree:\s+(\d+)/;
			$mem_avail = $1 if /^MemAvailable:\s+(\d+)/;
			$swap_total = $1 if /^SwapTotal:\s+(\d+)/;
			$swap_free = $1 if /^SwapFree:\s+(\d+)/;
		}
		close $fh;
	}

	$mem_info{mem_total} = format_size($mem_total // 0, 'KB');
	$mem_info{mem_free} = format_size($mem_free // 0, 'KB');
	$mem_info{mem_avail} = format_size($mem_avail // 0, 'KB');
	$mem_info{swap_total} = format_size($swap_total // 0, 'KB');
	$mem_info{swap_free} = format_size($swap_free // 0, 'KB');
	return (\%cpu_info, \%mem_info);
}


sub get_virtual
{
	my $virt = `systemd-detect-virt 2>/dev/null`;
	chomp $virt;
	if ($virt eq 'kvm' && -f '/sys/devices/virtual/dmi/id/product_name') {
		if (open my $fh, '<', '/sys/devices/virtual/dmi/id/product_name') {
			my $name = <$fh>; chomp $name; close $fh;
			$virt .= " ($name)";
		}
	} elsif ($virt eq 'xen' && -f '/sys/devices/virtual/dmi/id/product_version') {
		if (open my $fh, '<', '/sys/devices/virtual/dmi/id/product_version') {
			my $ver = <$fh>; chomp $ver; close $fh;
			$virt .= " ($ver)";
		}
	}
	return $virt;
}


sub get_security
{
	my $secur = '';
	my $apparmor = system('systemctl status apparmor > /dev/null 2>&1');
	my $selnx = `getenforce 2>/dev/null`;
	chomp $selnx;
	if ($apparmor == 0) {
		$secur = 'AppArmor: Running';
	} elsif ($apparmor == 768) {
		$secur = 'AppArmor: Not Running';
	} elsif ($selnx) {
		$secur = "SELinux: $selnx";
	}
	my $fwall = system('systemctl status firewalld > /dev/null 2>&1') == 0
				? 'Running' : 'Not Running';
	return ($secur, $fwall);
}


sub get_network
{
	my @lines = `ip a`;
	my (@info, $iface, $stat, $ifaces, $work);
	my ($ipa, $ext_ip, $ext_ip4, $ext_ip6) = ('', '', '', '');
	my ($ifaces_lines, $ipa_lines);

	foreach my $line (@lines) {
		chomp $line;
		@info = split /\s+/, $line;
		if ($line =~ /^\d+:/) {
			$iface = $info[1];
			if ($line =~ /state UP/ or $line =~ /<.*,UP,.*>/) {
				$stat = 'UP';
			} elsif ($line =~ /state DOWN/ or $line =~ /<.*,DOWN,.*>/) {
				$stat = 'DOWN';
			} else {
				$stat = 'UNKNOWN';
			}
			$work = sprintf "%-5s %s", $iface, $stat;
			$ifaces .= "$work\n";
		} elsif ($line =~ /scope global|scope host|scope link/) {
			next if $line =~ /deprecated/;
			my $type = $info[1] eq 'inet' ? 'IPv4:' : 'IPv6:';
			my ($ip_addr, $net) = split '/', $info[2];
			my $work = $info[$#info] ;
			if ($work =~ /^(lo|noprefixroute|dynamic|kernel)$/) {
				$work = '';
			}
			$work = sprintf "%-5s %-12s /%-3s %s", $type, $ip_addr, $net, $work;
			$ipa .= "$work\n";
		}
	}

	$ifaces_lines = multi_line($ifaces);
	$ipa_lines = multi_line($ipa);

	$ext_ip4 = `curl -s4 ifconfig.me`;
	$ext_ip6 = `curl -s6 ifconfig.me`;
	chomp $ext_ip4;
	chomp $ext_ip6;
	if ($ext_ip4 && $ext_ip6) {
		$ext_ip = "IPv4: $ext_ip4 - IPv6: $ext_ip6";
	} elsif ($ext_ip4) {
		$ext_ip = "IPv4: $ext_ip4";
	} elsif ($ext_ip6) {
		$ext_ip = "IPv6: $ext_ip6";
	} else {
		$ext_ip = "N/A";
	}
	return ($ifaces_lines, $ipa_lines, $ext_ip);
}


sub get_drives
{
	my @z = `df -h`;
	my ($work, %seen, @drives);

	foreach my $ln (@z) {
		my @parts = split /\s+/, $ln;
		next if $seen{$parts[0]}++;
		next if $parts[0] =~ /tmpfs/;
		my $mtpt = $parts[5] // '';
		$mtpt = 'MountPoint' if $mtpt eq 'Mounted';
		$work = sprintf "%-5s %-5s %-6s %-5s %s",
				$parts[1], $parts[2], $parts[3], $parts[4], $mtpt;
		push @drives, $work;
	}

	my $drives = join("\n", @drives);
	$drives = multi_line($drives, "$_dg$_u");
	return $drives;
}

sub get_users
{
	my @work = `w -sf`;
	shift @work;
	my @users = ();

	foreach my $line (@work) {
		chomp $line;
		push @users, $line;
	}

	my $work = join("\n", @users);
	my $users = multi_line($work, "$_dg$_u");
	return $users;
}


sub get_key
{
	my $c = ReadKey(0);


	return $c if !defined $c || $c ne "\e";   # normal char or timeout/undef

	# Possible escape sequence → read next chars with short timeout
	my $timeout = 0.05;   # adjust if needed (very short for fast typing)
	my $next = ReadKey($timeout);
	return "ERR" unless defined $next;   # just lone ESC

	if ($next eq '[') {   # most common: CSI sequences
		my $code = ReadKey($timeout);
		my $extra = ReadKey($timeout) // '';
		return 'ERR' unless defined $code;

		# Arrow keys
		return 'UP'    if $code eq 'A';             # \e[A
		return 'DOWN'  if $code eq 'B';             # \e[B

		# Page Up / Page Down (common xterm-like)
		if (defined $extra && $extra eq '~') {
			return 'PGUP'   if $code eq '5';         # \e[5~
			return 'PGDN'   if $code eq '6';         # \e[6~
		}
	}

	# Fallback:
	return "ERR";
}

sub page_output
{
	my @lines = @_;
	my $screen_height = `tput lines`;
	chomp $screen_height;
	my $line_count = 0;
	my $top_line = 0;
	my $lines_to_print = $screen_height - 4; # header + footer + margin
	my $skip = "n";

	while (1) {
		if ($skip ne "y") {
			print "${_cls}$header";
			$line_count = 0;
			$top_line = 0 if $top_line < 0;
			for (my $i = $top_line; $line_count < $lines_to_print && $i <= $#lines; $i++) {
				print "  $lines[$i]\n";
				$line_count++;
			}

			return if $#lines <= $lines_to_print;
			print "  $footer";
			print "\r";
		}

		$skip = "n";
		ReadMode(4);
		my $c = get_key();
		ReadMode(0);

		if (!defined $c or $c eq "ERR") {
			$skip = "y";
			next;
		}
		if ($c eq 'q' || $c eq 'Q') { print "\n"; last; }
		if ($c eq 'UP') {
			if ($top_line > 0) { $top_line--; } else { $skip = "y"; }
		} elsif ($c eq 'DOWN' or $c eq "\n") {
			if ($top_line + $lines_to_print -1 < $#lines)
				{ $top_line++; } else { $skip = "y"; }
		} elsif ($c eq 'PGUP') {
			if ($top_line > 0)
				{ $top_line -= $lines_to_print; } else { $skip = "y"; }
			$top_line = 0 if $top_line < 0;
		} elsif ($c eq 'PGDN' or $c eq ' ') {
			$top_line += $lines_to_print;
			if ($top_line + $lines_to_print -1 > $#lines) {
				$top_line = $#lines - $lines_to_print + 1;
				$top_line = 0 if $top_line < 0;
			}
		} else {
			$skip = "y";
		}
	}
}


if (scalar @ARGV > 0) {
	for my $arg (@ARGV) {
		if ($arg eq '-V' || $arg eq '--version') {
			print "\n${_dg}SysInfo Script - Version $version${_rst}\n\n";
			exit 0;
		} else {
			print "Unknown argument: $arg\n";
			print "Usage: sysinfo.pl [-V|--version]\n";
			exit 1;
		}
	}
}

my $basic = get_basic();
my ($cpu, $mem) = get_cpu_mem();
my $virt = get_virtual();
my ($secur, $fwall) = get_security();
my ($ifaces_lines, $ipa_lines, $ext_ip) = get_network();
my $drives = get_drives();
my $users = get_users();

my @output = ();
push @output, "${_dc}Host name:       ${_dw}$basic->{hn}${_rst}";
push @output, "${_dc}Distribution:    ${_dw}$basic->{dist}${_rst}";

if ($basic->{rel}) {
	push @output, "${_dc}Release:         ${_dw}$basic->{rel}${_rst}";
	if ($basic->{eol}) {
		push @output, "${_dc}End of Life:     ${_dw}$basic->{eol}${_rst}";
	}
}
push @output, "${_dc}Machine:         ${_dw}$cpu->{machine}${_rst}";
push @output, "${_dc}CPU:             ${_dw}$cpu->{cpu_mod}${_rst}";
push @output, "                 ${_dw}$cpu->{cpu_sockets} Sockets  $cpu->{cpu_cores} Cores  $cpu->{cpu_thrds} Threads/core  $cpu->{cpu_speed} GHz${_rst}";
push @output, "${_dc}Uptime:          ${_dw}$basic->{uptime}${_rst}";
push @output, "${_dc}Load Avg:        ${_dg}1m: ${_dw}$basic->{m1}  ${_dg}5m: ${_dw}$basic->{m5}  ${_dg}15m: ${_dw}$basic->{m15}${_rst}";
if ($basic->{sess_type}) {
	push @output, "${_dc}Desktop:         ${_dw}$basic->{sess_dt} / $basic->{sess_type} ${_rst}";
}
push @output, "${_dc}Memory:          ${_dg}Total: ${_dw}$mem->{mem_total}  ${_dg}Free: ${_dw}$mem->{mem_free}  ${_dg}Available: ${_dw}$mem->{mem_avail}${_rst}";
push @output, "${_dc}Swap:            ${_dg}Total: ${_dw}$mem->{swap_total}  ${_dg}Free: ${_dw}$mem->{swap_free}${_rst}";

my $line = "${_dc}Drives:          ${_dw}" . shift @{$drives};
push @output, "$line";
for my $line (@$drives) {
	push @output, "$line";
}

$line = "${_dc}Interfaces:      ${_dw}" . shift @{$ifaces_lines};
push @output, "$line";
for my $line (@$ifaces_lines) {
	push @output, "$line";
}

$line = "${_dc}IP Addresses:    ${_dw}" . shift @{$ipa_lines};
push @output, "$line";
for my $line (@$ipa_lines) {
	push @output, "$line";
}

push @output, "${_dc}External IP:     ${_dw}$ext_ip${_rst}";
push @output, "${_dc}Virtualization:  ${_dw}$virt${_rst}";
push @output, "${_dc}Security:        ${_dw}$secur${_rst}";
push @output, "${_dc}Firewall:        ${_dw}$fwall${_rst}";

$line = "${_dc}Users:           ${_dw}" . shift @{$users};
push @output, "$line";
for my $line (@$users) {
	push @output, "$line";
}

page_output(@output);
print "\n";
