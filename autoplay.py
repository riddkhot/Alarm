#!/usr/bin/env python3
"""Puts the Mac to sleep, wakes it on a timer, then plays an audio file on repeat.

  python3 autoplay.py              sleep now, wake in 2 minutes, loop the default audio
  python3 autoplay.py -m 10        wake 10 minutes from now
  python3 autoplay.py -a 05:17     wake at 05:17 (tomorrow if that time has passed)
  python3 autoplay.py -n           don't sleep the Mac; you sleep it yourself
  python3 autoplay.py -f FILE      play a different audio file
  python3 autoplay.py -v 40        set output volume (0-100) before playing
  python3 autoplay.py -t           test playback right now (no sleep, no password)

The audio repeats until you press Ctrl-C in this Terminal window.
Keep the lid open and the Mac on power. Leave this Terminal window open.
"""

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_AUDIO = Path.home() / "Desktop" / "Max Rayne House.qta"
MIN_LEAD = 60  # the wake must be at least this many seconds away

# JavaScript for Automation, run with osascript. One player loops the file
# internally, so there is no gap between repeats. It quits by itself if this
# Python script goes away.
LOOP_SCRIPT = """
ObjC.import("AVFoundation");
ObjC.import("unistd");
function run(argv) {
  var player = $.AVAudioPlayer.alloc.initWithContentsOfURLError(
      $.NSURL.fileURLWithPath(argv[0]), null);
  if (player.isNil()) throw new Error("This file can't be played as audio.");
  player.numberOfLoops = -1;
  if (!player.play) throw new Error("Playback did not start.");
  var parent = $.getppid();
  while ($.getppid() == parent) $.NSThread.sleepForTimeInterval(1);
}
"""


def clock_time(value):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        raise argparse.ArgumentTypeError("needs a 24-hour time like 05:17")
    return value


def volume_level(value):
    if not value.isdigit() or int(value) > 100:
        raise argparse.ArgumentTypeError("needs a number from 0 to 100")
    return int(value)


def whole_minutes(value):
    if not value.isdigit():
        raise argparse.ArgumentTypeError("needs a whole number of minutes")
    return int(value)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-m", dest="minutes", type=whole_minutes, default=2,
                        help="wake this many minutes from now (default 2)")
    parser.add_argument("-a", dest="at", type=clock_time,
                        help="wake at this 24-hour clock time, e.g. 05:17")
    parser.add_argument("-f", dest="audio", type=Path, default=DEFAULT_AUDIO,
                        help="audio file to play on repeat")
    parser.add_argument("-v", dest="volume", type=volume_level,
                        help="output volume 0-100 to set before playing")
    parser.add_argument("-n", dest="sleep_now", action="store_false",
                        help="don't sleep the Mac; you sleep it yourself")
    parser.add_argument("-t", dest="test_only", action="store_true",
                        help="test playback right now")
    return parser.parse_args(argv)


def wake_time(args, now):
    """Returns the datetime the Mac should wake at."""
    if args.at:
        hour, minute = map(int, args.at.split(":"))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target
    return now.replace(microsecond=0) + timedelta(minutes=args.minutes)


def play_forever(audio, volume):
    # Make the timed wake a full wake, then keep the Mac awake for as long as
    # this script is running.
    subprocess.Popen(["caffeinate", "-u", "-t", "5"])
    subprocess.Popen(["caffeinate", "-is", "-w", str(os.getpid())])

    if volume is not None:
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {volume} without output muted"],
            check=True,
        )

    print(f"{datetime.now():%H:%M:%S}  Playing {audio.name} on repeat. Press Ctrl-C to stop.")
    player = subprocess.Popen(
        ["osascript", "-l", "JavaScript", "-e", LOOP_SCRIPT, str(audio)]
    )
    try:
        failed = player.wait() != 0
    finally:
        player.terminate()
    if failed:
        sys.exit(f"Error: could not play {audio}")


def main():
    args = parse_args()

    if not args.audio.is_file():
        sys.exit(f"Error: audio file not found: {args.audio}")

    if args.test_only:
        play_forever(args.audio, args.volume)

    now = datetime.now()
    target = wake_time(args, now)
    if (target - now).total_seconds() < MIN_LEAD:
        sys.exit("Error: The wake time must be at least 1 minute away.")

    print(f"Scheduling wake for {target:%a %d %b %H:%M:%S} (needs your Mac password).")
    subprocess.run(
        ["sudo", "pmset", "schedule", "wake", target.strftime("%m/%d/%y %H:%M:%S")],
        check=True,
    )

    if args.sleep_now:
        print("Sleeping in 5 seconds. Press Ctrl-C to cancel.")
        time.sleep(5)
        subprocess.run(["pmset", "sleepnow"], check=True, stdout=subprocess.DEVNULL)
    else:
        print("Wake is set. Sleep the Mac whenever you like, with the lid open.")

    # Compare against the wall clock: this loop is frozen while the Mac sleeps
    # and resumes when it wakes. (time.monotonic() does not advance during sleep.)
    while datetime.now() < target:
        time.sleep(2)

    play_forever(args.audio, args.volume)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
    except subprocess.CalledProcessError as error:
        sys.exit(f"Error: {error.cmd[0]} failed with exit code {error.returncode}.")
