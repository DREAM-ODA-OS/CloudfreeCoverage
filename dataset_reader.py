#!/usr/bin/env python
#
#------------------------------------------------------------------------------
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#
#
#       Dataset reader module of the create_cloudless.py 
#      --- currently containing Readers for:
#        -- Reader Class (General)
#          - CF_landsat5_2a_Reader
#          - CF_spot4take5_n2a_pente_Reader
#          - CF_cryoland_Reader
#
#          - CF_landsat5_f_Reader
#          - CF_spot4take5_f_Reader
#          - CF_landsat5_m_Reader
#          - CF_cryoland_local_Reader
#
#
#       for internal testing:
#            '_f' = means located  at hard disk
#            '_w' = means accessible via WCS service
#            '_m' = means use of the "local-mixed" dataset
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

import sys
import os
import os.path
import time
import fnmatch
import datetime

from util import parse_xml, print_log

import wcs_client
wcs = wcs_client.wcsClient()



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
    to_date ='%.4d-%.2d-%.2d' %  (difference.year, difference.month, difference.day)

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
    def __init__(self):
        pass

#---------
    def get_filelist(self, input_params, settings):
        """
            uses WCS requests to generate filelist of files available  at service/server
        """
        cov_list = self.base_desceocover(input_params, settings, mask=False)
            # check if there is realy a list of datasets returned or an error msg
        if type(cov_list) is str:   # and cov_list.find('numberMatched="0"') is not -1:
            err_msg = '[Error] -- No Datasets found. Service returned the follwing information.'
            print_log(settings, err_msg)
            print_log(settings, cov_list)
            sys.exit()

        
        mask_list = self.base_desceocover(input_params, settings, mask=True)
        if type(mask_list) is str:  # and cov_list.find('numberMatched="0"') is not -1:
            err_msg = '[Error] -- No Datasets found. Service returned the follwing information.'
            print_log(settings, err_msg)
            print_log(settings, cov_list)
            sys.exit()

        
 
            # split up the received listing - Base, Base_mask, GFPs, GFPMask 
            # (--> cryoland products do not have masks)
        cnt = 0
        base_flist = []
        gfp_flist = []

        for elem in cov_list:
            idx = elem.find(input_params['toi'])
            if idx > -1:
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
                b_mask = mask_list.pop(cnt)
                base_mask_flist.append(b_mask)
            cnt += 1

        gfpmask_flist = list(mask_list)

        gfp_flist, gfpmask_flist = self.apply_scenario(gfp_flist, gfpmask_flist, input_params['scenario'], base_flist, base_mask_flist )


        if len(base_flist) != len(base_mask_flist):
            err_msg = 'Number of datafiles and number of cloud-masks do not correspond'
            print_log(settings, err_msg)
            sys.exit(4)
        if len(gfp_flist) != len(gfpmask_flist):
            err_msg = 'Number of datafiles and number of cloud-masks do not correspond'
            print_log(settings, err_msg)
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


        aoi_values = input_params['aoi']
        toi_values = []
        if input_params['scenario'] == 'T':
            target_date = get_daterange(input_params['toi'], -input_params['period'])
            in_date = get_daterange(input_params['toi'], 0)
            toi_values.append(target_date)
            toi_values.append(in_date)

        if input_params['scenario'] == 'B':
            target_date = get_daterange(input_params['toi'], input_params['period'])
            in_date = get_daterange(input_params['toi'], 0)
            toi_values.append(in_date)
            toi_values.append(target_date)

        if input_params['scenario'] == 'M':
            tt = int((input_params['period']/2))
            tt1 = int((input_params['period']/2.)+0.5)       # correct for the rounding error
            target_date = get_daterange(input_params['toi'], -tt)
            toi_values.append(target_date)
            target_date = get_daterange(input_params['toi'], tt1)
            toi_values.append(target_date)


        service1 = service.rsplit('EOID')[0]
        dss = service.rsplit('EOID')[1][1:]
        
        return service1, toi_values, aoi_values, dss

#---------
    def base_desceocover(self, input_params, settings, mask):
        """
            Send a DescribeEOCoverageSet request to the WCS Service, asking for the available Coverages, according
            to the user defined AOI, TOI, and DatasetSeries. The function returns the available CoveragesIDs.
        """
        target_server, toi_values, aoi_values, dss = self.set_request_values(settings, input_params, mask)

        request = {'request': 'DescribeEOCoverageSet' , 
                   'server_url': target_server , 
                   'eoID': dss ,
                   'subset_lon': aoi_values[0]+','+aoi_values[1] ,
                   'subset_lat': aoi_values[2]+','+aoi_values[3] ,
                   'subset_time': toi_values[0]+'T00:00'+','+ toi_values[1]+'T23:59' ,
                   'IDs_only': True }
                   
           
        cids = wcs.DescribeEOCoverageSet(request, settings)
        
        return cids   

       
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
            print_log(settings, '[Error] -- Choosen Scenario is not supported. Please use either T, B or M -- ')
            sys.exit(3)

