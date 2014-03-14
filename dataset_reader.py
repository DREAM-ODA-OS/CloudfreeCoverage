#!/usr/bin/env python
#------------------------------------------------------------------------------
#
#
#       Dataset reader module -- currently containing readers for:
#         - landsat5_f  datasets
#
#
#       for internal testing:
#           '_f' = means located  at hard disk
#           '_w' = means accessible via WCS service
#
#
# Project: DeltaDREAM
# Name:    dataset_reader.py
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

## TODO: --  include/harmonize Error handling and printing of Error and other messages


import sys
import os
import os.path
import time

#import glob
import fnmatch
#from urlparse import urlparse
import datetime
from osgeo import gdal
#from osgeo import gdal_array
from osgeo.gdalconst import *          # this allows leaving off gdal eg. at GA_ReadOnly
#from osgeo.gdalnumeric import *
#import numpy as np
import urllib2,  socket
#from xml.dom import minidom
#from time import strftime,  gmtime
gdal.UseExceptions()

from create_cloudless import now
from create_cloudless import handle_error
from create_cloudless import parse_xml

# for debugging
from create_cloudless import do_interupt


#/************************************************************************/
#/                      some conversion settings/functions               */
#/************************************************************************/
GDT2DT = {
    gdal.GDT_Byte : "uint8",
    gdal.GDT_UInt16 : "uint16",
    gdal.GDT_Int16 : "int16",
    gdal.GDT_UInt32 : "uint32",
    gdal.GDT_Int32 : "int32",
    gdal.GDT_Float32 : "float32",
    gdal.GDT_Float64 : "float64"  }


#/************************************************************************/

DT2GDT = dict( (v, k) for (k, v) in GDT2DT.items() )

#/************************************************************************/

def getGdalDataType(ndtype):
    """
        convert numpy dtype to gdal dtype
    """
    gdtype = DT2GDT.get( str(ndtype).lower() , None )
    if gdtype is None :
        raise ValueError("Unsupported data type '%s'!"%(str(ndtype)))

    return gdtype

#/************************************************************************/

def getNumpyDataType(gdtype):
    """
        convert gdal dtype to numpy dtype
    """
    ndtype = GDT2DT.get( gdtype , None )
    if ndtype is None :
        raise ValueError("Unsupported data type %s!"%(str(gdtype)))

    return ndtype

#/************************************************************************/

def set_base_desccov():
    """
        sets the basic urls components for a DescribeCoverage Request
    """


    base_desccov = ('service=wcs', \
        '&version=2.0.0', \
        '&request=DescribeEOCoverageSet&',  \
        '&subset=x,http://www.opengis.net/def/crs/EPSG/0/4326(' ,  \
            # add the AOI minx,maxy  here
        ')&subset=y,http://www.opengis.net/def/crs/EPSG/0/4326(',  \
            # add the AOI miny,maxy  here
        ')&subset=phenomenonTime(%22',  \
            # add the TOI - beginTime as Date  here
        '%22,%22',  \
            # add the TOI - endTime as Date  here
        '%22)'  )


    return base_desccov

#/************************************************************************/

def set_base_getcov():
    """
        sets the basic urls components for a GetCoverage Request
    """

    base_getcov = ('service=wcs', \
        '&version=2.0.0', \
        '&request=GetCoverage', \
        '&coverageid=',  \
            # add the desired CoverageID here
        '&format=image/tiff',  \
            # we will always use tiff as a tmp-donwload format here, the final output-format is set elsewhere
        '&subset=x,http://www.opengis.net/def/crs/EPSG/0/4326(',  \
            # add the AOI - minx,maxx  here
        ')&subset=y,http://www.opengis.net/def/crs/EPSG/0/4326(',  \
            # add the AOI - miny,maxy  here
        ')' , \
        '&rangesubset=', \
            # add gray or RGB etc.  here
        '&output_crs=' )
            # add some epsg code eg. epsg:4326  here



    return base_getcov

#/************************************************************************/
#/*                            findfile()                                */
#/************************************************************************/


def findfile(indir, inmask):
    """
        literal_directory, basename_pattern (simple shell-style wildcards), includes dot-files
        no regex, but constructs like e.g. L5_[!a-f]*.tif , are possible
    """
    filelist = []
    for root, dd, files in os.walk(indir):
        for ff in files:
            if fnmatch.fnmatchcase(ff, inmask):
                filelist.append( os.path.join(root, ff) )

    return filelist


