import time
import os
import sys
import logging 
from nwpy.dateutils  import conversions
from pycane.postproc.tracker import utils as trkutils
from pycane.postproc.tracker import objects as trkobj
# export PYTHONPATH=$PYTHONPATH:/home/Javier.Delgado/apps/pyhwrf/r3963/ush
from hwrf.config import HWRFConfig
import hwrf.config
from datetime import datetime as dtime
from datetime import timedelta as tdelta
import glob
import logging as log
from math import sqrt

# Set names of products. These should correspond to the names given 
# in the product configuration files 
DIAPOST_TRK_PROD = 'diapost_track'
GFDLTRK_TRK_PROD = 'gfdltrk_track'
GFDLTRK_FLAG_PROD = 'gfdltrk_flagged_entries'


class ExperimentDataset(object):
    '''
    Encapsulates attributes of an experiment. This is an abstract class. You
    should instantiate one of its subclasses that are specific to the 
    system used to run the experiment (e.g. DaffyExperimentDataset), which
    provide the methods for extracting experiment-related data. 
    If truth_tracker_data is passed in, it should be a dictionary mapping 
    dates to NatureTrack objects. The `plot_options` dictionary will 
    contain things like "line_color", "line_style", etc.
    The required and optional products are specified via config files. One
    config file, containing common parameters, is read by the 
    ExperimentDataset superclass and another is ready by each of the subclasses.
    An HWRFConfig object (from pyhwrf) is used for parsing the parameter values,
    so all rules of its conftimestrinterp method apply
    '''
    def __init__(self, name, path, start_date, end_date, cycle_frequency,
                 forecast_frequency, forecast_duration, history_interval, 
                 plot_options, truth_track=None, genericConfigFile=None,
                 log=None, storm_id=None, best_track_path=None):
        '''
        Construct an ExperimentDataset. Hint: You probably do not want to 
        instantiate one of these but rather one of the experiment-type-specific
        subclasses.
        @param name - Name given to the experiment (e.g. for labeling)
        @param path - top-level directory of the experiment output 
        @param start_date - First cycle of the experiment (UTC secs since epoch)
        @param end_date - Last cycle of the experiment (UTC seconds since epoch)
        @param cycle_frequency - How often it cycled (seconds)
        @param forecast_frequency - How often deterministic forecasts were run 
        @param forecast_duration - Length of forecasts
        @param plot_options - Map containing plot options to be passed to 
                              plotting methods
        @param genericConfigFile Configuration file specifying product-related 
               parameters. If not passed in, use
               <os.getcwd()>/conf/products_generic.cfg 
        @param storm_id The number+basin code of the Storm (e.g. '07L') 
                If working with a real case, this is required since the 
                path will include it.
        @param best_track_path Path to best track 
        @param experiment_id - Experiment ID
        @param experiment_uuid - Experiment UUID
        '''
        self.name = name
        self.path = path
        self.start_date = start_date
        self.end_date = end_date
        self.cycle_frequency = cycle_frequency
        self.forecast_frequency = forecast_frequency
        self.forecast_duration = forecast_duration
        self.history_interval = history_interval
        self.plot_options = plot_options
        self.storm_id = storm_id

        if log is None:
            log = logging.getLogger()
        self.log = log
        ## TODO
        #self.experiment_id =
        #self.experiment_uuid =
        
        if genericConfigFile is None:
            self.common_products_conf_file = os.path.join(os.getcwd(),
                                                          'conf',
                                                          'products_common.cfg')
        else:
            self.common_products_conf_file = genericConfigFile
        # HWRFConfig does not check existance of the config file 
        if not os.path.exists(self.common_products_conf_file):
            raise Exception("Config file %s does not exist" 
                             %self.common_products_conf_file)
        self.conf = hwrf.config.from_file(self.common_products_conf_file)
        self.conf.add_section("dynamic")
        self.conf.set_options("dynamic", expt_rundir=self.path)
        if storm_id is not None:
            self.conf.set_options("dynamic", storm_id=storm_id)
            self.conf.set_options("dynamic", storm_id_lc=storm_id.lower())
            self.conf.set_options("dynamic", storm_id_uc=storm_id.upper())
        #self.conf.set_options("dynamic", best_track=best_track_path)
        self._initialize_min_max_vars()

        # this should be a ForecastTrack
        if truth_track is not None:
            self.truth_track = truth_track
        # TODO : deprecate separate truth_track
        '''
        if best_track_path is not None:
            dirN = os.path.dirname(best_track_path)
            baseN = os.path.basename(best_track_path)
            fetcher = ProductFetcher('diapost_track', self.conf, dirN, baseN)
            path = fetcher.get_path(self.cycle)
            trkGlob = self.conf.get("dynamic", "best_track") # interplate date
            assert len(trkGlob) == 1
            self.best_track_path = trkGlob[0]
            self.best_track = trkutils.get_track_data(self.best_track_path)
        '''
        # create line style string
        if self.plot_options['line_style'] == '-':
            self.plot_options['line_style_string'] = 'solid'
        if self.plot_options['line_style'] == '--':
            self.plot_options['line_style_string'] = 'dashed'
        if self.plot_options['line_style'] == '..':
            self.plot_options['line_style_string'] = 'dotted'
        if self.plot_options['line_style'] == ':':
            self.plot_options['line_style_string'] = 'dashdot'

    def __str__(self):
        return "Dataset(name={}, path={}, type={})"\
               .format(self.name, self.path, type(self).__name__)

    def set_paths(self):
        '''
        Set paths of various cycle-specific output files. This method will
        set self.products which is a dictionary that maps each product 
        name (which is the name specified in 'products' under section "generic"
        of self.conf) to a ProductFetcher
        '''
        self.products = {}
        possibleProducts = self.conf.get("general", 'products').split(", ")
        for prodName in possibleProducts:
            if self.conf.has_section(prodName):
                # instantiate ProductFetcher with raw strings, so that later
                # queries for cycle-specific data may be fulfilled
                prodDir = self.conf.getraw(prodName, 'dir')
                prodPattern = self.conf.getraw(prodName, 'filePattern')
                prodF = ProductFetcher(prodName, self.conf, prodDir, prodPattern, 
                                       stormId=self.storm_id)
                self.products[prodName] = prodF
            else:
                self.log.warn("Config section for product '%s' does not exist"
                              %prodName)
            
    
    def _initialize_min_max_vars(self):
        '''
        Set some global attributes - these are the min/max values for this 
        dataset, across all cycles.
        The values are updated in calls to get_tc_stats()
        The publicly-accessible versions are set via property to ensure the 
        values are set
        '''
        self._unset_min = 99999999.0
        self._unset_max = -99999999.0
        self._expt_min_track_error = self._unset_min
        self._expt_min_maxwind_error = self._unset_min
        self._expt_min_mslp_error = self._unset_min
        self._expt_max_track_error = self._unset_max
        self._expt_max_maxwind_error = self._unset_max
        self._expt_max_mslp_error = self._unset_max
        self._expt_min_track_value = self._unset_min
        self._expt_min_maxwind_value = self._unset_min
        self._expt_min_mslp_value = self._unset_min
        self._expt_max_track_value = self._unset_max
        self._expt_max_maxwind_value = self._unset_max
        self._expt_max_mslp_value = self._unset_max


    def get_mean_tc_error_stats(self):
        '''
        Calculate and return the mean error across all cycles, along the 
        forecast hours, using the get_tc_error_stats() method
        RETURN A 2-tupple consisting of:
           1) A list of TrackerDataDiff populated with the mean of the 
              individual errors, excluding flagged entries
           2) Number of unflagged entries
           The elements in each tupple correspond to the tracker outputs, 
           so the frequency correponds to self.history_interval
        '''

        # initialize
        tracker_entries_avg = []
        num_unflagged_entries = []
        for i in range( int(self.forecast_duration / self.history_interval + 1) ):
            currFhr = i * self.history_interval / 3600
            tracker_entries_avg.append(
                trkobj.TrackerDataDiff(currFhr, False, 0, 0, 0))
            # keep track of the number of unflagged entries for each tracker entry
            num_unflagged_entries.append(0)
        # accumulate foreach cycle
        for cycle in self.cycles:
            #import pdb ; pdb.set_trace()
            log.debug("Getting TCV error stats for cycle {}"
                      .format(conversions.epoch_to_yyyymmddHHMM(cycle)))
            cycle_tcv_errors = self.get_tc_error_stats(cycle).tracker_entries
            assert cycle_tcv_errors[-1].fhr <= self.forecast_duration
            for i in range(len(cycle_tcv_errors) ):
                if not cycle_tcv_errors[i].flagged:
                    # get_tc_error_stats() will only return diapost entries
                    # that were not flagged, but mean_tcv_errors will have an 
                    # entry for all history intervals, so use indirect
                    # addressing
                    histIntvHrs = self.history_interval / 3600 
                    fhrIdx = int(cycle_tcv_errors[i].fhr / histIntvHrs)
                    # "avg" is actually a running sum, for now
                    tracker_entries_avg[fhrIdx].track_error += \
                            cycle_tcv_errors[i].track_error
                    tracker_entries_avg[fhrIdx].maxwind_error += \
                            cycle_tcv_errors[i].maxwind_error
                    tracker_entries_avg[fhrIdx].mslp_error += \
                            cycle_tcv_errors[i].mslp_error
                    num_unflagged_entries[fhrIdx] += 1
        # get mean
        #log.info('Number of unflagged entries: %s' %num_unflagged_entries)
        for i in range( len(tracker_entries_avg)):
            # For forecast hours in which all values are flagged, set the value
            # to the previous fhr's value, to keep the plots smooth. If they're
            # all flagged for the first forecast hour, set the value to None
            if num_unflagged_entries[i] == 0:
                if i == 0:
                    tracker_entries_avg[i].track_error = None
                    tracker_entries_avg[i].maxwind_error = None
                    tracker_entries_avg[i].mslp_error = None
                else:
                    tracker_entries_avg[i].track_error =\
                         tracker_entries_avg[i-1].track_error
                    tracker_entries_avg[i].maxwind_error =\
                         tracker_entries_avg[i-1].maxwind_error
                    tracker_entries_avg[i].mslp_error =\
                         tracker_entries_avg[i-1].mslp_error
            else:
                tracker_entries_avg[i].track_error /= num_unflagged_entries[i]
                tracker_entries_avg[i].maxwind_error /= num_unflagged_entries[i]
                tracker_entries_avg[i].mslp_error /= num_unflagged_entries[i]

        return (tracker_entries_avg, num_unflagged_entries)

    def get_rms_tc_error_stats(self):
        '''
        Calculate and return the mean error across all cycles, along the 
        forecast hours, using the get_tc_error_stats() method
        RETURN A 2-tupple consisting of:
           1) A list of TrackerDataDiff populated with the mean of the 
              individual errors, excluding flagged entries
           2) Number of unflagged entries
           The elements in each tupple correspond to the tracker outputs, 
           so the frequency correponds to self.history_interval
        
        TODO
         Lots of overlap with this function and get_mean_tc_error_stats - basically,
         the only difference is that we square the sums and take the square root at
         the end (so all but 6 lines are identical)
        '''

        # initialize
        tracker_entries_avg = []
        num_unflagged_entries = []
        for i in range( int(self.forecast_duration / self.history_interval + 1) ):
            currFhr = i * self.history_interval / 3600
            tracker_entries_avg.append(
                trkobj.TrackerDataDiff(currFhr, False, 0, 0, 0)) # initialize all errors to 0
            # keep track of the number of unflagged entries for each tracker entry
            num_unflagged_entries.append(0)
        # accumulate foreach cycle
        for cycle in self.cycles:
            #import pdb ; pdb.set_trace()
            log.debug("Getting TCV error stats for cycle {}"
                      .format(conversions.epoch_to_yyyymmddHHMM(cycle)))
            cycle_tcv_errors = self.get_tc_error_stats(cycle).tracker_entries
            if len(cycle_tcv_errors) == 0:
                log.warn("No useable TC stats for this cycle. Skipping...")
                continue
            assert cycle_tcv_errors[-1].fhr <= self.forecast_duration
            for i in range(len(cycle_tcv_errors) ):
                if not cycle_tcv_errors[i].flagged:
                    # get_tc_error_stats() will only return diapost entries
                    # that were not flagged, but mean_tcv_errors will have an 
                    # entry for all history intervals, so use indirect
                    # addressing
                    histIntvHrs = self.history_interval / 3600 
                    fhrIdx = int(cycle_tcv_errors[i].fhr / histIntvHrs)
                    # "avg" is actually a running sum of square errors, for now
                    tracker_entries_avg[fhrIdx].track_error += \
                            (cycle_tcv_errors[i].track_error)**2
                    tracker_entries_avg[fhrIdx].maxwind_error += \
                            (cycle_tcv_errors[i].maxwind_error)**2
                    tracker_entries_avg[fhrIdx].mslp_error += \
                            (cycle_tcv_errors[i].mslp_error)**2
                    num_unflagged_entries[fhrIdx] += 1
        # get mean
        #log.info('Number of unflagged entries: %s' %num_unflagged_entries)
        for i in range( len(tracker_entries_avg)):
            # For forecast hours in which all values are flagged, set the value
            # to the previous fhr's value, to keep the plots smooth. If they're
            # all flagged for the first forecast hour, set the value to None
            if num_unflagged_entries[i] == 0:
                # all entries for this fhr were flagged 
                if i == 0:
                    tracker_entries_avg[i].track_error = None
                    tracker_entries_avg[i].maxwind_error = None
                    tracker_entries_avg[i].mslp_error = None
                else:
                    tracker_entries_avg[i].track_error =\
                         tracker_entries_avg[i-1].track_error
                    tracker_entries_avg[i].maxwind_error =\
                         tracker_entries_avg[i-1].maxwind_error
                    tracker_entries_avg[i].mslp_error =\
                         tracker_entries_avg[i-1].mslp_error
            else:
                # at least one unflagged flagged
                tracker_entries_avg[i].track_error /= num_unflagged_entries[i]
                tracker_entries_avg[i].maxwind_error /= num_unflagged_entries[i]
                tracker_entries_avg[i].mslp_error /= num_unflagged_entries[i]
                tracker_entries_avg[i].track_error = sqrt(tracker_entries_avg[i].track_error)
                tracker_entries_avg[i].maxwind_error = sqrt(tracker_entries_avg[i].maxwind_error)
                tracker_entries_avg[i].mslp_error = sqrt(tracker_entries_avg[i].mslp_error)

        return (tracker_entries_avg, num_unflagged_entries)


    def _testing_get_mean_tc_error_stats(self):
        '''
        Calculate and return the mean error across all cycles, along the 
        forecast hours, using the get_tc_error_stats() method
        RETURN A 2-tupple consisting of:
           1) A list of TrackerDataDiff populated with the mean of the 
              individual errors, excluding flagged entries
           2) Number of unflagged entries
           The elements in each tupple correspond to the tracker outputs, 
           so the frequency correponds to self.history_interval
        '''

        # initialize
        expt_errors_by_fhr = [] # list of TrackerDataDiff 
        num_unflagged_entries = []
        for i in range(int(self.forecast_duration / self.history_interval + 1)):
            currFhr = i * self.history_interval / 3600
            error_by_fhr.append(
                trkobj.TrackerDataDiff(currFhr, False, 0, 0, 0))
            # keep track of the number of unflagged entries for each tracker entry
            num_unflagged_entries.append(0)
        # accumulate foreach cycle
        for cycle in self.cycles:
            #import pdb ; pdb.set_trace()
            log.debug("Getting TCV error stats for cycle {}"
                      .format(conversions.epoch_to_yyyymmddHHMM(cycle)))
            cycle_tcv_errors = self.get_tc_error_stats(cycle).tracker_entries
            assert cycle_tcv_errors[-1].fhr <= self.forecast_duration
            for i in range(len(cycle_tcv_errors) ):
                if not cycle_tcv_errors[i].flagged:
                    # get_tc_error_stats() will only return diapost entries
                    # that were not flagged, but mean_tcv_errors will have an 
                    # entry for all history intervals, so use indirect
                    # addressing
                    histIntvHrs = self.history_interval / 3600 
                    fhrIdx = int(cycle_tcv_errors[i].fhr / histIntvHrs)
                    # "avg" is actually a running sum, for now
                    tracker_entries_avg[fhrIdx].track_error += \
                            cycle_tcv_errors[i].track_error
                    tracker_entries_avg[fhrIdx].maxwind_error += \
                            cycle_tcv_errors[i].maxwind_error
                    tracker_entries_avg[fhrIdx].mslp_error += \
                            cycle_tcv_errors[i].mslp_error
                    num_unflagged_entries[fhrIdx] += 1
        # get mean
        #log.info('Number of unflagged entries: %s' %num_unflagged_entries)
        for i in range( len(tracker_entries_avg)):
            # For forecast hours in which all values are flagged, set the value
            # to the previous fhr's value, to keep the plots smooth. If they're
            # all flagged for the first forecast hour, set the value to None
            if num_unflagged_entries[i] == 0:
                if i == 0:
                    tracker_entries_avg[i].track_error = None
                    tracker_entries_avg[i].maxwind_error = None
                    tracker_entries_avg[i].mslp_error = None
                else:
                    tracker_entries_avg[i].track_error =\
                         tracker_entries_avg[i-1].track_error
                    tracker_entries_avg[i].maxwind_error =\
                         tracker_entries_avg[i-1].maxwind_error
                    tracker_entries_avg[i].mslp_error =\
                         tracker_entries_avg[i-1].mslp_error
            else:
                tracker_entries_avg[i].track_error /= num_unflagged_entries[i]
                tracker_entries_avg[i].maxwind_error /= num_unflagged_entries[i]
                tracker_entries_avg[i].mslp_error /= num_unflagged_entries[i]

        return (tracker_entries_avg, num_unflagged_entries)


    def get_tc_error_stats(self, cycle, is_absolute=False):
        '''
        Calculate and return the TC error value for the given `cycle`.
        The `cycle` is the seconds-since-epoch corresponding to the cycle date.
        RETURN A ForecastTCVError object populated with TCVErrorData elements 
        in its `tracker_entries` field, which contain the (experiment-nature) 
        values for the tracker and "truth" settings set in the cfg,
        for each forecast hour.
        @param is_absolute If True, calculate absolute error. Otherwise do
                           Experiment-Best
        '''
        if self.truth_track is None or not self.truth_track.tracker_entries:
            raise Exception(("self.truth_track does not contain any data. Is "
                        "it set correctly in the configuration and passed to "
                        "the constructor?".format()))
        expt_cycle_track = self.get_tc_value_stats(cycle)
        fcst_tcv_errors = trkobj.ForecastTrackDiff(expt_cycle_track, 
                                                   self.truth_track,
                                                   absoluteTimeDiff=True,
                                                   absolute=is_absolute)
        # (re)set experiment min/max error values
        for currFhrError in fcst_tcv_errors.tracker_entries:
            if self._expt_min_track_error > currFhrError.track_error: 
                self._expt_min_track_error = currFhrError.track_error
            if self._expt_max_track_error < currFhrError.track_error: 
                self._expt_max_track_error = currFhrError.track_error
            if self._expt_min_maxwind_error > currFhrError.maxwind_error: 
                self._expt_min_maxwind_error = currFhrError.maxwind_error
            if self._expt_max_maxwind_error < currFhrError.maxwind_error:
                self._expt_max_maxwind_error = currFhrError.maxwind_error
            if self._expt_min_mslp_error > currFhrError.mslp_error:
                self._expt_min_mslp_error = currFhrError.mslp_error
            if self._expt_max_mslp_error < currFhrError.mslp_error: 
                self._expt_max_mslp_error = currFhrError.mslp_error

        return fcst_tcv_errors

    def get_tc_value_stats(self, cycle):
        '''
        Generic method for getting TC Vitals stats for the given `cycle`.
        The `cycle` is the seconds-since-epoch corresponding to the cycle date.
        The values will be obtained using a separate method corresponding to the tracker specified in
        self.plot_options['tracker'].
        @return a [ForecastTrack] object for the given cycle.
        '''
        if self.plot_options['tracker'] == 'diapost':
            return self.get_experiment_forecast_diapost_data(
               self.path,
               cycle,
               include_flagged_entries=self.plot_options['plot_flagged_tracker_entries'],
               duration=self.forecast_duration)
        elif self.plot_options['tracker'] == 'gfdl':
            return self.get_experiment_forecast_gfdltrk_data(
               self.path,
               cycle,
               include_flagged_entries=self.plot_options['plot_flagged_tracker_entries'],
               duration=self.forecast_duration)
        else:
            raise Exception("The only supported trackers are diapost and gfdl")


    def get_experiment_forecast_diapost_data(self, dataset_path, cycle,
         include_flagged_entries=False, duration=None):
        '''
        Reads Diapost data using tracker_utils::get_diapost_track_data for a i
        given cycle, using the xperiment's directory structure. If 
        include_flagged_entries=False, only return entries in which the
        value is not flagged (i.e. only return those whose flag value is 0)
        @param dataset_path Path to the experiment's data
        @param cycle The cycle's start time, in seconds since epoch relative 
                     to GMT
        @param include_flagged_entries True if you want to include flagged 
               tracker entries
        @param duration How long in to the forecast to process data. If not 
               passed in, the behavior of trkutils.get_diapost_track_data 
               is assumed
        @return a [ForecastTrack] object for the given cycle.
        NOTE: Each ForecastTrack contains the list of TrackerData objects, one for each
        entry in the track file (which should correspond with the history interval)
        '''
        global g_min_mslp, g_max_mslp, g_min_wind, g_max_wind, g_min_track,\
               g_max_track

        self.log.debug('Reading Diapost data for dataset %s, cycle time %s'
                  %(self.name, cycle))
        diapost_atcf = self.products[DIAPOST_TRK_PROD].get_path(cycle)
        cycle_diapost_track =\
            trkutils.get_diapost_track_data(diapost_atcf, 
                                            include_flagged_entries, 
                                            None, 
                                            duration,
                                            skip_land_points=self.plot_options['ignore_land_points'])  # TODO pass in logger
        # set global attributes
        for trackData in [ c for c in cycle_diapost_track.get_tracker_entries() if not c.flagged]:
        #for trackData in cycle_diapost_track.get_tracker_entries():
            if trackData.mslp_value < self._expt_min_mslp_value: self._expt_min_mslp_value = trackData.mslp_value
            if trackData.mslp_value > self._expt_max_mslp_value: self._expt_max_mslp_value = trackData.mslp_value
            if trackData.maxwind_value < self._expt_min_maxwind_value: self._expt_min_maxwind_value = trackData.maxwind_value
            if trackData.maxwind_value > self._expt_max_maxwind_value: self._expt_max_maxwind_value = trackData.maxwind_value

        return cycle_diapost_track


    def get_experiment_forecast_gfdltrk_data(self, dataset_path, cycle, include_flagged_entries=False, duration=None):
        '''
        Reads GFDL tracker output data for a given cycle using
        tracker_utils::get_gfdltrk_track_data(). Please read the comments header
        for the method for important information.
        '''
        global g_min_mslp, g_max_mslp, g_min_wind, g_max_wind, g_min_track,\
               g_max_track
        
        # TODO pyhwrf
        suffix_curr_cycle = time.strftime('%Y_%m_%d_%H_%M',time.gmtime(cycle) )
        self.log.debug('Reading GFDL track data for dataset %s, cycle time %s' 
                  %(self.name, suffix_curr_cycle) )
        trkFile = self.products[GFDLTRK_TRK_PROD].get_path(cycle)
        flaggedEntriesExist = False
        try:
            flaggedEntriesFile = self.products[GFDLTRK_FLAG_PROD].get_path(cycle)
            flaggedEntriesExist = True
        except MissingProductException as e:
            self.log.debug("No flagged entries filed for the GFDL track found at {}"
                     .format(e.path))
            flaggedEntriesExist = False
            include_flagged_entries = False
            flaggedEntriesFile = None
        cycle_track = trkutils.get_gfdltrk_track_data(trkFile,
                                                      flaggedEntriesFile,
                                                      include_flagged_entries,
                                                      self.log,
                                                      duration,
                                                      skip_land_points=self.plot_options['ignore_land_points'])
        for trackData in [ c for c in cycle_track.get_tracker_entries() if not c.flagged]:
            if trackData.mslp_value < self._expt_min_mslp_value: 
                self._expt_min_mslp_value = trackData.mslp_value
            if trackData.mslp_value > self._expt_max_mslp_value: 
                self._expt_max_mslp_value = trackData.mslp_value
            if trackData.maxwind_value < self._expt_min_maxwind_value: 
                self._expt_min_maxwind_value = trackData.maxwind_value
            if trackData.maxwind_value > self._expt_max_maxwind_value: 
                self._expt_max_maxwind_value = trackData.maxwind_value

        return cycle_track

    ##
    # Setters/Getters for experiment-wide min/max values. Ensures that they are set before returning
    ##
    def get_min_value(self, attr):
        if getattr(self, attr) == self._unset_min : raise Exception('Experiment %s value has not been set' %attr)
        return getattr(self, attr)

    def get_max_value(self, attr):
        if getattr(self, attr) == self._unset_max : raise Exception('Experiment %s value has not been set' %attr)
        return getattr(self, attr)

    ##
    #Properties -
    ##

    @property
    def cycles(self):
        #import pdb ; pdb.set_trace()
        return range(int(self.start_date), 
                     int(self.end_date + 1), 
                     int(self.cycle_frequency) )

    # not using "setter' for these due to ancient python on Storm.
    #Here is what it should look like:
    #@property
    #def expt_min_mslp_value(self): return self.get_min_value('_expt_min_mslp_value')
    #@expt_min_mslp_value.setter
    #def expt_min_mslp_value(self, val): self._expt_min_mslp_value = val
    #@property
    #def expt_max_mslp_value(self): return self.get_max_value('_expt_max_mslp_value')
    #@expt_max_mslp_value.setter
    #def expt_max_mslp_value(self, val): self._expt_max_mslp_value = val
    ##
    # Here is what works with the midevil python:
    def expt_min_mslp_value_g(self): return self.get_min_value('_expt_min_mslp_value')
    def expt_min_mslp_value_s(self, val): self._expt_min_mslp_value = val
    def expt_max_mslp_value_g(self): return self.get_max_value('_expt_max_mslp_value')
    def expt_max_mslp_value_s(self, val): self._expt_max_mslp_value = val
    def expt_min_maxwind_value_g(self): return self.get_min_value('_expt_min_maxwind_value')
    def expt_min_maxwind_value_s(self, val): self._expt_min_maxwind_value = val
    def expt_max_maxwind_value_g(self): return self.get_max_value('_expt_max_maxwind_value')
    def expt_max_maxwind_value_s(self, val): self._expt_max_maxwind_value = val

    def expt_min_track_error_g(self): return self.get_min_value('_expt_min_track_error')
    def expt_min_track_error_s(self, val): self._expt_min_track_error = val
    def expt_max_track_error_g(self): return self.get_max_value('_expt_max_track_error')
    def expt_max_track_error_s(self, val): self._expt_max_track_error = val
    def expt_min_mslp_error_g(self): return self.get_min_value('_expt_min_mslp_error')
    def expt_min_mslp_error_s(self, val): self._expt_min_mslp_error = val
    def expt_max_mslp_error_g(self): return self.get_max_value('_expt_max_mslp_error')
    def expt_max_mslp_error_s(self, val): self._expt_max_mslp_error = val
    def expt_min_maxwind_error_g(self): return self.get_min_value('_expt_min_maxwind_error')
    def expt_min_maxwind_error_s(self, val): self._expt_min_maxwind_error = val
    def expt_max_maxwind_error_g(self): return self.get_max_value('_expt_max_maxwind_error')
    def expt_max_maxwind_error_s(self, val): self._expt_max_maxwind_error = val

    expt_min_mslp_value = property(expt_min_mslp_value_g, expt_min_mslp_value_s)
    expt_max_mslp_value = property(expt_max_mslp_value_g, expt_max_mslp_value_s)
    expt_min_maxwind_value = property(expt_min_maxwind_value_g, expt_min_maxwind_value_s)
    expt_max_maxwind_value = property(expt_max_maxwind_value_g, expt_max_maxwind_value_s)

    expt_min_mslp_error = property(expt_min_mslp_error_g, expt_min_mslp_error_s)
    expt_max_mslp_error = property(expt_max_mslp_error_g, expt_max_mslp_error_s)
    expt_min_maxwind_error = property(expt_min_maxwind_error_g, expt_min_maxwind_error_s)
    expt_max_maxwind_error = property(expt_max_maxwind_error_g, expt_max_maxwind_error_s)
    expt_min_track_error = property(expt_min_track_error_g, expt_min_track_error_s)
    expt_max_track_error = property(expt_max_track_error_g, expt_max_track_error_s)


