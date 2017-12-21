#!/usr/bin/env python

'''
Compare trackers - Use both the 'nolan' and 'gfdl' trackers for the nature run
and plot the TC stats for each experiment.
NOTE: Experiments must have run both the Diapost and GFDL trackers

Javier.Delgado@noaa.gov

'''

import os
import copy
import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import plot, ylabel, xlabel, show, legend, figure, savefig, axhline, ylim, gca, scatter
import logging as log
from daffy_plot.plot_helper import DaffyTCVPlotHelper
from daffy_plot.nature_track import NatureGfdlTrackHelper, NatureNolanTrackHelper

# override log level
log.basicConfig(level=log.DEBUG)

outputfile_prefix = 'tracker_comparo_'

USAGE = 'Usage: %prog [options]. '  + __doc__
plot_helper = DaffyTCVPlotHelper(usage_string=USAGE)

EXPT_DIAPOST_LINE_COLOR = 'green'
EXPT_GFDL_LINE_COLOR = 'red'

cfg = plot_helper.cfg 
#for metric_name in ('mslp_value', 'maxwind_value', 'mslp_error', 'maxwind_error', 'track_error'):
# Only plot the values, since errors are relative to a single NR
for metric_name in ('mslp_value', 'maxwind_value'):
   figure()
   for dataset in plot_helper.datasets:
      ax = gca()
      # plot the Diapost-obtained data 
      dataset.plot_options['tracker'] = 'diapost'
      dataset.plot_options['line_color'] = EXPT_DIAPOST_LINE_COLOR
      cfg.tracker_data_file_name = 'fcst_track.d02.txt'
      # the tracker file name is actually added when instantiating the DaffyDataset 
      dataset.tracker_output_file_name = cfg.tracker_data_file_name
      plot_helper.plot_dataset_metric_vs_fhr(dataset, cfg.start_date, metric_name, axes=ax, y_label=metric_name, label='diapost')
      # plot the gfdltrk-obtained data
      dataset.plot_options['tracker'] = 'gfdl'
      dataset.plot_options['line_color'] = EXPT_GFDL_LINE_COLOR
      cfg.tracker_data_file_name = 'atcf_trk.txt'
      dataset.tracker_output_file_name = 'atcf_trk.txt'
      plot_helper.plot_dataset_metric_vs_fhr(dataset, cfg.start_date, metric_name, axes=ax, y_label=metric_name, label='gfdl')
      
      # Now add line with GFDL track
      cfg.nature_line_color = 'purple' 
      cfg.nature_line_style = '--'
      cfg.nature_track_helper = NatureGfdlTrackHelper(cfg.start_date, 
                                                      cfg.end_date + cfg.forecast_duration, 
                                                      './sample_datasets/hnr1_gfdltrk_atcf.txt')
      plot_helper.plot_nature_run_values(cfg.start_date, metric_name, label="Nature_GFDL")
      
      # restore
      cfg.nature_line_color = 'black'
      cfg.nature_line_style = '-'
      cfg.nature_run_tracker = 'nolan'
      cfg.nature_track_helper =  NatureNolanTrackHelper(cfg.start_date, 
                                                        cfg.end_date + cfg.forecast_duration, 
                                                        './sample_datasets/atcfNRD03.txt')
      #nature_gfdl_atcf = './sample_datasets/hnr1_gfdltrk_atcf.txt'
      #if not os.path.exists(nature_gfdl_atcf):
      #    log.error("Could not find atcf file for nature with gfdl tracker")
      #gfdl_trk = NatureGfdlTrackHelper(cfg.start_date, cfg.end_date, nature_gfdl_atcf).get_nature_track_data()
       #NatureGfdlTrackHelper
      #plot(gfdl_trk.output_dates, getattr(gfdl_trk, metric_name) )
      #timeVals = range(int(cfg.start_date), int(cfg.end_date), 3600)
      #metricVals = [getattr(gfdl_trk[t], metric_name) for t in timeVals]
      #import pdb ; pdb.set_trace()
      #ax.plot(timeVals, metricVals, color='purple', label='nature_gfdl', ls='--')
      #legend() 
   handles, labels = gca().get_legend_handles_labels()
   
   plot_helper.create_simple_legend()
   savefig(outputfile_prefix + metric_name + '.png')
   

