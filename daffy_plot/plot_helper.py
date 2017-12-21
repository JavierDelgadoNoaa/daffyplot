#!/usr/bin/env python
'''
THis module contains classes to encapsulate routine tasks involved in creating plots
from data from experiments carried out using all modelling systems supported
by DaffyPlot

Javier.Delgado@noaa.gov
'''

import os
import sys
import time
import numpy as np
import matplotlib.pyplot as plt
import logging as log
import matplotlib.dates as mpl_dates
from matplotlib.dates import DateFormatter, WeekdayLocator, DayLocator, MONDAY, HourLocator
from matplotlib.colors import ColorConverter
import pytz
from tzlocal import get_localzone # $ pip install tzlocal
import datetime
import glob
from daffy_dataset import DaffyExperimentDataset
from daffy_plot_config import DaffyPlotConfig
#from map_plotter import plot_track # TODO : Use a pycane lib instead. This is in extern
from pycane.postproc.viz.tcv import track_plotter
from nwpy.viz.map import bling as pycane_bling
from  pycane.postproc.viz.tcv import tcv_plot_helper
from pycane.postproc.tracker import objects as trkobj
from pycane.postproc.tracker import utils as trkutils
#
# CONSTANTS
#

BEST_TRACK_LABEL = "Best"

# set to the current timezone, since we use localtime() (note date is random
# since we just need the tz name)
#TIMEZONE = pytz.timezone( get_localzone().tzname( datetime.datetime(2012,1,1) ) )
TIMEZONE = pytz.utc

#
# CLASSES
#

class DaffyPlotHelper(object):

    def __init__(self, usage_string=None):
        '''
        Instantiate a DaffyPlotHelper. Whatever options were passed in via command line will be parsed by the
        DaffyPlotConfig to determine the config file to use.
        The optional `usage_string` will be used to provide additional information when the user uses the -h
        command line option.
        '''
        self.cfg = DaffyPlotConfig(usage_string=usage_string)
        try: # string given for log level (e.g. DEBUG, INFO, etc.)
            log.basicConfig(level=getattr(log, self.cfg.log_level) )
        except: # number given for log level
            log.basicConfig(level=int(self.cfg.log_level) )
        plt.style.use(self.cfg.style_paths)

    def create_simple_legend(self, skip_duplicates=True):
        '''
        Wrapper around Pycane's legend creation function 
        that uses configured legend position and alpha settings
        '''
        pycane_bling.create_simple_legend(skip_duplicates=skip_duplicates,
                                          alpha=self.cfg.legend_alpha,
                                          position=self.cfg.legend_position)

    @property
    def datasets(self): return self.cfg.datasets


