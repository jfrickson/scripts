#!/bin/bash

shopt -s extglob

version="1.0.0"
printf -v _d "\\033[1m"		# Print bold
printf -v _y "\\033[1;33m"		# Print yellow
printf -v _c "\\033[1;36m"		# Print bold cyan
printf -v _rst "\\033[0m"		# Reset to normal color

header=0
got_host=0
grp=""
declare -a parts

function main()
{
	if [[ -z "${HOME}" ]]; then
		printf "Error: HOME environment variable is not set.\n" >&2
		exit 1
	fi

	if [[ -n "$1" ]]; then
		case $1 in
			--help|-h)
				printf "\n%sUsage:%s %s%s [--help|-h|--version|-V]%s\n\n" \
						"${_y}" "${_rst}" "${_d}" "$(basename "$0")" "${_rst}"
				printf "    Display the list of SSH hosts from the user's SSH config file.\n\n"
				exit 0
				;;
			--version|-V)
				printf "\n%s version %s\n\n" "$(basename "$0")" "${version}"
				exit 0
				;;
		esac
		printf "Error: Unknown argument: %s\n" "$1" >&2
		exit 1
	fi

	cd "${HOME}/.ssh" || { printf "Error: Unable to change directory to %s/.ssh\n" "${HOME}" >&2; exit 1; }
	get_hosts || exit 1
	printf "\n"
}

function get_hosts()
{
	local -a text
	local line host name

	if [[ ! -f config ]]; then
		printf "Error: config file not found in %s/.ssh\n" "${HOME}" >&2
		return 1
	fi

	readarray text < config

	for line in "${text[@]}"; do
		trim line
		[[ ${line} == "" ]] && continue
		process_line "${line}"
	done
}

function process_line()
{
	local line=$1
	local var

	if [[ ${line} =~ ^#[-]+ ]]; then
		header=$(( !header ))
		got_host=0
		return
	fi

	read -r -a parts <<< "${line}"
	[[ ${parts[0]} == '#' ]] && { process_header; return; }
	pop_entry var
	var=${var^^}

	case "${var}" in
		HOST)
			host="${parts[*]}"
			got_host=1
			;;
		HOSTNAME)
			[[ ${got_host} -eq 0 ]] && return
			process_hostname
			;;
		*) ;;					# Ignore other keywords
	esac
}

function process_header()
{
	if [[ ${header} -eq 1 && ${parts[1]} =~ ^[[:graph:]]+$ ]]; then
		[[ ${parts[1]} == "Global" ]] && return
		pop_entry				# Remove the '#' token
		grp=${parts[*]}
		printf "\n   %s%s%s\n" "${_c}" "${grp}" "${_rst}"
	fi
}

function process_hostname()
{
	pop_entry name
	comment="${parts[*]}"		# The rest is the comment
	got_host=0
	printf "      %s%-14s%s %-20s %s\n" \
			"${_d}" "${host}" "${_rst}" "${name}" "${comment}"
}

function pop_entry()
{
	local tok="${parts[0]}"
	unset 'parts[0]'		# Remove the first element
	parts=("${parts[@]}")	# Re-index the array (shifts everything down)
	if [[ -n "$1" ]]; then
		local -n out=$1
		out="${tok}"
	fi
}

function trim()
{
	local -n ln="$1"
	ln="${ln##*([[:space:]])}"	# remove leading whitespace characters
	ln="${ln%%*([[:space:]])}"	# remove trailing whitespace characters
}

main "$@"
