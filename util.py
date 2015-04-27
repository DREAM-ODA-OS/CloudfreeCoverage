#!/usr/bin/env python
#
#------------------------------------------------------------------------------
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#
#
#       some utilities used by create_cloudless.py, dataset_reader.py, 
#       dataset_porocessor.py, and wcs_client.py
#
#
# Project: DeltaDREAM
# Name:    util.py
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


import os
import sys

from xml.dom import minidom





#/************************************************************************/
#/*                               handle_error()                         */
#/************************************************************************/

def handle_error(err_msg, err_code, settings):
    """
        prints out the error_msg and err_code and exit
    """
    #print err_msg, err_code
    err_msg = (err_code,) + err_msg
    print_log(settings, err_msg)
#    usage()
    sys.exit(err_code)




#/************************************************************************/
#/*                        print_log()                                   */
#/************************************************************************/
def print_log(settings, msg):
    """
        writes log-output 
    """
    if msg.__class__ is str or msg.__class__ is unicode:
       print >> settings['logging.log_fsock']  , msg
    else:
        for elem in msg: 
            print >> settings['logging.log_fsock']  , "%s" % elem,
    
        print >> settings['logging.log_fsock'] ,''
    
    settings['logging.log_fsock'].flush()


#/************************************************************************/
#/*                           set_logging()                              */
#/************************************************************************/
def set_logging(settings):
    """
        set logging output according to configuration -> either to the 
        screen or to a files
    """
    #global settings
    if settings['logging.log_type'] == 'screen':
        log_fsock = sys.stdout
    if settings['logging.log_type'] == 'file':
        if settings['logging.log_file'] is None or settings['logging.log_file'] is '':
            err_msg = 'Error - there is no log-file location provided in the the config-file'
            handle_error(err_msg, 10)
        log_fsock = open(settings['logging.log_file'], 'a')
            # also write the stderr to the logfile (in anycase)
            # comment out next line if errors should go to screen and not to log-file
        sys.stderr = log_fsock

    
    #return log_fsock
    settings['logging.log_fsock'] = log_fsock



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