class PyHwrfExperimentDataset(ExperimentDataset):
    '''
    A PyHwrfExperimentDataset encapsulates the functionality for 
    retrieving products generated with the PyHWRF system
    '''
    def __init__(self, name, path, start_date, end_date, cycle_frequency,
                 forecast_frequency, forecast_duration, history_interval, 
                 plot_options, truth_track=None,
                 stormId=None, best_track_path=None,
                 exptTypeConfigFile=None, genericConfigFile=None):
        '''
        Instantiate a PyHwrfExperimentDataset. The parameters passed in are
        the same as those for the parent class ExperimentDataset, with the 
        addition of 
        @param exptTypeConfigFile config file containing product parameters 
               specific to PyHWRF experiments. If not passed, look in  
               <os.getcwd()>/conf/products_pyhwrf.cfg 
        '''
        if exptTypeConfigFile is None:
            exptTypeConfigFile = os.path.join(os.getcwd(), 
                                              'conf', 
                                              'products_pyhwrf.cfg')
        super(PyHwrfExperimentDataset, self).__init__(
                       name=name, path=path, start_date=start_date, 
                       end_date=end_date, cycle_frequency=cycle_frequency,
                       forecast_frequency=forecast_frequency,
                       forecast_duration=forecast_duration,
                       history_interval=history_interval,
                       plot_options=plot_options, 
                       truth_track=truth_track,
                       storm_id=stormId,
                       best_track_path=best_track_path,
                       genericConfigFile=genericConfigFile)
        # HWRFConfig does not check existance of the config file 
        if not os.path.exists(exptTypeConfigFile):
            raise Exception("Config file %s does not exist" 
                             %exptTypeConfigFile)
        self.conf.read(exptTypeConfigFile)
        self.set_paths()
    
    