#/************************************************************************/
#/*                               get_taget_list()                       */
#/************************************************************************/
def get_daterange(from_date, composite_range):
    """
        calculate the new date for the time interval depending on the composite_range
    """

    from_date = str(from_date)
    composite_range = int(composite_range)        # consider the starting day

    from_year = int(from_date[0:4])
    from_month = int(from_date[4:6])
    from_day = int(from_date[6:8])
    time_stamp = datetime.datetime(day=from_day, month=from_month, year=from_year )
    difference = time_stamp + datetime.timedelta(days=int(composite_range))
    to_date ='%.4d%.2d%.2d' %  (difference.year, difference.month, difference.day)

    return to_date




#/************************************************************************/
#/*                             Reader()                                 */
#/************************************************************************/



class Reader(object):
    """
        Reader class
         - gathering information about filenames, dates, etc.
         - provide the listing of Base-files, Base-masks, GFP-files and GFP-masks to be used
    """
        # default timeout for all sockets (in case a requests hangs)
    timeout = 180
    socket.setdefaulttimeout(timeout)

        # XML search tags for the request responses
    xml_ID_tag = ['wcseo:DatasetSeriesId', 'wcs:CoverageId' ]
    xml_date_tag = ['gml:beginPosition',  'gml:endPosition']

#---------
#    def fopen(self, filename):
#        return gdal.OpenShared(filename, GA_ReadOnly)
### TODO: check - is this needed? 
# 
#---------
#    def fopen_mask(self, filename):
#        """ This is an interface method to open the mask file as a gdal
#            dataset for the given data filename.
#        """
### TODO: check - is this needed? 
#
#---------
    def __init__(self):
        pass

#---------
    def get_filelist(self, input_params, settings):
        """
            uses WCS requests to generate filelist of files available  at service/server
        """
        cov_list = self.base_desccover(input_params, settings, mask=False)
        mask_list = self.base_desccover(input_params, settings, mask=True)

            # split up the received listing - Base, Base_mask, GFPs, GFPMask  (--> cryoland products do not have masks)
        cnt = 0
        base_flist = []
        gfp_flist = []

        for elem in cov_list:
            idx = elem.find(input_params['toi'])
            if idx > -1:
                #print idx,elem
                b_cov = cov_list.pop(cnt)
                base_flist.append(b_cov)
            cnt += 1
        gfp_flist = list(cov_list)

        base_mask_flist = []
        gfpmask_flist = []
        cnt = 0
        for elem in mask_list:
            idx = elem.find(input_params['toi'])
            if idx > -1:
                #print idx,elem
                b_mask = mask_list.pop(cnt)
                base_mask_flist.append(b_mask)
            cnt += 1

        gfpmask_flist = list(mask_list)

        gfp_flist, gfpmask_flist = self.apply_scenario(gfp_flist, gfpmask_flist, input_params['scenario'], base_flist, base_mask_flist )

# for debugging
#        from create_cloudless import do_print_flist
#        do_print_flist('BASE', base_flist)
#        do_print_flist('Base_Mask', base_mask_flist)
#        do_print_flist('GFP', gfp_flist)
#        do_print_flist('GFPMask', gfpmask_flist)
#        print input_params['toi']
#        sys.exit(1)

        if len(base_flist) != len(base_mask_flist):
            err_msg = 'Number of datafiles and number of cloud-masks do not correspond'
            print err_msg
            sys.exit(4)
        if len(gfp_flist) != len(gfpmask_flist):
            err_msg = 'Number of datafiles and number of cloud-masks do not correspond'
            print err_msg
            sys.exit(4)


        return  base_flist, base_mask_flist, gfp_flist, gfpmask_flist

#---------

    def get_maskname(self, filename):
        """
            set the mask filename filter and get the mask filename(-list)
            return mask-filename or list of mask-filenames (if list is provided)
        *) eg. CryoLand doesn't have mask files
        """
        pass

