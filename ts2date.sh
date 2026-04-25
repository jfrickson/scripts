#!/bin/bash
if [[ "$1" = "-q" ]]; then
	shift
else
	echo -n "date is: "
fi
if [[ -z "$1" ]]; then
	date +"%F %T"
else
	date --date="@$1" +"%F %T"
fi

