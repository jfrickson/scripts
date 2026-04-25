#!/bin/bash
if [[ "$1" = "-q" ]]; then
	shift
else
	echo -n "timestamp is: "
fi
if [[ -z "$1" ]]; then
	date +%s
else
	date --date="$1" +%s
fi