#---------
    def set_request_values(self, settings, input_params, mask):
        """
            set the request parameters
        """
        if mask is True:
            searchkey = input_params['dataset'][:-3]+'_mask_clouds'
            if settings.has_key('dataset.'+searchkey) is True:
                service = settings['dataset.'+searchkey]
            else:
                searchkey = input_params['dataset']+'_clouds'
                if settings.has_key('dataset.'+searchkey) is True:
                    service = settings['dataset.'+searchkey]
                else:
                    searchkey = input_params['dataset'][:-6]+'_nua'
                    if settings.has_key('dataset.'+searchkey) is True:
                        service = settings['dataset.'+searchkey]
        else:
            service = settings['dataset.'+input_params['dataset']]

        #print 'Service: ', service

        aoi_values = input_params['aoi']
        toi_values = []
        if input_params['scenario'] == 'T':
            target_date = get_daterange(input_params['toi'], -input_params['period'])
            toi_values.append(target_date)
            toi_values.append(input_params['toi'])

        if input_params['scenario'] == 'B':
            target_date = get_daterange(input_params['toi'], input_params['period'])
            toi_values.append(input_params['toi'])
            toi_values.append(target_date)

        if input_params['scenario'] == 'M':
            tt = int((input_params['period']/2))
            tt1 = int((input_params['period']/2.)+0.5)       # correct for the rounding error
            target_date = get_daterange(input_params['toi'], -tt)
            toi_values.append(target_date)
            target_date = get_daterange(input_params['toi'], tt1)
            toi_values.append(target_date)


        service1 = service.rsplit('EOID')[0]
        dss = 'eoid'+service.rsplit('EOID')[1]

        return service1, toi_values, aoi_values, dss

#---------
    def base_desccover(self, input_params, settings, mask):
        """
            Send a DescribeEOCoverageSet request to the WCS Service, asking for the available Coverages, according
            to the user defined AOI, TOI, and DatasetSeries. The function returns the available CoveragesIDs.
        """
        base_desccov = set_base_desccov()

        service1, toi_values, aoi_values, dss = self.set_request_values(settings, input_params, mask)

## older version
            # create the basic url
#        request_url_desccov = service1+base_desccov[0]+dss+base_desccov[1]+aoi_values[0]+','+ \
#            aoi_values[1]+base_desccov[2]+aoi_values[2]+','+aoi_values[3]+base_desccov[3]+toi_values[0]+'T00:00'+ \
#            base_desccov[4]+toi_values[1]+'T23:59'+base_desccov[5]
        request_url_desccov = service1+base_desccov[0]+base_desccov[1]+base_desccov[2]+dss+base_desccov[3]+aoi_values[0]+','+ \
            aoi_values[1]+base_desccov[4]+aoi_values[2]+','+aoi_values[3]+base_desccov[5]+toi_values[0]+'T00:00'+ \
            base_desccov[6]+toi_values[1]+'T23:59'+base_desccov[7]
        print request_url_desccov
        try:
                # access and the url
            res_desccov = urllib2.urlopen(request_url_desccov)
                # read the content of the url
            descov_xml = res_desccov.read()
            cids = parse_xml(descov_xml,  self.xml_ID_tag[1])
            res_desccov.close()
            return cids             # return value to calling get_filelist()

        except urllib2.URLError, url_ERROR:
            if hasattr(url_ERROR, 'reason'):
                print  time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  Server not accessible -", url_ERROR.reason
            elif hasattr(url_ERROR, 'code'):
                print time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  The server couldn\'t fulfill the request - Code returned:  ", url_ERROR.code,  url_ERROR.read()

#---------
    def apply_scenario(self, gfp_flist, gfpmask_flist, scenario, base_flist, base_mask_flist):
        """
            apply the selected scenario i.e. sort the gfp lists accordingly
        """
        if scenario == 'T':
            gfp_flist.reverse()
            gfpmask_flist.reverse()
            return gfp_flist, gfpmask_flist

        elif scenario == 'B':
            gfp_flist.sort()
            gfpmask_flist.sort()
            return gfp_flist, gfpmask_flist

        elif scenario == 'M':
            gfp_tmp = list(gfp_flist)
            gfp_masktmp = list(gfpmask_flist)
            gfp_tmp.extend(base_flist)
            gfp_masktmp.extend(base_mask_flist)
            gfp_tmp.sort()
            gfp_masktmp.sort()

# for debugging
#            from create_cloudless import do_print_flist
#            do_print_flist('INPUT-M: ',gfp_tmp )
#            do_print_flist('INPUT-M: ',gfp_masktmp )

            toi_pos1 = gfp_tmp.index(base_flist[0])
            toi_pos2 = gfp_masktmp.index(base_mask_flist[0])
            newer_flist1 = gfp_tmp[toi_pos1+1:]
            older_flist1 = gfp_tmp[:toi_pos1]
            older_flist1.reverse()
            newer_flist2 = gfp_masktmp[toi_pos2+1:]
            older_flist2 = gfp_masktmp[:toi_pos2]
            older_flist2.reverse()

                # we always use the newer files first
            gfp = map(None, newer_flist1, older_flist1)
            gfpm = map(None, newer_flist2, older_flist2)

            out_gfp = []
            for k, v in gfp:
                if k is not None:
                    out_gfp.append(k)
                if v is not None:
                    out_gfp.append(v)

            out_gfpm = []
            for k, v in gfpm:
                if k is not None:
                    out_gfpm.append(k)
                if v is not None:
                    out_gfpm.append(v)

            return out_gfp, out_gfpm

        else:
            print '[Error] -- Choosen Scenario is not supported. Please use either T, B or M -- '
            sys.exit(3)

