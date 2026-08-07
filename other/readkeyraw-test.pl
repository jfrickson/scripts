#!/usr/bin/env perl

use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/../.local/lib/perl5";
use readkeyraw qw(read_key_raw set_debug);

my $timeout = 1.0;
my $debug = 0;

for my $arg (@ARGV) {
	if ($arg eq '--debug') {
		$debug = 1;
	} elsif ($arg =~ /^--timeout=(\d+(?:\.\d+)?)$/) {
		$timeout = $1;
	}
}

set_debug($debug);

print "readkeyraw test\n";
print "Press keys to see translated tokens.\n";
print "Press Esc twice quickly or Ctrl-C to exit.\n";
print "Timeout token appears every ${timeout}s if no key is pressed.\n\n";

my $prev = '';
while (1) {
	my $key = read_key_raw(timeout => $timeout);
	my $display = $key;
	$display =~ s/\n/\\n/g;
	$display =~ s/\t/\\t/g;
	print "$display\n";

	last if $key eq '#C-C';
	last if $key eq '#ESC' && $prev eq '#ESC';
	$prev = $key;
}

print "exiting\n";
