#!/bin/bash
# Puts the Mac to sleep, wakes it on a timer, then plays a YouTube video in Chrome.
#
#   ./autoplay.sh              sleep now, wake in 2 minutes, play the default video
#   ./autoplay.sh -m 10        wake 10 minutes from now
#   ./autoplay.sh -a 05:17     wake at 05:17 (tomorrow if that time has passed)
#   ./autoplay.sh -n           don't sleep the Mac; you sleep it yourself
#   ./autoplay.sh -u URL       play a different video
#   ./autoplay.sh -v 40        set output volume (0-100) before playing
#   ./autoplay.sh -t           test playback right now (no sleep, no password)
#
# Keep the lid open and the Mac on power. Leave this Terminal window open.

set -euo pipefail

URL="https://www.youtube.com/watch?v=4t4AQ15yj1M"
MINUTES=2
AT=""
SLEEP_NOW=1
VOLUME=""
TEST_ONLY=0
KEEP_AWAKE=600   # seconds to hold the Mac awake after waking, so playback can start

die() { echo "Error: $*" >&2; exit 1; }

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while getopts "m:a:u:v:nth" opt; do
  case "$opt" in
    m) MINUTES="$OPTARG" ;;
    a) AT="$OPTARG" ;;
    u) URL="$OPTARG" ;;
    v) VOLUME="$OPTARG" ;;
    n) SLEEP_NOW=0 ;;
    t) TEST_ONLY=1 ;;
    h) usage 0 ;;
    *) usage 1 ;;
  esac
done

[[ "$MINUTES" =~ ^[0-9]+$ ]] || die "-m needs a whole number of minutes."
[[ -z "$VOLUME" || "$VOLUME" =~ ^(100|[0-9]{1,2})$ ]] || die "-v needs a number from 0 to 100."
[[ -z "$AT" || "$AT" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]] || die "-a needs a 24-hour time like 05:17."
[ -d "/Applications/Google Chrome.app" ] || die "Google Chrome is not installed in /Applications."

play() {
  # Turn the display on and hold the Mac awake while the video starts.
  caffeinate -disu -t "$KEEP_AWAKE" &

  # Wi-Fi takes a few seconds to reconnect after wake; wait up to a minute.
  for _ in $(seq 1 30); do
    nc -z -G 2 www.youtube.com 443 >/dev/null 2>&1 && break
    sleep 2
  done

  if [ -n "$VOLUME" ]; then
    osascript -e "set volume output volume $VOLUME without output muted"
  fi

  # The --args flag only takes effect if Chrome was not already running.
  open -a "Google Chrome" "$URL" --args --autoplay-policy=no-user-gesture-required
  echo "$(date '+%H:%M:%S')  Opened $URL in Chrome."
}

if [ "$TEST_ONLY" -eq 1 ]; then
  play
  exit 0
fi

now=$(date +%s)
if [ -n "$AT" ]; then
  target=$(date -j -f "%Y-%m-%d %H:%M:%S" "$(date +%Y-%m-%d) $AT:00" +%s)
  if [ "$target" -le "$now" ]; then
    target=$(date -j -v+1d -r "$target" +%s)
  fi
else
  target=$((now + MINUTES * 60))
fi
[ $((target - now)) -ge 60 ] || die "The wake time must be at least 1 minute away."

wake_str=$(date -r "$target" "+%m/%d/%y %H:%M:%S")
echo "Scheduling wake for $(date -r "$target" '+%a %d %b %H:%M:%S') (needs your Mac password)."
sudo pmset schedule wake "$wake_str"

if [ "$SLEEP_NOW" -eq 1 ]; then
  echo "Sleeping in 5 seconds. Press Ctrl-C to cancel."
  sleep 5
  pmset sleepnow >/dev/null
else
  echo "Wake is set. Sleep the Mac whenever you like, with the lid open."
fi

# This loop is frozen while the Mac sleeps and resumes when it wakes.
while [ "$(date +%s)" -lt "$target" ]; do
  sleep 2
done

play
