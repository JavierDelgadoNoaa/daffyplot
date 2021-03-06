#!/usr/bin/env python

import sys
import os
import gzip
import glob
from date_utils import epoch_to_yyyymmddHHMM
import subprocess
import logging as log

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.pyplot import gca, savefig
from mpl_toolkits.basemap import Basemap
#from util import get_marked_indices
from matplotlib.colors import ColorConverter


'''
This module provides methods that encapsulate properties of a GSI run. 

        contains                 contains  
GsiRun ---------> GsiObTypeDiag ---------->  GsiObservation
  |                    |                          |
  |                    |                          |
  |                  build()                (various SubTypes)
various getters  make_plain_text_diag_file()   to_csv()
                process_rad_diag_reader_output()
                process_conv_diag_reader_output()
                   various getters
                   
TODO: Get more details about the radiance observations. For now, I'm just getting
the number assimilated. I need a better understanding of how things work.
e.g. there is a separate iuse for each channel, but I don't know which channel
     corresponds to which ob.
'''

GES_DIAGFILE_SUFFIX = 'ges'
ANL_DIAGFILE_SUFFIX = 'anl'
DIAG_FILE_PREFIX = 'diag_'
DIAG_FILE_SUFFIX = ''
TEXT_DIAG_PREFIX = 'diag_'
TEXT_DIAG_SUFFIX = '.dat.gz'

log.basicConfig( level=log.DEBUG)



'''
MAP STUFF THAT PROBABLY DOES NOT BELONG HERE
'''
WEST_CORNER = -80.0
EAST_CORNER = -55.0
NORTH_CORNER = 40.0
SOUTH_CORNER = 25.0

WEST_CORNER = -80.0
EAST_CORNER = -30.0
NORTH_CORNER = 40.0
SOUTH_CORNER = 10.0

GRIDLINE_WE = 10
GRIDLINE_NS = 10
# Coastlines and lakes with an area (in sq. km) smaller than this will not be plotted
AREA_THRESHOLD = 1000.
# Map resolution should be (c)rude, (l)ow, intermediate, high, full, or None
MAP_RESOLUTION = 'l'
# Map projection - only 'cyl' is tested
MAP_PROJECTION = 'cyl'

TRACK_LINE_COLOR = '#ffffff'
TRACK_LINE_WIDTH = 1.5

# How frequently to create markers indicating time
TIME_MARKER_INTERVAL=24 # daily

def plot_obs(lats, lons, **kwargs):
    '''
    Given a list of latitudes and a list of longitudes corresponding to
    a hurricane track, plot the track using Basemap.

    REQUIRED ARGUMENTS
     - lats - List of latitude points
     - lons - List of longitude points

    OPTIONAL KEYWORD ARGUMENTS (and their corresponding functionality):
     - label - Label to  use for the legend
     - marker - Type of marker to use
     - ax - Axes object to plot on. This overrides the 'basemap' argument.
     - basemap - If set, use it as the Basemap object for plotting.
                 Otherwise instantiate a new one.
     - extents - If set and basemap is not passed in, use these extents
                 for the map. Should be a 4-element list as follows:
                     [lowerLat, westLon, upperLat, eastLon]
                 If not passed in, use the global variables defined in
                 this module
     - ns_gridline_freq - Interval (in degrees) at which to show north->south
                          gridlines
     - we_gridline_freq - Interval (in degrees) at which to show west->east
                          gridlines
     - draw_coastlines - Draw lines separating water from land? (Default: True)
     - draw_countries - Show the countries? (Default: True)
     - water_color - Colorize bodies of water? Default: Just leave it
                     as background color (white)
     - lake_color - Color to use for lakes within continents. Default: Leave as
                    background color.
     - continent_color - Color to use for continents. Default: white

     *NOTE: For b/w figure, only set draw_coastlines to True

    '''
    # Set basic optional values

    # array of arguments to pass to the plot() call
    mpl_plot_kwargs = {}

    # Set the axes
    if kwargs.has_key('ax'):
        ax = kwargs['ax']
    else:
        ax = gca()

    # Instantiate/set the Basemap object
    if kwargs.has_key('basemap'):
        m = kwargs['basemap']
    else:
        if kwargs.has_key('extents'):
            lowerLat = kwargs['extents'][0]
            westLon = kwargs['extents'][1]
            upperLat = kwargs['extents'][2]
            eastLon = kwargs['extents'][3]
        else:
            lowerLat = SOUTH_CORNER
            westLon = WEST_CORNER
            upperLat = NORTH_CORNER
            eastLon = EAST_CORNER
        m = Basemap(llcrnrlon=westLon,llcrnrlat=lowerLat,
                    urcrnrlon=eastLon,urcrnrlat=upperLat,
                    projection=MAP_PROJECTION, resolution=MAP_RESOLUTION,
                    area_thresh=AREA_THRESHOLD,
                    ax=ax)
    if kwargs.has_key('label'):
        label = kwargs['label']
    else:
        label = None
    if kwargs.has_key('facecolor'):
        facecolor=kwargs['facecolor']
    else:
        facecolor = 'red'
    if kwargs.has_key('marker'):
        marker = kwargs['marker']
    else:
        marker = '.'
    #
    # Plot the data
    #
    m.scatter(lons, lats,  latlon=True,
           label=label,
           marker=marker,
           color=facecolor,
           s=10,
            )
    #          marker=markers[obGroup])

    # draw coastlines, meridians and parallels.
    if kwargs.has_key('draw_coastlines') and not kwargs('draw_coastlines'):
        pass
    else:
        m.drawcoastlines()
    if kwargs.has_key('draw_countries') and not kwargs('draw_countries'):
        pass
    else:
        m.drawcountries()
    if kwargs.has_key('water_color'):
        m.drawmapboundary(fill_color=kwargs['water_color'])
    if kwargs.has_key('lake_color') or kwargs.has_key('continent_color'):
        if not kwargs.has_key('continent_color'):
            m.fillcontinents(lake_color=kwargs['lake_color'], color='white')
        elif not kwargs.has_key('lake_color'):
            m.fillcontinents(color=kwargs['continent_color'])
        else:
            m.fillcontinents(color=kwargs['continent_color'],
                             lake_color=kwargs['lake_color'])
    if kwargs.has_key('ns_gridline_freq'):
        m.drawparallels(np.arange(lowerLat,upperLat,kwargs['ns_gridline_freq']),
                        labels=[1,1,0,0])
    if kwargs.has_key('we_gridline_freq'):
        m.drawmeridians(np.arange(westLon,eastLon,kwargs['we_gridline_freq']),
                        labels=[0,0,0,1])



