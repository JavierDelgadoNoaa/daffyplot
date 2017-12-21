#!/usr/bin/env python

'''
Calculate and create plots for the mean track, MSLP, and maxwind errors 
(experiment - truth) across multiple cycles. The cycles included are specified
via the start_date, end_date, and frequency parameters in the given 
configuration file.

Usage: %prog [options].

'''

import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import plot, ylabel, xlabel, show, legend, figure, savefig, axhline, ylim, gca, scatter
import logging as log
from daffy_plot.plot_helper import DaffyTCVPlotHelper


# override log level
log.basicConfig(level=log.DEBUG)
#log.basicConfig(level=log.INFO)

outputfile_prefix = 'mean_'


def main():
    plot_helper = DaffyTCVPlotHelper(usage_string=__doc__)
       
    for metric_name in ('track_error', 'mslp_error', 'maxwind_error'):
       figure()
       for dataset in plot_helper.datasets:
          plot_helper.plot_mean_dataset_metric_vs_fhr(dataset, metric_name, y_label=metric_name)
       plot_helper.create_simple_legend()
       savefig(outputfile_prefix + metric_name + '.png')
       
if __name__ == '__main__':
    main()
    #import profile
    #profile.run('main()')