#---------
    def base_getcover(self, file_list, input_params, settings, temp_storage, mask):
        """
            Function to actually requesting and saving the available coverages on the local file system.
        """
        wcs_ext = '.tif'
        base_getcov = set_base_getcov()

       # try:
                # get the time of downloading - to be used in the filename (to differentiate if multiple AOIs of
                # the same coverages are downloaded to the same output directory)
            #dwnld_time = time.strftime("%Y%m%d%H%M%S",time.gmtime())
        service1, toi_values, aoi_values, dss = self.set_request_values(settings, input_params, mask=False)

            # create output-crs syntax to be added to GetCoverage request
        if input_params['output_crs'] != None:
#            output_crs = "&outputcrs="+input_params['output_crs']
            output_crs = base_getcov[9]+input_params['output_crs']
        else:
            output_crs = ''

            # handle band-subsetting
        if input_params['bands'] != '999':
            bands = ''
            for bb in input_params['bands']:
                bands = bands+bb+','
                rangesubset = base_getcov[8]+bands[:-1]
        else:
            rangesubset = ''

            # don't use bandsubsetting for requests regarding mask-files
        if mask is True:
            rangesubset = ''

### TODO -- handle input_params['output_format']
# to do so the  base_getcov[*]  (and probably also the base_desccov[*] should be better separated (for easier access))
#            if input_params['output_format'] is not 'tif':
#                base_getcov[1] = 'image/'+input_params['output_format']

        try:
                # perform it for all CoverageIDs
            for COVERAGEID in file_list:
                    # construct the url for the WCS access
            # old request @@
#                request_url_getcov = service1+base_getcov[0]+COVERAGEID+ \
#                    base_getcov[1]+aoi_values[0]+','+aoi_values[1]+base_getcov[2]+aoi_values[2]+','+aoi_values[3]+ \
#                    base_getcov[3]+output_crs+rangesubset
                request_url_getcov = service1+base_getcov[0]+base_getcov[1]+base_getcov[2]+base_getcov[3]+COVERAGEID+ \
                    base_getcov[4]+base_getcov[5]+aoi_values[0]+','+aoi_values[1]+base_getcov[6]+aoi_values[2]+','+aoi_values[3]+ \
                    base_getcov[7]+output_crs+rangesubset

                print request_url_getcov
                    # open and access the url

                try:
                    res_getcov = urllib2.urlopen(request_url_getcov)

## comment out the next line if you don't want to have the requests written to the logfile
                    #print request_url_getcov, ' - ',  res_getcov.code

                        # save the received coverages in the corresponding file at the temp-directory
                      #outfile = COVERAGEID+'_'+dwnld_time+COVERAGEID[-4:]
# this here could also be a seperate function
                    if COVERAGEID.endswith(('.tif')):
                        outfile = COVERAGEID
                    elif COVERAGEID.endswith(('.TIF','.Tif')):
                        outfile = COVERAGEID[:-4]+wcs_ext
                    elif COVERAGEID.endswith(('.tiff','.Tiff','.TIFF')):
                        outfile = COVERAGEID[:-5]+wcs_ext
                    else:
                        outfile = COVERAGEID+wcs_ext
                        
                    #file_getcov = open(input_params['output_dir']+outfile, 'w+b')
                    #file_getcov = open(settings['def_temp_dir']+outfile, 'w+b')
# @@ debugging
                    print temp_storage
                    print outfile
                    file_getcov = open(temp_storage+outfile, 'w+b')
                    file_getcov.write(res_getcov.read())
                    file_getcov.flush()
                    os.fsync(file_getcov.fileno())
                    file_getcov.close()
                    res_getcov.close()

                except IOError as (errno, strerror):
                    print "I/O error({0}): {1}".format(errno, strerror)
                except:
                    print "Unexpected error:", sys.exc_info()[0]
                    raise


        except urllib2.URLError, url_ERROR:
            if hasattr(url_ERROR, 'reason'):
                print  time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  Server not accessible -", url_ERROR.reason
            elif hasattr(url_ERROR, 'code'):
                print time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  The server couldn\'t fulfill the request - Code returned:  ", url_ERROR.code,  url_ERROR.read()
        except TypeError:
            pass