class DaffyTCVPlotHelper(DaffyPlotHelper):
    '''
    Provides routines for plotting TCVitals statistics
    '''

    def __init__(self, usage_string=None):
        ''' Instantiate a TCVPlotHelper '''
        super(DaffyTCVPlotHelper, self).__init__(usage_string=usage_string)



    def _replace_nonpresent_kwargs(self, original_kwargs, **new_kwargs):
        '''
        Helper functions that create plots and decorate them based on cfg/dataset attributes take in a kwargs
        argument with plot options passed in from higher level functions. This method adds cfg/dataset-specific
        attributes only if they are not already in the kwargs
        '''
        for key,value in new_kwargs.iteritems():
            if not key in original_kwargs: original_kwargs[key] = value
        return original_kwargs
    
    
    def line_plot_wrapper(self, xVals, yVals, ax=None, dataset=None, 
                          x_label=None, y_label=None,
                          **kwargs):
        '''
        Create a line plot of the given x and y values, taking into 
        account configuration options encapsulated in the optionally
        given`dataset` and in self.cfg.
        @param xVals list of x values
        @param yVals list of y values
        @param ax Axes object to plot on
        @param dataset DaffyDataset object containing  plot options
        @param x_label text to use for the x-axis label
        @param y_label text to use for the y-axis label
        @param **kwargs dictionary with arguments to be passed to MPL::plot()
        '''
        if ax is None:
            ax = plt.gca()
        if dataset is not None:
            kwargs['color'] = dataset.plot_options['line_color']
            kwargs['linestyle'] = dataset.plot_options['line_style']
            kwargs['label'] = dataset.name
            kwargs['linewidth'] = dataset.plot_options['line_width']
            # add horizontal line at 0 if set in config
            if dataset.plot_options.has_key('hline_at_zero'):
                plt.axhline(y=0, color='#222222', ls=':', linewidth=6) # TODO : ensure this is always here so it is not overriden by the stylesheet. Gotta find a value that goes well with all view targets
        
        if not kwargs.has_key('linewidth'):
            kwargs['linewidth'] = self.cfg.line_width

        tcv_plot_helper.tcv_plot_basic(xVals, yVals, ax=ax, **kwargs)

        # add axis labels
        if x_label:
            plt.xlabel(x_label)
        else:
            if self.cfg.time_axis_parameter == 'fhr':
                plt.xlabel('Forecast Hour')
        if y_label:
            # automagically make y axis label text better
            y_label = y_label.replace("_", " ").title()
            if dataset.plot_options['tracker'] in ('diapost', 'gfdltrk'):
                log.info("Assuming units of kts and mb based on tracker setting")
                if y_label.startswith("Maxwind"):
                    y_label += ' (kts)'
                elif y_label.startswith("Mslp"):
                    y_label += ' (mb)'
                elif y_label.startswith("Track"):
                    # pycane currently returns km for distance error
                    y_label += ' (km)'
            plt.ylabel(y_label)#, fontsize=20)

        # set tick marks to 12,24...
        if self.cfg.time_axis_parameter == 'fhr':
            ax.set_xticks(np.arange(0, self.cfg.forecast_duration/3600, 12))

    def plot_dataset_metric_vs_fhr(self, dataset, cycle, metric_name, 
                                   axes=None, do_scatter=False, 
                                   x_label=None, y_label=None, 
                                   **kwargs):
        '''
        Plots the <metric_name> values for the <dataset>, for the <cycle>th 
        cycle, where <cycle> is in seconds since epoch. The metric plotted is 
        specified in <metric_name> and should be a field in the object returned 
        by the plot_helper's dataset's get_tc_error_stats() or 
        get_tc_value_stats() methods. The method used is determined by the 
        <metric_name>. If it contains "_value", use get_tc_value_stats(). If it
        contains "_error", use get_tc_error_stats()
        OPTIONAL ARGUMENTS
           - "axes" element pointing to the axes object to plot on (if not 
             passed in, use gca())
           - "do_scatter" parameter to override decision to create
                                  a scatter plot showing the points where the
                                  tracker flagged the values
           - x_label - string containing x label text
           - y_label - string containing y label text
           - **kwargs argument may contain any arguments normally passed to 
              MPL::plot()

        '''
        if not dataset in self.datasets: 
           msg = 'Passed in dataset is not in self.datasets. Cowardly bailing'
           raise Exception(msg)
        if "_value" in metric_name:
            # This will be a ForecastTrack object
            fcst_track = dataset.get_tc_value_stats(cycle) 
            tracker_data = fcst_track.tracker_entries
        #elif metric_name.find("_error") > -1:
        elif "_error" in metric_name:
            if self.cfg.difference_type == "absolute":
                is_absolute = True
            elif self.cfg.difference_type == "relative":
                is_absolute = False
            else:
                raise Exception("Unknown difference type")
            fcst_track = dataset.get_tc_error_stats(cycle, is_absolute=is_absolute)
            tracker_data = fcst_track.tracker_entries
        else:
            msg = "`metric_name` passed to `create_gridded_figure()` is "\
                  "expected to have either '_value' or '_error' in its name"
            raise ValueError(msg)
        #time_axis_values = self.get_time_axis_values(
                                        #cycle, metric_name, 
                                        #[ x.fhr for x in tracker_data ] )
        #line = ax.plot( fhrs, values, 
        #                color=dataset.plot_options['line_color'], 
        #                linestyle=dataset.plot_options['line_style'],
        #                label=dataset.name)
        kwargs = \
          self._replace_nonpresent_kwargs(
                            kwargs,
                            color=dataset.plot_options['line_color'],
                            linestyle=dataset.plot_options['line_style'],
                            label=dataset.name,
                            linewidth=dataset.plot_options['line_width'])
        
        if not do_scatter: # i.e. if it was not passed in
            do_scatter = self.cfg.plot_flagged_tracker_entries
        
        if dataset.plot_options['hline_at_zero'] :
            hline_at_zero = '#222222'
        else:
            hline_at_zero = False
            
        # plot it
        tcv_plot_helper.plot_tcv_metric_vs_fhr(
                                        fcst_track, 
                                        metric_name,
                                        indicate_flagged=do_scatter,
                                        x_label=x_label, y_label=y_label,
                                        hline_at_zero=hline_at_zero,
                                        **kwargs)
        # plot nature run values, if indicated in config and if plotting values (as opposed to errors)
        #import pdb ; pdb.set_trace()
        # TODO Figure out where self.cfg.plot_nature_values is being reset
        #if '_value' in metric_name and self.cfg.plot_nature_values:
        if '_value' in metric_name:
            self.plot_nature_run_values(cycle, metric_name)


    def plot_nature_run_values(self, cycle, metric_name, label=BEST_TRACK_LABEL):
        '''
        Plot the Truth values for the given `metric_name', using the 
        corresponding absolute times for `cycle'.
        The time axis values will not really correspond to the forecast 
        times of the Nature Run, so just create an array using 
        self.cfg.forecast_duration and self.cfg.history_interval
        ''' 
        log.debug('plotting nature run data')
        epoch2num = lambda x: mpl_dates.num2date(mpl_dates.epoch2num(x))
        natureTimesDict = self.cfg.truth_track.absolute_times_dict()
        endFhr = int(self.cfg.forecast_duration)
        interval = int(self.cfg.history_interval)
        fhrs = range(0, endFhr, interval)
        nature_data = [] #self.cfg.truth_track.tracker_entries
        for outputTime in range(cycle, cycle + endFhr, interval):
            nature_data.append(natureTimesDict[outputTime])
        if self.cfg.time_axis_parameter == 'epoch_zeta':
            nature_time_vals = [epoch2num(cycle+fhr) for fhr in fhrs]
        # This is causing breakage ever since I switched to UTC
        elif self.cfg.time_axis_parameter == 'fhr':
            nature_time_vals = [t/3600 for t in fhrs]
        nature_vals = [getattr(x,metric_name) for x in nature_data]
        #import pdb ; pdb.set_trace()
        self.line_plot_wrapper(nature_time_vals,
                               nature_vals, 
                               color=self.cfg.nature_line_color, 
                               linestyle=self.cfg.nature_line_style, 
                               label=label)


    def plot_mean_dataset_metric_vs_fhr(self, dataset, metric_name, axes=None, 
                                        x_label=None, y_label=None, **kwargs):
        '''
        Plots the mean value of <metric_name> values for the <dataset>. The means
        are calculated for each lead time. The metric plotted is specified in 
        <metric_name> and should be a field in the object returned by the 
        plot_helper's dataset's get_tc_error_stats() methods. Since only averages 
        for errors are supported, the metric name should have "_error" in its name.
        If the "annotate_unflagged_entries" parameter of the cfg is enabled, 
        annotate each point with the number of values that went into the average 
        (i.e. number of unflagged entries). The **kwargs argument may contain any 
        arguments normally passed to MPL's plot()
        Other optional arguments:
           - "axes" element pointing to the axes object to plot on (if not passed in, 
              use gca())
        '''
        log.info("Plotting mean of metric {} for dataset {}"
                 .format(metric_name, dataset))
        if not dataset in self.datasets: 
            raise Exception(('Passed in dataset is not in self.datasets.'
                             ' Cowardly bailing'.format()))
        if "_value" in metric_name:
            raise Exception('Only averages of errors are supported at this time')
        elif "_error" in metric_name:
            if self.cfg.average_type == 'mean':
                (mean_tracker_data, unflagged_entries) = \
                    dataset.get_mean_tc_error_stats()
            elif self.cfg.average_type == 'rmse':
                (mean_tracker_data, unflagged_entries) = \
                    dataset.get_rms_tc_error_stats()
            else:
                raise Exception("Unknown average_type")

        else:
            raise ValueError(("`metric_name' in `create_gridded_figure()` is "
                              "expected to have '_error' suffix".format()))
        
        time_axis_values = [ x.fhr for x in mean_tracker_data ]
        values = [getattr(x,metric_name) for x in mean_tracker_data ]
        #import pdb ; pdb.set_trace()
        if len(values) == 0:
            log.warn('No values for metric %s in dataset' %metric_name)
       
        if axes is None: 
            axes = plt.gca()
        #import pdb ; pdb.set_trace()
        self.line_plot_wrapper(time_axis_values, values, dataset=dataset, 
                               ax=axes, x_label=x_label, y_label=y_label,
                               **kwargs)

        # Put text indicating number of unflagged values that went into each 
        # point. Only label if there were flagged entries to help keep the 
        # figure as reabable as possible.
        # note: this is pretty time consuming
        for i in range(len(values)):
            # Annotate points that have at least one flagged entry
            # lighten the text color in proportion to the number of unflagged entries.
            # The maximum amount by which we can scale the value is (1-c)*scaleFactor+c,
            # since they must all be in the range (0,1). The scaleFactor is basically the
            # "step" of lightening, which will be #unflagged_entries/(number-of-forecasts).
            if dataset.plot_options['annotate_unflagged_entries']:
                log.debug('Annotating unflagged tracker entries in plot')
                rgb = ColorConverter().to_rgb( dataset.plot_options['line_color'] )
                scaleFactor =  float(unflagged_entries[i]) / len(dataset.cycles)
                #rgb = [ (c + min(maxDelta)*scaleFactor) for c in rgb]
                rgb = [ (c + (1-c)*scaleFactor) for c in rgb]
                # set the offset from the line
                yMin,yMax = axes.get_ylim()
                offset = (yMax - yMin) * 0.02
                if unflagged_entries[i] != len(dataset.cycles):
                    axes.annotate(unflagged_entries[i], xy=(time_axis_values[i],values[i]),
                                xytext=(time_axis_values[i],values[i]+offset),
                                color=rgb, fontsize=10, alpha=0.5)



    def set_y_limits(self, param):
        '''
        Set limits for y axis. For cases where the g_static_ylim_<param> 
        variable is True, use the corresponding y_limits_<param> value-pair. 
        For cases where it's false, use the value returned by the 
        get_min_<param> method.
        '''
        min_idx = 0
        max_idx = 1
        if getattr(self.cfg, 'static_y_limit_' + param):
            # static y limit requested in config
            static_limits = getattr(self.cfg, 'y_limits_' + param)
            setattr(self, 'yMin_' + param, static_limits[min_idx] )
            setattr(self, 'yMax_' + param, static_limits[max_idx] )
        else:
            # dynamic y limit based on min/max of all datasets 
            setattr(self, 
                    'yMin_' + param,   
                    self.get_min_value_for_all_datasets('expt_min_' + param) )
            setattr(self, 
                    'yMax_' + param,  
                    self.get_max_value_for_all_datasets('expt_max_' + param) )

        ## Basically, this is what it's doing:
        #if self.cfg.static_y_limit_track_error:
            #self.yMin_track_error = self.cfg.y_limits_track_error[min_idx]
            #self.yMax_track_error = self.cfg.y_limits_track_error[max_idx]
        #else:
            #self.yMin_track_error = \
            #   self.get_min_value_for_all_datasets('expt_min_track_error')
            #self.yMax_track_error = \ self.get_max_value_for_all
            #_datasets('expt_max_track_error')


    #
    # Methods for getting min/max values for all datasets
    #
    def get_min_value_for_all_datasets(self, param_name):
        return min( getattr(x, param_name) for x in self.datasets )

    def get_max_value_for_all_datasets(self, param_name):
        return max( getattr(x, param_name) for x in self.datasets )

    def get_min_mslp_value(self):
        ''' Determine the minimum MSLP value for all datasets, using the Dataset(s)' `expt_min_mslp_value` '''
        return min( x.expt_min_mslp_value for x in self.datasets)
    def get_max_mslp_value(self):
        ''' Determine the maximum MSLP value for all datasets, using the Dataset(s)' `expt_max_mslp_value` '''
        return max( x.expt_max_mslp_value for x in self.datasets )
    def get_min_maxwind_value(self):
        ''' Determine the minimum maxwind value for all datasets, using the Dataset(s)' `expt_min_maxwind_value` '''
        return min( x.expt_min_maxwind_value for x in self.datasets)
    def get_max_maxwind_value(self):
        ''' Determine the maximum maxwind value for all datasets, using the Dataset(s)' `expt_max_maxwind_value` '''
        return max( x.expt_max_maxwind_value for x in self.datasets )