'''
///////////////////////////////////////////////////////
END MAP STUFF THAT PROBABLY DOes NOT BELONG HERE
//////////////////////////////////////////////
'''
class GsiRun(object):
     '''
     Encapsulate properties of a GsiRun. I chose "GsiRun" instead of "GsiExperiment" to avoid
     confusion as "GsiExperiment" can be a cycled GSI experiment run with a DA system.
     Each GsiRun contains a set of GsiObTypeDiag objects mapped to the ob types of interesst.
     This class provides high level methods to retrieve obs.
     '''
    
     def __init__(self, products_dir, date=None, ob_types=None, num_iterations=None,  rundir=None, diag_reader_rad=None, diag_reader_conv=None):
        '''
        Instantiate a GsiRun using product located in the given `products_dir`
        and populate the firstguess_diagnostics and (if applicable) analysis_diagnostics, 
        which are lists of GsiObTypeDiag objects.
        The products dir can be any directory containing GSI diagnostics in either the
        native format produced by GSI or the text-based format created using
        GsiObTypeDiag::dump_to_ascii
        
        Optional arguments:
           date - The experiment/cycle date, in seconds since epoch. 
                  If not given, attempt to determine from the namelist
           ob_types - List of ob types to include. Should correspond to the diag file
                      naming conventions. e.g. "foo_bar" for diag_foo_bar_anl.200508010600.
                      If None given, use all diag* files in the `products_dir`
           num_iterations - Number of minimization iterations (i.e. 1 for firstguess-only, 3 for analyses. 
                            If none given, attempt to figure out from namelist or from available
                            diagnostic files
           rundir - The directory where GSI was run, which may be different from where the products are.
        '''
        
        self.use_plaintext_diag = False # will be set to True if using plaintext diag files
        
        self.products_dir = products_dir
        if rundir is None: rundir = self.products_dir
        if num_iterations: self.num_iterations = num_iterations
        else: self.num_iterations = self._get_num_iter_from_output_path(rundir)
        self.is_analysis = False
        if date is None:
           raise Exception("Not implemented")
        else:
           self.date = date
        self.firstguess_diags = {}
        if self.num_iterations > 1:
            self.analysis_diags = {}
            self.is_analysis = True
            
        if ob_types: self.ob_types = ob_types
        else: self.ob_types = self._get_obTypes_from_products_dir()
        
        for obType in self.ob_types:
            #import pdb ; pdb.set_trace()
            self.firstguess_diags[obType] = GsiObTypeDiag(self.products_dir, obType, date, GES_DIAGFILE_SUFFIX, self.use_plaintext_diag, diag_reader_conv, diag_reader_rad)
            if self.is_analysis:
                self.analysis_diags[obType] = GsiObTypeDiag(self.products_dir, obType, date, ANL_DIAGFILE_SUFFIX, self.use_plaintext_diag, diag_reader_conv, diag_reader_rad )
        
        @property
        def firstguess_obs(self):
            return [ ob for obList in self.firstguess_diags.itervalues() for ob in obList ]

     def _get_num_iter_from_output_path(self, workdir):
         '''
         Determine the number of iterations based on either the namelist or the output files
         # TODO : need a unit test for this (e.g. different gsiparm.anl files: miter=2, miter=0, no miter)
         '''
         # try determining from namelist option miter
         with open(os.path.join(workdir, 'gsiparm.anl')) as elFile:
             for line in elFile.readlines():
                 if line.find("miter") > 0:
                    toks = line.split("=")
                    miter = int(toks[1][0])
                    if miter == 2: # assuming no characters before the value
                        log.info("Guessing this is an analysis run based on namelist value of 'miter'")
                        return 2 
                    else:
                        log.info("Guessing this is an O-F only run based on namelist value of 'miter'")
                        return 0
         
         #try to find 'anl' diag files
         pattern = DIAG_FILE_PREFIX + "*" + "_" + ANL_DIAGFILE_SUFFIX + "." +  epoch_to_yyyymmddHHMM(self.date) + DIAG_FILE_SUFFIX
         matches = glob.glob(os.path.join(workdir, pattern) )
         if len(matches) > 0:
             log.info("Guessing this is an analysis run based on existence of diag files for analysis")
             return 2
    
        # now try with the plaintext diag files
         pattern = TEXT_DIAG_PREFIX + "*" + "_" + ANL_DIAGFILE_SUFFIX + "." +  epoch_to_yyyymmddHHMM(self.date) + TEXT_DIAG_SUFFIX
         matches = glob.glob(os.path.join(workdir, pattern) )
         if len(matches) > 0:
             log.info("Guessing this is an analysis run based on existence of text diag files for analysis")
             return 2
         
         # assume its ges only
         return 0
             
     def _get_obTypes_from_products_dir(self):
        '''
         RETURN A list of obTypes by looking in self.products_dir for files matching the diag 
            file naming convention. 
            First, look for the binary diag files. If none are found, look for the plaintext
            diag files. If none are found, raise an exception
            If this is an analysis experiment, use the "_anl" files to get the obTypes. 
            Otherwise use the "_ges" files
            TODO: Create unit test for this (1)with binary diag files (2) plaintext diag files
        '''
        if self.is_analysis: 
            diag_step = ANL_DIAGFILE_SUFFIX
            log.info("Since this is an analysis run, will only process ob types for which a diag file was created for the analysis")
        else: 
            diag_step = GES_DIAGFILE_SUFFIX
        
        file_prefix = DIAG_FILE_PREFIX
        file_suffix = "_" + diag_step + "." +  epoch_to_yyyymmddHHMM(self.date) + DIAG_FILE_SUFFIX
        pattern = file_prefix + "*" + file_suffix # diag_cris_npp_anl.200508010600
        log.debug("Looking for files matching pattern %s" %os.path.join(self.products_dir, pattern))
        diag_files = glob.glob( os.path.join(self.products_dir, pattern)  ) 
        if len(diag_files) > 0:
            log.debug("Using GSI-generated binary diagnostic files")
            return [ x[x.index(file_prefix)+len(file_prefix):x.index(file_suffix)] for x in diag_files ]
        else: # attempt to find plaintext diag files
            file_prefix = TEXT_DIAG_PREFIX
            file_suffix = "_" + diag_step + "." +  epoch_to_yyyymmddHHMM(self.date) + TEXT_DIAG_SUFFIX
            pattern = file_prefix + "*" + diag_step + file_suffix
            diag_files = glob.glob( os.path.join(self.products_dir, pattern  ) )
            if len(diag_files) > 0:
                self.use_plaintext_diag = True
                log.debug("Using plaintext diagnostic files")
                return [ x[x.index(len(file_prefix)):x.index(file_suffix)] for x in diag_files ]
            else:
                raise Exception("Could not find any diagnostic files")

                
                