#---------
    def base_getcover_single(self, COVERAGEID, input_params, settings, temp_storage, mask):
        """
            Function to actually requesting and saving the available coverages on the local file system.
        """
        wcs_ext = '.tif'
        base_getcov = set_base_getcov()
        service1, toi_values, aoi_values, dss = self.set_request_values(settings, input_params, mask=False)

            # create output-crs syntax to be added to GetCoverage request
        if input_params['output_crs'] != None:
#            output_crs = "&outputcrs="+input_params['output_crs']
            output_crs = base_getcov[9]+input_params['output_crs']
        else:
            output_crs = ''

            # handle band-subsetting
        if input_params['bands'] != '999':
            bands = ''
            for bb in input_params['bands']:
                bands = bands+bb+','
                rangesubset = base_getcov[8]+bands[:-1]
        else:
            rangesubset = ''

            # don't use bandsubsetting for requests regarding mask-files
        if mask is True:
            rangesubset = ''

        try:
                # donwload a single coverage (product or mask)
            request_url_getcov = service1+base_getcov[0]+base_getcov[1]+base_getcov[2]+base_getcov[3]+COVERAGEID+ \
                base_getcov[4]+base_getcov[5]+aoi_values[0]+','+aoi_values[1]+base_getcov[6]+aoi_values[2]+','+aoi_values[3]+ \
                base_getcov[7]+output_crs+rangesubset

            print request_url_getcov
                # open and access the url

            try:
                res_getcov = urllib2.urlopen(request_url_getcov)

                if COVERAGEID.endswith(('.tif')):
                    outfile = COVERAGEID
                elif COVERAGEID.endswith(('.TIF','.Tif')):
                    outfile = COVERAGEID[:-4]+wcs_ext
                elif COVERAGEID.endswith(('.tiff','.Tiff','.TIFF')):
                    outfile = COVERAGEID[:-5]+wcs_ext
                else:
                    outfile = COVERAGEID+wcs_ext

                #print temp_storage
                #print outfile
                file_getcov = open(temp_storage+outfile, 'w+b')
                file_getcov.write(res_getcov.read())
                file_getcov.flush()
                os.fsync(file_getcov.fileno())
                file_getcov.close()
                res_getcov.close()

            except IOError as (errno, strerror):
                print "I/O error({0}): {1}".format(errno, strerror)
            except:
                print "Unexpected error:", sys.exc_info()[0]
                raise

        except urllib2.URLError, url_ERROR:
            if hasattr(url_ERROR, 'reason'):
                print  time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  Server not accessible -", url_ERROR.reason
            elif hasattr(url_ERROR, 'code'):
                print time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  The server couldn\'t fulfill the request - Code returned:  ", url_ERROR.code,  url_ERROR.read()
        except TypeError:
            pass


#---------
## TODO  @@  - should we move this outside the Reader() as a general function, -> set_base_getcov and set_base_desccov
    def get_available_dss(self, input_params, settings, printit):
        request_dss_sum = '&service=wcs&version=2.0.0&request=GetCapabilities&sections=DatasetSeriesSummary'
        service = settings['dataset.'+input_params['dataset']]
        service1 = service.rsplit('EOID')[0]
        request_url_dss_sum = service1+request_dss_sum

            # for logging purpose
        print request_url_dss_sum

        try:
                # access and the url & read the content
            res_dss_sum = urllib2.urlopen(request_url_dss_sum)
            getcap_xml = res_dss_sum.read()

                # parse the received xml and extract the DatasetSeriesIds
            dss_ids = parse_xml(getcap_xml, self.xml_ID_tag[0])
            dss_date1 = parse_xml(getcap_xml, self.xml_date_tag[0])
            dss_date2 = parse_xml(getcap_xml, self.xml_date_tag[1])

#### for logging and/or for debugging
            if printit is True:
                    # print the available DatasetSeriesIds to the screen
                print "The following DatasetSeries [Name: From-To] are available:"
                for i in range(len(dss_ids)):
                    print " - ", dss_ids[i] , ": \t", dss_date1[i], " - ", dss_date2[i]

                # close the acces to the url
            res_dss_sum.close()
            dss_result = [dss_ids, dss_date1, dss_date2]

            return  dss_result

        except urllib2.URLError, url_ERROR:
            if hasattr(url_ERROR, 'reason'):
                print  time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  Server not accessible -", url_ERROR.reason
            elif hasattr(url_ERROR, 'code'):
                print time.strftime("%Y-%m-%dT%H:%M:%S%Z"), "- ERROR:  The server couldn\'t fulfill the request - Code returned:  ", url_ERROR.code,  url_ERROR.read()
        
        



