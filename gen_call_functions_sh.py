"""Generate call_functions_batch.sh
    - in : from/to date
    - out: shell script for calling cloud functions
"""

import datetime
import json
import pytz
import sys


def main():
    args = sys.argv
    oldest_dt = datetime.datetime.strptime(args[1], '%Y-%m-%d')
    latest_dt = datetime.datetime.strptime(args[2], '%Y-%m-%d')
    
    # check
    if oldest_dt >= latest_dt:
        print('oldest_dt must be less than latest_dt.')
        sys.exit(1)
    
    # split day by day
    intervals = []
    _start = oldest_dt
    _end = _start + datetime.timedelta(days=1)
    while _end <= latest_dt:
        intervals.append([_start.timestamp(), _end.timestamp()])
        _start = _end
        _end = _start + datetime.timedelta(days=1)
    
    # make script string
    base_str = "python main.py"
    cmd_lines = []
    for i, interv in enumerate(intervals):
        comment_str = "echo exec call function {}".format(i+1)
        cmd_lines.append(comment_str)
        
        opt_str = f"{interv[1]} {interv[0]}"  # latest_ut oldest_ut
        cmd_lines.append(base_str + " " + opt_str)

    # write script
    with open('call_functions_batch.sh', 'w') as f:
        f.write("\n".join(cmd_lines))


if __name__ == "__main__":
    args = sys.argv
    
    # parse args
    if len(args) != 3:
        print('3 args are required.')
        print('{} args are input.'.format(len(args)))
        print('1st positional arg is oldest date (YYYY-MM-DD)')
        print('2nd positional arg is latest date (YYYY-MM-DD)')
        sys.exit(1)
    main()

