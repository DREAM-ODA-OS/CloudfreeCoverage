#!/usr/bin/env python
#
#------------------------------------------------------------------------------
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#
#
#       process provided datasets and cloudmasks to generate cloud-freee
#       images by replacing cloud-covered pixels with cloudfree pixels of
#       previous or follow-up datasets of the same type
# 
#       - by supplying additonal Processor classes, the specific need of new 
#         Datasets can be easily handled
#
#
# Project: DeltaDREAM
# Name:    dataset_processor.py
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


import os
import sys
import time
from osgeo import gdal
from osgeo import gdal_array
from osgeo.gdalconst import *     # this allows leaving of gdal eg. at GA_ReadOnly
from osgeo.gdalnumeric import *
import numpy as np

from util import handle_error, print_log

gdal.UseExceptions()

global dsep
dsep = os.sep





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


#/************************************************************************/
#/*                         calc_overviews()                             */
#/************************************************************************/
def calc_overviews(inbase_band, baseshape):
    """
        calculates the required overviews for the GTiFF output file(s)
    """
        # for the overview pyramids
    def_tilesize = [256, 256]

        # calculate required overviews from the newly created product size
    xsize = baseshape[1]
    ysize = baseshape[0]
    maxsize = None
    tilesize = None

         # uses max-extension as a starting point
    if xsize > ysize:
        maxsize = xsize
        tilesize = def_tilesize[0]
    else:
        maxsize = ysize
        tilesize = def_tilesize[1]

    overview_sizes = []
    factor = 1
    while (maxsize / 2) >= tilesize:
        maxsize = maxsize / 2
        factor = factor * 2
        overview_sizes.append(factor)

    overview_sizes.append(factor * 2)

    return overview_sizes



#/************************************************************************/
#/*                            CFProcessor()                                */
#/************************************************************************/
class CFProcessor(object):
    """
        General CloudFree processor class
    """
    def __init__(self):
        pass

#---------
    def fopen(self, filename):
        """
            opens a file and provide handle
        """
        return gdal.OpenShared(filename, GA_ReadOnly)

#---------
    def read_img(self, baseImg, infile):
        """
            read an image
        """
        inDim = []
        inDim.append([baseImg.RasterXSize])
        inDim.append([baseImg.RasterYSize])
        inDim.append([baseImg.RasterCount])
        inDim.append([baseImg.GetDriver().ShortName])

        inProj = baseImg.GetProjection()
        inLocation = baseImg.GetGeoTransform()

        return inDim, inProj, inLocation

#---------
    def read_mask(self, baseImg, infile, isBaseImg):
        """
            Read in the mask and analyse wich pixels and coordinates are masked
        """
        inDim = []
        inDim.append([baseImg.RasterXSize])
        inDim.append([baseImg.RasterYSize])
        inDim.append([baseImg.RasterCount])
        inDim.append([baseImg.GetDriver().ShortName])

        inProj = baseImg.GetProjection()

        inLocation = baseImg.GetGeoTransform()

        inImg = gdal_array.LoadFile(infile)
        inImg.dtype
        inImg.shape

            # which pixels are marked as clouds & how many
        inClouds = np.array(np.where(inImg > 0))

        if inClouds[1].__len__() > 0 and isBaseImg == True:
            baseCoord = self.get_coordinates(inClouds, inDim, inLocation)

            return inDim, inProj, inLocation, inImg, inClouds, baseCoord
        else:
            return inDim, inProj, inLocation, inImg, inClouds


#---------
    def get_coordinates(self, inClouds, inDim, inLocation):
        """
            get the coordinates of the clouded pixels
        """
            # caclulate image coordinates for all clouded pixel
        baseCoord = []

        xpos = np.uint64(inLocation[0] + (inClouds[1, :] * inLocation[1]))
        ypos = np.uint64(inLocation[3] + (inClouds[0, :] * inLocation[5]))

        baseCoord = np.array([xpos,ypos])

        return baseCoord


