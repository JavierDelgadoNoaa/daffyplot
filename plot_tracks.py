#!/usr/bin/env python

'''
Plot the tracks for all datasets specified in the config file using the
DaffyTrackPlotHelper class, which will obey all the config settings in 
the "map_settings" section of the config file. Tracker used will depend
on the 'tracker', 'tracker_data_file_name', and 'truth_tracker' config
options.
'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import plot, show, legend, figure, savefig, gca
import logging as log
from daffy_plot.plot_helper import DaffyTrackPlotHelper


# override log level
log.basicConfig(level=log.DEBUG)

USAGE = 'Usage: %prog [options]. '  + __doc__
#plot_helper = DaffyTrackPlotHelper(usage_string=USAGE)
plot_helper = DaffyTrackPlotHelper(usage_string=USAGE, shadeLines=False)

   
#figure()
for dataset in plot_helper.datasets:
    for cycle in dataset.cycles:
        plot_helper.plot_track_for_cycle(dataset, cycle)
log.info("Overriding alpha level for legend")
plot_helper.cfg.legend_alpha = 0.97
plot_helper.create_simple_legend() # TODO : can we use same one from tcvplothelper?
savefig('tracks.png')  
#savefig('/home/Javier.Delgado/www/img/tracks.png')

