#!/usr/bin/env bash

set -u

PATH="${HOME}/.local/lib/bash:${PATH}"
# shellcheck disable=SC1091
. ReadKeyRaw

timeout="1"

for arg in "$@"; do
	case "$arg" in
		--debug)
			rkr_debug=1
			;;
		--timeout=*)
			timeout="${arg#*=}"
			;;
	esac
done

echo "readkeyraw test"
echo "Press keys to see translated tokens."
echo "Press Esc twice quickly or Ctrl-C to exit."
echo "Timeout token appears every ${timeout}s if no key is pressed."
echo

prev=""
while true; do
	read_key_raw key "-r -d '' -n1 -t${timeout}"
	display="${key//$'\n'/\\n}"
	display="${display//$'\t'/\\t}"
	echo "${display}"

	if [[ "${key}" == "#C-C" ]]; then
		break
	fi
	if [[ "${key}" == "#ESC" && "${prev}" == "#ESC" ]]; then
		break
	fi
	prev="${key}"
done

echo "exiting"
