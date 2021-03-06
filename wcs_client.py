#!/usr/bin/env python

# -*- coding: utf-8 -*-
"""
#------------------------------------------------------------------------------
# Name:  wcs_client.py
#
#   General purpose WCS 2.0/EO-WCS Client:
#       The routine is inteded to be imported as modules. 
#       If cmd-line usage is desired the cmdline_wcs_client.py will provide it.
#       The documentation of the modules functionality is provided as doc-strings.
#
#   This WCS-Client provides the following functionality:
#         - GetCapabilities Request
#         - DescribeCoverage Request
#         - DescribeEOCoverageSet Request
#         - GetMap Request
#
#         - return responses
#         - download coverages
#         - download time-series of coverages
#
#   It allows users to specify:
#         + Server URL
#         + Area of Interest (subset)
#         + Time of Interest (time constrain)
#         + DatasetSeries or Coverage
#         + Rangesubsetting (eg. Bands)
#         + File-Format (image format) for downloads
#         + output CRS for downloads
#         + mediatype
#         + updateSequence
#         + containment
#         + section
#         + count
#         + interpolation
#         + size or resolution
#
#   Additional (non-standard parameters implemented:
#           + mask
#           + IDs_only (DescribeEOCoverageSet returns only CoverageIDs - to be used for immediate download)
#           + output (GetCoverage only - local location where downloaded files shall be written too)
#
#
#
# Name:        wcs_client.py
# Project:     DeltaDREAM
# Author(s):   Christian Schiller <christian dot schiller at eox dot at>
##
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
"""

import sys
import os
import time, datetime
import urllib2, socket
from xml.dom import minidom

from util import print_log



global __version__
__version__ = '0.1'

    # check for OS Platform and set the Directory-Separator to be used
global dsep
dsep = os.sep

    # sets the url where epsg CRSs are defined/referenced
global crs_url
crs_url = 'http://www.opengis.net/def/crs/EPSG/0/'

    # sets a storage location in case the user doesn't provide one (to be on the save side)
global temp_storage
temp_storage = None
try_dir = ['TMP', 'TEMP', 'HOME', 'USER']
for elem in try_dir:
    temp_storage = os.getenv(elem)
    if temp_storage != None:
        break

if temp_storage is None:
    cur_dir = os.getcwd()
    temp_storage = cur_dir # +'/tmp'


global file_ext
file_ext = {'tiff': 'tif' ,
            'jpeg': 'jpg' ,
            'png': 'png', 
            'gif': 'gif',
            'x-netcdf': 'nc', 
            'x-hdf': 'hdf' }


#/************************************************************************/
#/*                              wcsClient()                             */
#/************************************************************************/

