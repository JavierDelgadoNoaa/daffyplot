#!/usr/bin/env python

'''
Create plots showing the maxwind and intensity values obtained from the given tracker's output file.
A line is created for each cycle that falls within the start and end dates in the config file. 
The following parmeters specific to this script will adjust the output:
   FADE_LINES_WITH_TIME -  Make lines progressively darker for each cycle, when plotting multiple cycles
   FORCE_SKIP_NATURE_PLOT - Override setting to include the nature run plot. (e.g. if plotting more than one cycle)
See the comments below for additional insight on these.parameter is set

Issues:
 - The scheme for adjusting the colors is not great, but it works and is concise
 - As a consequence of the above, the lines in the legend entries also appear faded.
   This can probably be fixed fairly easily
 -> Since only one cycle's forecast is generally plotted, these shouldn't be serious issues.

Javier.Delgado@noaa.gov

'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import plot, ylabel, xlabel, show, legend, figure, savefig, axhline, ylim, gca, scatter
import logging as log
from daffy_plot.plot_helper import DaffyTCVPlotHelper

#
# Set options specific to this script
#

# If True and plotting multiple cycles, the nature run lines will not be plotted even if set 
# to do so in the config file. You generally want this to be True or you'll get multiple 
# nature run lines, since the plot helper plots them per cycle.
FORCE_SKIP_NATURE_PLOT_IF_MULTIPLE_CYCLES = True
# If True, use increasing alpha levels for each cycle. This facilitates interpretation   
# of the plots when plotting several cycles of data.
FADE_LINES_WITH_TIME = True
# override log level
#log.basicConfig(level=log.DEBUG)

#
# MAIN
#

plot_helper = DaffyTCVPlotHelper()

if FORCE_SKIP_NATURE_PLOT_IF_MULTIPLE_CYCLES and len(plot_helper.datasets[0].cycles) > 1:
   log.info("Overriding config option to plot the nature run values")
   plot_helper.cfg.plot_nature_values = False

for metric_name in ('mslp_value', 'maxwind_value'):
   figure()
   for dataset in plot_helper.datasets:
      for cycleIdx,cycle in enumerate(dataset.cycles):
         if not FADE_LINES_WITH_TIME or len(dataset.cycles)==1: alpha = 1
         else: alpha = max(0.2, float(cycleIdx)/(len(dataset.cycles)-1) )
         plot_helper.plot_dataset_metric_vs_fhr(dataset, cycle, metric_name, y_label=metric_name, alpha=alpha) 
         #plot_helper.plot_dataset_metric_vs_fhr(dataset, cycle, metric_name, y_label=metric_name, alpha=0.5)
   plot_helper.create_simple_legend()
   savefig(metric_name + '.png')
   

