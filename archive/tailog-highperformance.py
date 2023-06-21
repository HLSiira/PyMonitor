#!/usr/bin/python3

"""
Description:
    This will create two files names logname.log.head and logname.log.tail.
    To read what's in the log, you can do cat logname.log.head logname.log.tail and pipe that into whatever, or better yet, just cat logname.log.* assuming you don't have any naming conventions.
    If you really only want the 5 bytes, you can pipe that into tail -c 5
    
    To read the log, use the same stuff as above, and if you really only want the last 2 lines, you can pipe the output of the cat into tail -2


Usage:
    Line Mode: echo -ne "$(date)\n" | tailog -l 2 samples/logname.log
    Byte Mode: echo -ne "I'm only keeping the last 5 bytes in the file" | tailog -b 5 samples/logname.log

"""


from sys import stdin
from math import ceil
import os
import argparse

parser = argparse.ArgumentParser(description='Create a tailog.')
parser.add_argument('fpath', help='the path of the tailog to be created')
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('-l', '--lines', metavar='NLINES', dest='num_lines', type=int, default=100, help='the number of lines to limit the tailog to (default 100)')
group.add_argument('-b', '--bytes', metavar='NBYTES', dest='num_bytes', type=int, default=0, help='the number of bytes to limit the tailog to')
args = parser.parse_args()

fpath = args.fpath
if not os.path.isabs(fpath):
   dname = os.getcwd()
   fpath = os.path.join(dname, fpath)
fpath = os.path.abspath(fpath)

headfpath = f'{fpath}.head'
tailfpath = f'{fpath}.tail'

if not os.path.exists(headfpath):
   open(headfpath, 'a').close()
if not os.path.exists(tailfpath):
   open(tailfpath, 'a').close()

line_mode = args.num_bytes == 0

if line_mode:
   # line mode
   num_lines = args.num_lines

   tail = open(tailfpath, 'r')
   curr = sum(1 for line in tail)
   tail.close()
   tail = open(tailfpath, 'a')


   for line in stdin:
      tail.write(line)
      curr += 1
      if curr == num_lines:
         curr = 0
         tail.close()
         os.remove(headfpath)
         os.rename(tailfpath, headfpath)
         tail = open(tailfpath, 'a')

   tail.close()

else:
   # byte mode
   num_bytes = args.num_bytes

   tail = open(tailfpath, 'ab')

   while True:
      in_bytes = stdin.buffer.read1(num_bytes - tail.tell())
      if len(in_bytes) == 0:
         break
      tail.write(in_bytes)
      if tail.tell() == num_bytes:
         tail.close()
         os.remove(headfpath)
         os.rename(tailfpath, headfpath)
         tail = open(tailfpath, 'ab')
   
   tail.close()