#---------
    def process_clouds(self, base_flist, base_mask_flist, gfp_flist, gfpmask_flist, input_params, settings, temp_storage, f_read):
        """
            make sure all donwloaded CoverageIDs come in with ".tiff" extension
        """
        wcs_ext = '.tif'

            # add the file-format extension to the list of CoverageIDs
            # the filenames are already changed in:  dataset_reader.base_getcover 
        base_flist_e = [item+wcs_ext for item in base_flist if not item.lower().endswith(wcs_ext) ] or \
                       [item for item in base_flist if item.lower().endswith(wcs_ext) ]
        base_mask_flist_e = [item+wcs_ext for item in base_mask_flist if not item.lower().endswith(wcs_ext) ] or \
                            [item for item in base_mask_flist if item.lower().endswith(wcs_ext) ]
        gfp_flist_e = [item+wcs_ext for item in gfp_flist if not item.lower().endswith(wcs_ext) ] or \
                      [item for item in gfp_flist if item.lower().endswith(wcs_ext) ]
        gfpmask_flist_e = [item+wcs_ext for item in gfpmask_flist if not item.lower().endswith(wcs_ext) ] or \
                          [item for item in gfpmask_flist if item.lower().endswith(wcs_ext) ]


            # test if the files are really available at temp_storage
        for ifile, mfile in zip(base_flist_e, base_mask_flist_e):
            if os.path.exists(temp_storage+ifile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+ifile
                print_log(settings, err_msg)
                sys.exit(5)
            if os.path.exists(temp_storage+mfile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+mfile
                print_log(settings, err_msg)
                sys.exit(5)

        for gfile, gmfile in zip(gfp_flist_e, gfpmask_flist_e):
            if os.path.exists(temp_storage+gfile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+gfile
                print_log(settings, err_msg)
                sys.exit(5)
            if os.path.exists(temp_storage+gmfile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+gmfile
                print_log(settings, err_msg)
                sys.exit(5)

        cf_result = self.change_img(base_flist_e, base_mask_flist_e, gfp_flist_e, gfpmask_flist_e, input_params, temp_storage)

        return cf_result


#--------
    def process_clouds_1(self, base_flist, base_mask_flist, gfp_flist, gfpmask_flist, input_params, settings, temp_storage, f_read):
        """
            proxy function - make sure the donwloaded CoverageIDs come in with ".tif" extension
        """
        wcs_ext = ('.tif')

            # add the file-format extension to the list of CoverageIDs
            # the filenames are already changed in:  dataset_reader.base_getcover 
        base_flist_e = [item+wcs_ext for item in base_flist if not item.lower().endswith(wcs_ext) ] or \
                       [item for item in base_flist if item.lower().endswith(wcs_ext) ]
        base_mask_flist_e = [item+wcs_ext for item in base_mask_flist if not item.lower().endswith(wcs_ext) ] or \
                            [item for item in base_mask_flist if item.lower().endswith(wcs_ext) ]
        gfp_flist_e = [item+wcs_ext for item in gfp_flist if not item.lower().endswith(wcs_ext) ] or \
                      [item for item in gfp_flist if item.lower().endswith(wcs_ext) ]
        gfpmask_flist_e = [item+wcs_ext for item in gfpmask_flist if not item.lower().endswith(wcs_ext) ] or \
                          [item for item in gfpmask_flist if item.lower().endswith(wcs_ext) ]


        cf_result = self.change_img(base_flist_e, base_mask_flist_e,  gfp_flist, gfpmask_flist, gfp_flist_e, gfpmask_flist_e, input_params, temp_storage, f_read, settings)
        
        return cf_result


#---------
    def access_ds(self, basefile, basemaskfile, temp_storage):
        """
            provide file access handle to RasterImg and MaskImg
        """
            # the actual image datasets
        infile_basef = os.path.join(temp_storage, basefile)
        baseImg = self.fopen(infile_basef)
            # the corresponding mask files
        infile_basemaskf = os.path.join(temp_storage, basemaskfile)
        basemaskImg = self.fopen(infile_basemaskf)

        if baseImg is None:
            err_msg = '[Error] -- Could not open: ', temp_storage+infile_basef
            print_log(settings, err_msg)
            sys.exit(6)
        if basemaskImg is None:
            err_msg = '[Error] -- Could not open: ', temp_storage+infile_basemaskf
            print_log(settings, err_msg)
            sys.exit(6)

        return baseImg, infile_basef, basemaskImg, infile_basemaskf


#---------
    def change_img(self, base_flist_e, base_mask_flist_e,  gfp_flist, gfpmask_flist, gfp_flist_e, gfpmask_flist_e, input_params, temp_storage, f_read, settings):
        """
            replace clouded pixels with non-clouded pixels
            write out cloud-free product, metadata-maskfile and metadata-textfile (of used products)
            option uses full file reading (which is faster, but has higher memory usage)
        """
        out_prefix = 'CF_'
        img_cnt = 1

        out_meta_mask = '_composite_mask.tif'
        startTime2 = time.time()

        for basefile, basemaskfile in zip(base_flist_e, base_mask_flist_e):
            baseImg, infile_basef, basemaskImg, infile_basemaskf = self.access_ds(basefile, basemaskfile, temp_storage)
            baseImgDim, baseProj, baseLocation = self.read_img(baseImg, infile_basef)
            basemaskDim, basemaskProj, basemaskLocation, basemaskImg, basemaskClouds, basemaskCoord = self.read_mask(basemaskImg, infile_basemaskf, isBaseImg=True)

            baseImgDim.append([baseImg.GetDriver().ShortName])
            baseImgBand = baseImg.GetRasterBand(1)
            baseImgDt = getNumpyDataType(baseImgBand.DataType)
            gDType = getGdalDataType(baseImgDt)

            driver = baseImg.GetDriver()

                # create the cloud-free output dataset
            outFile = infile_basef.rsplit(dsep, 1)
            outFile[1] = out_prefix + outFile[1]
            if outFile[1].endswith('.tiff'):
               outFile[1] = outFile[1].replace('.tiff','.tif')

            outFile[0] = temp_storage[:-1]



# @@ testing intermediary -> comment out the following line  --> see also below
            #outImg = driver.Create((outFile[0]+dsep+outFile[1]), baseImgDim[0][0], baseImgDim[1][0], baseImgDim[2][0], gDType)
            outImg = driver.Create((outFile[0]+dsep+outFile[1]), baseImgDim[0][0], baseImgDim[1][0], baseImgDim[2][0], gDType, [ 'TILED=YES', 'COMPRESS=DEFLATE' ] )
            
                # metadata mask & txt-file for storing the info about used (combined) datasets
            cur_ext = os.path.splitext(outFile[1])[1]
            metamaskTIF = outFile[1].replace(cur_ext, out_meta_mask)
            metamaskTXT = metamaskTIF.replace('.tif','.txt')

                # the metamask - will always be a 8-Bit GeoTiff
            metamaskImg = np.zeros((baseImgDim[1][0], baseImgDim[0][0]), uint8)
            eval_mask = np.array(basemaskImg)
            out_data = np.zeros((baseImgDim[2][0], baseImgDim[1][0], baseImgDim[0][0]), dtype=baseImgDt)

            for i in range(1, baseImgDim[2][0]+1,1):
                baseBand = baseImg.GetRasterBand(i)
                baseBand1 = baseBand.ReadAsArray(0, 0, baseImgDim[0][0], baseImgDim[1][0])
                out_data[i-1, :, :] = baseBand1

            
            #for gfpfile, gfpmaskfile in zip(gfp_flist_e, gfpmask_flist_e):
            for gfpfile, gfpmaskfile, gfpfile_e, gfpmaskfile_e in zip(gfp_flist, gfpmask_flist, gfp_flist_e, gfpmask_flist_e):
                startTime3 = time.time()

                lmsg = 'Using GFP-'+str(img_cnt)+': ', gfpfile   #, type(gfpfile)
                print_log(settings, lmsg)

                f_read.base_getcover([gfpfile], input_params, settings, temp_storage, mask=False)                
                f_read.base_getcover([gfpmaskfile], input_params, settings, temp_storage, mask=True)                
                
                lmsg = 'Using GFPMask-'+str(img_cnt)+': ', gfpmaskfile   #, type(gfpmaskfile)
                print_log(settings, lmsg)
                gfpImg, infile_gfpf, gfpmaskImg, infile_gfpmaskf = self.access_ds(gfpfile_e, gfpmaskfile_e, temp_storage)
                gfpImgDim, gfpProj, gfpLocation = self.read_img(gfpImg, infile_gfpf)
                gfpmaskDim, gfpmaskProj, gfpmaskLocation, gfpmaskImg, gfpmaskClouds = self.read_mask(gfpmaskImg, infile_gfpmaskf, isBaseImg=False)

                res2 = np.ma.MaskedArray((eval_mask > 0) & (gfpmaskImg == 0))
                lmsg = 'N_cloudpixel replaced: ', res2.sum()
                print_log(settings, lmsg)

                metamaskImg[res2] = img_cnt
                eval_mask[res2] = 0

                   #  write the maskfile, modify existing if available
                if os.path.exists(outFile[0]+dsep+metamaskTIF):
                    out_metamask_tif = gdal.OpenShared(outFile[0]+dsep+metamaskTIF, GA_Update)
                else:
                    out_metamask_tif = driver.Create((outFile[0]+dsep+metamaskTIF), baseImgDim[0][0], baseImgDim[1][0], 1, GDT_Byte)

                maskBand = out_metamask_tif.GetRasterBand(1)
                maskBand.WriteArray(metamaskImg, 0, 0)
                maskBand.FlushCache()
                out_metamask_tif.SetGeoTransform(baseImg.GetGeoTransform())
                out_metamask_tif.SetProjection(baseImg.GetProjection())

# @@ for testing intermediary -- uncomment the following line  --> see also above and below
                    # to test you may write out intermediary products
                #outImg = driver.Create((outFile[0]+dsep+outFile[1])+'_'+str(img_cnt), baseImgDim[0][0], baseImgDim[1][0], baseImgDim[2][0], gDType)

                    # create a txt file containing the image-filenames and byte-codes used in the metamask
                if os.path.exists(outFile[0]+dsep+metamaskTXT):
                    out_metamask_txt = open(outFile[0]+dsep+metamaskTXT, "a")
                else:
                    out_metamask_txt = open(outFile[0]+dsep+metamaskTXT, "w")

                applied_mask = infile_gfpmaskf.rsplit(dsep, 1)
                out_metamask_txt.write(str(img_cnt)+';'+applied_mask[1]+'\n')
                out_metamask_txt.flush()

                    # read all bands, check each for cloud-free areas, and write to cloud-free image
                for i in range(1, baseImgDim[2][0]+1, 1):
                    gfpBand = gfpImg.GetRasterBand(i)
                    gfpBand1 = gfpBand.ReadAsArray(0, 0, gfpImgDim[0][0], gfpImgDim[1][0])
                    out_data[i-1][res2] = gfpBand1[res2]


                lmsg = 'Remaining masked pixels: ', np.count_nonzero(eval_mask)
                print_log(settings, lmsg)

                    # bail out if no more clouded picels are available
                if eval_mask.sum() == 0:
                    lmsg = 'All pixels masked as clouds have been replaced'
                    print_log(settings, lmsg)
                    break

                img_cnt += 1
                
                lmsg = 'GFP Product processing time: ', time.time() - startTime3
                print_log(settings, lmsg)
                

            lmsg = 'Writing CloudFree product...'
            print_log(settings, lmsg)
                    #write out all Bands into outFile
            for i in range(1, baseImgDim[2][0]+1, 1):
                outBand = outImg.GetRasterBand(i)
                outBand.WriteArray(out_data[i-1], 0, 0)
                outBand.FlushCache()

                # set the Porjection info - copied from baseImg
            outImg.SetGeoTransform(baseImg.GetGeoTransform())
            outImg.SetProjection(baseImg.GetProjection())
                # calculate the overviews needed
            overview_sizes = calc_overviews(outBand, [baseImgDim[0][0], baseImgDim[1][0]])
                # initate pyramid creation
            outImg.BuildOverviews(resampling="NEAREST", overviewlist=overview_sizes)

# @@ for testing intermediary - uncomment the following line -- see also above
                #outImg = None

        lmsg = 'CloudFree processing - RUNTIME in sec: ',  time.time() - startTime2
        print_log(settings, lmsg)

        cf_result = [outFile[1], metamaskTIF, metamaskTXT]

        out_metamask_tif = None
        out_metamask_txt.close()
        outImg = None
        basemaskImg = None
        infile_basemaskf = None
        infile_gfpmaskf = None

        return cf_result



#/************************************************************************/
#/*                   CF_cryoland_Processor()                             */
#/************************************************************************/
class CF_cryoland_Processor(CFProcessor):
    """
        CloudFree processor for the cryoland snowmaps
        The CryoLand Snowmaps are 8-Bit Thematic maps with Clouds encoded in the 
        image. No separate Cloud-mask is available.
    """
    def __init__(self):
        CFProcessor.__init__(self)

    def process_clouds_1(self, base_flist, base_mask_flist, gfp_flist, gfpmask_flist, input_params, settings, temp_storage, f_read):
        """
            perform the required cloud removal processing steps
        """
        out_meta_mask = '_composite_mask.txt'

    # some values used for cryoland cloud masking
        cloud_val = 30
        zero_val = 0
    # all values above are not in use in CryoLand
        nodata_val = 253

            # provide additional tiff-settings for the tif-creation
        # tiff_options = [ "TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256" ]
        tiff_options = []
        
        outFile = os.path.join(temp_storage+'CF_'+base_flist[0])
        metamaskTXT = outFile.replace('.tif', out_meta_mask)
       
        if os.path.exists(metamaskTXT):
            out_metamask_txt = open(metamaskTXT, "a")
        else:
            out_metamask_txt = open(metamaskTXT, "w")
            
        
        inbase_img = self.fopen(temp_storage+base_flist[0])
        if inbase_img is None:
            err_msg = 'Could not open file: ', temp_storage+base_flist[0]
            handle_error(err_msg, 4)

        inbase_NumBands = inbase_img.RasterCount
        inbase_band = inbase_img.GetRasterBand(inbase_NumBands)
        nDtype = getNumpyDataType(inbase_band.DataType)
        gDtype = getGdalDataType(nDtype)

## TODO -- make this more egeneral ie. read DriverType from file
        indriver = gdal.GetDriverByName('GTiFF')

            # load file directly into numpy array - faster, but needs more memory
        base_img = gdal_array.LoadFile(temp_storage+base_flist[0])

        outImg = np.zeros((base_img.shape[0], base_img.shape[1]), dtype=nDtype)
        outImg = np.array(base_img)

        num_clouds = size(np.array(np.where(outImg == cloud_val)))
        lmsg = 'Pixels masked as clouds: ', num_clouds
        print_log(settings, lmsg)
        
        out_clouds = 0
        cnt = 1
        
        for gfp_file in gfp_flist:
            lmsg ='Using GFP-'+str(cnt)+': ', gfp_file 
            print_log(settings, lmsg)

            gfp_file1 = [gfp_file]

            f_read.base_getcover(gfp_file1, input_params, settings, temp_storage, mask=False)
            gfile =  gdal_array.LoadFile(temp_storage+gfp_file)
                # evaluate the cloud masking
            res2 = np.ma.MaskedArray( ((outImg == cloud_val) | (outImg == zero_val) | (outImg >= nodata_val)) & ((gfile != zero_val ) & (gfile != cloud_val) & (gfile < nodata_val)) )
            outImg[res2] = gfile[res2]
            out_clouds = size(np.array(np.where(outImg == cloud_val)))

                 # write out the files used for CF-product generation           
            out_metamask_txt.write(str(cnt)+';'+str(gfp_file)+'\n')
            out_metamask_txt.flush()
            
            cnt += 1
            lmsg = 'N_cloudpixel replace: ', num_clouds - out_clouds
            print_log(settings, lmsg)
            lmsg = 'Remaining masked pixels: ', out_clouds
            print_log(settings, lmsg)
            
            num_clouds = out_clouds
            
                # if there are no more clouded pixels - stop processing
            if (out_clouds == 0):
                lmsg = 'All pixels masked as clouds have been replaced'
                print_log(settings, lmsg)
                break

           # now create the cloudfree output products file
        output = indriver.Create(outFile, base_img.shape[1], base_img.shape[0], inbase_NumBands, gDtype, options=tiff_options)
            # set the GeoCorrdinates parameters etc.
        output.SetGeoTransform(inbase_img.GetGeoTransform())
            # set the Prohjection parameters etc.
        output.SetProjection(inbase_img.GetProjection())
        outBand = output.GetRasterBand(1)
            # set the NoData value in the GTiff
        if inbase_band.GetNoDataValue() is None:
            outBand.SetNoDataValue(255)
        else:
            outBand.SetNoDataValue(inbase_band.GetNoDataValue())

            # add the corrsponding colortable (taken from the input file)
        outBand.SetRasterColorTable(inbase_band.GetRasterColorTable())
        outBand.WriteArray(outImg, 0, 0)
        output.FlushCache()
            # calculate the overviewlist first
        overview_sizes = calc_overviews(inbase_band, base_img.shape)
            # create the overviews
        output.BuildOverviews(resampling = "NEAREST", overviewlist = overview_sizes)
        #print 'Overviewlist: ', overview_sizes

                    # free the open files
        output = None
        inbase_img = None
        base_img = None
        gfp_file = None
        outImg = None
        out_metamask_txt.close()

        
        return [os.path.basename(outFile),os.path.basename(metamaskTXT)]


#/************************************************************************/
#/*                      CF_landsat5_2A_processor()                      */
#/************************************************************************/
class CF_landsat5_2a_Processor(CFProcessor):
    """
        CloudFree processor for the MUSCAT Landsat 5 (Level 2A) dataset
    """
    def __init__(self):
        CFProcessor.__init__(self)


#/************************************************************************/
#/*                      CF_spot4take5_Processor()                       */
#/************************************************************************/
class CF_spot4take5_n2a_pente_Processor(CFProcessor):
    """
        CloudFree processor for the MUSCAT Landsat 5 (Level 2A) dataset
    """
    def __init__(self):
        CFProcessor.__init__(self)


#/************************************************************************/
#/*                     CF_landsat5_m_Processor()                        */
#/************************************************************************/
class CF_landsat5_m_Processor(CFProcessor):
    """
        CloudFree processor for the MUSCAT Landsat 5 (Level 2A) dataset
        as a locally stored dataset --> MIXED DATASET IN 1 DIR
    """
    def __init__(self):
        CFProcessor.__init__(self)

#/************************************************************************/
#/*                        CF_landsat5_f_Processor()                     */
#/************************************************************************/
class CF_landsat5_f_Processor(CFProcessor):
    """
        CloudFree processor for the MUSCAT Landsat 5 (Level 2A) dataset
        as a locally stored dataset --> WITHIN A DIR-STRUCTURE
    """
    def __init__(self):
        CFProcessor.__init__(self)

#/************************************************************************/
#/*                          CF_spot4take5_f()                           */
#/************************************************************************/
class CF_spot4take5_f_Processor(CFProcessor):
    """
        CloudFree processor for the MUSCAT Landsat 5 (Level 2A) dataset
        as a locally stored dataset
    """
    def __init__(self):
        CFProcessor.__init__(self)

#/************************************************************************/
#/*                            ()                                */
#/************************************************************************/