#---------
    def base_getcover(self, file_list, input_params, settings, temp_storage, mask):
        """
            Function to actually requesting and saving the available coverages on the local file system.
        """
                # get the time of downloading - to be used in the filename (to differentiate if multiple AOIs of
                # the same coverages are downloaded to the same output directory)
        target_server, toi_values, aoi_values, dss = self.set_request_values(settings, input_params, mask=False)

        request = {'request': 'GetCoverage' , 
                   'server_url': target_server , 
                       # this is set in the file_list loop
               #    'coverageID': COVERAGEID , 
                   'format': 'tiff' ,
                   'subset_x': 'epsg:4326 Long '+ aoi_values[0]+','+aoi_values[1] , 
                   'subset_y': 'epsg:4326 Lat '+aoi_values[2]+','+aoi_values[3],
                  # 'output':  input_params['output_dir'] }
                       # we need to use the tmporary directory here!
                   'output':  temp_storage }

            # create output-crs syntax to be added to GetCoverage request
        if input_params['output_crs'] != None:
            request['outputcrs'] = input_params['output_crs'].split(':')[1]

            # handle band-subsetting
        if input_params['bands'] != '999':
            bands = ''
            for bb in input_params['bands']:
                bands = bands+bb+','
  
            request['rangesubset'] = bands[:-1]

            # don't use bandsubsetting for requests regarding mask-files
        if mask is True:
            request['rangesubset'] = None


        for COVERAGEID in file_list:
            request['coverageID'] = COVERAGEID
            res_getcov = wcs.GetCoverage(request, settings, input_params)

            if res_getcov is not 200:
                print_log(settings, res_getcov)


#/************************************************************************/
#/*                      CF_landsat5_2a_Reader                          */
#/************************************************************************/

class CF_landsat5_2a_Reader(Reader):

    """
        reader module for the cryoland dataset
         - mainly for testing and development
         - and for demonstration of WCS usage
    """
    def __init__(self):
        Reader.__init__(self)



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

#---------

    def get_filelist(self, input_params, settings):
        """
            uses WCS requests to generate filelist of files available  at service/server
        """
        cov_list = self.base_desceocover(input_params, settings, mask=False)

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
                print_log(settings, str(ValueError))


        gfp_flist = list(cov_list)

        return  base_flist, base_mask_flist, gfp_flist, gfpmask_flist


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

#----
    def base_getcover(self, file_list, input_params, settings, temp_storage, mask):
        """
            Processing takes place on the original data (skipping copying, but 
            maybe risking data cuorruption ?), no data transformation (subsetting, CRS, 
            band subsetting) is currently implemented
        """
        pass

#----
    




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
               #basename1 =  basename.replace('_ORTHO_','_')
               # basename1 =  basename1.replace('_PENTE_','_')
                m_filename1 = basename[0:25]+'*_NUA.TIF'
                m_filename = sorted(findfile(dirname+'/MASK/', m_filename1))
                mask_filename.append(str(m_filename[0]))

        elif type(filename) == str:
            dirname = os.path.dirname(elem)
            basename = os.path.basename(elem)
            #basename1 =  basename.replace('_ORTHO_','_')
            #basename1 =  basename1.replace('_PENTE_','_')
            m_filename1 = basename[0:25]+'*_NUA.TIF'
            m_filename = sorted(findfile(dirname+'/MASK/', m_filename1))
            mask_filename = str(m_filename[0])

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

        base_fname_syntax = 'SPOT4_*' + target_date + '*_PENTE_*.TIF'
        gfp_fname_syntax = 'SPOT4_*_PENTE_*.TIF'

        base_flist = base_flist+sorted(findfile(access_path, base_fname_syntax))
        base_mask_flist = self.get_maskname(base_flist)
        gfp_flist = gfp_flist+sorted(findfile(access_path, gfp_fname_syntax))
        gfp_flist = [item for item in gfp_flist if not item in base_flist]
        gfpmask_flist = self.get_maskname(gfp_flist)


        return base_flist, base_mask_flist, gfp_flist, gfpmask_flist

#----
    def base_getcover(self, file_list, input_params, settings, temp_storage, mask):
        """
            Processing takes place on the original data (skipping copying, but 
            maybe risking data cuorruption ?), no data transformation (subsetting, CRS, 
            band subsetting) is currently implemented
        """
        pass

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

#----
    def get_filelist(self, input_params, settings):
        """
            uses WCS requests to generate filelist of files available  at service/server
        """
        avail_dss = self.get_available_dss(input_params, settings, False)

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
        pos1    = str.index(access_path1, '://')
        acces_path = access_path1[pos1+3:]

        base_fname_syntax = 'L*_' + target_date + '_L5_*_surf_pente_30m.tif'
        gfp_fname_syntax = 'L*_*_L5_*_surf_pente_30m.tif'
        base_flist = sorted(findfile(acces_path, base_fname_syntax))
        gfp_flist = sorted(findfile(acces_path, gfp_fname_syntax))[0:input_params['period']]

            # now remove any base_filenames from the gfp_flist, to avoid duplicates
        gfp_flist = [item for item in gfp_flist if not item in base_flist]
            # create the file-list for the mask-files
        gfpmask_flist = self.get_maskname(gfp_flist)
        base_mask_flist = self.get_maskname(base_flist)
        
        return base_flist, base_mask_flist, gfp_flist, gfpmask_flist

#----
    def base_getcover(self, file_list, input_params, settings, temp_storage, mask):
        """
            Processing takes place on the original data (skipping copying, but 
            maybe risking data cuorruption ?), no data transformation (subsetting, CRS, 
            band subsetting) is currently implemented
        """
        pass


#/************************************************************************/
#/*                            main()                                    */
#/************************************************************************/

if __name__ == '__main__':
    Reader()
