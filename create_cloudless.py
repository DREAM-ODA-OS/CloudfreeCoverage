#!/usr/bin/env python
#------------------------------------------------------------------------------
#
#
#       Tool to generate cloudless products over a period of chosen time
#       e.g. 10-days from the existing products
#
#
# Project: DeltaDREAM
# Name:    create_cloudless.py
# Authors: Christian Schiller <christian dot schiller at eox dot at>
#
#-------------------------------------------------------------------------------
# Copyright (C) 2014 EOX IT Services GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies of this Software or works derived from this Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#-------------------------------------------------------------------------------
#
#
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------





#### TODO:
##        *) add check about returned size - all need to be equal
##        *) add check/fallback if requested images do not contain bands requested (eg. fallback to band 1)
##        *) add OUTPUT_CRS to user supplied input parameters (optional)
##        *) add OUTPUT_FORMAT to user supplied input parameters (optional)
##        *) add Output DataType - to specify if datsets shell be changed to a different Datatype
##            eg. from 16-Bit Input to 8-Bit Output eg. for RGB image generation scenario [default = as Input]
##        *) change description of period (from number of days to number of products) ???
##        *) harmonize err_codes and sys.exit codes - and create a listing of their meanings
##        *) add full log-file support
##        *) maybe - allow the user to supply a SHP-file for data extraction (also KML, GML, GeoJason)
##



import sys
import os
import time
#import glob
import getopt
#from datetime import date

# specific imports
from get_config import get_config
import tempfile
import shutil
import urllib2,  socket
from xml.dom import minidom

    # check for OS Platform and set the Directory-Separator to be used
global dsep
dsep = os.sep


# the default config file (use full path here) - all other config parameters
# e.g. logging, dataset locations, etc. should be provided there
#default_config_file = "/home/schillerc/cs_pylib/spot4take5/conf/cloudless_config.cfg"
default_config_file = "/home/schillerc/cs_pylib/spot4take5/conf/cloudless_config.cfg"

    # default timeout for all sockets (in case a requests hangs)
timeout = 180
socket.setdefaulttimeout(timeout)

    # XML search tags for the request responses
xml_ID_tag = ['wcseo:DatasetSeriesId', 'wcs:CoverageId' ]
xml_date_tag = ['gml:beginPosition',  'gml:endPosition']


# ----------
# for performance testing
startTime1 = time.time()


#/************************************************************************/
#/*                               usage()                                */
#/************************************************************************/

def usage():
    """
        Print out the Usage information
    """
    print ""
    print "Usage: create_cloudless.py  [-d|--dataset] <dataset>  [-a|--aoi] <'minx,maxx,miny,maxy'>  [-t|--time] <startdate> "
    print "                  ([-s|--scenario] <T|M|B>)  ([-e|--extract] <full|sub>) ([-p|--period] <num days>)"
    print "  Tool to generate cloudless products over a period of X-days from the existing products. The processing ends after X-days"
    print "  or when no more clouds are present."
    print "  REQUIRED parameters: "
    print "   -d|--dataset <dataset>    --  Dataset to be used e.g. SPOT4Take5 "
    print "   -a|--aoi <'maxx,minx,maxy,miny'>  --  the Area of Interest (AOI), with the coordinates of the BoundingBox, provided as"
    print "                                          the corner coordinates in Degrees (WGS84, Lat/Lon)"
    print "   -t|--time <stardate>      --  Starttime - Date of the image to start with in ISO-Format e.g. '20120423' "
    print "  OPTIONAL parameters: "
    print "   -h|--help                 --  This help information"
    print "   -i|--info                 --  Information about available DatasetSeries (result of GetCapability-DatasetSeriesSummary requests)"
    print "   -s|--scenario  <T|M|B>    --  Scenario type: a) input Dataset is topmost-layer (T), filling in clouded areas with pixels"
    print "                                                   from older images [=default]"
    print "                                                b) input Dataset is middle (M), alternating newer and older images"
    print "                                                c) input Dataset acts as bottom-layer (B), filling in clouded areas with pixels"
    print "                                                   from newer images"
    print "                                 [default=SUB]"
    print "   -p|--period  <num days>   --  time period (number of days/images) to run the cloudless processing [optional, default=7]"
    print "                                 a period of 10 days/images will usually be sufficient to achieve a good result."
    print "   -b|--bands <'b1,b2,..bn'> --  list of bands to be processed e.g. '3,2,1'  [default = use all bands] "
    print "   -o|--output_dir           --  location to store the output/results (optional: -> but only for CLI usage) "
