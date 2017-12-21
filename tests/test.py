#!/usr/bin/env python
##
# Test program : Compares outputs to expected
##

from subprocess import call, Popen, STDOUT
import sys
import os

# Location of top-level directory of daffyplot distribution to test
TEST_DISTRIBUTION = '../trunk'
# configurations to test - should have matching x.cfg for each element in CWD
CONFIGS = ['cfg1', 'cfg2', 'cfg3', 'cfg4'] 
CONFIGS = ['cfg4'] 
# Prefix of subdirectories containing expected outputs for the corresponding
# configuration. Suffix should be the config element string in CONFIGS
EXPECTED_OUTPUTS_DIR = 'expected_outputs'
# Directory containing configuration files for testing
CONFIGS_DIR = 'configs'
# Directory containing datasets (with DAFFY output data) to use for the test
TEST_DATASETS_DIR = 'sample_datasets'

# map scripts to the outputs they generate
test_cases = \
    {  'grid_fhr_vs_tcvValue_multipleForecasts.py' : ('mslp_grid.png', 
                                                      'maxwind_grid.png') ,
       'grid_fhr_vs_tcvError_multipleForecasts.py' : ('mslp_error_grid.png',
                                                      'maxwind_error_grid.png',
                                                      'track_error_grid.png'),
       'plot_fhr_vs_tcvErr_multiForecast.py' : ( 'track_error.png', 
                                                 'maxwind_error.png', 
                                                 'mslp_error.png' ) ,
       'plot_gesproxy_and_analysis.py' : ( 'analysis_and_proxyges_track_error.png',
                                           'analysis_and_proxyges_maxwind_error.png',
                                           'analysis_and_proxyges_mslp_error.png'),
       'plot_meanTcvError_vs_fhr.py' : ('mean_track_error.png',
                                        'mean_maxwind_error.png',
                                        'mean_mslp_error.png'),
       'plot_tcvValues_with_Nature.py' : ( 'maxwind_value.png', 'mslp_value.png'),
       'plot_tracks.py' : ['tracks.png'],
    }
# map configurations to dataset(s) they should use for testing
dataset_mappings = \
    { 'cfg1' : '1cs1gsi2enkf_1',
      'cfg2' : '1cs1gsi2enkf_1',
      'cfg3' : '1cs1gsi2enkf_1',
      'cfg4' : 'different_model_configs',
    }

# run tests to compare each script's output to the existing output
for config in CONFIGS:
    print 'Testing configuration "%s" with dataset "%s"' \
        %(config, dataset_mappings[config])
    # create link to test dataset, if necessary - prolly don't need this 
    # now that the sample data sets are kept in the test directory 
    test_data_path = "%s/%s" %(TEST_DATASETS_DIR, dataset_mappings[config])
    if not os.path.islink(dataset_mappings[config]):
        os.symlink(test_data_path, dataset_mappings[config])
    expected_output_dir = os.path.join(EXPECTED_OUTPUTS_DIR, config)
    config_file = os.path.join(CONFIGS_DIR, config + '.cfg')
    if not os.path.exists(config_file): 
        raise Exception("config file %s not found" %config_file)
    regressions = []
    for scriptName,outputs in test_cases.iteritems():
        logfile_name = scriptName + '.log'
        with open(logfile_name, 'w') as logfile:
            p = Popen( [TEST_DISTRIBUTION+'/'+scriptName,"-c",config_file],
                       stdout=logfile, stderr=STDOUT )
            p.wait()
        #if x != 0:
        #   print "Error with ", scriptName
        for outFile in outputs:
            x = call(["diff", outFile, expected_output_dir+"/"+outFile])
            if x != 0:
                regressions.append(outFile)
            else:
                os.unlink(outFile)
        # check if logfile output matches expected output
        x = call(["diff", logfile_name, expected_output_dir])
        if x != 0:
            regressions.append(logfile_name)
        else:
            os.unlink(logfile_name)

    # Since the user will probably want to look at the output, 
    # terminate execution if differences were found, lest we 
    # overwrite the file with subsequent configs
    if len(regressions) > 0:
        print 'Exiting now since differences were found for config "%s"' %config
        sys.exit(1)

    os.unlink(dataset_mappings[config])

if len(regressions) > 0:
    print "Difference found the following output files", regressions, "!!"
else:
    print 'All tests succeeded!'