#/************************************************************************/
#/*                      CF_landsat5_2A_Reader                          */
#/************************************************************************/

class CF_landsat5_2a_Reader(Reader):

    """
        reader module for the cryoland dataset
        - mainly for testing and development
        - and for demonstration of WCS usage
    """
    def __init__(self):
        Reader.__init__(self)

#            # get the available dss - maybe make a check if user provided dss really exists
#        avail_dss = self.get_available_dss(input_params, settings)
#        if input_params['dataset'] not in avail_dss[0]:
#            for ds in in avail_dss:
#                print ds
#            err_msg = 'DSS not available: ', input_params['dataset']
#            handle_error(err_msg, 4)

##---------
#
#    def get_maskname(self, filename):
#        """
#            set the mask filename filter and get the mask filename(-list)
#            return mask-filename or list of mask-filenames (if list is provided)
#        *) CryoLand doesn't have seperate mask files
#        """
#        pass

#---------






#/************************************************************************/
#/*                         CF_spot4take5_Reader()                       */
#/************************************************************************/
class CF_spot4take5_n2a_pente_Reader(Reader):
    """
        reader module for the spot4take5_n2a_pentec dataset
        - mainly for testing and development
        - and for demonstration of WCS usage
    """
    def __init__(self):
        Reader.__init__(self)

#            # get the available dss - maybe make a check if user provided dss really exists
#        avail_dss = self.get_available_dss(input_params, settings)
#        if input_params['dataset'] not in avail_dss[0]:
#            for ds in in avail_dss:
#                print ds
#            err_msg = 'DSS not available: ', input_params['dataset']
#            handle_error(err_msg, 4)

##---------
#
#    def get_maskname(self, filename):
#        """
#            set the mask filename filter and get the mask filename(-list)
#            return mask-filename or list of mask-filenames (if list is provided)
#        """
#        pass
#

#---------




#/************************************************************************/
#/*                      CF_cryoland_Reader                          */
#/************************************************************************/

class CF_cryoland_Reader(Reader):
    """
        reader module for the cryoland dataset
        - mainly for testing and development
        - and for demonstration of WCS usage
    """
    def __init__(self):
        Reader.__init__(self)

#            # get the available dss - maybe make a check if user provided dss really exists
#        avail_dss = self.get_available_dss(input_params, settings)
##        print type(test), len(test)
##        print 'TEST: ', test

## ther is some better method to do this - just can't remember now
#        for for ds in avail_dss[0]:
#            if input_params['dataset'] not in ds.lower():
##                print 'DSS not available: ', input_params['dataset']
##                print 'Available Datasets are: ', ds
#                err_msg = 'DSS not available: ', input_params['dataset']
#                handle_error(err_msg, 4)

##---------
#
#    def get_maskname(self, filename):
#        """
#            set the mask filename filter and get the mask filename(-list)
#            return mask-filename or list of mask-filenames (if list is provided)
#        *) eg. CryoLand doesn't have mask files
#        """
#        pass

#---------

    def get_filelist(self, input_params, settings):
        """
            uses WCS requests to generate filelist of files available  at service/server
        """
        cov_list = self.base_desccover(input_params, settings, mask=False)

        base_flist = []
        base_mask_flist = []
        gfp_flist = []
        gfpmask_flist = []

            # split up the received listing - Base, Base_mask, GFPs, GFPMask  (--> cryoland products do not have masks)
        cnt = 0
        for elem in cov_list:
            try:
                idx = elem.find(input_params['toi'])
                if idx > -1:
                    b_cov = cov_list.pop(cnt)
                    base_flist.append(b_cov)
                else:
                    b_cov = ''
                cnt += 1

            except ValueError:
                print str(ValueError)
            #except str.ValueError:
                #pass

            #print 'cov_list: ',len(cov_list), type(cov_list)
        #base_flist.append(b_cov)
        gfp_flist = list(cov_list)


        return  base_flist, base_mask_flist, gfp_flist, gfpmask_flist




#/************************************************************************/
#/*                   CF_landsat_obj_test_Reader()                       */
#/************************************************************************/
## TODO -- to be deleted
#class CF_landsat_obj_test_Reader(Reader):
#    """
#        Landsat reader - testing .... --> to be deleted
#    """
#    def __init__(self):
#        Reader.__init__(self)
#
#    def get_maskname(self, filename):
#        base, extension = os.path.splitext(filename)
#        mask_filename = "%s.nuages%s" % (base, extension)
#        return mask_filename
#        #return gdal.Open(mask_filename)