# TODO - not fully implemented yet
#    print "   -c|--output_crs           --  the EPSG code (epsg:number) of the desired output [default='epsg:4326'] "
#    print "   -y|--output_datatype      --  the datatype of the desired output e.g. INT8, UINT16, FLOAT32 [default = same as input] "
#    print "   -f|--output_format        --  output fileformat for the cloud-free product [default=GeoTiFF] "
#    print "                                  - possible output formats:  GeoTiFF, (all formats supported by gdal as writable)"
#    print "                                  - currently only GeoTiFF is supported"
#    print "   -e|--extract  <FULL|SUB>  --  work on an extracted subset or use all datsets, as  full files, touched by the AOI"
# TODO: @@  maybe we also should consider a WCS-server address as an input recieved from the WPS-server
    print ""
    print "Example: create_cloudless.py -d landsat5_2a -a 3.5,3.6,43.3,43.4 -t 20110513 -s T -b 3,2,1 -p 90 "
    sys.exit()


#/************************************************************************/
#/*                            do_interupt()                                     */
#/************************************************************************/
def do_interupt():
    """
        stop at call, to allow interactive usage with eg. iPython
        and variable exploration for dubugging
    """
    import pdb #@@
    pdb.set_trace() #@@
    print 'stop here' #@@

#/************************************************************************/
#/*                            now()                                     */
#/************************************************************************/
def now():
    """
        get the current time stamp eg. for error messages
    """
    return  time.strftime('[%Y%m%dT%H%M%S] - ')


#/************************************************************************/
#/*                               handle_error()                              */
#/************************************************************************/

def handle_error(err_msg, err_code):
    """
        prints out the error_msg and err_code and exit
        Mainly used during debugging
    """
    print err_msg, err_code
#    usage()
    sys.exit(err_code)


#/************************************************************************/
#/*                               dss_info()                              */
#/************************************************************************/
def dss_info():
    """
        provide listings of available DatasetSeries from all configured servers
        (from the configuration file)
    """
        # get all uniq servers defined in the config-file
    serv_list = []
        # just grab the server info - strip off the rest
    for vv in settings.itervalues():
        if vv.startswith('http'):
            ss = vv.split('?')
            serv_list.append(ss[0]+'?')

        # get the uniqu server listing
    serv_list = sorted(set(serv_list))

        # call each server and ask for a GetCapabilities-DatasetSeriesSummary
    for target_server in serv_list:
#        result_list = list_available_dss(target_server, True)
        list_available_dss(target_server, True)
        print '-----------'

    sys.exit()

#/************************************************************************/
#/*                             parse_xml()                              */
#/************************************************************************/

def parse_xml(in_xml, tag):
    """
        Function to parse the request results (GetCapabilities & DescribeEOCoverageSet) for the available
        DataSetSeries (EOIDs) and CoveragesIDs.
    """

        # parse the xml - received as answer to the request
    xmldoc = minidom.parseString(in_xml)
        # find all the tags (CoverageIds or DatasetSeriesIds)
    tagid_node = xmldoc.getElementsByTagName(tag)
        # number of found tags
    n_elem = tagid_node.length
    tag_ids = []
        # store the found items
    for n  in range(0, n_elem):
        tag_ids.append(tagid_node[n].childNodes.item(0).data)

        # return the found items
    return tag_ids


#/************************************************************************/
#/*                               get_available_dss()                              */
#/************************************************************************/

def list_available_dss(target_server, printit):
    request_dss_sum = 'service=wcs&version=2.0.0&request=GetCapabilities&sections=DatasetSeriesSummary'
    #service = settings['dataset.'+input_params['dataset']]
    #service1 = service.rsplit('EOID')[0]
    #request_url_dss_sum = service1+request_dss_sum
    request_url_dss_sum = target_server+request_dss_sum

        # for logging purpose
    print 'Server: ', '\n', request_url_dss_sum

    try:
            # access and the url & read the content
        res_dss_sum = urllib2.urlopen(request_url_dss_sum)
        getcap_xml = res_dss_sum.read()

        dss_ids = parse_xml(getcap_xml, xml_ID_tag[0])
        dss_date1 = parse_xml(getcap_xml, xml_date_tag[0])
        dss_date2 = parse_xml(getcap_xml, xml_date_tag[1])


#### for logging and/or for debugging
        if printit is True:
                # print the available DatasetSeriesIds to the screen
            print "The following DatasetSeries [Name: From-To] are available:"
            for i in range(len(dss_ids)):
                print " - ", dss_ids[i] , ": \t", dss_date1[i], " - ", dss_date2[i]


            # close the acces to the url
        res_dss_sum.close()
