#!/usr/bin/env python
# -*- encoding: UTF8 -*-
 
""" read out S.M.A.R.T. values out of the database and plot them using matplotlib
 
<http://matplotlib.sourceforge.net/examples/pylab_examples/anscombe.html>
"""
 
from pylab import *
from os import geteuid
import sys
import pdb

import smartToDB
 
def main(*args):
    if geteuid() != 0:
        print("You must be root to run this script.")
        sys.exit(1)
    if len(args)<2:
        print("usage: "+args[0]+" t / s")
        sys.exit(1)
    # meaning of the positions in the returned list:
    dev_pos=1
    date_pos=2
    temperature_pos=3
    seek_err_pos=4
    #
    date, temperature, seek_err, style = dict(), dict(), dict(), dict()
    datasets = smartToDB.get_all_datasets()
    styles, i = ['bo','go','ro'], 0 # plot styles
    for dataset in datasets:
        name = dataset[dev_pos]
        try:
            date[name]
        except:
            date[name], temperature[name], seek_err[name] = [], [], []
            style[name] = styles[i%len(styles)]
            i = i+1
        date[name].append(dataset[date_pos])
        temperature[name].append(dataset[temperature_pos])
        seek_err[name].append(dataset[seek_err_pos])
 
    for name in date.keys():
        if args[1]=="t":
            # <http://matplotlib.sourceforge.net/api/pyplot_api.html#matplotlib.pyplot.plot_date>
            plot_date(date[name], temperature[name], fmt=style[name], tz=None, xdate=True, ydate=False, label=name)
            title("Temperature of the HDDs over time")
        elif args[1]=="s":
            plot_date(date[name], seek_err[name], fmt=style[name], tz=None, xdate=True, ydate=False, label=name)
            title("Seek errors of the HDDs over time")
        else:
            print("no proper action defined!")
            sys.exit(1)
    legend()
    grid()
    show()
 
if __name__ == "__main__":
    main(*sys.argv)