class DaffyExperimentDataset(ExperimentDataset):
    '''
    A DaffyExperimentDataset encapsulates the functionality for 
    retrieving products generated with the DAFFY system
    '''
    def __init__(self, name, path, start_date, end_date, cycle_frequency,
                 forecast_frequency, forecast_duration, history_interval, 
                 plot_options, truth_track=None,
                 exptTypeConfigFile=None, genericConfigFile=None):
        '''
        Instantiate a DaffyExperimentDataset. The parameters passed in are
        the same as those for the parent class ExperimentDataset, with the 
        addition of 
        @param exptTypeConfigFile config file containing product parameters 
               specific to DAFFY experiments. If not passed, look in  
               <os.getcwd()>/conf/products_daffy.cfg 
        '''
        if exptTypeConfigFile is None:
            exptTypeConfigFile = os.path.join(os.getcwd(), 
                                              'conf', 
                                              'products_daffy.cfg')
        super(DaffyExperimentDataset, self).__init__(
                       name=name, path=path, start_date=start_date, 
                       end_date=end_date, cycle_frequency=cycle_frequency,
                       forecast_frequency=forecast_frequency,
                       forecast_duration=forecast_duration,
                       history_interval=history_interval,
                       plot_options=plot_options, 
                       truth_track=truth_track,
                       genericConfigFile=genericConfigFile)
        # HWRFConfig does not check existance of the config file 
        if not os.path.exists(exptTypeConfigFile):
            raise Exception("Config file %s does not exist" 
                             %exptTypeConfigFile)
        self.conf.read(exptTypeConfigFile)
        self.set_paths()

