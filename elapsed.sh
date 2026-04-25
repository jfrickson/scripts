#!/bin/bash

# TODO - Get number of years by using end year minus start year
# and updating start date appropriately. Something like:
#     2000-06-15 12:00:00 to 2023-08-01 08:00:00 =
#     23 years and 2023-06-15 12:00:00 to 2023-08-01 08:00:00

hrs=$(( 60 * 60 )); day=$(( hrs * 24))
d=0; h=0; m=0; s=0

if [[ -z "$2" ]]; then
	if [[ -z "$1" ]] || [[ "$1" = "-q" ]]; then
		printf "\nUsage: elapsed <date1> [<date2>]\n"
		printf "    date1  Starting date\n"
		printf "    date2  Ending date. If not supplied, will use current time\n\n"
	fi
fi

if [[ "$1" = "-q" ]]; then
	shift
else
	echo -n "elapsed time is: "
fi

# Get the starting timestamp
start_ts="$1"
if [[ ! ${start_ts} =~ ^[0-9]+$ ]]; then
	# Probably a date/time string so convert
	start_ts=$(date --date="${start_ts}" +%s)
fi

# Get the ending timestamp
if [[ -n "$2" ]]; then
	end_ts="$2"
	if [[ ! ${end_ts} =~ ^[0-9]+$ ]]; then
		# Probably a date/time string so convert
		end_ts=$(date --date="${end_ts}" +%s)
	fi
else
	end_ts=$(date +%s)
fi

# Number of seconds from start to end
diff_ts=$(( end_ts - start_ts ))

# Get number of days
if [[ ${diff_ts} -ge ${day} ]]; then
	d=$(( diff_ts / day ))
	diff_ts=$(( diff_ts % day ))
fi

# Get number of hours
if [[ ${diff_ts} -ge ${hrs} ]]; then
	h=$(( diff_ts / hrs ))
	diff_ts=$(( diff_ts % hrs ))
fi

# Get number of minutes
if [[ ${diff_ts} -ge 60 ]]; then
	m=$(( diff_ts / 60 ))
	diff_ts=$(( diff_ts % 60 ))
fi

# Remainder is seconds
s=${diff_ts}

# Format minutes and seconds
printf -v s "%02d" "${s}"
printf -v m "%02d:" "${m}"

# Format hours or leave blank
if [[ ${h} -eq 0 ]]; then
	h=""
else
	printf -v h "%02d:" "${h}"
fi

# Format days or leave blank
if [[ ${d} -eq 0 ]]; then
	d=""
elif [[ ${d} -eq 1 ]]; then
	d="${d} Day "
else
	d="${d} Days "
fi

# Print it all out
printf "%s%s%s%s\n" "${d}" "${h}" "${m}" "${s}"
