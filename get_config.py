#!/usr/bin/env python 
#
#------------------------------------------------------------------------------
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#
#
#       read the default configuration file  -->  e.g. cloudless_config.cfg
#
#
# Project: DeltaDREAM
# Name:    get_config.py
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


def get_config(default_config_file, def_config = None):
    """ 
		returns a dictionary with keys of the form
		<section>.<option> and the corresponding values 
    """
    import ConfigParser
    import string

    if def_config is None:
        config = {}    
    else: 
        config = def_config.copy()
        
    try:
        #print default_config_file
        if not os.path.isfile(default_config_file):
            raise IOError 
    except (IOError, OSError): 
        print "\n*** ERROR ***:  File does not exist: --> ",  default_config_file


    cp = ConfigParser.SafeConfigParser()
    cp.read(default_config_file)

    for sec in cp.sections():
        name = string.lower(sec)
        for opt in cp.options(sec):
            config[name + "." + string.lower(opt)] = string.strip(cp.get(sec, opt))
    return config
    



if __name__ == '__main__':
    get_config()