#!/usr/bin/env python

'''

Create 2 figures with TCstats output, one for windwind and one for MSLP values.
If configured, put the nature run values as well.
Each figure consists of a grid of subplots, one subplot for each forecast.

Javier.Delgado@noaa.gov

'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import savefig, show
import os
import time
import sys
from daffy_plot.plot_helper import DaffyTCVPlotHelper
from common import create_grid_of_plots



#
# MAIN
#
if __name__ == '__main__':
   
   plot_helper = DaffyTCVPlotHelper()
   
   create_grid_of_plots( plot_helper, 'maxwind_value', x_label="Forecast Hour", y_label="Max 10m Wind", figure_title="Intensity/Max Wind Values", legend_position = plot_helper.cfg.legend_position)
   savefig('maxwind_grid.png')

   create_grid_of_plots(plot_helper, 'mslp_value', x_label="Forecast Hour", y_label="MSLP Value (mb)", figure_title="MSLP Values", legend_position = plot_helper.cfg.legend_position) #yMin=plot_helper.yMax_mslp_error, yMax=plot_helper.yMax_mslp_error)
   savefig('mslp_grid.png')
   show()

