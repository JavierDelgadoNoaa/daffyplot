import matplotlib
matplotlib.use('Agg')
from matplotlib.pyplot import plot, legend, figure, subplot, title, subplots_adjust, figlegend, ylim, figtext, savefig, axhline
import os
import sys
import time
from math import sqrt, ceil
from daffy_plot.plot_helper import DaffyTCVPlotHelper
from pycane.timing.conversions import epoch_to_pretty_time_string

'''
Common methods for plotting

Javier.Delgado@noaa.gov
'''

FIG_HEIGHT = 15
FIG_WIDTH = 15
SUBPLOT_HSPACE = 0.5
SUBPLOT_WSPACE = 0.4
FIG_TITLE_X = 0.3
FIG_TITLE_Y = 0.96
FIG_TITLE_FONTSIZE = 22


def create_grid_of_plots(plot_helper, metric_name, x_label="fhr", y_label="", 
                         figure_title="", legend_position = 'best', 
                         plots_per_page=16, save_prefix=None, file_type='png'):
    num_cycles = len(plot_helper.datasets[0].cycles)
    num_pages = ceil(num_cycles / plots_per_page)
    for i, startCycle in enumerate(range(0, num_cycles, plots_per_page)):
        endCycle = startCycle + plots_per_page
        #currCycles = plot_helper.datasets[startCycle:endCycle]
        currCycles = plot_helper.datasets[0].cycles[startCycle:endCycle]
        _create_one_grid(currCycles, plot_helper, metric_name, x_label, 
                         y_label, figure_title, legend_position)
        if save_prefix is not None:
            savefig(save_prefix + '_' + str(i) + '.' + file_type)

def _create_one_grid(cycles, plot_helper, metric_name, x_label, y_label,
                     figure_title, legend_position='best'):
   '''
   Creates a figure consisting of several subplots, one for each cycle in plot_helper.datasets[0].cycles
   The metric plotted is specified in <metric_name> and should be a field in the object returned by 
   the plot_helper's dataset's get_tc_error_stats() or get_tc_value_stats() methods. The method used is
   determined by the <metric_name>. 
   The default plot_helper behavior applies: If it contains "_error", use 
   get_tc_error_stats(). If it contains "_value", use get_tc_value_stats()

   NOTE : 'cycles' is just a list of ints (i.e. time since epoch), which should be the same for all `dataset's, so passing just one in should be fine
   '''
   nRows = nCols = ceil( sqrt( len(cycles) ) )
   fig = figure(figsize=(FIG_WIDTH, FIG_HEIGHT))
   subplots_adjust(hspace=SUBPLOT_HSPACE, wspace=SUBPLOT_WSPACE)
   dsCtr = 0
   for dataset in plot_helper.datasets:
      i = 1 # subplot uses 1-indexing
      #for cycle in dataset.cycles:
      for cycle in cycles:
         #if metric_name.find("_value") > -1:
         ax = subplot(nRows, nCols, i)
         i += 1
         plot_helper.plot_dataset_metric_vs_fhr(dataset, cycle, metric_name, x_label=x_label, y_label=y_label, axes=ax)
         # labels and title only need be done on the final dataset, but for each cycle. 
         # actually labels are automatically created by PlotHelper.
         if dsCtr == len(plot_helper.datasets) - 1:
            title(epoch_to_pretty_time_string(cycle) )
      dsCtr += 1      
      
  # Set y limits to be the same for all plots
   plot_helper.set_y_limits(metric_name)
   for ii in range( 1, int(nRows*nCols) + 1 ):
      ax = subplot(nRows, nCols, ii)
      # Get the min/max y extents from fields in the PlotHelper
      ylim( getattr(plot_helper, 'yMin_' + metric_name), getattr(plot_helper, 'yMax_' + metric_name) )
   
    # Create legend
#   handles, labels = ax.get_legend_handles_labels()
#   fig.legend(handles, labels)
#      figtext( FIG_TITLE_X, FIG_TITLE_Y, figure_title, fontsize=FIG_TITLE_FONTSIZE)
   
   # ignore duplicates
   handles, labels = ax.get_legend_handles_labels()
   unique_handles = []
   unique_labels = []
   #print len(labels)
   for j in range(len(labels)):
      #print j
      if not labels[j] in unique_labels:
         unique_labels.append(labels[j])
         unique_handles.append(handles[j])
   handles = unique_handles
   labels = unique_labels
   #leg = legend(handles, labels, loc=plot_helper.cfg.legend_position)
   leg = fig.legend(handles, labels)
   leg.get_frame().set_alpha(plot_helper.cfg.legend_alpha)
   if len(figure_title) > 0:
      figtext( FIG_TITLE_X, FIG_TITLE_Y, figure_title, fontsize=FIG_TITLE_FONTSIZE)
  