class wcsClient(object):
    """
        General purpose WCS client for WCS 2.0/EO-WCS server access.
        This client provides all functionalities as described in the EOxServer ver.0.3
        documentation (http://eoxserver.org/doc/en/users/EO-WCS_request_parameters.html).
        It offers:
          - GetCapabilities Request
          - DescribeCoverage Request
          - DescribeEOCoverageSet Request
          - GetMap Request
        It therefore provides the receipt of
            - GetCapabilities response XML documents
            - DescribeCoverage response XML documents
            - DescribeEOCoverageSet response XML documents
            - download coverages using GetCoverage request
            - download time-series of coverages using the combination of
              DescribeEOCoverageSet and GetCoverage requests
         It allows the users to specify:
            + Server URL
            + Area of Interest (subset)
            + Time of Interest (time constrain)
            + DatasetSeries or Coverage
            + Rangesubsetting (eg. Bands)
            + File-Format (image format) for downloads
            + output CRS for downloads
            + mediatype
            + updateSequence
            + containment
            + section
            + count
            + interpolation
            + size or resolution

         Aadditional (non-standard) parameters implemented:
            + mask
            + IDs_only (DescribeEOCoverageSet returns only CoverageIDs - to be
              used for immediate download)
            + output (GetCoverage only - local location where downloaded files
              shall be written too)

        Detailed description of parameters associated with each Request are
        porvided with the respective request
    """
        # default timeout for all sockets (in case a requests hangs)
    _timeout = 180
    socket.setdefaulttimeout(_timeout)
    
        # XML search tags for the request responses
    _xml_ID_tag = ['wcseo:DatasetSeriesId', 'wcs:CoverageId']
   # _xml_date_tag = ['gml:beginPosition',  'gml:endPosition']


    def __init__(self):
        pass


    #/************************************************************************/
    #/*                       _valid_time_wrapper()                           */
    #/************************************************************************/

    def _valid_time_wrapper(self, indate_list):
        """
           Wrapper function to _validate_date(),it handles the looping through
           multiple input date values
           It test if the provided date value(s) are a valid dates and are formated in ISO-8601 format
           The function  _validate_date() performs the actual testing, but this
           is not intended to be called directly
           Input:  a 1 or 2-element list of ISO-8601 formated dates
           Returns:  a 2-element list of ISO-8601 formated dates
           Error:  if either, date is not valid or not in ISO-8601 format
        """
        outdate = []
        for d in indate_list:
            outdate.append(self._validate_date(d))

            # add one day to get correct responses from WCS Servers
        if len(outdate) < 2:
            fyear = int(outdate[0][0:4])
            fmonth = int(outdate[0][5:7])
            fday = int(outdate[0][8:10])
            time_stamp = datetime.datetime(day=fday, month=fmonth, year=fyear)
            difference = time_stamp+datetime.timedelta(days=1)
            to_date ='%.4d-%.2d-%.2d' %  (difference.year, difference.month, difference.day)
            outdate.append(to_date)

        return outdate

    #/************************************************************************/
    #/*                          _validate_date()                            */
    #/************************************************************************/

    def _validate_date(self, indate):
        """
            Performs testing of the supplied date values (checks formats, validity, etc.)
            private function of _valid_time_wrapper(), which only handles the looping.
            _validate_date() is not intended to be called directly, only through the
            _valid_time_wrapper() function.
        """
        if indate.endswith('Z'):
            testdate = indate[:-1]
        else:
            testdate = indate
            if len(indate) == 16 or len(indate) == 19:
                indate = indate+'Z'


        dateformat = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H", "%Y-%m-%dT", "%Y-%m-%d"]

        dformat = dateformat.__iter__()
        cnt = dformat.next()
        while True:
            try:
                time.strptime(testdate, cnt)
                return indate
            except ValueError:
                try:
                    cnt = dformat.next()
                except StopIteration:
                    raise ValueError("Could not parse date - either date not valid or date not in ISO-8601 format : ", testdate)


    #/************************************************************************/
    #/*                           _set_base_request()                        */
    #/************************************************************************/
    def _set_base_request(self):
        """
            Returns the basic url components for any valid WCS request
        """
        base_request = {'service': 'service=wcs',
                'version': '&version=2.0.1'}


        return base_request

    #/************************************************************************/
    #/*                            _set_base_cap()                           */
    #/************************************************************************/
    def _set_base_cap(self):
        """
            Returns the basic url components for a valid GetCapabilities request
        """
        base_cap = {'request': '&request=',
            'server_url': '',
            'updateSequence': '&updateSequence=',
            'sections' :'&sections='}


        return base_cap


    #/************************************************************************/
    #/*                            _set_base_desccov()                       */
    #/************************************************************************/
    def _set_base_desccov(self):
        """
            Returns the basic urls components for a valid DescribeCoverage Request
        """
        base_desccov = {'request': '&request=',
            'server_url': '',
            'coverageID': '&coverageID='}

        return base_desccov


    #/************************************************************************/
    #/*                             _set_set_base_desceocovset()              */
    #/************************************************************************/
    def _set_base_desceocoverageset(self):
        """
            Returns the basic urls components for a valid DescribeEOCoverageSet Request
        """
        base_desceocoverageset = {'request': '&request=',
            'server_url': '',
            'eoID': '&eoID=',
            'subset_lon': '&subset=Long,'+crs_url+'4326(',
            'subset_lat': '&subset=Lat,'+crs_url+'4326(',
            'subset_time': '&subset=phenomenonTime(%22',
            'containment': '&containment=',
            'section': '&section=',
            'count': '&count=',
            'IDs_only': False}


        return base_desceocoverageset


    #/************************************************************************/
    #/*                             _set_base_getcov()                        */
    #/************************************************************************/
    def _set_base_getcov(self):
        """
           Rreturns the basic urls components for a GetCoverage Request
        """
        getcov_dict = {'request': '&request=',
            'server_url': '',
            'coverageID': '&coverageid=',
            'format': '&format=image/',
            'subset_x': '&subset=',
            'subset_y': '&subset=',
            'rangesubset': '&rangesubset=',
            'outputcrs': '&outputcrs='+crs_url,
            'interpolation': '&interpolation=',
            'mediatype': '&mediatype=',
            'mask': '&mask=polygon,'+crs_url,
            'size_x': '&',
            'size_y': '&',
            'output': None}

        return getcov_dict



    #/************************************************************************/
    #/*                           GetCapabilities()                          */
    #/************************************************************************/
    def GetCapabilities(self, request_params, settings):
        """
            Creates a GetCapabilitiy request url based on the input_parameters
            and executes the request.
            The input_parameters have to be supplied as a dictionary.
            Input:
                Mandatory Parameters to be provided:
                    Request:      GetCapabilities
                    server_url:   Server URL to be accessed
                Optional prameters:
                    updateSequence:   Receive a new document only if it has changed since last
                        requested (expressed in ISO-8601 date format e.g. 2007-04-05)
                    sections:         Request one or more section(s) of a Capabilities Document
                        possible sections: [ DatasetSeriesSummary, CoverageSummary, Content,
                        ServiceIdentification, ServiceProvider, OperationsMetadata, Languages, All ]
            Example:
                request_params = {'request': 'GetCapabilities',
                               'server_url': 'http://some.where.org/ows?' ,
                               'updateSequence': '2007-04-05',
                               'sections' : 'CoverageSummary' }
            Returns:  XML GetCapabilities resonse
        """
        
        if request_params.has_key('updateSequence') and request_params['updateSequence'] is not None:
            res_in = self._valid_time_wrapper(list(request_params.get('updateSequence').split(',')))
            request_params['updateSequence'] = ','.join(res_in)

        procedure_dict = self._set_base_cap()
        http_request = self._create_request(request_params, procedure_dict)

        # print http_request   #@@
        result_xml = wcsClient._execute_xml_request(self, http_request)

        return result_xml


    #/************************************************************************/
    #/*                           DescribeCoverage()                         */
    #/************************************************************************/
    def DescribeCoverage(self, request_params, settings):
        """
            Creates a DescribeCoverage request url based on the input_parameters
            and executes the request.
            The input_parameters have to be supplied as a dictionary.
            Input:
                Mandatory Parameters to be provided:
                    Request:      DescribeCoverage
                    server_url:   Server URL to be accessed
                    coverageID:   one valid ID of a [ Coverage | StitchedMosaic ]
                Optional prameters:
                    None
            Example:
                request_params = {'request': 'DescribeEOCoverageSet',
                               'server_url': 'http://some.where.org/ows?' ,
                               'coverageid': 'some_Coverage_ID_yxyxyx_yxyxyx' }
            Returns:   XML DescribeCoverage response
        """
        procedure_dict = self._set_base_desccov()
        http_request = self._create_request(request_params, procedure_dict)
       
        # print http_request   #@@        
        result_xml = wcsClient._execute_xml_request(self, http_request)

        return result_xml


    #/************************************************************************/
    #/*                          DescribeEOCoverageSet()                     */
    #/************************************************************************/
    def DescribeEOCoverageSet(self, request_params, settings):
        """
            Creates a DescribeEOCoverageSet request url based on the input_parameters
            and executes the request.
            The input_parameters have to be supplied as a dictionary.
            Input:
                Mandatory Parameters to be provided:
                    Request:      DescribeEOCoverageSet;
                    server_url:   Server URL to be accessed;
                    eoID:         One valid ID of a: [ DatasetSeries | Coverage | StitchedMosaic ]
                Optional Parameters:
                    subset_lat:   Allows to constrain the request in Lat-dimensions. \
                                  The spatial constraint is always expressed in WGS84
                    subset_lon:   Allows to constrain the request in Long-dimensions. \
                                  The spatial constraint is always expressed in WGS84.
                    subset_time:  Allows to constrain the request in Time-dimensions. The temporal \
                                  constraint is always expressed in ISO-8601 format and in the UTC  \
                                  time zone (e.g. subset_time 2007-04-05T14:30:00Z,2007-04-07T23:59Z).
                    containment:  Allows to limits the spatial search results. \
                                  [ overlaps (just touching)(=default) | contains (fully within) ]
                    count:        Limits the maximum number of DatasetDescriptions returned
                    section:      Request one or more section(s) of a DescribeEOCoverageSet Document;
                                  possible section: [ DatasetSeriesSummary, CoverageSummary, All ]
                Non-standard Parameters implemented:
                    IDs_only:     Will provide only a listing of the available CoverageIDs;
                                  intended to feed results directly to a GetCoverage request loop [ True | False ]
            Example:
                request_params = {'request': 'DescribeEOCoverageSet',
                              'server_url': 'http://some.where.org/ows?' ,
                              'eoID':  'some_ID_of_coverage_or_datasetseries_or_stitchedmosaic' ,
                              'subset_lon': '-2.7,-2.6' ,
                              'subset_lat': '47.6,47.7' ,
                              'subset_time':'2013-06-16,2013-07-01T23:59Z' ,
                              'IDs_only': True }
            Returns:    XML DescribeEOCoverageSet response  or  only a list of available coverageIDs
        """
            # validate that the provided date/time stings are in ISO8601
        res_in = self._valid_time_wrapper(list(request_params.get('subset_time').split(',')))
        request_params['subset_time'] = ','.join(res_in)

        procedure_dict = self._set_base_desceocoverageset()
        http_request = self._create_request(request_params, procedure_dict)
      
        # print http_request   #@@        
        if request_params.has_key('IDs_only') and request_params['IDs_only'] == True:
            result_list = wcsClient._execute_xml_request(self, http_request, IDs_only=True)
        else:
            result_list = wcsClient._execute_xml_request(self, http_request)

        return result_list


    #/************************************************************************/
    #/*                              GetCoverage()                           */
    #/************************************************************************/

    def GetCoverage(self, request_params, settings, input_params):
        """
            Creates a GetCoverage request url based on the input_parameters
            and executes the request.
            The input_parameters have to be supplied as a dictionary.
            Input:
                Mandatory Parameters to be provided:
                    Request:      DescribeEOCoverageSet;
                    server_url:   Server URL to be accessed;
                    coverageID:   A valid coverageID
                    format:       Requested format of coverage to be returned, (e.g. tiff, jpeg, png, gif)
                                  but depends on offering of the server
                Non-standard Parameter implemented (Mandatory):
                    output:      Location where downloaded data shall be stored
                                 (defaulting to: global variable temp_storage, which will get set to
                                 the available environmental variables [ TMP | TEMP | HOME | USER | current_directory ] )
                Optional Parameters:
                    subset_x:    Trimming of coverage in X-dimension (no slicing allowed!),
                                 Syntax: Coord-Type Axis-Label Coord,Coord;
                                 either in: pixel coordinates [use: pix x 400,200 ], coordinates without
                                 CRS (-> original projection) [use:  orig Long 12,14 ], or coordinates
                                 with CRS (-> reprojecting) [use:  epsg:4326 Long 17,17.4 ]
                    subset_y:    Trimming of coverage in y-dimension (no slicing allowed!),
                                 Syntax: Coord-Type Axis-Label Coord,Coord;
                                 either in: pixel coordinates [use: pix x 400,200 ], coordinates without
                                 CRS (-> original projection) [use:  orig Long 12,14 ], or coordinates
                                 with CRS (-> reprojecting) [use:  epsg:4326 Long 17,17.4 ]
                    rangesubset: Subsetting in the range domain (e.g. Band-Subsetting, e.g. 3,2,1)
                    outputcrs:   CRS for the requested output coverage, supplied as EPSG number (default=4326)
                    size_x:      Mutually exclusive, enter either: size & Axis-Label & integer dimension of
                                 the requested coverage or resolution & Axis-Label & the dimension of one pixel
                                 in X-Dimension e.g.[size X 800 | resolution Long 15 ]
                    size_y:      Mutually exclusive, enter either: size & Axis-Label & integer dimension of
                                 the requested coverage or resolution & Axis-Label & the dimension of one pixel
                                 in Y-Dimension e.g.[size Y 320 | resolution Lat 55 ]
                    interpolation: Interpolation method to be used (default=nearest), ['nearest | bilinear | average]
                    mediatype:   Coverage delivered directly as an image file or enclosed inside a GML structure.
                                 parameter either [ not present (=default) | multipart/mixed ]
                Non-standard Parameter implemented (optional):
                    mask:        Masking of coverage by polygon: define the polygon as a list of points
                                 (i.e. latitude and longitude values), e.g. lat1,lon1,lat2,lon2,...; make sure
                                 to close the polygon with the last pair of coordinates; CRS is optional; per default
                                 EPSG 4326 is assumed; use the subset parameter to crop the resulting coverage
                                 Syntax:  epsg:xxxx lat1,lon1,lat2,lon2, lat3,lon3,lat1,lon1
                                 e.g.  epsg:4326 42,10,43,12,39,13,38,9,42,10'
                Example:        
                    request_params = {'request': 'GetCoverage' , 
                                  'server_url': 'http://some.where.org/ows?' , 
                                  'coverageID': 'some_Coverage_ID_yxyxyx_yxyxyx' , 
                                  'formtat': 'tif' ,
                                  'subset_x': 'epsg:4326 Long -2.7,-2.6' , 
                                  'subset_y': 'epsg:4326 Lat 47.6,47.7' , 
                                  'rangesubset': '3,2,1' ,
                                  'outputcrs': '3035' ,
                                  'output': '/home/mydir/somedir' }
                
                Return:      Nothing, but stores downloaded dataset(s) at user defined output location
        """
            # provide the same functionality for input as for the cmd-line
            # (to get around the url-notation for input)
        if request_params['subset_x'].startswith('epsg'):
            crs = request_params['subset_x'].split(':')[1].split(' ')[0]
            label = request_params['subset_x'].split(':')[1].split(' ')[1]
            coord = request_params['subset_x'].split(':')[1].split(' ')[2]
            out = label+','+crs_url+crs+'('+coord
            request_params['subset_x'] = out
        elif request_params['subset_x'].startswith('pix') or request_params['subset_x'].startswith('ori'):
            label = request_params['subset_x'].split(' ')[1]
            coord = request_params['subset_x'].split(' ')[2]
            out = label+'('+coord
            request_params['subset_x'] = out
        else:
            pass

        if request_params['subset_y'].startswith('epsg'):
            crs = request_params['subset_y'].split(':')[1].split(' ')[0]
            label = request_params['subset_y'].split(':')[1].split(' ')[1]
            coord = request_params['subset_y'].split(':')[1].split(' ')[2]
            out = label+','+crs_url+crs+'('+coord
            request_params['subset_y'] = out
        elif request_params['subset_y'].startswith('pix') or request_params['subset_y'].startswith('ori'):
            label = request_params['subset_y'].split(' ')[1]
            coord = request_params['subset_y'].split(' ')[2]
            out = label+'('+coord
            request_params['subset_y'] = out
        else:
            pass


        procedure_dict = self._set_base_getcov()
        http_request = self._create_request(request_params, procedure_dict, input_params['extract'])
      
        result = wcsClient._execute_getcov_request(self, http_request, request_params)

        return result


    #/************************************************************************/
    #/*                             parse_xml()                              */
    #/************************************************************************/
    def _parse_xml(self, in_xml, tag):
        """
            Function to parse the request results of a DescribeEOCoverageSet
            and extract all available CoveragesIDs.
            This function is used when the the  IDs_only  parameter is supplied.
            Return:  List of available coverageIDs
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
    #/*                         _execute_xml_request()                       */
    #/************************************************************************/
    def _execute_xml_request(self, http_request, IDs_only=False):
        """
            Executes the GetCapabilities, DescribeCoverage, DescribeEOCoverageSet
            requests based on the generate http_url
            Returns:  either XML response document  or  a list of coverageIDs
            Output: prints out the submitted http_request  or Error_XML in case of failure
        """
        try:
                # access the url
            request_handle = urllib2.urlopen(http_request)
                # read the content of the url
            result_xml = request_handle.read()

                # extract only the CoverageIDs and provide them as a list for further usage
            if IDs_only == True:
                cids = self._parse_xml(result_xml, self._xml_ID_tag[1])
                request_handle.close()
                # if no datasets are found return the XML
                if len(cids) == 0 or cids is None:
                    cids = result_xml
                
                return cids
            else:
                request_handle.close()
                return result_xml

        except urllib2.URLError, url_ERROR:
            if hasattr(url_ERROR, 'reason'):
                err_msg = '\n', time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  Server not accessible -", url_ERROR.reason
                print_log(settings, err_msg)
                
                try:
                    err_msg = url_ERROR.read(), '\n'
                    print_log(settings, err_msg)
                except:
                    pass

            elif hasattr(url_ERROR, 'code'):
                lmsg = time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  The server couldn\'t fulfill the request - Code returned:  ", url_ERROR.code, url_ERROR.read()
                print_log(settings, lmsg)
                err_msg = str(url_ERROR.code)+'--'+url_ERROR.read()
                return err_msg

        return


    #/************************************************************************/
    #/*                     _execute_getcov_request()                        */
    #/************************************************************************/

    def _execute_getcov_request(self, http_request, request_params):
        """
            Executes the GetCoverage request based on the generated http_url and stores
            the receved/downloaded coverages in the defined  output location.
            The filenames are set to the coverageIDs (with extension according to requested file type)
            plus the the current date and time. This timestamp is added to avoid accidently overwriting of
            received coverages having the same coverageID but a differerent extend (AOI) (i.e.
            multiple subsets of the same coverage).
            
            Output: prints out the submitted http_request
                    stores the received datasets
                    saves Error-XML (-> access_error_"TimeStamp".xml) at output location (in case of failure)
            Returns:  HttpCode (if success)  
        """
        global file_ext
        now = time.strftime('_%Y%m%dT%H%M%S')
       
        if not request_params['coverageID'].endswith( ('tif','tiff','Tif','Tiff','TIFF','jpeg','jpg','png','gif','nc','hdf') ):
            out_ext = file_ext.get( str(request_params['format'].lower()))
            out_coverageID = request_params['coverageID']+'.'+out_ext
        else:
            out_coverageID = request_params['coverageID'] 

        if request_params['coverageID'].endswith( ('tiff','Tiff','TIFF','jpeg') ):
            out_ext = file_ext.get( str(request_params['coverageID'][-4:].lower()))
            out_coverageID = request_params['coverageID'][:-4]+out_ext

            
        if request_params.has_key('output') and request_params['output'] is not None:
            outfile = request_params['output']+out_coverageID
        else:
            outfile = temp_storage+out_coverageID


        try:
            request_handle = urllib2.urlopen(http_request)
            status = request_handle.code

            try:
                file_getcov = open(outfile, 'w+b')
                file_getcov.write(request_handle.read())
                file_getcov.flush()
                os.fsync(file_getcov.fileno())
                file_getcov.close()
                request_handle.close()
                return status

            except IOError as (errno, strerror):
                err_msg = "I/O error({0}): {1}".format(errno, strerror)
                print_log(settings, err_msg)
            except:
                err_msg = "Unexpected error:", sys.exc_info()[0]
                print_log(settings, err_msg)
                raise


        except urllib2.URLError as url_ERROR:
            if hasattr(url_ERROR, 'reason'):
                err_msg = '\n', time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  Server not accessible -", url_ERROR.reason
                print_log(settings, err_msg)
                    # write out the servers return msg
                errfile = outfile.rpartition(dsep)[0]+dsep+'access_error'+now+'.xml'
                access_err = open(errfile, 'w+b')
                access_err.write(url_ERROR.read())
                access_err.flush()
                access_err.close()
            elif hasattr(url_ERROR, 'code'):
                lmsg = time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  The server couldn\'t fulfill the request - Code returned:  ", url_ERROR.code, url_ERROR.read()
                print_log(settings, lmsg)
                err_msg = str(url_ERROR.code)+'--'+url_ERROR.read()
                return err_msg
        except TypeError:
            pass

        return


    #/************************************************************************/
    #/*                              _merge_dicts()                           */
    #/************************************************************************/
    def _merge_dicts(self, request_params, procedure_dict):
        """
            Merge and harmonize the request_params-dict with the required request-dict
            e.g. the base_getcov-dict
        """
        request_dict = {}
        for k, v in request_params.iteritems():
                # skip all keys with None or True values
            if v == None or v == True:
                continue

                # create the request-dictionary but ensure there are no whitespaces left
                # (which got inserted for argparse() to handle negativ input values correctly)
            request_dict[k] = str(procedure_dict[k])+str(v).strip()


            # get the basic request settings
        base_request = self._set_base_request()
        request_dict.update(base_request)

        return request_dict



    #/************************************************************************/
    #/*                               _create_request()                      */
    #/************************************************************************/
    def _create_request(self, request_params, procedure_dict, extract=None):
        """
            Create the http-request according to the user selected Request-type
        """
        request_dict = self._merge_dicts(request_params, procedure_dict)
            # check for SUB or FULL scene extraction
        if extract == 'FULL':
            request_dict.pop('subset_x')
            request_dict.pop('subset_y')

        
            # this doesn't look nice, but this way I can control the order within the generated request
        http_request = ''
        if request_dict.has_key('server_url'):
            http_request = http_request+request_dict.get('server_url')
        if request_dict.has_key('service'):
            http_request = http_request+request_dict.get('service')
        if request_dict.has_key('version'):
            http_request = http_request+request_dict.get('version')
        if request_dict.has_key('request'):
            http_request = http_request+request_dict.get('request')
        if request_dict.has_key('coverageID'):
            http_request = http_request+request_dict.get('coverageID')
        if request_dict.has_key('subset_x'):
            http_request = http_request+request_dict.get('subset_x')+')'
        if request_dict.has_key('subset_y'):
            http_request = http_request+request_dict.get('subset_y')+')'
        if request_dict.has_key('format'):
            http_request = http_request+request_dict.get('format')
        if request_dict.has_key('rangesubset'):
            http_request = http_request+request_dict.get('rangesubset')
        if request_dict.has_key('outputcrs'):
            http_request = http_request+request_dict.get('outputcrs')
        if request_dict.has_key('interpolation'):
            http_request = http_request+request_dict.get('interpolation')
        if request_dict.has_key('mediatype'):
            http_request = http_request+request_dict.get('mediatype')
        if request_dict.has_key('size_x'):
            http_request = http_request+request_dict.get('size_x')+')'
        if request_dict.has_key('size_y'):
            http_request = http_request+request_dict.get('size_y')+')'
        if request_dict.has_key('mask'):
            http_request = http_request+request_dict.get('mask')+')'
        if request_dict.has_key('updateSequence'):
            http_request = http_request+request_dict.get('updateSequence')
        if request_dict.has_key('sections'):
            http_request = http_request+request_dict.get('sections')
        if request_dict.has_key('eoID'):
            http_request = http_request+request_dict.get('eoID')
        if request_dict.has_key('subset_lat'):
            http_request = http_request+request_dict.get('subset_lat')+')'
        if request_dict.has_key('subset_lon'):
            http_request = http_request+request_dict.get('subset_lon')+')'
        if request_dict.has_key('subset_time'):
            http_request = http_request+request_dict.get('subset_time').split(',')[0] \
                +'%22,%22'+request_dict.get('subset_time').split(',')[1]+'%22)'
        if request_dict.has_key('containment'):
            http_request = http_request+request_dict.get('containment')
        if request_dict.has_key('section'):
            http_request = http_request+request_dict.get('section')
        if request_dict.has_key('count'):
            http_request = http_request+request_dict.get('count')


        return http_request


#/************************************************************************/
# /*            END OF:        wcs_Client()                              */
#/************************************************************************/




