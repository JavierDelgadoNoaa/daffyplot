#!/usr/bin/env python

'''
Create plots showing the experiment-nature values for track, maxwind, and intensity values obtained from the given tracker's output file.
A line is created for each cycle that falls within the start and end dates specified in the config file. 
The following parmeters can be used:
   FADE_LINES_WITH_TIME -  Make lines progressively darker for each cycle, when plotting multiple cycles
See the comments below for additional insight on these.

OUTPUT: track_error.png, mslp_error.png, maxwind_error.png

Issues:
 - The scheme for lightening the colors is not great, but it works and is concise
 - As a consequence of the above, the lines in the legend entries also appear faded.

Javier.Delgado@noaa.gov

'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import plot, ylabel, xlabel, show, legend, figure, savefig, axhline, ylim, gca, scatter
import logging as log
from daffy_plot.tracker_utils import get_experiment_diapost_data, get_nature_track_data
from daffy_plot.plot_helper import DaffyTCVPlotHelper

#
# Set options specific to this script
#

# If True, use increasing alpha levels for each cycle. This facilitates interpretation   
# of the plots when plotting several cycles of data.
FADE_LINES_WITH_TIME = True
# override log level
#log.basicConfig(level=log.DEBUG)

#
# MAIN
#

plot_helper = DaffyTCVPlotHelper()

for metric_name in ('track_error', 'mslp_error', 'maxwind_error'):
   figure()
   for dataset in plot_helper.datasets:
      for cycleIdx,cycle in enumerate(dataset.cycles):
         if not FADE_LINES_WITH_TIME or len(dataset.cycles)==1: alpha = 1
         else: alpha = max(0.2, float(cycleIdx)/(len(dataset.cycles)-1) )
         plot_helper.plot_dataset_metric_vs_fhr(dataset, cycle, metric_name, y_label=metric_name, alpha=alpha) 
   plot_helper.create_simple_legend()
   savefig(metric_name + '.png')
   

