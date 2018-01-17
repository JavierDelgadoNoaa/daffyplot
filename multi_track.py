from tempfile import mkstemp
from datetime import datetime, timedelta
import os
import shutil
import itertools

src_config_file = "sample.cfg"
start_date = datetime(year=2005, month=8, day=1, hour=6, minute=0)
end_date = datetime(year=2005, month=8, day=5, hour=0, minute=0)
interval_seconds = 6 * 3600

def date_generator():
    curr_date = start_date
    while curr_date <= end_date:
        yield curr_date
        curr_date += timedelta(seconds=interval_seconds)

dates = list(itertools.islice(date_generator(), 0, None))
print dates

'''
## easier:
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