class GsiObTypeDiag(object):
    ''' 
    This class encapsulates the diagnostics for a specific ob type from a GsiRun.
    It stores everything of interest written in the pe*/diag* files. 
    '''
    def __init__(self, path, ob_type, date, step, use_plaintext_diag=False, diag_reader_conv=None, diag_reader_rad=None):
            '''
            Instantiate a GsiObTypeDiag object, which will be populated based on diag file 
            inside the given `path`. The `ob_type` should correspond to the GSI naming convention, 
            which is <obType>_<platform>. The cycle is `date` and step `step` (i.e. 'anl' or 'ges'), 
            If using plaintext diag files to build the object, `use_plaintext_diag` should be True
            If using binary diag files generated by GSI, the optional arguments diag_reader_conv
            and diag_reader_rad must be passed in. These point to the executables that extract ob stats
            from the diag files. THey are included in the GSI distribution under util/Analysis_Utilities.
            '''
            self.path = path
            self.ob_type = ob_type
            self.date = date # seconds since epoch
            self.step = step
            self.use_plaintext_diag = use_plaintext_diag
            self.gsi_diag_reader_conv = diag_reader_conv # may be None
            self.gsi_diag_reader_rad = diag_reader_rad # may be None
            #import pdb ; pdb.set_trace()

            self.build_obs_list()
            
    @property 
    def diag_file_name(self):
        return get_diag_file_name(self.ob_type, self.step, self.date, self.use_plaintext_diag)

    # TODO : THIS IS no longer needed, may be useful elsewhere
    def _add_obs(self, obs):
        '''
        Add a list of obs to the corresponding object field, depending on ob type
        '''
        for ob in obs:
            if isinstance(ob, GsiConventionalObservation): self.conv_obs.extend(obs)
            elif isinstance(ob, GsiRadianceObservation): self.rad_obs.extend(obs)
            else: raise Exception("Unknown or unsupported observation type: %s" %ob)

    
    def _create_diag_reader_namelist(self, ob_string, in_file_name, out_file_name):
        if ob_string == 'conv': suffix = 'conv'
        else: suffix = 'rad'
        elfilename = 'namelist.' + suffix
        elfile = open(elfilename, 'w')
        elfile.write('&iosetup\n')
        elfile.write("  infilename='%s',\n" %in_file_name)
        elfile.write("  outfilename='%s',\n" %out_file_name)
        elfile.write("/\n")
        elfile.close()  
    
    def process_conv_diag_reader_output(self, infile):
        '''
        Process output generated by diag file reader.
        Assume the following write statements were used (except the width; 
        just tokenize) for non-uv obs:
        write (42,'(A3," @ ",A8," : ",I3,F10.2,F8.2,F8.2,F8.2,I5,2F10.2)') &
                var,stationID,itype,rdhr,rlat,rlon,rprs,iuse,robs1,ddiff
        for uv-obs:
            write (42,'(A3," @ ",A8," : ",I3,F10.2,F8.2,F8.2,F8.2,I5,4F10.2)') &
                var,stationID,itype,rdhr,rlat,rlon,rprs,iuse,robs1,ddiff,robs2, rdpt2
        * Note the '@' and ':' will affect indexing
        ddiff is the o-g  (of u for uv obs)
        rlat/rlon are obs lat/lon ; rprs is ob pres
        rdhr is the time difference in hours, relative to analysis time
        iuse: was it used
        robs1 - ob value (of u in the case of uv)
        robs2 - ob value (of v)
        rdpt2 is the o-g of v
        UNITS: K,m/s, hPa,  (kg/m**2 for tpw i.e. lidar)
    
        RETURN : A list of GsiObservation elements 
    
        ***  NOTE: It's good to verify these against readconvobs.f90 (in enkf)  and $GSI_ROOT/util/Analysis_Utilities/read_diag/read_diag_conv
                if using a new version of GSI ***
        '''
        obs = []
        diffs = []
        with open(infile, 'r') as elfile:
            for line in elfile:
                data = line.strip().split()
                if len(data) < 10:
                    log.warn('Unrecognized line while reading diag file output [%s]:' %line)
                    continue
                station_id = data[2]
                type = data[0]
                subtype = data[4]
                time_delta = float(data[5]) # in hours relative to analysis time
                lat = float(data[6])
                lon = float(data[7] )
                pres = float(data[8])
                iuse = int(data[9])
                value = float(data[10])
                diff = float(data[11]) # this is the o-g value
                if type != 'uv':
                    ob = GsiConventionalObservation(type, station_id, time_delta, lat, lon, pres, iuse, value, diff)
                # for wind data
                else:
                    u = float(data[10])
                    v = float(data[12])
                    u_diff = float(data[11])
                    v_diff = float(data[13])
                    ob = GsiWindObservation(type, station_id, time_delta, lat, lon, pres, iuse, u, v, u_diff, v_diff)
                obs.append(ob)
                # TODO ? : handle gps obs differently?
        return obs
    
    def process_rad_diag_reader_output(self, infile):
        '''
        process output from the radiance diag file reader
        # TODO : Need a better understanding of these
        '''
        with open(infile, 'r') as fd:
            lines = fd.readlines()
            # NOTE: It's important to verify these with each new release
            dat = lines[0].strip().split()
            if len(dat) == 3: (isis,platform,ob_type) = dat
            else: raise ValueError("unexpected input in rad diag file")
            (jiter,num_channels,idate,ireal,ipchan,iextra,jextra) = ( int(x) for x in lines[1].strip().split() )
            # first num_channels lines after the two meta lines contain information about each channel
            for i in range(2, num_channels + 2):
                # TODO: Store this data in the GsiObTypeDiag 
                # sample data: nchanl=  1 76996.531     1.000  2568.328     1.800     0.000   -1    1 1586
                dat = lines[i].strip().split()[1:]
                if len(dat) == 9:
		            (channel_number,freq4,pol4,wave4,varch4,tlap4,iuse_rad,nuchan,ich) = [ float(x) for x in dat ]
                else: 
		            raise ValueError("Unexpected input in channel header section of input of rad diag file")
            # now read the obs
            for i in range(num_channels + 2, len(lines)):
                (lat,lon,pres,dtime_hrs) = ( float(x) for x in lines[i].strip().split() )
	
	
	## !! I think o-g for rad obs is by channel, not by ob, so I have to rethink constructors  (see enkf screen)
	## or I can just go with the ob-centric approach and output the corresponding channels' stats in each line 
    
    
    #def _extract_gsi_diag(self, diag_file_path, cycle, diag_step, diag_reader_conv, diag_reader_rad, gzip=True):
    def _extract_gsi_diag(self):
        '''
        Read GSI diag file using a reader, convert entries into GsiObservation objects, and return 
         a list containing these objects
        '''
        #in_file_name = 'diag_' + ob_string + '_' + diag_step + '.' + epoch_to_yyyymmddHHMM(cycle) 
        intermediate_file_name = 'results_' + self.ob_type + '_' + self.step + '.' + epoch_to_yyyymmddHHMM(self.date) 
        # determine ob type
        log.debug("Processing ob type: %s for step %s" %(self.ob_type, self.step) )

        # create intermediate text file
        try:
            owd = os.getcwd()
            os.chdir(self.path)
        except:
            log.error("Unable to change to directory: %s" %self.path)
            sys.exit(13)
         
        self._create_diag_reader_namelist(self.ob_type, self.diag_file_name, intermediate_file_name)
        if self.ob_type == 'conv':
            ret = subprocess.call([self.gsi_diag_reader_conv], shell=True, stdout=open("/dev/null", 'w') )
        elif self.ob_type == 'oz':
            raise Exception("Not implemented for oz obs")
        else: # assume radiance
            ret = subprocess.call([self.gsi_diag_reader_rad], shell=True, stdout=open("/dev/null", 'w') )
        # TODO  ensure it returns with exit code 9999    AND    have option of sending output to a file instead of /dev/null
         
        # process output
        if self.ob_type == 'conv':
            obs = self.process_conv_diag_reader_output(intermediate_file_name)
        else: # assume rad
            obs = self.process_rad_diag_reader_output(intermediate_file_name)
                         
        try:
            os.chdir(owd)
        except:
            log.error("Unable to switch back to original directory: %s" %owd)
            sys.exit(13)
        finally:
            os.unlink(os.path.join(self.path,intermediate_file_name))
        
        return obs
    
    """
    def dump_to_ascii(self, output_dir, gz=True):
        '''
        Create a plaintext diag file with relevant parameters.
        The diag file name will be determined using get_diag_file_name()
        and it will be placed in output_dir
        '''
        for step in ... :
            outfile_name = get_diag_file_name(obType, self.step, self.date, True)
            with gzip.open(outfile_name, 'rb') as outfile:
                for ob in self.obs:
                    outfile.write():
   """                 

        
    def _extract_gsi_textdiag(self):
        '''
        RETURN a GsiObTypeDiag object encapsulating the parameters output in the plain text diag 
                file
        ARGS
            - diag_file_path - Path to the diag file
            - date - Date of experiment, in seconds since epoch
            - diag_step - 'anl' or 'ges'
            - TODO : allow for non-gziped files
        '''
        obs = []
        diag_file_path = os.path.join(self.path, self.diag_file_name)
        if not os.path.exists(diag_file_path): 
            raise Exception("Path to diag file does not exist: [%s]" %diag_file_path)
        with gzip.open(diag_file_path, 'rb') as diagFile:
            for line in diagFile.readlines():
                # TODO : verify line numbers and limits
                toks = line.strip().split()
                ob_var = toks[0]
                ob_meta = toks[1] # could be platform,subtype,etc.
                (lat,lon,pres,time_delta) = (float(x) for x in toks[2:6])
                iuse = int(toks[6])
                if self.ob_type == 'conv':
                    if not (9,11) in len(toks): # 11 for uv, 9 for others: # TODO get exact size
                        raise Exception("Unrecognized input line in diag file [%s] " %diag_file_name)
                    if len(toks) == 9: # non-uv
                        assert toks[0] not in ('u', 'v')
                        obs.append(GsiConventionalObservation(ob_var, ob_meta, time_delta, lat, lon, pres, iuse, 
                                                float(toks[7]), float(toks[8])))
                    elif len(toks) == 11: # uv
                        assert toks[0] in ('u', 'v')
                        obs.append(GsiWindObservation(ob_var, ob_meta, time_delta, lat, lon, pres, iuse, 
                                          float(toks[7]), float(toks[8]), float(toks[9]), float(toks[10])))
                else: # assume radiance
                    raise Exception("not implemented")
                    
        
    #def build_obs_list(self, path, ob_type, date, diag_step, use_plaintext_diag, gsi_diag_reader_conv=None, gsi_diag_reader_rad=None):
    def build_obs_list(self):
        '''
        Populate the self.obs list
        
        ARGS   TODO :: uPDATE this now uses the class fields
            - path - Path to the diag file
            - ob_type - ob "tag" used by GSI naming convention consisting of <opType>_<platform> 
            - diag_step - 'anl' or 'ges'
            - use_plaintext_diag - True if using the plaintext diag files
            - diag_reader_conv - Reader for conventional-ob GSI diag files
            - diag_reader_rad - Reader for radiance-ob GSI diag files
            -   -> these last two may be None for use_plaintext_diag=True
        TODO :: Update this documentation, it no longer applies, but may be useful elsewhere
        The input source use is  as follows. If the path specified in 
        cfg.gsi_diag_reader_conv and cfg.gsi_diag_reader_rad exists
        on the local machine and there are diag files in the cycle's
        GSI output directory, use the diag files and the convert_gsi_diag()
        function. 
        Otherwise, look for the pre-generated plain-text diag files.
        If those don't exist, raise an exception
        '''
        diag_path = os.path.join(self.path, self.diag_file_name )
        if not os.path.exists(diag_path): raise Exception("Diag file not found: [%s]" %diag_path)
        
        if self.use_plaintext_diag:
            log.debug("Using plaintext diag to build GsiObTypeDiag object for obtype %s" %ob_type)
            self.obs = self._extract_gsi_textdiag()
        else:
            if self.gsi_diag_reader_conv is None or self.gsi_diag_reader_rad is None:
                raise Exception("Diag readers were not specified in the constructor. Try setting use_plaintext_diag to True if plaintext diag files are available")
            self.obs = self._extract_gsi_diag()
    
    
    def make_plain_text_diag_file(self, outfile='', outdir='',  gz=True, include_skipped=False):
        '''
        Make a plain-text diagnostic file given a GSI-generated "binary" diagnostic file
         
        PARAMETERS
         - outfile - Specify an output file name. If none is chosen, use "PLAIN_TEXT_DIAG_PREFIX + "_" + diag_step + "." + epoch_to_yyyymmddHHMM(cycle) + TEXT_DIAG_SUFFIX"
         - outdir - Specify and output directory. If none is given, use CWD
         - gz (Default True) - zip the output file using gzip
         - include_skipped (Default False) - include skipped (i.e. iuse != 1) observations in the output
        '''
        #import pdb ; pdb.set_trace()
        if self.obs is None:
            log.warn("No obs for ob type %s" %self.ob_type)
            return
        if len(outdir) == 0:
            outdir = os.getcwd()
        if len(outfile) == 0:
            outfile = TEXT_DIAG_PREFIX + self.ob_type + "_" + self.step + "." + epoch_to_yyyymmddHHMM(self.date) + TEXT_DIAG_SUFFIX
        if gz:
            outfile = gzip.open( os.path.join(outdir, outfile), 'wb')
        else:
            outfile = open( os.path.join(dataset.get_gsi_output_path(cycle), outfile), 'w')
        if include_skipped:
            #all_obs = self.conv_obs + self.rad_obs + self.oz_obs
            all_obs = self.obs
        else:
            #all_obs = self.non_skipped_conv_obs + self.non_skipped_rad_obs + self.non_skipped_oz_obs
            all_obs = [ ob for ob in self.obs if not ob.skipped ]
        for ob in all_obs:
            outfile.write( ob.to_csv() + "\n")
            
    '''
    Commenting these out since there is redundancy - GsiObTypeDiag objects only 
    obs of a certain type. These can be moved to the GsiRun class

    @property
    def non_skipped_conv_obs(self):
        return [ob for ob in self.conv_obs if ob.skipped == False]
    @property
    def non_skipped_rad_obs(self):
        return [ob for ob in self.rad_obs if ob.skipped == False]
    @property
    def non_skipped_oz_obs(self):
        return [ob for ob in self.oz_obs if ob.skipped == False]
    @property
    def conv_obs(self):
        return [ob for ob in self.obs if isinstance(ob, AbstractConventionalGsiObservation)]
    @property
    def rad_obs(self):
        return [ob for ob in self.obs]
    @property
    def oz_obs(self):
        return [ob for ob in self.obs]
    '''

    @property
    def all_obs(self):
        return self.obs
    @property
    def non_skipped_obs(self):
        return [ob for ob in self.obs if ob.skipped == False]
    @property 
    def skipped_obs(self):
        return [ob for ob in self.obs if ob.skipped]