#/************************************************************************/
#/*                      CF_landsat5_f_Reader                            */
#/************************************************************************/

class CF_landsat5_f_Reader(Reader):
    """
        reader module for the landsat5_f dataset
            '_f' = means located  at hard disk
            '_w' = means accessible via WCS service
    """
    def __init__(self):
        Reader.__init__(self)

#----
    def get_maskname(self, filename):
        """
            set the mask filename filter and get the mask filename(-list)
            return mask-filename or list of mask-filenames (if list is provided)
        """
            # check if list or single name has been provided
        if type(filename) == list:
            mask_filename = []
            for elem in filename:
                # for landsat5 -  mask would be
                base, extension = os.path.splitext(elem)
                m_filename = "%s.nuages%s" % (base, extension)
                mask_filename.append(m_filename)

        elif type(filename) == str:
            base, extension = os.path.splitext(filename)
            mask_filename = "%s.nuages%s" % (base, extension)

        return mask_filename

#----
    def get_filelist(self, input_params, settings):
        """
            gets the listing of filenames of available: Base files, GFP files and Mask files
        """
        target_date = input_params['toi']
        access_path1 = settings['dataset.'+input_params['dataset']]
        pos1 = str.index(access_path1, '://')
        access_path = access_path1[pos1+3:]


## TODO:  this should be more general - eg. using:  get_daterange() ??
        start_year = int(input_params['toi'][0:4])
        start_month = int(input_params['toi'][4:6])

        if input_params['scenario'] == 'T':
            if start_month == 1:
                loop = [ start_year - 1, '11', start_year -1 , '12', start_year, start_month ]
            elif start_month == 2:
                loop = [ start_year - 1, '12', start_year, start_month -1 , start_year, start_month ]
            else:
                loop = [start_year, start_month - 2, start_year, start_month -1 , start_year, start_month ]

        elif input_params['scenario'] == 'B':
            if start_month == 12:
                loop = [start_year, start_month, start_year + 1, '01', start_year + 1, '02' ]
            elif start_month == 11:
                loop = [start_year, start_month, start_year, start_month + 1 , start_year +1 , '01' ]
            else:
                loop = [start_year, start_month, start_year, start_month + 1, start_year, start_month + 2 ]

        elif input_params['scenario'] == 'M':
            if start_month == 12:
                loop = [start_year, start_month - 1, start_year, start_month, start_year +1 , '01' ]
            elif start_month == 1:
                loop = [start_year -1, '12', start_year, start_month, start_year, start_month + 1  ]
            else:
                loop = [start_year, start_month - 1, start_year, start_month, start_year, start_month + 1 ]


        if len(str(loop[1])) == 1:
            loop[1] = '0'+str(loop[1])
        if len(str(loop[3])) == 1:
            loop[3] = '0'+str(loop[3])
        if len(str(loop[5])) == 1:
            loop[5] = '0'+str(loop[5])

        base_flist = []
        base_mask_flist = []
        gfp_flist = []
        gfpmask_flist = []
        base_fname_syntax = 'L*_' + target_date + '*_L5_*_surf_pente_30m.tif'
        gfp_fname_syntax = 'L*_*_L5_*_surf_pente_30m.tif'


        for jj in range(0, len(loop)-1, 2):
            target = str(loop[jj])+'/'+str(loop[jj+1])+'/'
            base_flist = base_flist+sorted(findfile(access_path+target, base_fname_syntax))
            gfp_flist = gfp_flist+sorted(findfile(access_path+target, gfp_fname_syntax))

            # now remove any base_filenames from the gfp_flist, to avoid duplicates
        gfp_flist = [item for item in gfp_flist if not item in base_flist]
            # create the file-list for the mask-files
        gfpmask_flist = self.get_maskname(gfp_flist)
        base_mask_flist =  self.get_maskname(base_flist)

            # return all created file-lists
        return base_flist, base_mask_flist, gfp_flist, gfpmask_flist


#/************************************************************************/
#/*                      CF_spot4take5_f_Reader                          */
#/************************************************************************/

class CF_spot4take5_f_Reader(Reader):
    """
        reader module for the spot4take5_f dataset
            '_f' = means located  at hard disk
            '_w' = means accessible via WCS service
    """
    def __init__(self):
        Reader.__init__(self)