#        dss_result=[dss_ids, dss_date1, dss_date2]
#        return  dss_result

    except urllib2.URLError, url_ERROR:
        if hasattr(url_ERROR, 'reason'):
            print  time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  Server not accessible -", url_ERROR.reason
        elif hasattr(url_ERROR, 'code'):
            print time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  The server couldn\'t fulfill the request - Code returned:  ", url_ERROR.code,  url_ERROR.read()


#/************************************************************************/
#/*                              do_cleanup()                            */
#/************************************************************************/
def do_cleanup_tmp(temp_storage, cf_result, input_params):
    """
        clean up the temporary storagespace  used during download and processing
    """

    for elem in cf_result:
        shutil.copy2(temp_storage+dsep+elem, input_params['output_dir'])

    if os.path.exists(input_params['output_dir']+cf_result[0]) \
      and os.path.exists(input_params['output_dir']+cf_result[1]) \
      and os.path.exists(input_params['output_dir']+cf_result[2]):
          # remove all the temporay storage area
#        shutil.rmtree(temp_storage, ignore_errors=True)
        print '[Info] -- The Cloud-free dataset has been generated and is available at: '
        for elem in cf_result:
            print '  - ', input_params['output_dir']+elem
    else:
        print '[Error] -- The generated output-file could not be written to: ', input_params['output_dir']+cf_result
        sys.exit(7)

#/************************************************************************/
#/*                           do_print_flist()                           */
#/************************************************************************/
def do_print_flist(name, a_list):
    f_cnt = 1
#    print name, len(list), type(list)
    for elem in a_list:
        print  name, f_cnt,': ', elem
        f_cnt += 1


#/************************************************************************/
#/*                              get_cmdline()                           */
#/************************************************************************/
def get_cmdline():
    """
        get_cmdline() function - processing of the command-line inputs
        Outputs the dictionary: input[ 'in_dataset':, 'in_aoi':, 'in_toi': 'in_scenario':,
                    'in_extract':, 'in_period':, 'in_output_crs':, 'in_bands':, 'in_output_datatype':, 'in_output_dir':,
                    'output_format': ]
    """

# TODO: @@  maybe we also should consider a WCS-server address as an input recieved from the WPS-server
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hia:d:t:s:e:p:c:b:y:o:f:", ["help", "info", "aoi",
                    "time", "dataset", "scenario", "extract", "period", "crs", "bands", "datatype",
                    "output_dir", "output_format"])
    except getopt.GetoptError, err:
        # print help information and exit - will print something like "option -x not recognized"
        print '[Error] -- ', now(), str(err)
        usage()

    input_params = {
    'dataset' : None,
    'aoi' : None,
    'toi' : None,
    'scenario' : None,
    'extract' : None,
    'period' : None,
    'output_crs' : None,
    'bands': None,
    'output_datatype'  : None,
    'output_dir'   : None,
    'output_format' : None
    }


    for opt, arg in opts:
        if opt in ("-h", "--help", "-help", "help"):
            usage()

        elif opt in ("-i", "--info", "-info", "info"):
            print '==== You requested DatasetSeries information from all configured Servers ===='
            dss_info()

        elif opt in ("-d", "--dataset"):
            if arg is None or arg.startswith('-'):
                print "[Error] -- 'dataset' is a required input parameter"
                usage()
            else:
                input_params['dataset'] = arg

        elif opt in ("-a", "--aoi"):
            if arg is None:
                print "[Error] -- 'aoi' is a required input parameter"
                usage()
            else:
                input_params['aoi'] = arg.split(',')     # as minx, maxx, miny, maxy
                if len(input_params['aoi']) != 4:
                    print "[Error] -- the aoi requires 4 parameters 'minx, maxx, miny, maxy'"

        elif opt in ("-t", "--time"):
            if arg is None or arg.startswith('-'):
                print "[Error] -- the 'time' is a required input parameter"
                usage()
            else:
                input_params['toi'] = arg

        elif opt in ("-s", "--scenario"):
            input_params['scenario'] = str.upper(arg)

        elif opt in ("-e","--extract"):
            input_params['extract'] = str.lower(arg)

        elif opt in ("-p","--period"):
            input_params['period'] = int(arg)

        elif opt in ("-c","--crs"):
            input_params['output_crs'] = arg

        elif opt in ("-b","--bands"):
            if arg.count(',') > 0 or len(arg) == 1:
                input_params['bands'] = arg.split(',')
            else:
                err_msg = '[Error] -- supplied Band parameters cannot be handled: ', opt, arg
                handle_error(err_msg, 2)

        elif opt in ("-y","--datatype"):
            input_params['output_datatype'] = str.lower(arg)

        elif opt in ("-o","--output_dir"):
            input_params['output_dir'] = arg
            if input_params['output_dir'][-1] != dsep:
                input_params['output_dir'] = input_params['output_dir']+dsep

        elif opt in ("-f", "--output_format"):
            input_params['output_format'] = str.lower(arg)

        else:
            print '[Error] -- ', now(), ' unknown option(s): ', opts


        # set the default values if optional parameters have not been supplied at the cmd-line
    if input_params['bands'] is None:    input_params['bands'] = settings['general.def_bands']
    if input_params['period'] is None:    input_params['period'] = int(settings['general.def_period'])
    if input_params['scenario'] is None:    input_params['scenario'] = str.upper(settings['general.def_scenario'])
    if input_params['output_crs'] is None:    input_params['output_crs'] = settings['general.def_output_crs']
    if input_params['output_datatype'] is None:    input_params['output_datatype'] = str.lower(settings['general.def_output_datatype'])
    if input_params['output_format'] is None:    input_params['output_format'] = str.lower(settings['general.def_output_format'])
    if input_params['extract'] is None:    input_params['extract'] = str.lower(settings['general.def_extract'])

    return input_params



