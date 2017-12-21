#!/usr/bin/env python

'''

Create 3 figures with TCstats error (i.e. experiment-nature) output, 
one for track, one for wind, one for MSLP.
Each figure consists of a grid of subplots, one subplot for each forecast.

Javier.Delgado@noaa.gov

'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import savefig, show
from daffy_plot.plot_helper import DaffyTCVPlotHelper
from common import create_grid_of_plots

USAGE_STRING = ("Usage: %prog [options].\nCreate images consisting of "
               "grids of errors for each cycle in the specified range "
               "of start_date and end_date. 3 images are created: "
               "track_error, mslp_error, and maxwind_error")


#
# MAIN
#
if __name__ == '__main__':
   
   plot_helper = DaffyTCVPlotHelper(usage_string=USAGE_STRING)
   if plot_helper.cfg.difference_type == 'absolute':
        diffStr = "[abs(Experiment - Nature)]"
   else:
        diffStr = "(Experiment - Nature)"
   
   create_grid_of_plots(plot_helper, 'track_error', x_label="Forecast Hour", 
                        y_label="Track Error", figure_title="Track Error", 
                        legend_position = plot_helper.cfg.legend_position, 
                        plots_per_page=16, save_prefix='track_error_grid')

   create_grid_of_plots(plot_helper, 'maxwind_error', x_label="Forecast Hour", 
                        y_label="Max 10m Wind Error", 
                        figure_title="Max Wind Error {}.".format(diffStr),
                        legend_position = plot_helper.cfg.legend_position,
                        plots_per_page=16, save_prefix='maxwind_error_grid')

   create_grid_of_plots(plot_helper, 'mslp_error', x_label="Forecast Hour", 
                        y_label="MSLP Error (mb)", 
                        figure_title="MSLP Error {}".format(diffStr),
                        legend_position = plot_helper.cfg.legend_position,
                        plots_per_page=16, save_prefix='mslp_error_grid')
   #savefig('maxwind_error_grid.png')
   #savefig('maxwind_error_grid.png')
   #savefig('mslp_error_grid.png')
   
   show()