##
class NmmbAutorunnerExperimentDataset(ExperimentDataset):
    '''
    A NmmbAutorunnerExperimentDataset encapsulates the functionality for 
    retrieving products generated with the NMM-B autorunner
    '''
    def __init__(self, name, path, start_date, end_date, cycle_frequency,
                 forecast_frequency, forecast_duration, history_interval, 
                 plot_options, truth_track=None,
                 stormId=None,
                 exptTypeConfigFile=None, genericConfigFile=None):
        '''
        Instantiate a NmmbAutorunnerExperimentDataset. The parameters passed in are
        the same as those for the parent class ExperimentDataset, with the 
        addition of 
        @param exptTypeConfigFile config file containing product parameters 
               specific to NMM-B autorunner experiments. If not passed, look in  
               <os.getcwd()>/conf/products_pyhwrf.cfg 
        '''
        if exptTypeConfigFile is None:
            exptTypeConfigFile = os.path.join(os.getcwd(), 
                                              'conf', 
                                              'products_nmmb_autorunner.cfg')
        super(NmmbAutorunnerExperimentDataset, self).__init__(
                       name=name, path=path, start_date=start_date, 
                       end_date=end_date, cycle_frequency=cycle_frequency,
                       forecast_frequency=forecast_frequency,
                       forecast_duration=forecast_duration,
                       history_interval=history_interval,
                       plot_options=plot_options, 
                       truth_track=truth_track,
                       genericConfigFile=genericConfigFile,
                       storm_id=stormId)
        # HWRFConfig does not check existance of the config file 
        if not os.path.exists(exptTypeConfigFile):
            raise Exception("Config file %s does not exist" 
                             %exptTypeConfigFile)
        self.conf.read(exptTypeConfigFile)
        self.set_paths()

