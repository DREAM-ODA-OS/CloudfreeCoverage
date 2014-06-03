EOxWCSClient
============
# Name:  wcs_client.py
#
#   General purpose WCS 2.0/EO-WCS Client:
#       This routine is inteded to be imported as modules.
#       If cmd-line usage is desired use  "cmdline_wcs_client.py". It provides the 
#       cmd-line interface to  "wcs_client.py". Full help is available from 
#       "cmdline_wcs_client.py"  by running   "cmdline_wcs_client.py  --help"
#
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