class DaffyMapHelper(DaffyPlotHelper):
    '''
    Provides routines for plotting stuff on maps
    '''
    def __init__(self, usage_string=None, axes=None):
        '''
        Instantiate a DaffyMapHelper. This will create the `basemap' member
        variable according to the settings in self.cfg
        '''
        from mpl_toolkits.basemap import Basemap
        super(DaffyMapHelper, self).__init__(usage_string=usage_string)
        if axes is None:
            axes = plt.gca()
        self.basemap = Basemap(llcrnrlon=self.cfg.map_options['western_longitude'],
                               llcrnrlat=self.cfg.map_options['southern_latitude'],
                               urcrnrlon=self.cfg.map_options['eastern_longitude'],
                               urcrnrlat=self.cfg.map_options['northern_latitude'],
                               projection=self.cfg.map_options['projection'],
                               resolution=self.cfg.map_options['resolution'],
                               #area_thresh=AREA_THRESHOLD,
                               ax=axes)

    def decorate_map(self):
        '''
        Decorates the map according to the settings in the DaffyPlotConfig
        object (e.g. draw oceans, map boundaries, etc.)
        *NOTE: For conciseness, this method assumes that all parameters are
         present*
        '''
        map_settings = self.cfg.map_options
        westLon = map_settings['western_longitude']
        eastLon = map_settings['eastern_longitude']
        upperLat = map_settings['northern_latitude']
        lowerLat = map_settings['southern_latitude']

        if map_settings['draw_coastlines']:
            self.basemap.drawcoastlines()
        if map_settings['draw_countries']:
            self.basemap.drawcountries()
        if map_settings['ocean_color'] != None:
            self.basemap.drawmapboundary(fill_color=map_settings['ocean_color'])
        self.basemap.fillcontinents(color=map_settings['continents_fill_color'],
                                    lake_color=map_settings['lake_color'])
        self.basemap.drawparallels(np.arange(lowerLat, upperLat,
                                             map_settings['latitude_line_freq']),
                                   labels=map_settings['latitude_label_mask'])
        self.basemap.drawmeridians(np.arange(westLon, eastLon,
                                             map_settings['longitude_line_freq']),
                                    labels=map_settings['longitude_label_mask'])