#/************************************************************************/
#/*                               main()                                 */
#/************************************************************************/

def main():
    """
        Main function - processing the command-line inputs
    """
        # read in the default settings from the configuration file
    global settings
    settings = get_config(default_config_file)
#        for k, v in settings.items():
#            print k,' -- ', v

        # get all parameters provided via cmd-line
    global input_params
    input_params = get_cmdline()
#        print 'I: ', input_params
#        print 'S1: ', settings
#        print 'S2: ', settings.keys(), ' ==== ', settings.values()


        # now that we know what dataset we need and where to find them, select the
        # correct reader for the requested dataset
        # first test if requested dataset does exist
    if settings.has_key('dataset.'+input_params['dataset']):
        reader = 'CF_' + input_params['dataset'] + '_Reader'
    else:
        err_msg = '[Error] -- ', now(), ' the requested dataset does not exist (is not configured)', input_params['dataset']
        err_code = 3
        handle_error(err_msg, err_code)

# @@ for debugging
    #do_interupt()

        # call the reader module for the resepective dataset and process the data
    import dataset_reader
    attribute = getattr(dataset_reader, reader)
    f_read = attribute()

        # gets a listing of available DatasetSeries and their corresponding time-range
    base_flist, base_mask_flist, gfp_flist, gfpmask_flist = f_read.get_filelist(input_params, settings)

# @@ for debugging
    #do_interupt()

        # print the available datasets:  ?? during testing only
    do_print_flist('BASE', base_flist)
    do_print_flist('BASE_Mask', base_mask_flist)
    do_print_flist('GFP', gfp_flist)
    do_print_flist('GFP_Mask', gfpmask_flist)


    print 'dataset_listing - RUNTIME in sec: ',  time.time() - startTime1
        # create a temporarylocation under the provided settings['general.def_temp_dir'] to be used
        # for the temporary storage during processing
    temp_storage = tempfile.mkdtemp(prefix='cloudfree_',dir=settings['general.def_temp_dir'])
    if temp_storage[-1] != dsep:
        temp_storage = temp_storage+dsep

    if len(base_flist) >= 1:
        f_read.receive_data(base_flist, input_params, settings, temp_storage, mask=False)

    if len(base_mask_flist) >= 1:
        f_read.receive_data(base_mask_flist, input_params, settings, temp_storage, mask=True)

# @@ TODO - the downloads shall be made one after the other and shall be immediately processed,
# so that once the baseImg is cloudfree no unnecessary downloads are made
# i.e. change these to a download-process-download loop
    if len(gfp_flist) >= 1:
        f_read.receive_data(gfp_flist, input_params, settings, temp_storage, mask=False)

    if len(gfpmask_flist) >= 1:
        f_read.receive_data(gfpmask_flist, input_params, settings, temp_storage, mask=True)


    print 'dataset_download - RUNTIME in sec: ',  time.time() - startTime1

        # call the Processor module for the resepective dataset and process the data
    import dataset_processor
    cfprocessor = 'CF_' + input_params['dataset'] + '_Processor'
    attribute = getattr(dataset_processor, cfprocessor)
    f_proc = attribute()
    cf_result = f_proc.process_clouds(base_flist, base_mask_flist, gfp_flist, gfpmask_flist, input_params, settings, temp_storage)


# @@ -- off during testing
        # copy results to output location and clean-up the temporary storage area
   #do_cleanup_tmp(temp_storage, cf_result, input_params)


# ----------
# for performance testing
    print 'full processing time - RUNTIME in sec: ',  time.time() - startTime1
    print '**** D O N E ****', '\n'


#/************************************************************************/
#/*                            main()                                    */
#/************************************************************************/


if __name__ == "__main__":
    main()