class AbstractGsiObservation(object):
   ''' 
   Encapsulate attributes common to all GSI observations
   '''
   def __init__(self, type, time_delta, lat, lon, pres, iuse):
      self.type = type
      self.time_delta = time_delta
      self.lat = lat
      self.lon = lon
      self.pres = pres
      if iuse < 1:
         self.skipped = True
      else:
         self.skipped = False
         
   def to_csv(self):
       return ('%s, %f, %f, %f, %f' %(self.type, self.time_delta, self.lat, self.lon, self.pres))

class AbstractConventionalGsiObservation(AbstractGsiObservation):
   '''
   Encapsulate attributes common to all "conventional" GSI observations (i.e. not satellite nor ozone)
   '''
   def __init__(self, type, station_id, time_delta, lat, lon, pres, iuse):
      super(AbstractConventionalGsiObservation, self).__init__(type,  time_delta, lat, lon, pres, iuse)
      self.station_id = station_id

class GsiConventionalObservation(AbstractConventionalGsiObservation):
   def __init__(self, type, station_id, time_delta, lat, lon, pres, skipped, value, bias):
      super(GsiConventionalObservation, self).__init__(type, station_id, time_delta, lat, lon, pres, skipped)
      self.value = value
      self.bias = bias # o-g

   def to_csv(self):
       return ('%s, %f, %f, %f, %f, %f, %f' %(self.type, self.time_delta, self.lat, self.lon, self.pres, self.value, self.bias))