class DaffyTrackPlotHelper(DaffyMapHelper):
    '''
    Provides routines for plotting tracks.
    Note that this is a subclass of DaffyMapHelper, since it utilizes a lot of
    the options from that class.
    '''

    def __init__(self, usage_string=None, draw_nature_track=True, 
                 shadeLines=True, axes=plt.gca()):
        ''' 
        Instantiate a DaffyTrackPlotHelper 
        @param shadeLines If True, the shade of the line will be
               intensified according to the max wind speed
        @param axes Axes object to use to dra the nature run track.
        TODO: This is not a good place to plot the nature run
        track since the axes on which the tracks will be
        plotted may change (e.g. if doing subplots)
        '''
        super(DaffyTrackPlotHelper, self).__init__(usage_string=usage_string)
        self.shade_lines_by_intensity = shadeLines
        self.decorate_map()
        if draw_nature_track:
            self.draw_nature_run_track(axes=axes)

    def draw_nature_run_track(self, zorder=2, shadeLines=True, axes=plt.gca(),
                              lineAlpha=0.8):
        '''
        Plot the nature run track for the entire duration stored in
        self.cfg.nature_track_helper (i.e. the duration within the
        start_date and end_date in the config)
        @param zorder Z-level ordering
        '''
        log.debug('plotting nature run data')
        nature_data = self.cfg.truth_track.tracker_entries
        nrLats = [x.lat for x in nature_data]
        nrLons = [x.lon for x in nature_data]
        if self.shade_lines_by_intensity:
            nrWindSpeeds = [x.maxwind_value for x in nature_data]
        else:
            nrWindSpeeds = None
        # TODO pass in the gridline frequency
        #import pdb ; pdb.set_trace()
        track_plotter.plot_track(
                    nrLats, nrLons, windspeeds=nrWindSpeeds,
                    basemap=self.basemap,
                    line_color=self.cfg.nature_line_color,
                    line_style=self.cfg.nature_line_style,
                    line_width=self.cfg.line_width,
                    label=BEST_TRACK_LABEL,
                    zorder=zorder,
                    alpha=lineAlpha,
                    ax=axes)


    def plot_track_for_cycle(self, dataset, cycle, axes=plt.gca(), lineAlpha=0.8):
        '''
        Plots the track for the given dataset and cycle using the external
        plot_track() function from the map_plotter library
        '''
        # Get the ForecastTrack for the given dataset and cycle and
        # extract its position, mslp, maxwind, and flag attributes
        forecast_track = dataset.get_tc_value_stats(cycle)
        lons = [entry.lon for entry in forecast_track.tracker_entries]
        lats = [entry.lat for entry in forecast_track.tracker_entries]
        fhrs = [entry.fhr for entry in forecast_track.tracker_entries]
        if self.shade_lines_by_intensity:
            maxwinds = [entry.maxwind_value for entry in forecast_track.tracker_entries]
        else:
            maxwinds = None
        flagged = [entry.flagged for entry in forecast_track.tracker_entries]
        flagged_idc = [ i for i,v in enumerate(flagged) if v is True ]

        # plot markers every 24 hours (or whatever frequency given in config)
        freq = self.cfg.map_options['track_plot_time_indicator_freq']
        if freq > 0:
            day_idc = [idx for idx,fhr in enumerate(fhrs) if (fhr*3600)%freq == 0]
            for i in day_idc:
                self.basemap.scatter(lons[i], lats[i],
                                     latlon=True,
                                     color=dataset.plot_options['line_color'],
                                     s=10.0)

        # draw stuff
        #import pdb ; pdb.set_trace()
        track_plotter.plot_track(lats, lons, windspeeds=maxwinds,
                   basemap=self.basemap,
                   indicator_freq=day_idc,
                   line_color=dataset.plot_options['line_color'],
                   line_style=dataset.plot_options['line_style'],
                   line_width=dataset.plot_options['line_width'],
                   label=dataset.name,
                   flagged_idc=flagged_idc,
                   alpha=lineAlpha,
                   ax=axes)


