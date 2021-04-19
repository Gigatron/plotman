#!/usr/bin/python3

import os
import re
import statistics
from datetime import datetime, timedelta

import texttable as tt

import plot_util

SEC = 1
MIN = SEC * 60
HOUR = MIN * 60
DAY = HOUR * 24
LOG_FILE_PATTERN = r"\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}\.log"
LOG_FILE_TIME_STR = "%Y-%m-%d-%H:%M:%S"
PLOT_SIZE_TB = 108.8 / 1000


class LogAnalyzer(object):
    # Map from key (e.g. logdir or the like) to (map from measurement name to list of values)
    all_measures = ["phase 1", "phase 2", "phase 3", "phase 4", "total time"]

    def __init__(self, window_in_day=3):
        self._window_in_day = window_in_day

    def analyze(self, log_dir_or_file):
        now = datetime.now()
        data = {}
        log_file_names = []
        if os.path.isdir(log_dir_or_file):
            for f in os.listdir(log_dir_or_file):
                if re.match(LOG_FILE_PATTERN, f):
                    time_str = f.split(".")[0]
                    creation_time = datetime.strptime(time_str, LOG_FILE_TIME_STR)
                    if creation_time > now - timedelta(days=self._window_in_day):
                        log_file_names.append(os.path.join(log_dir_or_file, f))
        else:
            log_file_names.append(log_dir_or_file)

        done = 0
        for logfilename in log_file_names:
            with open(logfilename, "r") as f:
                key = None
                for line in f:
                    #
                    # Aggregation specification
                    #

                    # Starting phase 1/4: Forward Propagation into tmp files... Sun Nov 15 00:35:57 2020
                    # TODO: This only does by day!!!
                    m = re.search(
                        r"^Starting phase 1/4.*files.*\d\d (\d\d):\d\d:\d\d \d\d\d\d", line
                    )
                    if m:
                        bucketsize = 2
                        hour = int(m.group(1))
                        hourbucket = int(hour / bucketsize)
                        # key += '-%02d-%02d' % (hourbucket * bucketsize, (hourbucket + 1) * bucketsize)

                    # Starting plotting progress into temporary dirs: /mnt/tmp/01 and /mnt/tmp/a
                    m = re.search(r"^Starting plotting.*dirs: (.*) and (.*)", line)
                    if m:
                        key = m.group(1)

                    #
                    # Data collection
                    #

                    # Time for phase 1 = 22796.7 seconds. CPU (98%) Tue Sep 29 17:57:19 2020
                    for phase in ["1", "2", "3", "4"]:
                        m = re.search(r"^Time for phase " + phase + " = (\d+.\d+) seconds..*", line)
                        if m:
                            data.setdefault(key, {}).setdefault("phase " + phase, []).append(
                                float(m.group(1))
                            )

                    # Total time = 49487.1 seconds. CPU (97.26%) Wed Sep 30 01:22:10 2020
                    m = re.search(r"^Total time = (\d+.\d+) seconds.*", line)
                    if m:
                        done += 1
                        data.setdefault(key, {}).setdefault("total time", []).append(
                            float(m.group(1))
                        )

        # Prepare report
        tab = tt.Texttable()
        headings = ["tmp_dir"] + self.all_measures
        tab.header(headings)

        # for logdir in logdirs:
        for key in data.keys():
            row = [key]
            for measure in self.all_measures:
                values = data.get(key, {}).get(measure, [])
                if len(values) > 1:
                    row.append(
                        "μ=%s σ=%s"
                        % (
                            plot_util.human_format(statistics.mean(values), 1),
                            plot_util.human_format(statistics.stdev(values), 0),
                        )
                    )
                elif len(values) == 1:
                    row.append(plot_util.human_format(values[0], 1))
                else:
                    row.append("N/A")
            tab.add_row(row)

        (rows, columns) = os.popen("stty size", "r").read().split()
        tab.set_max_width(int(columns))
        s = tab.draw()
        print(f"{s}\n")
        velocity = PLOT_SIZE_TB * done / self._window_in_day
        print(
            f"{done} plots have been done in past {self._window_in_day} days, "
            f"approximately {velocity:.2f} TB/Day"
        )
