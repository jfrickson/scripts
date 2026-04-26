#!/bin/bash

# Configuration
DTACH_DIR="/home/<YOUR_USERNAME>/.dtach"

# Things to send to new sessions based on their ID (e.g. to set up environment)
declare -A feed_keys=(
	[root]='sudo -i\n'
	[dummy]='echo "Welcome to the dummy session!"\n'
)

# ==================== Modify items above this line ====================

if [[ "${DTACH_DIR}" =~ "<YOUR_USERNAME>" ]]; then
	echo "Please edit the DTACH_DIR variable to set your home directory."
	echo "Do not use ~ or \$HOME in the path, as this script may be run"
	echo "in contexts where those are not properly expanded."
	echo "Example: DTACH_DIR=\"/home/klaatu/.dtach\""
	exit 1
fi
mkdir -p "${DTACH_DIR}"
chmod g+rwx "${DTACH_DIR}" 2>/dev/null || true

# Ansi color codes for output
printf -v _rst	"\e[0m"				# Reset
printf -v _d	"\e[1m"				# Bold
printf -v _dr	"\e[1;31m"			# Bold Red
printf -v _dy	"\e[1;33m"			# Bold Yellow
printf -v _dg	"\e[1;32m"			# Bold Green
printf -v _vdbW	"\e[1;7;37;44m"		# Dark Blue on White

#----------------------------------------------------------------------
# function sk:
#	Kill a session by ID, ensuring the socket is cleaned up. This is
#	a more forceful alternative to detaching, useful if the session is
#	unresponsive or you want to ensure it's terminated.
#----------------------------------------------------------------------
function sk
{
	local sock="" id=""

	if [[ -z "$1" ]]; then
		printf "\n%sSpecify a session id to kill%s\n" "${_dr}" "${_rst}"
		return
	fi

	while [[ -n "$1" ]]; do
		id="$1"
		shift
		sock="${DTACH_DIR}/${id}"

		if [[ ! -S "${sock}" ]]; then
			printf "%sSession '${id}' not found.%s\n" "${_dr}" "${_rst}"
		else
			# Find the PID of the process holding the socket open
			local pid
			pid=$(fuser "${sock}" 2>/dev/null | awk '{print $NF}')
			if [[ -n "${pid}" ]]; then
				printf "%sKilling session '${id}' (PID: ${pid})...%s\n" "${_dr}" "${_rst}"
				kill -9 "${pid}"
				rm "${sock}"
			else
				printf "%sNo active process found for '${id}'. Cleaning up socket.%s\n" "${_dy}" "${_rst}"
				rm "${sock}"
			fi
		fi
	done
}

