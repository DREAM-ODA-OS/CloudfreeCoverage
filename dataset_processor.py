#!/usr/bin/env python
#------------------------------------------------------------------------------
#
#
#       process provided datasets and cloudmasks to generate cloud-freee
#		images by replacing cloud-covered pixels with cloudfree pixels of
#		previous or follow-up datasets of the same type
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
#
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------


import os
import sys
import time
from osgeo import gdal
from osgeo import gdal_array
from osgeo.gdalconst import *     # this allows leaving of gdal eg. at GA_ReadOnly
from osgeo.gdalnumeric import *
import numpy as np

gdal.UseExceptions()

global dsep
dsep = os.sep

from create_cloudless import now
from create_cloudless import handle_error
from dataset_reader import getGdalDataType
from dataset_reader import getNumpyDataType
#from dataset_reader import GDT2DT, DT2GDT

# for debugging
from create_cloudless import do_interupt



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
    def __init__(self):
        pass

    def fopen(self, filename):
        return gdal.OpenShared(filename, GA_ReadOnly)


#    def process_clouds(base_flist, base_mask_flist, gfp_flist, gfpmask_flist, input_params, settings, temp_storage):
#        pass

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
#        print 'read_img - inDim: ', inDim

        inProj = baseImg.GetProjection()
#        print 'read_img - inProj: ', inProj

        inLocation = baseImg.GetGeoTransform()
#        print 'read_img - inLocation: ', inLocation

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
#        print 'read_mask - inDim: ', inDim

        inProj = baseImg.GetProjection()
#        print 'read_mask - inProj: ', inProj

        inLocation = baseImg.GetGeoTransform()
#        print 'read_mask - inLocation: ', inLocation

        inImg = gdal_array.LoadFile(infile)
        inImg.dtype
        inImg.shape

            # which pixels are marked as clouds & how many
        inClouds = np.array(np.where(inImg > 0))

        if inClouds[1].__len__() > 0 and isBaseImg == True:
#            print 'inClouds :',inClouds[0:10][0:10]
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
#        print 'type(inClouds): ',type(inClouds)
#        print 'inClouds.shape: ', inClouds.shape
#        print "inLocation: ",inLocation

        xpos = np.uint64(inLocation[0] + (inClouds[1, :] * inLocation[1]))
        ypos = np.uint64(inLocation[3] + (inClouds[0, :] * inLocation[5]))

#        print 'xpos: ', type(xpos), xpos.shape
#        print 'ypos: ', type(ypos), ypos.shape

        baseCoord = np.array([xpos,ypos])
        #type(baseCoord)
#        print 'BaseCoord: ',baseCoord[0:5][0:5]

        return baseCoord


#---------
    def process_clouds(self, base_flist, base_mask_flist, gfp_flist, gfpmask_flist, input_params, settings, temp_storage):
        """
            make sure all donwloaded CoverageIDs come in with ".tif" extension
        """
