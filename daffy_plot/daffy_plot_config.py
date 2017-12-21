import os
import sys
import ConfigParser
from time import strptime, mktime, tzset
from optparse import OptionParser
import logging 
from odict import OrderedDict
import glob # only need this temporarily, for the best_track_hack
import re

from daffy_dataset import DaffyExperimentDataset, PyHwrfExperimentDataset
from daffy_dataset import NmmbAutorunnerExperimentDataset
from daffy_dataset import AmbiguousProductException, MissingProductException

from nwpy.dateutils  import conversions # only needed temp. for best_track hack
from pycane.postproc.tracker import objects as trkobj
from pycane.postproc.tracker import utils as trkutils

'''
Provides an interface between the config file and the runtime environment
'''

class DaffyPlotConfig:
    DEFAULT_CONFIG_FILE = 'default.cfg'

    def __init__(self, config_file=None, usage_string=None, log=None):
        ''' Instantiate a DaffyPlotConfig. The config file used will be one of the following:
            The optionally passed in `config_file` OR the --config passed via command line OR  the default (default.cfg)
            The optionally passed in `usage_string` will be used to display additional information when the "-h" command
            line argument is used.
        '''
        if log is None:
            log = logging.getLogger('DaffyPlotConfig')
            log.setLevel(logging.INFO)
            ch  = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            log.addHandler(ch)
            log.info("Adding default logging settings ")
        self.log = log
        parser = self.setup_option_parser(usage_string)
        if config_file:
            self.config_file = config_file
        else:
            self.config_file = self.get_config_file(parser)
        self.read_config(self.config_file) # sets several instance variables (self.datasetes, etc.)
        self.parse_cmdline_args(parser) # TODO : The start_date and end_date are ignored since the DaffyPlotConfig objects are created in read_config

    def get_config_file(self, parser):
        '''
        Get the config file from the passed in-args, or use default.
        This is done before parsing the rest of the command line options since
        the other command line options override what is set in the config file
        '''
        (options, args) = parser.parse_args()
        if options.config_file:
            return  options.config_file
        else:
            return self.DEFAULT_CONFIG_FILE

    def setup_option_parser(self, usage_string=None):
        '''
        Sets up possible options that can be passed as command line options. There is a separate method
        for this since the --config (file) must be read before the others, since the other parameters override
        the values in the config file
        '''
        parser = OptionParser(usage=usage_string)
        parser.add_option("-c", "--config", dest="config_file", default=self.DEFAULT_CONFIG_FILE,
           help='DaffyPlot configuration file (default: default.cfg)' )
        parser.add_option("-s", "--start-date", dest="start_date",
           help='Date (of output) to start the processing/product generation  on')
        parser.add_option("-e", "--end-date", dest="end_date",
           help='Date (of output) to end the processing/product generation on')
        parser.add_option("-d", "--debug-mode", action="store_true", dest="debug_mode", default=False,
           help='Debug mode: Sets log level to be very verbose.')
        return parser

    def parse_cmdline_args(self, parser):
        '''
        Parse command line options passed in `args`.
        Use already-set values created at initialization for defaults
        '''
        (options, args) = parser.parse_args()
        #self.config_file = options.config_file
        if options.start_date:
            try:
                os.environ['TZ'] = 'UTC'
                tzset()
                # TODO : ? timezone
                self.start_date = mktime( strptime(options.start_date, '%m-%d-%Y %H:%M') )
            except ValueError:
                print 'Passed in start date', options.start_date, 'does not match expected format MM-DD-YYYY hh:mm'
                sys.exit(1)
        if options.end_date:
            try:
                os.environ['TZ'] = 'UTC'
                tzset()
                self.end_date = mktime( strptime(options.end_date, '%m-%d-%Y %H:%M') )
            except ValueError:
                print 'Passed-in end date', options.end_date, 'does not match expected format MM-DD-YYYY hh:mm'
                sys.exit(1)
        self.debug_mode = options.debug_mode

        if self.debug_mode :
            #logging.setLevel(logging.DEBUG)
            logging.basicConfig(level=logging.DEBUG)
            self.debug_mode_str = 'TRUE'
        else:
            self.debug_mode_str = 'FALSE'

   
    def _getopt(self, config, section, param, default):
        '''
        Attempt to get a configuration option. If it does not exist, 
        set its value to the specified `default'
        @param config ConfigParser object
        @param section section in the `config'
        @param param the name of the parameter in `section'
        @param default The default value to use
        '''
        try:
               v = config.get(section, param)
        except ConfigParser.NoOptionError:
               v = default
        self.log.debug("Setting {} = {}".format(param, v))
        return v

    def read_config(self, config_file):
        '''
        Read the given `config_file' and set member variables accordingly
        '''
        
        BASIC_CONFIG_SECTION = 'basic_settings'
        DATA_CONFIG_SECTION = 'data_settings'
        PLOT_CONFIG_SECTION = 'plot_settings'
        MAP_CONFIG_SECTION = 'map_settings'
        STORM_CONFIG_SECTION = 'storm_settings'

        # read config file - if you get a TypeError you need a newer
        # version of Pyhon or a third-party ordered dictionary. The
        # OrderedDict is needed since the items() must be kept in order 
        config = ConfigParser.ConfigParser(dict_type=OrderedDict)
        if not os.path.exists(config_file):
            logging.fatal("Specified/Default config file %s does not exist" %config_file)
            raise Exception("Specified/Default config file %s does not exist" 
                            %config_file)
        config.readfp(open(config_file))

        # Set dataset-specific information
        datasets = [ v for (k,v) in  config.items('dataset_names') ]
        data_paths = [ v for (k,v) in config.items('data_paths') ]
        plot_colors = [ v.replace("'","").replace('"','') for (k,v) in config.items('plot_colors') ]
        line_styles  = [ v for (k,v) in config.items('line_styles') ]
        line_widths  = [ float(v) for (k,v) in config.items('line_widths') ]
        assert len(datasets) > 0
        assert len(datasets) == len(data_paths) 
        assert len(plot_colors) == len(datasets) 
        assert len(line_styles) == len(datasets)
        assert len(line_widths) == len(datasets)
        for path in data_paths: 
            if not os.path.exists(path):
                self.log.error("Specified experiment path does not exist: {}"
                          .format(path))
                sys.exit(1)

        # Set basic configuration settings
        self.log_level = config.get(BASIC_CONFIG_SECTION, 'log_level')
        self.value_source = config.get(BASIC_CONFIG_SECTION, 'value_source')
        startDate = config.get(BASIC_CONFIG_SECTION, 'start_date')

        try:
            startDate = startDate.replace("'", "").replace('"', '')
            os.environ['TZ'] = 'UTC'
            tzset()
            self.start_date = mktime(strptime(startDate, '%m-%d-%Y %H:%M'))
        except ValueError:
            print 'Given start date', startDate, 'does not match expected format MM-DD-YYYY hh:mm'
            sys.exit(1)
        endDate = config.get(BASIC_CONFIG_SECTION, 'end_date')
        try:
            endDate = endDate.replace("'", "").replace('"', '')
            os.environ['TZ'] = 'UTC'
            tzset()
            self.end_date = mktime( strptime(endDate, '%m-%d-%Y %H:%M') )
        except: # ValueError
            print 'Given end date', endDate, 'does not match expected format MM-DD-YYYY hh:mm'
            sys.exit(1)
        self.cycle_frequency = config.getfloat(BASIC_CONFIG_SECTION, 'cycle_frequency') * 3600.0
        self.forecast_frequency = config.getfloat(BASIC_CONFIG_SECTION, 'forecast_frequency') * 3600.0
        self.forecast_duration = config.getfloat(BASIC_CONFIG_SECTION, 'forecast_duration') * 3600.0
        self.history_interval = config.getfloat(BASIC_CONFIG_SECTION, 'history_interval') * 3600.0
        self.tracker = config.get(BASIC_CONFIG_SECTION, 'tracker')

        # storm settings
        self.storm_id = config.get(STORM_CONFIG_SECTION, 'storm_id')
        try:
            self.best_track_db_path = config.get(STORM_CONFIG_SECTION, "best_track_db_path")
            self.log.warn("Best_track was set. Will use this for truth_track. "
                     "Hence the 'truth_tracker_data_file' and 'nature_run_tracker'"
                     " options will be ignored".format())
            # UPDATE : For NHC b-deck best tracks
            # TODO : Still want to support different kinds. I'm just hardcoding for B-deck here
            startYear = conversions.epoch_to_yyyymmddHHMM(self.start_date)[0:4]
            self.best_track_db_path = self.best_track_db_path.replace("{aY}", startYear)
            self.truth_track = trkutils.get_track_data(self.best_track_db_path, 
                                                       self.storm_id, 
                                                       self.start_date)
            """
            # TODO : this cannot be instantiated here since it depends on the cycle date
            #        and storm name
            ymdh = conversions.epoch_to_yyyymmddHHMM(self.start_date)[:-2]
            self.best_track_db_path = self.best_track_db_path.replace("{aYMDH}", ymdh)
            globs = glob.glob(self.best_track_db_path)
            print self.best_track_db_path
            assert len(globs) == 1
            self.best_track_db_path = globs[0]
            self.truth_track = trkutils.get_track_data(self.best_track_db_path)
            """
        except ConfigParser.NoOptionError:
            self.best_track_db_path = None
        try:
            # TODO : This actually isn't being used, it will always try to guess it
            #        i.e. call  trkutils.get_track_data()
            self.best_track_db_format = config.get(STORM_CONFIG_SECTION, 'best_track_db_format')
        except ConfigParser.NoOptionError:
            self.best_track_db_format = '_guess_it'

        # data settings
        self.average_type = config.get(DATA_CONFIG_SECTION, "average_type")
        if not self.average_type in ('mean', 'rmse'):
            raise Exception("Average type should be 'mean' or 'rmse'")
        self.difference_type = config.get(DATA_CONFIG_SECTION, "difference_type")
        if not self.difference_type in ("absolute", "relative"):
            raise Exception("Difference type should be 'absolute' or 'relative'")
        self.plot_flagged_tracker_entries = config.getboolean(DATA_CONFIG_SECTION, 'plot_flagged_tracker_entries')
        self.annotate_unflagged_entries = config.getboolean(DATA_CONFIG_SECTION, 'annotate_unflagged_entries')
        self.ignore_land_points = config.getboolean(DATA_CONFIG_SECTION, "ignore_land_points")
        # TODO : Unify the best track and truth track stuff. Leave this one as a
        #       deprecated option
        if self.best_track_db_path is None:
            truthTrackFile = config.get(DATA_CONFIG_SECTION, 'truth_tracker_data_file')
            try:
                self.nature_run_tracker = config.get(DATA_CONFIG_SECTION, 'nature_run_tracker')
            except ConfigParser.NoOptionError:
                self.nature_run_tracker = '_guess_it'
            #import pdb ; pdb.set_trace()
            if self.nature_run_tracker == 'diapost':
                self.truth_track = trkutils.get_diapost_track_data(truthTrackFile)
            elif self.nature_run_tracker == 'nolan':
                self.truth_track = trkutils.get_nolan_track_data(truthTrackFile)
            elif self.nature_run_tracker == 'gfdl':
                self.truth_track = trkutils.get_gfdltrk_track_data(truthTrackFile)
            else:
                try:
                    self.truth_track = trkutils.get_track_data(truthTrackFile)
                except:
                    sys.stderr.writeln(
                        ("Unable to determine ATCF type for best track/truth. Try"
                         " to manually pass in via `nature_run_tracker'. Possible"
                         " values are 'nolan', 'gfdl', and 'diapost'."))
                    sys.exit(1)
            
        # plot settings
        self.time_axis_parameter = config.get(PLOT_CONFIG_SECTION, 'time_axis_parameter')
        self.legend_position = config.get(PLOT_CONFIG_SECTION, 'legend_position')
        self.legend_alpha = config.getfloat(PLOT_CONFIG_SECTION, 'legend_alpha')
        self.plot_nature_values = config.getboolean(PLOT_CONFIG_SECTION, 'plot_nature_values')
        # since hex codes use hash symbol, they need to be quoted in config file
        self.nature_line_color = config.get(PLOT_CONFIG_SECTION, 'nature_line_color').replace("'", "")
        self.nature_line_style = config.get(PLOT_CONFIG_SECTION, 'nature_line_style').replace("'", "")
        self.hline_at_zero = config.getboolean(PLOT_CONFIG_SECTION, 'add_hline_at_zero')
        # TODO : make this optional, since it will be set in stylesheets anyway
        self.line_width = config.getfloat(PLOT_CONFIG_SECTION, 'line_width')
        
        # Set Styles. Specifically, set self.style_paths which will be a list
        # containing the paths to the styles to use. For now, this consists
        # of the style specified in the file <stylesheets_path>/general/<view_target>.mplstyle
        # and any extra style specified by parameter <stylesheets>. The latter having 
        # higher priority. Eventually, method-specific styles will be supported, maybe.
        self.view_target = self._getopt(config, PLOT_CONFIG_SECTION,
                                        'view_target', 'desktop')
        self.stylesheets_path = self._getopt(config, PLOT_CONFIG_SECTION, 
                                             'stylesheets_path',
                                             './conf/styles')
        generalStyle = os.path.join(self.stylesheets_path, 'general', 
                                    self.view_target)                                             
        # we're going to pass in an exact path, so the extension is required
        generalStyle = generalStyle + '.mplstyle' 
        userStyles = self._getopt(config, PLOT_CONFIG_SECTION,
                                  'stylesheets', None)
        if userStyles is None:
            self.style_paths = [generalStyle]
        else:
            userStyles = re.split(', |  |,', userStyles)
            self.style_paths = [generalStyle].extend(userStyles)
        for i,path in enumerate(self.style_paths):
            if not os.path.exists(path):
                self.log.warn("Style sheet path {} does not exist!".format(path))
                self.style_paths.pop(i)
                #sys.exit(133)

        #self.static_y_limit_track = config.getboolean(PLOT_CONFIG_SECTION, 'static_y_limit_track')
        self.static_y_limit_mslp_value = config.getboolean(PLOT_CONFIG_SECTION, 'static_y_limit_mslp')
        self.static_y_limit_maxwind_value = config.getboolean(PLOT_CONFIG_SECTION, 'static_y_limit_maxwind')
        self.static_y_limit_track_error = config.getboolean(PLOT_CONFIG_SECTION, 'static_y_limit_track_error')
        self.static_y_limit_mslp_error = config.getboolean(PLOT_CONFIG_SECTION, 'static_y_limit_mslp_error')
        self.static_y_limit_maxwind_error = config.getboolean(PLOT_CONFIG_SECTION, 'static_y_limit_maxwind_error')

        self.y_limits_track = self.get_list(config.get(PLOT_CONFIG_SECTION, 'y_limits_track'), minValues=2, maxValues=2)
        self.y_limits_mslp = self.get_list(config.get(PLOT_CONFIG_SECTION, 'y_limits_mslp'), minValues=2, maxValues=2)
        self.y_limits_maxwind = self.get_list(config.get(PLOT_CONFIG_SECTION, 'y_limits_maxwind'), minValues=2, maxValues=2)
        self.y_limits_track_error = self.get_list(config.get(PLOT_CONFIG_SECTION, 'y_limits_track_error'), minValues=2, maxValues=2)
        self.y_limits_mslp_error = self.get_list(config.get(PLOT_CONFIG_SECTION, 'y_limits_mslp_error'), minValues=2, maxValues=2)
        self.y_limits_maxwind_error = self.get_list(config.get(PLOT_CONFIG_SECTION,
                                                               'y_limits_maxwind_error'),
                                                    minValues=2, maxValues=2)

        #
        # Process Map-related options
        #
        self.map_options = {}

        # settings that are parsed as lists
        self.map_options['padding'] = self.get_list(config.get(MAP_CONFIG_SECTION,
                                                               'padding'),
                                                    cast=float,
                                                    minValues=4, maxValues=4)
        # settings with string values
        for param in ('projection', 'resolution', 'latitude_label_mask',
                      'longitude_label_mask', 'ocean_color',
                      'lake_color', 'continents_fill_color',
                      'map_extents'):
            self.map_options[param] = config.get(MAP_CONFIG_SECTION, param)
        # populate all the boolean settings
        for param in ('draw_coastlines', 'draw_countries', 'get_extents_from_grib'):
            self.map_options[param] = config.getboolean(MAP_CONFIG_SECTION, param)
        #settings with integer values
        for param in ('latitude_line_freq', 'longitude_line_freq',
                      'track_plot_time_indicator_freq'):
            self.map_options[param] = int(config.get(MAP_CONFIG_SECTION, param))
        # TODO : Don't need
        #draw_map_boundary : Use the 'water_color'/'map_boundary_color' ;
        #lake_color and continent_color can be used instead of fill_continents

        #
        # convert input
        #
        #label masks
        for param in ('latitude_label_mask', 'longitude_label_mask'):
            # convert label masks to list, as expected by drawparallels/meridians
            self.map_options[param] = self.get_list(self.map_options[param],
                                                    cast=int,
                                                    minValues=4,
                                                    maxValues=4)
        # map extents
        self.map_options['map_extents'] = self.map_options['map_extents']\
                                          .replace("'", "").replace('"', '')
        toks = self.map_options['map_extents'].strip().split()
        self.map_options['southern_latitude'] = float(toks[0])
        self.map_options['western_longitude'] = float(toks[1])
        self.map_options['northern_latitude'] = float(toks[2])
        self.map_options['eastern_longitude'] = float(toks[3])
        # padding
        #self.map_options['padding'] = \
          #[x for x in self.map_options['padding'].strip().split(' ')]

        # validate input
        if not self.map_options['resolution'] in ('l', 'c', 'i', 'h', 'f'):
            raise Exception("Resolution in config file should be c/crude, "\
                            "l/low, i/intermediate, h/high, f/full")

        # populate list of DaffyExperimentDataset objects corresponding to the
        # datasets being plotted
        self.datasets = []
        
        for i in range(len(datasets)):
            plot_options = {}
            plot_options['tracker'] = self.tracker
            plot_options['plot_flagged_tracker_entries'] = self.plot_flagged_tracker_entries
            plot_options['line_color'] = plot_colors[i]
            plot_options['line_style'] = line_styles[i]
            plot_options['line_width'] = line_widths[i]
            plot_options['annotate_unflagged_entries'] = self.annotate_unflagged_entries
            plot_options['hline_at_zero'] = self.hline_at_zero
            plot_options['ignore_land_points'] = self.ignore_land_points 
            # Determine what system was used to run the experiment
            # and instantiate either DaffyExperimentDataset or PyHwrfExperimentDataset
            # For now, simply look for the gfdltrk product, since that should
            # probably exist for all experiments. 
            exptTypeFound = False
            try:
                #import pdb ; pdb.set_trace()
                ds = DaffyExperimentDataset(
                    name=datasets[i], path=data_paths[i], 
                    start_date=self.start_date, end_date=self.end_date, 
                    cycle_frequency=self.cycle_frequency,
                    forecast_frequency=self.forecast_frequency, 
                    forecast_duration=self.forecast_duration,
                    history_interval=self.history_interval, 
                    plot_options=plot_options, 
                    truth_track=self.truth_track)
                p = ds.products['gfdltrk_track'].get_path(cycle=self.end_date)
                exptTypeFound = True
                self.log.info("Guessing this is a DAFFY experiment based on "\
                              "existance of %s" %p)
            except (MissingProductException, AmbiguousProductException) as e:
                self.log.info("Assuming it's not a DAFFY experiment due to exc."
                         "Original exception: {0}".format(e))
                pass
            if not exptTypeFound:
                try:
                    ds = PyHwrfExperimentDataset(
                        name=datasets[i], path=data_paths[i], 
                        start_date=self.start_date, end_date=self.end_date, 
                        cycle_frequency=self.cycle_frequency,
                        forecast_frequency=self.forecast_frequency, 
                        forecast_duration=self.forecast_duration,
                        history_interval=self.history_interval, 
                        plot_options=plot_options, 
                        stormId=self.storm_id,
                        best_track_path=self.best_track_db_path,
                        truth_track=self.truth_track)
                    p = ds.products['gfdltrk_track'].\
                            get_path(cycle=self.end_date)
                    self.log.info("Guessing this is a PyHWRF experiment based "\
                                  "on existance of %s" %p)
                    exptTypeFound = True
                except (MissingProductException, AmbiguousProductException):
                    pass
            if not exptTypeFound:
                try:
                    ds = NmmbAutorunnerExperimentDataset(
                        name=datasets[i], path=data_paths[i],
                        start_date=self.start_date, end_date=self.end_date,
                        cycle_frequency=self.cycle_frequency,
                        history_interval=self.history_interval,
                        forecast_frequency=self.forecast_frequency,
                        forecast_duration=self.forecast_duration,
                        plot_options=plot_options,
                        stormId=self.storm_id,
                        truth_track=self.truth_track,
                       )
                    p = ds.products['diapost_track_domSpecific'].\
                            get_path(cycle=self.end_date, domain=2) 
                    exptTypeFound = True
                    self.log.info("Guessing this is an NMM-B autorunner"\
                                  " experiment based on existance of %s" %p)
                    # TODO: unhack this. 
                    self.log.warn("Forcing 'tracker' for this Dataset to diapost, since that is all the NMMB autorunner supports")
                    plot_options['tracker'] = 'diapost'
                except (MissingProductException, AmbiguousProductException):
                    raise Exception("{} : Unable to determine experiment type "
                                    "from the last cycle's tracker output"
                                    "check that path to experiments and that "
                                    " settings in conf/<experiment_type>.cfg "
                                    " are correct".
                                    format(datasets[i]))
                
            self.datasets.append(ds)


    def get_list(self, list_string, cast=None, minValues=-1, maxValues=-1):
        '''
        Convert space separated list (as string) to a list object, trimming the
        leading or trailing single or double quotes.
        If `cast` is not None: use method named `cast` to convert each element to
         this Type
        If minValues > -1,  raise an exception if we don't have at least minValues values
        If maxValues > -1, raise an exception if we have more than maxValues values
        '''
        list_string = list_string.replace("'", "").replace('"', '')
        l = list_string.strip().split(' ')
        if cast is not None:
            l = [ cast(e) for e in l ]
        if minValues > -1:
            if len(l) < minValues: raise Exception('Value given [%s] should be at least %i values long' %(list_string, minValues) )
        if maxValues > -1:
            if len(l) > maxValues: raise Exception('Value given [%s] should be at most %i values long' %(list_string, maxValues) )
        return l

    @property
    def nature_track(self):
        logging.info("nature_track is deprecated. Use 'truth_track'")
        return self.truth_track