#----------------------------------------------------------------------
# function sc:
#	Clean up stale session sockets. This checks for sockets in the
#	DTACH_DIR that are not currently active (i.e. no process is
#	holding them open) and removes them. This is useful to keep the
#	session list clean and avoid confusion with defunct sessions.
#----------------------------------------------------------------------
function sc {
	if [[ -O "${DTACH_DIR}" ]]; then
		for sock in "${DTACH_DIR}"/*; do
			if [[ -S "${sock}" ]] && ! dtach -p "${sock}" < /dev/null > /dev/null 2>&1; then
				rm -f "${sock}"
			fi
		done
	fi
}

function get_sessions
{
	local path
	for path in "${DTACH_DIR}"/*; do
		[[ -e "${path}" ]] || continue
		basename "${path}"
	done | sort
}

#----------------------------------------------------------------------
# function sl:
#	List current dtach sessions. This shows all session sockets in
#	the DTACH_DIR, indicating which one (if any) is currently
#	attached. It also marks any entries that are not valid sockets,
#	which may indicate stale or corrupted session files.
#----------------------------------------------------------------------
function sl
{
	local -a sessions
	local sock
    sc # Refresh the list before showing it

	printf "\n%s Current dtach sessions %s\n" "${_vdbW}" "${_rst}"
	mapfile -t sessions < <(get_sessions)

	if [[ ${#sessions[@]} -eq 0 ]]; then
		echo "  ${_dg}No sessions found${_rst}"
		return
	fi

	for session in "${sessions[@]}"; do
		sock="${DTACH_DIR}/${session}"
		if [[ -S "${sock}" ]]; then
			if [[ "${DTACH_SESSION}" = "${session}" ]]; then
				printf "  %s${session}%s %s*%s\n" "${_d}" "${_rst}" "${_dg}" "${_rst}"
			else
				printf "  %s${session}%s\n" "${_d}" "${_rst}"
			fi
		else
			printf "  %s${session} (not a socket)%s\n" "${_dr}" "${_rst}"
		fi
	done
    printf "\n\n"
}

#----------------------------------------------------------------------
# function s:
#	Attach to a session by ID, or create it if it doesn't exist.
#	This function handles the logic of checking if the session already
#	exists, creating it if necessary, and then attaching to it. It
#	also sets up the environment for the session based on predefined
#	keys, and manages the tracking of the attached session for
#	switching purposes.
#----------------------------------------------------------------------
function s
{
	if [[ -z "$1" ]]; then
		printf "\n%sYou must specify a session id%s\n" "${_dr}" "${_rst}"
		return
	fi

	local id="$1"
	local sock="${DTACH_DIR}/${id}"
	local keys="${feed_keys[${id}]}"

	if [[ -n "${DTACH_SESSION}" ]]; then
		printf "\n%sAlready in a dtach session. Please exit or detach first.%s\n\n" "${_dr}" "${_rst}"
		return
	elif [[ -S "${sock}" ]]; then
		attach_with_tracking "${id}" "${sock}"
	elif [[ -n "${keys}" ]]; then
		env DTACH_SESSION="${id}" dtach -n "${sock}" -z bash
		echo -en "${keys}" | dtach -p "${sock}"
		attach_with_tracking "${id}" "${sock}"
	else
		env DTACH_SESSION="${id}" dtach -n "${sock}" -z bash
		attach_with_tracking "${id}" "${sock}"
	fi

	if [[ -f "${DTACH_DIR}/.next_session" ]]; then
		local next
		next=$(<"${DTACH_DIR}/.next_session")
		rm "${DTACH_DIR}/.next_session"
		if [[ -n "${next}" ]]; then
			s "${next}"
		fi
	fi
}

#----------------------------------------------------------------------
# function sw:
#	Switch to another session by ID. This function handles the logic
#	of detaching from the current session (if any) and attaching to
#	the new session. It also manages the tracking files to ensure that
#	the session switch is smooth and that the next session is queued
#	up if the detach cannot be performed immediately (e.g. due to
#	cross-UID issues). The function supports switching to the next or
#	previous session in the list if '+' or '-' is provided as the ID.
#----------------------------------------------------------------------
function sw
{
	local id="$1"
	local -a sessions
	local i current_index=-1

	if [[ -z "${DTACH_SESSION}" ]]; then
		printf "%sNot in a dtach session%s\n" "${_dy}" "${_rst}"
		return
	fi

	mapfile -t sessions < <(get_sessions)
	for i in "${!sessions[@]}"; do
		if [[ "${sessions[${i}]}" = "${DTACH_SESSION}" ]]; then
			current_index=${i}
			break
		fi
	done

	case "${id}" in
		+)	if [[ ${#sessions[@]} -eq 0 ]]; then
				printf "%sNo next session found%s\n" "${_dy}" "${_rst}"
				return
			fi
			if [[ ${current_index} -lt 0 || ${current_index} -ge $((${#sessions[@]} - 1)) ]]; then
				id="${sessions[0]}"
			else
				id="${sessions[$((current_index + 1))]}"
			fi
			if [[ -z "${id}" || "${id}" = "${DTACH_SESSION}" ]]; then
				printf "%sNo next session found%s\n" "${_dy}" "${_rst}"
				return
			fi
			;;
		-)	if [[ ${#sessions[@]} -eq 0 ]]; then
				printf "%sNo previous session found%s\n" "${_dy}" "${_rst}"
				return
			fi
			if [[ ${current_index} -le 0 ]]; then
				id="${sessions[$(( ${#sessions[@]} - 1 ))]}"
			else
				id="${sessions[$((current_index - 1))]}"
			fi
			if [[ -z "${id}" || "${id}" = "${DTACH_SESSION}" ]]; then
				printf "%sNo previous session found%s\n" "${_dy}" "${_rst}"
				return
			fi
			;;
	esac

	local sock="${DTACH_DIR}/${id}"
	local pid_file="${DTACH_DIR}/.pid_${DTACH_SESSION:-}"

	if [[ -z "${id}" ]]; then
		printf "%sSpecify a session to switch to%s\n" "${_dy}" "${_rst}"
		return
	fi

	local client_pid
	client_pid=$(<"${pid_file}")
	echo "${id}" > "${DTACH_DIR}/.next_session"
	chmod g+w "${DTACH_DIR}/.next_session"
	if ! detach_client "${DTACH_SESSION}" "${client_pid}"; then
		printf "%sCould not auto-detach. Press Ctrl+\\ to detach manually (switch is queued).%s\n" "${_dy}" "${_rst}"
	fi
}

#----------------------------------------------------------------------
# function attach_with_tracking:
#	Called by function `s`
#	Helper function to attach to a dtach session while also setting up
#	tracking files for the session. This allows the script to manage
#	detach requests and session switching across different UIDs, by
#	creating PID files and request files in the DTACH_DIR. The
#	function spawns a background watcher process that listens for
#	detach requests and signals to clean up the tracking files when
#	the session ends.
#----------------------------------------------------------------------
function attach_with_tracking
{
	local id="$1"
	local sock="$2"
	local pid_file="${DTACH_DIR}/.pid_${id}"
	local req_file="${DTACH_DIR}/.detach_req_${id}"
	local watcher_pid

	rm -f "${pid_file}" "${req_file}"

	# Owner-side watcher: handles detach requests from shells running as other UIDs.
	(
		# Wait briefly for attach process to publish PID, otherwise exit.
		for _ in {1..20}; do
			[[ -f "${pid_file}" ]] && break
			sleep 0.1
		done

		while [[ -f "${pid_file}" ]]; do
			if [[ -f "${req_file}" ]]; then
				rm -f "${req_file}"
				if [[ -f "${pid_file}" ]]; then
					client_pid=""
					client_pid=$(<"${pid_file}")
					kill -HUP "${client_pid}" 2>/dev/null || true
				fi
			fi
			sleep 0.2
		done
	) &
	watcher_pid=$!

	bash -c "echo \$\$ > \"${pid_file}\"; exec dtach -a \"${sock}\" -z"

	kill "${watcher_pid}" 2>/dev/null || true
	rm -f "${pid_file}" "${req_file}"
}

#----------------------------------------------------------------------
# function detach_client:
#   Called by function `sw`
#	Attempt to detach a client by sending it a HUP signal. If the
#	client is running under a different UID and cannot be signaled,
#	this function falls back to creating a detach request file that
#	the owner-side watcher will detect and handle. This allows for
#	cross-UID detach requests, albeit with a slight delay as the
#	watcher process checks for requests.
#----------------------------------------------------------------------
function detach_client
{
	local id="$1"
	local client_pid="$2"
	local req_file="${DTACH_DIR}/.detach_req_${id}"

	if kill -HUP "${client_pid}" 2>/dev/null; then
		return 0
	fi

	# Cross-UID fallback: request detach from the owner-side watcher.
	if : > "${req_file}" 2>/dev/null; then
		return 0
	fi

	return 1
}


#----------------------------------------------------------------------
# Main command dispatch. This checks the name of the script or the first
# argument to determine which function to call. If the script is called
# without arguments or with '-h', it prints the usage information. Otherwise,
# it calls the corresponding function based on the command (e.g. 'sl' for listing sessions, 's' for attaching/creating a session, 'sc' for cleaning stale sessions, 'sk' for killing a session, 'sw' for switching sessions).
#----------------------------------------------------------------------

cmd=$(basename "$0")
if [[ "${cmd}" = "dtach-ctl.sh" || "$1" = "-h" ]]; then
	printf "\n%sUsage:%s\n" "${_d}" "${_rst}"
	printf "   %ssl%s       %ss%session %sl%sist\n" "${_dy}" "${_rst}" \
				"${_d}" "${_rst}" "${_d}" "${_rst}"
	printf "   %ss  <id>%s  attach to or create a %ss%session named %sid%s\n" \
				"${_dy}" "${_rst}" "${_d}" "${_rst}" "${_dy}" "${_rst}"
	printf "   %ssc%s       stale %ss%session %sc%slean up \n" \
				"${_dy}" "${_rst}" "${_d}" "${_rst}" "${_d}" "${_rst}"
	printf "   %ssk <id>%s  %ss%session %sk%sill by %sid%s\n" "${_dy}" \
				"${_rst}" "${_d}" "${_rst}" "${_d}" "${_rst}" "${_dy}" "${_rst}"
	printf "   %ssw <id>%s  %ssw%sitch session to %sid%s\n" \
				"${_dy}" "${_rst}" "${_d}" "${_rst}" "${_dy}" "${_rst}"
	printf "   %ssw +%s     %ssw%sitch to next session\n" \
				"${_dy}" "${_rst}" "${_d}" "${_rst}"
	printf "   %ssw -%s     %ssw%sitch to previous session\n\n" \
				"${_dy}" "${_rst}" "${_d}" "${_rst}"
	exit 1
fi

${cmd} "$@"