class GsiWindObservation(AbstractConventionalGsiObservation):
   def __init__(self, type, station_id, time_delta, lat, lon, pres, skipped, u_value, v_value, u_bias, v_bias):
      super(GsiWindObservation, self).__init__(type, station_id, time_delta, lat, lon, pres, skipped)
      self.u_value = u_value ; self.v_value = v_value
      self.u_bias = u_bias ; self.v_bias = v_bias
      
   def to_csv(self):
       return ('%s, %f, %f, %f, %f, %f, %f, %f, %f' %(self.type, self.time_delta, self.lat, self.lon, self.pres, self.u_value, self.v_value, self.u_bias, self.v_bias) )


def get_diag_file_name(obType, diag_step, date, is_text_diag):
    '''
    Create the file name based on known GSI naming convention
    ARGS:
      obType - The ob name or <obType>_<platform> "tag" used in GSI naming convention
      diag_step - the keyword used by GSI to distinguish ges and analysis (i.e. 'ges' or 'anl')
      date - The cycle date in seconds since epoch
      is_text_diag - True if using plaintext diag files
    '''
    if is_text_diag:
        return TEXT_DIAG_PREFIX + obType + "_" + diag_step + "." +  epoch_to_yyyymmddHHMM(date) + TEXT_DIAG_SUFFIX
    else:
        return DIAG_FILE_PREFIX + obType + "_" + diag_step + "." +  epoch_to_yyyymmddHHMM(date) + DIAG_FILE_SUFFIX
        

