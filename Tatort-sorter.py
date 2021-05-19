#!/usr/bin/env python3
# -*- coding: utf-8; mode: python; -*-
PROG_VERSION = u"Time-stamp: <2021-05-19 21:43:01 vk>"
PROG_VERSION_DATE = PROG_VERSION[13:23]

import time
INVOCATION_TIME = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
import sys
import os
PROG_NAME = os.path.basename(sys.argv[0])

# TODO:
# - fix parts marked with «FIXXME»
# -

# ===================================================================== ##
#  You might not want to modify anything below this line if you do not  ##
#  know, what you are doing :-)                                         ##
# ===================================================================== ##

from importlib import import_module

def save_import(library):
    try:
        globals()[library] = import_module(library)
    except ImportError:
        print("Could not find Python module \"" + library + "\".\nPlease install it, e.g., with \"sudo python3 -m pip install " + library + "\"")
        sys.exit(2)

save_import('pandas')
save_import('lxml')

import re
import sys
import os
import argparse   # for handling command line arguments
import datetime
import logging
import locale


DESCRIPTION = """This script moves episodes of "Tatort" into sub-folders according to the names of the Ermittler."""

EPILOG = """
:copyright: (c) by Karl Voit <tools@Karl-Voit.at>
:license: GPL v3 or any later version
:URL: https://github.com/novoid/FIXXME
:bugreports: via github or <tools@Karl-Voit.at>
:version: """ + PROG_VERSION_DATE + "\n·\n"

import argparse   # for handling command line arguments

parser = argparse.ArgumentParser(prog=sys.argv[0],
                                 # keep line breaks in EPILOG and such
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=EPILOG,
                                 description=DESCRIPTION)

parser.add_argument("-s", "--simulate",
                    dest="simulate", action="store_true",
                    help="Just print what's being done, do not move files or create directories (no file exists check though)")

parser.add_argument("-v", "--verbose",
                    dest="verbose", action="store_true",
                    help="Enable verbose mode")

parser.add_argument("-q", "--quiet",
                    dest="quiet", action="store_true",
                    help="Enable quiet mode")

parser.add_argument("--version",
                    dest="version", action="store_true",
                    help="Display version and exit")

options = parser.parse_args()

import logging

def handle_logging():
    """Log handling and configuration"""

    if options.verbose:
        FORMAT = "%(levelname)-8s %(asctime)-15s %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=FORMAT)
    elif options.quiet:
        FORMAT = "%(levelname)-8s %(message)s"
        logging.basicConfig(level=logging.ERROR, format=FORMAT)
    else:
        FORMAT = "%(levelname)-8s %(message)s"
        logging.basicConfig(level=logging.INFO, format=FORMAT)

def error_exit(errorcode, text):
    """exits with return value of errorcode and prints to stderr"""

    sys.stdout.flush()
    logging.error(text)
    #input('Press <Enter> to finish with return value %i ...' % errorcode).strip()
    sys.exit(errorcode)


def successful_exit():
    logging.debug("successfully finished.")
    sys.stdout.flush()
    sys.exit(0)


def main():
    """Main function"""

    if options.version:
        print(os.path.basename(sys.argv[0]) + " version " + PROG_VERSION_DATE)
        sys.exit(0)

    handle_logging()

    if options.verbose and options.quiet:
        error_exit(1, "Options \"--verbose\" and \"--quiet\" found. " +
                   "This does not make any sense, you silly fool :-)")


    url = r'https://de.wikipedia.org/wiki/Liste_der_Tatort-Folgen'
    tables = pandas.read_html(url)  # Returns list of all tables on page
    table = tables[0]  # The list of Tatort episodes

    # invert the order of the table, starting with the newest episode
    table = table.reindex(index=table.index[::-1])

    ## We follow an interate-over-table first instead of
    ## iterate-over-files first, resulting in going through all files
    ## per table row: this could be performance improved! For a small
    ## set of files and a large table of Tatort episodes, this should
    ## be totally OK. However, I can't print out all non-matching file
    ## names.
    for index, row in table.iterrows():

        # Folge                                                            1159
        # Titel                        Borowski und die Angst der weißen Männer
        # Sender                                                            NDR
        # Erstausstrahlung                                         7. März 2021
        # Ermittler                                          Borowski und Sahin
        # Fall                                                               36
        # Autor                                   Peter Probst und Daniel Nocke
        # Regie                                                 Nicole Weegmann
        # Besonderheiten      Ausstrahlung anlässlich des Weltfrauentages (8...

        rootdir = "."
        regex = re.compile(r'.+? Tatort .*?' + row['Titel'] + r'.+$')

        locale.setlocale(locale.LC_ALL, 'de_AT.utf8')

        if 'wieder Oper' in row['Titel']:
            pass
            #import pudb; pu.db
        
        for root, dirs, files in os.walk(os.getcwd()):

            del dirs[:]  # do not visit sub-directories
            
            for file in files:
                if regex.match(file):
                    
                    logging.debug('found match: ' + file)

                    # the resulting files will be moved to directory names according to the Ermittler
                    directory = row['Ermittler']
                    
                    if not os.path.exists(directory) and not options.simulate:
                        os.makedirs(directory)

                    # removing footnotes in dates and fixing "Jan." for %B matching:
                    erstausstrahlung = re.sub(r'\[.+\]', '', row['Erstausstrahlung'].replace('Jan.', 'Jänner'))

                    # parsing the date:
                    try:
                        # example: '17.\xa0Juli 2021'
                        mydate = datetime.datetime.strptime(erstausstrahlung, '%d.\xa0%B %Y')
                    except ValueError:
                        # example: '17.\xa0Jul. 2021'
                        mydate = datetime.datetime.strptime(erstausstrahlung, '%d.\xa0%b. %Y')

                    if ' -- ' in file:
                        # if there are filetags, preserve them in the resulting file name
                        end_with_tags = re.match(r'.+( -- .+)', file).group(1)
                    else:
                        # pre-fill file name end with file extension (in case of no filetags)
                        end_with_tags = os.path.splitext(file)[-1]  

                    # example file names:
                    # 2011-08-28 Tatort 807 - Eisner 26 - Lohn der Arbeit -- highquality karl.mp4
                    # 2007-10-28 Tatort 678 - Thiel und Boerne 12 - Satisfaktion.mp4
                    newfilename = mydate.strftime('%Y-%m-%d') + ' Tatort ' + str(row['Folge']) + ' - ' + row['Ermittler'] + ' ' + \
                        str(row['Fall']) + ' - ' + row['Titel'] + end_with_tags

                    destinationpath = os.path.join(directory, newfilename)
                    if os.path.isfile(destinationpath):
                        # warn if an episode was downloaded twice without overwriting the previous version
                        logging.warning('File "' + file + '" \n' + ' ' * 5 + 'already exists as: ' + destinationpath + '\n')
                    else:
                        logging.info('Moving file "' + file + '" → \n' + ' ' * 5 + destinationpath + '\n')
                        if not options.simulate:
                            os.rename(file, destinationpath)

    logging.debug("successfully finished.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:

        logging.info("Received KeyboardInterrupt")

# END OF FILE #################################################################