## TODO -- need to add the time limitation for the resulting listings

    def get_maskname(self, filename):
        """
            set the mask filename filter and get the mask filename(-list)
            return m ask-filename or list of mask-filenames (if list is provided)
        """
            # check if list or single name has been provided
        if type(filename) == list:
            mask_filename = []
            for elem in filename:
                dirname = os.path.dirname(elem)
                basename = os.path.basename(elem)
                basename1 =  basename.replace('_AOT_','_')
                m_filename = dirname+'/MASK/'+basename1[0:-4]+'_NUA.TIF'
                mask_filename.append(m_filename)

        elif type(filename) == str:
            dirname = os.path.dirname(elem)
            basename = os.path.basename(elem)
            basename1 =  basename.replace('_AOT_','_')
            mask_filename = dirname+'/MASK/'+basename1[0:-4]+'_NUA.TIF'

        return mask_filename

#----
    def get_filelist(self, input_params, settings):
        """
            gets the listing of filenames of available: Base files, GFP files and Mask files
        """
        target_date = input_params['toi']
        access_path1 = settings['dataset.'+input_params['dataset']]
        pos1 = str.index(access_path1, '://')
        access_path = access_path1[pos1+3:]

        base_flist = []
        base_mask_flist = []
        gfp_flist = []
        gfpmask_flist = []
        base_fname_syntax = 'SPOT4_*' + target_date + '_N2A_AOT_*.TIF'
        gfp_fname_syntax = 'SPOT4_*_N2A_AOT_*.TIF'

        base_flist = base_flist+sorted(findfile(access_path, base_fname_syntax))
        base_mask_flist = self.get_maskname(base_flist)
        gfp_flist = gfp_flist+sorted(findfile(access_path, gfp_fname_syntax))
        gfp_flist = [item for item in gfp_flist if not item in base_flist]
        gfpmask_flist = self.get_maskname(gfp_flist)


        return base_flist, base_mask_flist, gfp_flist, gfpmask_flist



#/************************************************************************/
#/*                      CF_spot4take5_f_Reader                          */
#/************************************************************************/

class CF_cryoland_local_Reader(Reader):
    """
        reader module for the cryoland dataset
        - mainly for testing and development
        - and for demonstration of WCS usage
    """
    def __init__(self):
        Reader.__init__(self)

#
#    def get_maskname(self, filename):
#        """
#            set the mask filename filter and get the mask filename(-list)
#            return mask-filename or list of mask-filenames (if list is provided)
#        """
#        pass
#

    def get_filelist(self, input_params, settings):
        """
            uses WCS requests to generate filelist of files available  at service/server
        """
        avail_dss = self.get_available_dss(input_params, settings, False)
#        print type(test), len(test)
#        print 'TEST: ', test
        base_flist = []
        base_flist = list(avail_dss)
        base_mask_flist = list(base_flist)
        gfp_flist = []
        gfpmask_flist = list(gfp_flist)

        return  base_flist, base_mask_flist, gfp_flist, gfpmask_flist



#/************************************************************************/
#/*                      CF_landsat5_m_Reader                          */
#/************************************************************************/

class CF_landsat5_m_Reader(Reader):
    """
    This represents actually a "_f"  but it contians files in an unstructured
    way (-> mix) set-up for easier testing purpose only
        reader module for the landsat5_f dataset
            '_f' = means located  at hard disk
            '_w' = means accessible via WCS service
            '_m' = means use of the "local-mixed" dataset
    """
    def __init__(self):
        Reader.__init__(self)

#    def get_maskname(self, filename):
#        """
#            set the mask filename filter and get the mask filename(-list)
#            return m ask-filename or list of mask-filenames (if list is provided)
#        """
#            # check if list or single name has been provided
#        #if type(filename) == list:
#        pass


    def get_filelist(self, input_params, settings):
        """
            gets the listing of filenames of available: Base files, GFP files and Mask files
        """
        target_date = input_params['toi']
        access_path1 = settings['dataset.'+input_params['dataset']]
        pos1    = str.index(access_path1, '://')
        acces_path = access_path1[pos1+3:]

        base_fname_syntax = 'L*_' + target_date + '_L5_*_surf_pente_30m.tif'
        gfp_fname_syntax = 'L*_*_L5_*_surf_pente_30m.tif'
        base_flist = sorted(findfile(acces_path, base_fname_syntax))
        gfp_flist = sorted(findfile(acces_path, gfp_fname_syntax))[0:input_params['period']]

            # tzhese parameters are mssing here - I guess they should also be crated, in order to be returned
        #base_mask_flist =
        #gfpmask_flist =

        #return base_flist, base_mask_flist, gfp_flist, gfpmask_flist
        return base_flist, gfp_flist







#/************************************************************************/
#/*                            main()                                    */
#/************************************************************************/

if __name__ == '__main__':
    #dataset_reader()
    Reader()