class GsiDiagPlotHelper(DaffyPlotHelper):

    def __init__(self, usage_string):
        super(GsiDiagPlotHelper, self).__init__(usage_string=usage_string)

    def get_gsi_diag(self, dataset, cycle):
        '''
        Populate a GsiDiag object as follows. If the path specified in
        cfg.gsi_diag_reader_conv and cfg.gsi_diag_reader_rad exists
        on the local machine and there are diag files in the cycle's
        GSI output directory, use the diag files and the convert_gsi_diag()
        function.
        Otherwise, look for the pre-generated plain-text diag files.
        If those don't exist, raise an exception

        RETURN a GsiDiag object
        '''
# NOTE : This must be changed to comply with new GsiDiag object scheme, which takes the
#         obs_to_assimilate and searches for the binary and then text diag files
        if os.path.exists(cfg.gsi_diag_reader_rad) and os.path.exists(cfg.gsi_diag_reader_conv):
            if cfg.obs_to_include == 'all':
                diag_files = glob.glob(os.path.join(dataset.get_gsi_output_path(cycle), "diag*" + epoch_to_yyyymmddHHMM(cycle))) # diag_cris_npp_anl.200508010600
                if len(diag_files)  > 0:
                    return self._convert_gsi_diag(dataset, cycle)
                else:
                    log.info("No diag files found, attempting to use pregenerated text-diag files (assuming pattern diag_foo_bar_anl.yyyymmddHHMM)")
                    raise Exception("not implemented")


    def plot_numobs_by_type_coarse(self, dataset):
        '''
        Plots a bar chart showing the number of obs for each type.
        This is a "coarse" plot. It has one 'bar' per cycle, stacked with
        each ob type.
        '''
        for cycle in dataset.cycles:
            gsirun = GsiRun( daffyexpt.get_gsi_path(dataset,cycle), date=cycle, obTypes=self.cfg.obs_to_include)
            # TODO daffyexpt will be a module to envapsulate various DAFFY experiment specific things
            num_obs = {}
            for ob in cfg.obs_to_include:
                num_obs[ob] = len(gsirun.diags[ob])
            # TODO : create barplot for this cycle

#
# TEST
#
if __name__ == '__main__':
    helper = DaffyPlotHelper('default.cfg')