## TODO  --- but shall this be done really here ?? probably better to change it in:  change_img
# import dataset_reader
# create a while loop here to go through gfp_flist and gfpmask_flist while!!!  needed (unitl )
# call base_getcover

        wcs_ext = '.tif'

            # add the file-format extension to the list of CoverageIDs
            # the filenames are already changed in:  dataset_reader.base_getcover 
        base_flist_e = [item+wcs_ext for item in base_flist]
        base_mask_flist_e = [item+wcs_ext for item in base_mask_flist]
        gfp_flist_e = [item+wcs_ext for item in gfp_flist]
        gfpmask_flist_e = [item+wcs_ext for item in gfpmask_flist]

            # test if the files are really available at temp_storage
        for ifile, mfile in zip(base_flist_e, base_mask_flist_e):
            if os.path.exists(temp_storage+ifile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+ifile
                print  err_msg
                sys.exit(5)
            if os.path.exists(temp_storage+mfile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+mfile
                print  err_msg
                sys.exit(5)

        for gfile, gmfile in zip(gfp_flist_e, gfpmask_flist_e):
            if os.path.exists(temp_storage+gfile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+gfile
                print  err_msg
                sys.exit(5)
            if os.path.exists(temp_storage+gmfile) is False:
                err_msg = '[Error] -- File does not exist: ', temp_storage+gmfile
                print  err_msg
                sys.exit(5)

        cf_result = self.change_img(base_flist_e, base_mask_flist_e, gfp_flist_e, gfpmask_flist_e, input_params, temp_storage)


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
            print '[Error] -- Could not open: ', temp_storage+infile_basef
            sys.exit(6)
        if basemaskImg is None:
            print '[Error] -- Could not open: ', temp_storage+infile_basemaskf
            sys.exit(6)

        return baseImg, infile_basef, basemaskImg, infile_basemaskf


#---------
    #def change_img(self, basemaskImg, infile_basemaskf, gfpmaskimg, infile_gfpmaskf, img_cnt):
    def change_img(self, base_flist_e, base_mask_flist_e, gfp_flist_e, gfpmask_flist_e, input_params, temp_storage):
    #def  change_img(self, Imgfile, Maskfile, img_cnt):
        """
            replace clouded pixels with non-clouded pixels
            write out cloud-free product, metadata-maskfile and metadata-textfile (of used products)
            option using full file reading (faster, but higher memory usage)
        """
        out_prefix = 'CF_'
        img_cnt = 1
### TODO  -> for future use of differernt output formats (see below)
#        -- needs additional checking to find the correct gdal-driver-name  eg. GTiff from tif
#        -- out_ext = '.'+input_params['output_format']
##  -- output_format
##  -- output_crs
##  -- output_datatype
### -- consider multiple files in the base_flist (eg. if extract=FULL or AOI spans multiple files) could happen at cmd-line
##     if WCS is not used (but only the file-system directly)
##  -- extract  <FULL|SUB> ??
#
##     nodata_val = 253
#    # additional tiff_settings for the tif-creation
#        tiff_options = [ "TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256" ]
##            "COMPRESS=DEFLATE"]                         # not used in Cryoland
##            "TIFFTAG_GDAL_NODATA=255" }# "NODATA=255" ]        # these seem not to work
#

        out_meta_mask = '_composite_mask.tif'
        #out_meta_list = '_composite_list.txt'
        startTime1 = time.time()

        #print 'File2: ', gfp_flist_ew
        #print 'Mask2: ', gfpmask_flist_e

        for basefile, basemaskfile in zip(base_flist_e, base_mask_flist_e):
#            print 'Using BaseImg: ', basefile, type(basefile)
#            print 'Using BaseMaks: ', basemaskfile, type(basemaskfile)
            baseImg, infile_basef, basemaskImg, infile_basemaskf = self.access_ds(basefile, basemaskfile, temp_storage)
            baseImgDim, baseProj, baseLocation = self.read_img(baseImg, infile_basef)
            basemaskDim, basemaskProj, basemaskLocation, basemaskImg, basemaskClouds, basemaskCoord = self.read_mask(basemaskImg, infile_basemaskf, isBaseImg=True)
#            print 'baseImg: ', type(baseImg), baseImg.RasterCount, baseImg.RasterXSize , baseImg.RasterYSize

            baseImgDim.append([baseImg.GetDriver().ShortName])
            #print 'DriverShort: ',baseImg.GetDriver().ShortName
            #print 'baseImg: ', type(baseImg)
            baseImgBand = baseImg.GetRasterBand(1)
            #baseDt = gdal.GetDataTypeName(baseImgBand.DataType)
            baseImgDt = getNumpyDataType(baseImgBand.DataType)
#            print 'np_dtype: ',baseImgDt
            gDType = getGdalDataType(baseImgDt)
#            print 'gdal_dtype: ', gDType

### TODO - change the following line to add support for other file formats --  also consider output_datatype!!
            driver = baseImg.GetDriver()
# taken (mostly) from gdal tutorial:  but this needs additional checking to find the correct gdal-driver-name  eg. GTiff from tif
#            format = "GTiff"
#            driver = gdal.GetDriverByName( format )
#            metadata = driver.GetMetadata()
#            if metadata.has_key(gdal.DCAP_CREATE) and metadata[gdal.DCAP_CREATE] == 'YES':
#                print 'Driver %s supports Create() method.' % format
#            else:
#                print 'gdal's does not Driver %s supports Create() method.' % format
#            #if metadata.has_key(gdal.DCAP_CREATECOPY) \
#            #   and metadata[gdal.DCAP_CREATECOPY] == 'YES':
#            #    print 'Driver %s supports CreateCopy() method.' % format
#            else:
#                print 'gdal's does not Driver %s supports CreateCopy() method.' % format


                # create the cloud-free output dataset
            outFile = infile_basef.rsplit(dsep, 1)
            outFile[1] = out_prefix + outFile[1]
# @@ testing intermediary -> comment out the following line
            outImg = driver.Create((outFile[0]+dsep+outFile[1]), baseImgDim[0][0], baseImgDim[1][0], baseImgDim[2][0], gDType)



### TODO -- an Alternative - which would also cover reprojection !!
#  gdal.CreateAndReprojectImage(<source_dataset>, <output_filename>, src_wkt=<source_wkt>, dst_wkt=<output_wkt>,
#        dst_driver=<Driver>, eResampleAlg=<GDALResampleAlg>)


                # metadata mask & txt-file for storing the info about used (combined) datasets
            metamaskTIF = outFile[1].replace('.tif', out_meta_mask)
            metamaskTXT = metamaskTIF.replace('.tif','.txt')


                # the metamask - will always be a 8-Bit GeoTiff
            metamaskImg = np.zeros((baseImgDim[1][0], baseImgDim[0][0]), uint8)
            eval_mask = np.array(basemaskImg)

            out_data = np.zeros((baseImgDim[2][0], baseImgDim[1][0], baseImgDim[0][0]), dtype=baseImgDt)


# @@ debug
                # @@ just for debugging
#            do_interupt()



            for i in range(1, baseImgDim[2][0]+1,1):
                baseBand = baseImg.GetRasterBand(i)
#                print 'baseBand: ', type(baseBand)
                baseBand1 = baseBand.ReadAsArray(0, 0, baseImgDim[0][0], baseImgDim[1][0])
#                print 'Num of Bands,', baseImgDim[2][0], i
#                print 'Size: ', type(baseBand1)
                out_data[i-1, :, :] = baseBand1



            for gfpfile, gfpmaskfile in zip(gfp_flist_e, gfpmask_flist_e):
#                print 'Using GFP-'+str(img_cnt)+': ', gfpfile, type(gfpfile)
                print 'Using GFPMask-'+str(img_cnt)+': ', gfpmaskfile, type(gfpmaskfile)
                gfpImg, infile_gfpf, gfpmaskImg, infile_gfpmaskf = self.access_ds(gfpfile, gfpmaskfile, temp_storage)
                gfpImgDim, gfpProj, gfpLocation = self.read_img(gfpImg, infile_gfpf)
                gfpmaskDim, gfpmaskProj, gfpmaskLocation, gfpmaskImg, gfpmaskClouds = self.read_mask(gfpmaskImg, infile_gfpmaskf, isBaseImg=False)


                res2 = np.ma.MaskedArray((eval_mask > 0) & (gfpmaskImg == 0))
                #print type(basemaskImg), basemaskImg.shape, type(gfpmaskImg), gfpmaskImg.shape
                #print 'res2: ', '\n',type(res2), res2.shape
                print 'n_cloudpixel replaced: ', res2.sum()

                metamaskImg[res2] = img_cnt
#                print 'metamaskTIF: ',type(metamaskImg),  metamaskImg.shape, metamaskImg.min(), metamaskImg.max()
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

# @@ for testing intermediary -- uncomment the following line
                    # to test to write out intermediary products
                #outImg = driver.Create((outFile[0]+dsep+outFile[1])+'_'+str(img_cnt), baseImgDim[0][0], baseImgDim[1][0], baseImgDim[2][0], gDType)


### TODO  --  maybe add some statistics to the mask file, eg. No. of clouded pixels replaced? or some overall statistics?  TBD


                    # create a txt file containing the image-filenames and byte-codes used in the metamask
                if os.path.exists(outFile[0]+dsep+metamaskTXT):
                    out_metamask_txt = open(outFile[0]+dsep+metamaskTXT, "a")
                else:
                    out_metamask_txt = open(outFile[0]+dsep+metamaskTXT, "w")


                applied_mask = infile_gfpmaskf.rsplit(dsep, 1)
                out_metamask_txt.write(str(img_cnt)+';'+applied_mask[1]+'\n')


                    # read all bands, check each for cloud-free areas, and write to cloud-free image
                for i in range(1, baseImgDim[2][0]+1, 1):
                    gfpBand = gfpImg.GetRasterBand(i)
                    gfpBand1 = gfpBand.ReadAsArray(0, 0, gfpImgDim[0][0], gfpImgDim[1][0])

                    out_data[i-1][res2] = gfpBand1[res2]

                    # quit if no more clouded picels are available
                print 'Nonzero pixel: ', np.count_nonzero(eval_mask)
#                print 'Eval_mask.sum: ', eval_mask.sum()    # provides a cumulative sum of all non-zero pixels
                #if np.count_nonzero(eval_mask) == 0:
                if eval_mask.sum() == 0:
                    break

                img_cnt += 1


                    #write out all Bands into outFile
            for i in range(1, baseImgDim[2][0]+1, 1):
                outBand = outImg.GetRasterBand(i)
                outBand.WriteArray(out_data[i-1], 0, 0)
                    # some band statistics (min,max,mean,std)
                #outBand.GetStatistics(0, 1)
                outBand.FlushCache()

            outImg.SetGeoTransform(baseImg.GetGeoTransform())
            outImg.SetProjection(baseImg.GetProjection())

                # calculate the overviews needed
            overview_sizes = calc_overviews(outBand, [baseImgDim[0][0], baseImgDim[1][0]])
            print 'Overviewlist: ', overview_sizes
                # initate pyramid creation
            outImg.BuildOverviews(resampling="NEAREST", overviewlist=overview_sizes)


# @@ for testing intermediary - uncomment the following line
                #outImg = None

        print 'change_img - RUNTIME in sec: ',  time.time() - startTime1

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
        cloudfree processor for the cryoland snowmaps
    """

    def process_clouds(self, base_flist, base_mask_flist, gfp_flist, gfpmask_flist, input_params, settings, temp_storage):
        """
            perform the required cloud removal processing steps
        """
## TODO -- consider multiple files in the base_flist (eg. if extract=FULL or AOI spans multiple files)
    # some values used for cryoland cloud masking
        cloud_val = 30
        zero_val = 0
    # all values above are not in use in CryoLand
        nodata_val = 253
    # tiff_settings for the tif-creation
        tiff_options = [ "TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256" ]
#            "COMPRESS=DEFLATE"]                         # not used in Cryoland
#            "TIFFTAG_GDAL_NODATA=255" }# "NODATA=255" ]        # these seem not to work

        outfile = os.path.join(temp_storage+'CF_'+base_flist[0])

# @@ for debugging
       # do_interupt()

#        print temp_storage
#        print base_flist[0]
        
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
        out_clouds = 0
        cnt = 1

        for gfp_file in gfp_flist:
            gfile =  gdal_array.LoadFile(temp_storage+gfp_file)
            # evaluate the cloud masking
            res2 = np.ma.MaskedArray( ((outImg == cloud_val) | (outImg == zero_val) | (outImg >= nodata_val)) & ((gfile != zero_val ) & (gfile != cloud_val) & (gfile < nodata_val)) )
            outImg[res2] = gfile[res2]
            out_clouds = size(np.array(np.where(outImg == cloud_val)))
            cnt += 1

                # if there are no more clouded pixels - stop processing
            if (out_clouds == 0):
                break

               # now create the cloudfree output products file
            output = indriver.Create(outfile, base_img.shape[1], base_img.shape[0], inbase_NumBands, gDtype, options=tiff_options)
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

                    # free the open files
        output = None
        inbase_img = None
        base_img = None
        gfp_file = None
        outImg = None

        return outfile




#/************************************************************************/
#/*                      CF_landsat5_2A_processor()                      */
#/************************************************************************/
class CF_landsat5_2a_Processor(CFProcessor):
    """
        cloudfree processor for the MUSCAT Landsat 5 (Level 2A) dataset
    """


#/************************************************************************/
#/*                      CF_spot4take5_Processor()                       */
#/************************************************************************/
class CF_spot4take5_n2a_pente_Processor(CFProcessor):
    """
        cloudfree processor for the MUSCAT Landsat 5 (Level 2A) dataset
    """


#/************************************************************************/
#/*                            ()                                */
#/************************************************************************/



#/************************************************************************/
#/*                            main()                                    */
#/************************************************************************/





