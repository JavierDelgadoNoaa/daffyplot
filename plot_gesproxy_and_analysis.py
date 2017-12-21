#!/usr/bin/env python

'''

Show the TC Vitals stats for the  "firstguess proxy" (i.e. the 6th hour of the previous deterministic forecast)
and analysis for each cycle of the experiment.

Javier.Delgado@noaa.gov

'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import plot, ylabel, xlabel, show, legend, figure, savefig, axhline, ylim, gca, scatter, title
from daffy_plot.tracker_utils import get_experiment_diapost_data, get_nature_track_data
import logging as log
from daffy_plot.daffy_plot_config import DaffyPlotConfig
import matplotlib.dates
from matplotlib.dates import DateFormatter, WeekdayLocator, DayLocator, MONDAY, HourLocator
import pytz
from tzlocal import get_localzone # $ pip install tzlocal
import datetime

#
# SET VARIABLES
#
GES_FHR = 6
ANALYSIS_FHR = 0
# set to the current timezone, since we use localtime() ( date is arbitrary since we just need the tz name)
#TIMEZONE = pytz.timezone( get_localzone().tzname( datetime.datetime(2012,1,1) ) ) 
TIMEZONE = pytz.utc

# override log level
log.basicConfig(level=log.INFO)


#
# MAIN
# 
daffy_config = DaffyPlotConfig()
   
for metric_name in ('mslp_error', 'maxwind_error', 'track_error'):
   for dataset in daffy_config.datasets:
      ges_data = []
      analysis_data = []
      epochs_ges = []
      epochs_analysis = []
      for cycle in dataset.cycles:
         # read tracker data and extract the analysis and "firstguess proxy" values
         tracker_data = dataset.get_tc_error_stats(cycle)
         ges_tracker_data = [ tdEntry for tdEntry in tracker_data.tracker_entries if tdEntry.fhr == GES_FHR ]
         analysis_tracker_data = [ tdEntry for tdEntry in tracker_data.tracker_entries if tdEntry.fhr == ANALYSIS_FHR ]
         log.debug(ges_tracker_data)
         log.debug(analysis_tracker_data)
         assert len(ges_tracker_data) == 1
         assert len(analysis_tracker_data) == 1
         ges_tracker_data = ges_tracker_data[0]
         analysis_tracker_data = analysis_tracker_data[0]
         # populate lists for plotting
         ges_data.append( getattr(ges_tracker_data, metric_name) )
         analysis_data.append( getattr(analysis_tracker_data, metric_name) )
         epochs_ges.append(cycle + (3600*GES_FHR) )
         epochs_analysis.append(cycle)
      log.debug('%s : %s : ges : %s' %(dataset.name, metric_name, ges_data) )
      log.debug('%s : %s : analysis : %s' %(dataset.name, metric_name, analysis_data) )
      # convert x axis values from epoch to datetime obj
      epochs_ges = [ matplotlib.dates.num2date(matplotlib.dates.epoch2num(x), tz=TIMEZONE) for x in epochs_ges ]
      epochs_analysis = [ matplotlib.dates.num2date(matplotlib.dates.epoch2num(x), tz=TIMEZONE) for x in epochs_analysis ]
      # plot valaues
      plot(epochs_ges, ges_data, color=dataset.plot_options['line_color'], ls=' ', marker='x', label=dataset.name)
      # Note: Not putting label for these since its the same color as the ges. Title specifies what x and o mean
      plot(epochs_analysis, analysis_data, color=dataset.plot_options['line_color'], ls=' ', marker='o', alpha=0.7)
      # make x axis prettier
      ax = gca()
      ax.xaxis.set_major_locator( HourLocator(byhour=range(0,24,24), tz=TIMEZONE) )
      ax.xaxis.set_minor_locator( HourLocator(byhour=range(0,24,6), tz=TIMEZONE) )
      ax.xaxis.set_major_formatter( DateFormatter('%m/%d@%Hz') )
      ax.figure.autofmt_xdate()
   
   # legend
   handles, labels = gca().get_legend_handles_labels()
   leg = legend(handles, labels, loc=daffy_config.legend_position)
   leg.get_frame().set_alpha(daffy_config.legend_alpha)
   
   title("Analysis (o) and previous forecast's 6th forecast hour (x) for each cycle")
   axhline(y=0, color='#222222', ls='--')
   #savefig('nolegend_' + metric_name + '.png')
   savefig('analysis_and_proxyges_' + metric_name + '.png')
   figure()
   
#show()