if __name__ == '__main__':
    #date = 1122890400 # storm/dst
    date = 1122876000 # jet
    gsirun = GsiRun('./gsi_test_dir', date=date, 
                   diag_reader_rad='/home/Javier.Delgado/apps/gsi/comgsi/3.3/util/Analysis_Utilities/read_diag/read_diag_rad.exe', 
                   diag_reader_conv='/home/Javier.Delgado/apps/gsi/comgsi/3.3/util/Analysis_Utilities/read_diag/read_diag_conv.exe')
    # TODO : make the plain text diag files for that case. Can't do it now because I'm not populating the obs list
    # for radiance diags
    for obDiag in gsirun.firstguess_diags.itervalues():
       obDiag.make_plain_text_diag_file()
    
    '''
    date = 1122897600 # 8/1/ 12z
    
    #gsirun = GsiRun('/lfs3/projects/hur-aoml/Lisa.R.Bucci/osse/AIRS_ret/airs_ret_all_6hr/run/GSI_ANALYSIS.2005_08_01_12_00', date=date, ob_types=['conv'],
    gsirun = GsiRun('./gsi_airs_dir/', date=date, ob_types=['conv'],
                   diag_reader_rad='/home/Javier.Delgado/apps/gsi/comgsi/3.3/util/Analysis_Utilities/read_diag/read_diag_rad.exe', 
                   diag_reader_conv='/home/Javier.Delgado/apps/gsi/comgsi/3.3/util/Analysis_Utilities/read_diag/read_diag_conv.exe')
    #for obDiag in gsirun.firstguess_diags.itervalues():
    #   obDiag.make_plain_text_diag_file()
    
    # build dictioary to use as data to plot_obs() - obs will be separated by time delta
    ob_groups = {}
    ob_group_names = ['-3<=dt<=-2', '-2<dt<=-1', '-1<dt<=0', '0<dt<=1', '1<dt<=2', '2<dt<=3']
    for obGrp in ob_group_names:
        ob_groups[obGrp] = { 'lats':[], 'lons':[] }
    #import pdb ; pdb.set_trace()
    #non_skipped_conv_obs = [ob for ob in gsirun.analysis_diags['conv'] if not ob.skipped]
#.non_skipped_conv_obs: # TODO (design issue?):  'conv' is redundant here
    
    #for ob in non_skipped_conv_obs:
    #for ob in gsirun.analysis_diags['conv'].non_skipped_conv_obs: # TODO (design issue?):  'conv' is redundant here
    #for ob in gsirun.firstguess_diags['conv'].non_skipped_conv_obs: # TODO (design issue?):  'conv' is redundant here
    for ob in gsirun.analysis_diags['conv'].non_skipped_obs: 
        dt = ob.time_delta
        if dt >= -3 and dt <= -2:
            ob_groups['-3<=dt<=-2']['lats'].append(ob.lat)
            ob_groups['-3<=dt<=-2']['lons'].append(ob.lon)
        elif dt > -2 and dt <= -1:
            ob_groups['-2<dt<=-1']['lats'].append(ob.lat)
            ob_groups['-2<dt<=-1']['lons'].append(ob.lon)
        elif dt > -1 and dt <= 0:
            ob_groups['-1<dt<=0']['lats'].append(ob.lat)
            ob_groups['-1<dt<=0']['lons'].append(ob.lon)
        elif dt > 0 and dt <= 1:
            ob_groups['0<dt<=1'] ['lats'].append(ob.lat)
            ob_groups['0<dt<=1'] ['lons'].append(ob.lon)
        elif dt > 1 and dt <= 2:
            ob_groups['1<dt<=2'] ['lats'].append(ob.lat)
            ob_groups['1<dt<=2'] ['lons'].append(ob.lon)
        elif dt > 2 and dt <= 3:
            ob_groups['2<dt<=3'] ['lats'].append(ob.lat)
            ob_groups['2<dt<=3'] ['lons'].append(ob.lon)

    facecolors = ['blue', 'green', 'red', 'purple', 'cyan', 'orange', 'gray']
    markers = ['s', 'o', '8', '*', '+', 'x', '.']

    for i,obGrp in enumerate(ob_group_names):
        #import pdb ; pdb.set_trace()
        # Note that this is calling all the decoration stuff every time
        print obGrp, ': ', len(ob_groups[obGrp]['lats'])
        if len(ob_groups[obGrp]['lats']) == 0: continue
        plot_obs(ob_groups[obGrp]['lats'], ob_groups[obGrp]['lons'], 
                 label=obGrp,
                 facecolor=facecolors[i],
                 marker=markers[i],
                 ns_gridline_freq=10,
                 we_gridline_freq=10)
    leg = plt.legend()
    leg.get_frame().set_alpha(0.85)
    savefig('obs.png')
    '''
