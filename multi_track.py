"""
Wrapper around plot_tracks.py to plot one cycle per image.
Can be used as a template to wrap other scripts
"""

from tempfile import mkstemp
from datetime import datetime, timedelta
import os
import shutil
import itertools

##
# SETTINGS
##
# The config file to use. For each cycle, a copy will be created with new start_date and 
# end_date parameters.
src_config_file = "sample.cfg"
# First cycle to process
start_date = datetime(year=2005, month=8, day=1, hour=6, minute=0)
# Last cycle to process
end_date = datetime(year=2005, month=8, day=5, hour=0, minute=0)
# Interval in seconds of cycles to process
interval_seconds = 6 * 3600


##
# LOGIC
##
def date_generator():
    # Generator to get list of all dates to process
    curr_date = start_date
    while curr_date <= end_date:
        yield curr_date
        curr_date += timedelta(seconds=interval_seconds)


##
# MAIN
##

dates = list(itertools.islice(date_generator(), 0, None))
print dates

'''
## Easier, but requires Pandas (which is in my Jet environment but takes forever
## to load), so lets stick to generator approach
import pandas
f = str(interval_seconds) + "S"
dates = pandas.date_range(start_date, end_date, freq=f)
#dates.to_pydatetime()
print list(dates)
'''

for curr_date in dates:
    fh, abs_path = mkstemp()
    with os.fdopen(fh, "w") as new_file:
        for line in open(src_config_file):
            if "start_date" in line:
                # 08-01-2005 12:00
                new_file.write("start_date = {0:%m-%d-%Y %H:%M}\n".format(curr_date))
            elif "end_date" in line:
                new_file.write("end_date = {0:%m-%d-%Y %H:%M}\n".format(curr_date))
            else:
                new_file.write(line)
    shutil.move(abs_path, "current.cfg")

    os.system("python plot_tracks.py -c current.cfg")
    shutil.move("tracks.png", "tracks-{0:%Y%m%d%H%M}.png".format(curr_date))