##            


class ProductFetcher(object):
    '''
    This class encapsulates the retrieval of products.
    '''
    def __init__(self, name, conf, topdir, filePattern, stormId=None):
        '''
        Instantiate a ProductFetcher. Paths will be resolved using the
        timestrinterp() method of the given `conf'
        @param name name of the product. It _must_ be the same as the section
               name in `conf'
        @param conf HWRFConfig object whose timestrinterp method will be used
                    to determine the path
        @param topdir Top-level directory containing the product
        @param file Pattern describing name of single file
        @param fileset Pattern describing name of a list of files
        @param stormId Number+basin portion of the storm ID (e.g. 11L)
        '''
        self.name = name
        self._conf = conf
        self.topdir = topdir
        self.file_pattern = filePattern
        self.storm_id = stormId
            
    def get_path(self, cycle, domain=None, fhr=0):
        '''
        Get the path of a product for a given cycle, domain, and forecast hour.
        @param cycle Datetime object representing the cycle 
        @param domain Domain number, if applicable
        @param fhr Forecast hour, if applicable
        @return The path to the file, if it exists
        @raise AmbiguousProductException If more than one files match the 
               <self.file_pattern> for the given cycle
        @raise MissingProductException If no files match the <self.file_pattern> 
               for the given cycle
        '''
        # for legacy code, convert cycle in seconds since epoch to a datetime
        if not isinstance(cycle, dtime):
            tm = time.gmtime(cycle)
            cycle = dtime(year=tm.tm_year, month=tm.tm_mon, day=tm.tm_mday,
                          hour=tm.tm_hour, minute=tm.tm_min)
        # set additional keys to interpolate
        kwargs = {}
        if domain is not None:
            kwargs['dom'] = domain
        if self.storm_id is not None:
            kwargs['storm_id'] = self.storm_id
            kwargs['storm_id_lc'] = self.storm_id.lower()
            kwargs['storm_id_uc'] = self.storm_id.upper()
        path = os.path.join(self.topdir, self.file_pattern)    
        # resolve the path
        pathPattern = self._conf.timestrinterp(self.name, path, fhr,
                                        cycle,**kwargs)
        pathGlob = glob.glob(pathPattern)
        if len(pathGlob) == 1:
            return pathGlob[0]
        elif len(pathGlob) == 0:
            raise MissingProductException(pathPattern)
        else:
            raise AmbiguousProductException("Pattern {} matched more than one file, "
                                            "namely {}".format(pathPattern, pathGlob))
       
class MissingProductException(Exception):
    def __init__(self, path):
        self.path = path
    def __str__(self):
        return repr(self.path)

class AmbiguousProductException(Exception):
    pass

if __name__ == '__main__':
    from nature_track import NatureTrackHelper
    plot_options = {'tracker' : 'diapost' , 'plot_flagged_tracker_entries' : False , 'line_color' : 'black' , 'line_style' : '-' }
    nature_track_helper = NatureTrackHelper(1122890400, 1123214400 + 120*3600, '/home/Javier.Delgado/plot_testing/atcfNRD03.txt')
    #import pdb ; pdb.set_trace()
    ds = DaffyExperimentDataset('test', '/home/Javier.Delgado/www/experiments/stingray/gsi/perfect/d04_5km', 1122890400, 1123214400, 3600*6, 3600*6, 3600*120, 3600 * 6, plot_options, truth_tracker_data=nature_track_helper.nature_tracker_data)
    # test mean error (which will indirectly test getting the individual errors)
    (meanVals, numUnflagged) = ds.get_mean_tc_error_stats()
    print meanVals
    print numUnflagged
