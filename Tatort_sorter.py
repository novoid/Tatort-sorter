#!/usr/bin/env python3
# -*- coding: utf-8; mode: python; -*-
PROG_VERSION = u"Time-stamp: <2026-11-08 18:40:00 vk>"
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

def safe_import(library):
    try:
        globals()[library] = import_module(library)
    except ImportError:
        print("Could not find Python module \"" + library + "\".\nPlease install it, e.g., with \"sudo python3 -m pip install " + library + "\"")
        sys.exit(2)

safe_import('pandas')
safe_import('lxml')

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
:URL: https://github.com/novoid/Tatort-sorter
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
                    help="Just print what's being done, do not move or delete files, create directories, or write the history file")

parser.add_argument("--history",
                    dest="history", metavar="PATH",
                    help="History file of already sorted/seen Tatort numbers (default: $TATORT_SORTER_HISTORY or " +
                    "$XDG_STATE_HOME/tatort-sorter/seen_episodes.txt or ~/.local/state/tatort-sorter/seen_episodes.txt)")

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


VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.avi', '.m4v', '.ts')

# tokens which mark the start of release meta-information in web download file names
# (resolution or source); everything from such a token on is not part of the title
WEB_METADATA_TOKEN_REGEX = re.compile(
    r'(\d{3,4}[pi]|4k|uhd|[hs]d|web-?dl|webrip|web|hdtv|bluray|bdrip|brrip|dvdrip)',
    re.IGNORECASE)

# example: "Tatort S2026E18 Die letzten Menschen von Koeln 1080p ARD WEB-DL AAC2 0 H 264-NTb[EZTVx.to].mkv"
WEB_FILENAME_REGEX = re.compile(r'^Tatort\s+S(\d{4})E(\d{1,3})\s+(.+)$', re.IGNORECASE)

FILETAG_TO_REMOVE = 'highquality'


def parse_erstausstrahlung(erstausstrahlung):
    """Parses dates like '17.\xa0Juli 2021' or '17.\xa0Jul. 2021' (with optional footnotes)
    and returns a datetime object. Raises ValueError if not parseable."""

    # removing footnotes in dates and fixing "Jan." for %B matching:
    erstausstrahlung = re.sub(r'\[.+?\]', '', str(erstausstrahlung).replace('Jan.', 'Jänner')).strip()
    # some episodes list multiple dates such as '24. März 2008 (Das Erste) 13. Jan. 2008 (SF)':
    # use the first one
    first_date = re.match(r'\d{1,2}\.\s?\S+ \d{4}', erstausstrahlung)
    if first_date:
        erstausstrahlung = first_date.group(0)
    try:
        # example: '17.\xa0Juli 2021'
        return datetime.datetime.strptime(erstausstrahlung, '%d.\xa0%B %Y')
    except ValueError:
        # example: '17.\xa0Jul. 2021'
        return datetime.datetime.strptime(erstausstrahlung, '%d.\xa0%b. %Y')


def normalize_title(title):
    """Returns a simplified version of a title for comparing titles:
    lower case, umlauts transliterated, no punctuation, single spaces."""

    title = title.lower()
    for orig, replacement in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        title = title.replace(orig, replacement)
    title = re.sub(r'[^\w\s]', ' ', title)
    return ' '.join(title.split())


def parse_web_filename(filename):
    """Returns (year, episode, raw_title, extension) for web download file names
    like 'Tatort S2026E18 Die letzten Menschen von Koeln 1080p ARD WEB-DL AAC2 0 H 264-NTb[EZTVx.to].mkv'
    or None if the file name does not follow this pattern."""

    stem, extension = os.path.splitext(filename)
    if extension.lower() not in VIDEO_EXTENSIONS:
        return None
    if ' ' not in stem:
        # dot- or underscore-separated variant: "Tatort.S2026E18.Die.letzten.Menschen..."
        stem = re.sub(r'[._]', ' ', stem)
    components = WEB_FILENAME_REGEX.match(stem)
    if not components:
        return None

    title_words = []
    for word in components.group(3).split():
        if WEB_METADATA_TOKEN_REGEX.fullmatch(word):
            break
        title_words.append(word)
    if not title_words:
        return None

    return int(components.group(1)), int(components.group(2)), ' '.join(title_words), extension


def get_filetags_end(filename):
    """Returns the end of the file name containing filetags (without FILETAG_TO_REMOVE)
    and the file extension, e.g. ' -- karl.mp4' or '.mp4'."""

    extension = os.path.splitext(filename)[-1]
    if ' -- ' not in filename:
        return extension
    tags = re.match(r'.+ -- (.+)', os.path.splitext(filename)[0]).group(1).split()
    tags = [tag for tag in tags if tag != FILETAG_TO_REMOVE]
    if tags:
        return ' -- ' + ' '.join(tags) + extension
    return extension


def build_filename(row, mydate, se_code, end_with_tags):
    """Returns the new file name like:
    2026-09-20 Tatort 1340 S2026E18 - Ballauf und Schenk 96 - Die letzten Menschen von Köln.mkv"""

    se_part = ' ' + se_code if se_code else ''
    return mydate.strftime('%Y-%m-%d') + ' Tatort ' + str(row['Folge']) + se_part + ' - ' + \
        row['Ermittler'] + ' ' + str(row['Fall']) + ' - ' + row['Titel'] + end_with_tags


# sorted file names start with date and Tatort number (Folge), old and new pattern:
# "2014-03-23 Tatort 905 - Ballauf und Schenk 59 - Der Fall Reinhardt -- highquality.mp4"
# "2026-09-20 Tatort 1340 S2026E18 - Ballauf und Schenk 96 - Die letzten Menschen von Köln.mkv"
SORTED_FILENAME_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2} Tatort (\d+)( |\.|$)')


def iter_sorted_files():
    """Yields (folge, path) of all already sorted files within all sub-directories
    of the current directory."""

    for directory in sorted(entry for entry in os.listdir(os.getcwd()) if os.path.isdir(entry)):
        for entry in sorted(os.listdir(directory)):
            components = SORTED_FILENAME_REGEX.match(entry)
            if components and os.path.isfile(os.path.join(directory, entry)):
                yield components.group(1), os.path.join(directory, entry)


def find_potential_doubles(folge):
    """Returns the paths of already sorted files with the same Tatort number (Folge)
    within all sub-directories of the current directory, independent of
    file name pattern, title spelling, Ermittler directory, filetags, or extension."""

    return [path for current_folge, path in iter_sorted_files() if current_folge == str(folge)]


HISTORY_HEADER = '# Tatort-sorter history: Folge<TAB>recorded<TAB>source<TAB>file name\n'


def get_history_path():
    """--history, then $TATORT_SORTER_HISTORY, then the XDG state directory."""

    if options.history:
        return os.path.expanduser(options.history)
    if os.environ.get('TATORT_SORTER_HISTORY'):
        return os.path.expanduser(os.environ['TATORT_SORTER_HISTORY'])
    state_home = os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state')
    return os.path.join(state_home, 'tatort-sorter', 'seen_episodes.txt')


class History:
    """Persistent, append-only list of Tatort numbers (Folge) which were sorted or
    found in the target directories once. Helps to recognize episodes which were
    watched and deleted in the meantime. Lines: Folge<TAB>date<TAB>source<TAB>file name;
    a line containing a bare number is a valid (manual) entry as well."""

    def __init__(self, path):
        self.path = path
        self.entries_by_folge = {}
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as historyfile:
                for line in historyfile:
                    line = line.rstrip('\n')
                    if not line.strip() or line.lstrip().startswith('#'):
                        continue
                    fields = line.split('\t')
                    folge = fields[0].strip()
                    if not folge.isdigit():
                        logging.debug('Ignoring unparsable line in history file ' + path + ': ' + line)
                        continue
                    fields += [''] * (4 - len(fields))
                    self.entries_by_folge.setdefault(folge, []).append(tuple(fields[1:4]))
        logging.debug('Loaded ' + str(len(self.entries_by_folge)) + ' Tatort numbers from history file ' + path)

    def entries(self, folge):
        return self.entries_by_folge.get(str(folge), [])

    def record(self, folge, source, filename):
        """Adds the entry unless the same Folge with the same file name is already known."""

        folge = str(folge)
        if any(entry[2] == filename for entry in self.entries(folge)):
            return
        entry = (datetime.date.today().isoformat(), source, filename)
        self.entries_by_folge.setdefault(folge, []).append(entry)
        if options.simulate:
            return
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        write_header = not os.path.isfile(self.path)
        with open(self.path, 'a', encoding='utf-8') as historyfile:
            if write_header:
                historyfile.write(HISTORY_HEADER)
            historyfile.write('\t'.join((folge,) + entry) + '\n')


history = None  # History instance, initialized in main()


def format_history_entry(folge, entry):
    date, source, oldname = entry
    if not oldname:
        return 'Tatort ' + str(folge) + ' (manual entry)'
    return date + ' ' + source + ': ' + oldname


def ask_move_delete_skip(filename):
    """Returns True if the file should be moved; handles deletion and skipping."""

    answer = ''
    while answer not in ('m', 'd', 's'):
        answer = input('     Move it (m), delete it (d) or skip it (s)? ').strip().lower()
    if answer == 'd':
        logging.info('Deleting file "' + filename + '" due to user decision.\n')
        if not options.simulate:
            os.remove(filename)
        return False
    if answer == 's':
        logging.info('Leaving file "' + filename + '" untouched due to user decision.\n')
        return False
    return True


def move_file(filename, directory, newfilename, folge):
    """Moves the file into the directory with its new name (or warns if it already exists).
    folge (the Tatort number) is used to detect potential doubles with different file name
    patterns, titles, Ermittler directories, filetags, or extensions as well as episodes
    which were sorted or seen before according to the history file."""

    destinationpath = os.path.join(directory, newfilename)
    if os.path.isfile(destinationpath):
        # warn if an episode was downloaded twice without overwriting the previous version
        logging.warning('File "' + filename + '" \n' + ' ' * 5 + 'already exists as: ' + destinationpath + '\n')
        return

    doubles = find_potential_doubles(folge)
    previous_entries = history.entries(folge) if history else []
    if doubles:
        logging.warning('File "' + filename + '" \n' + ' ' * 5 + 'is a potential double of:\n' +
                        '\n'.join(' ' * 8 + double for double in doubles) + '\n' +
                        ' ' * 5 + '(target name would be: ' + destinationpath + ')')
        if not ask_move_delete_skip(filename):
            return
    elif previous_entries:
        logging.warning('File "' + filename + '" \n' + ' ' * 5 +
                        'was already sorted/seen before (it is not on disk any more), probably watched:\n' +
                        '\n'.join(' ' * 8 + format_history_entry(folge, entry) for entry in previous_entries) + '\n' +
                        ' ' * 5 + '(history file: ' + history.path + ')\n' +
                        ' ' * 5 + '(target name would be: ' + destinationpath + ')')
        if not ask_move_delete_skip(filename):
            return

    if not os.path.exists(directory) and not options.simulate:
        os.makedirs(directory)
        logging.warning('I created a new directory for "Ermitter": ' + directory)

    logging.info('Moving file "' + filename + '" → \n' + ' ' * 5 + destinationpath + '\n')
    if not options.simulate:
        os.rename(filename, destinationpath)
    if history:
        history.record(folge, 'sorted', destinationpath)


def ask_user_for_confirmation():
    answer = input('     Accept this match? [y/n] ').strip().lower()
    if answer != 'y':
        logging.info('Skipping file due to user decision.')
        return False
    return True


def build_season_episode_maps(table):
    """Season = year of Erstausstrahlung, episode = position within that year.
    Returns (dates_by_index, row_index_by_se_code, se_code_by_folge)."""

    dates_by_index = {}
    for index, row in table.iterrows():
        try:
            dates_by_index[index] = parse_erstausstrahlung(row['Erstausstrahlung'])
        except ValueError:
            logging.debug('Could not parse Erstausstrahlung "' + str(row['Erstausstrahlung']) +
                          '" of Folge ' + str(row['Folge']) + ' - ignoring it for season/episode numbering')

    def folge_sort_key(index):
        try:
            return int(table.loc[index, 'Folge'])
        except (ValueError, TypeError):
            return 0

    index_by_se_code = {}
    se_code_by_folge = {}
    episode_counter = {}
    for index in sorted(dates_by_index, key=lambda i: (dates_by_index[i], folge_sort_key(i))):
        year = dates_by_index[index].year
        episode_counter[year] = episode_counter.get(year, 0) + 1
        se_code = 'S%04dE%02d' % (year, episode_counter[year])
        index_by_se_code[se_code] = index
        se_code_by_folge[str(table.loc[index, 'Folge'])] = se_code

    return dates_by_index, index_by_se_code, se_code_by_folge


def get_files_in_current_directory():
    return sorted(entry for entry in os.listdir(os.getcwd()) if os.path.isfile(entry))


def handle_web_downloads(table, dates_by_index, index_by_se_code):
    """Handles files like 'Tatort S2026E18 Die letzten Menschen von Koeln 1080p ARD WEB-DL ....mkv'"""

    for file in get_files_in_current_directory():
        components = parse_web_filename(file)
        if not components:
            continue
        year, episode, raw_title, extension = components
        se_code = 'S%04dE%02d' % (year, episode)

        if se_code not in index_by_se_code:
            logging.warning('Could not find ' + se_code + ' in Wikipedia table: skipping file "' + file + '"')
            continue
        index = index_by_se_code[se_code]
        row = table.loc[index]

        if normalize_title(raw_title) != normalize_title(row['Titel']):
            logging.warning('found ' + se_code + ' match with a different title: ' + file + '\n' +
                            ' ' * 5 + '(title in file name: "' + raw_title + '", Wikipedia title: "' + row['Titel'] + '")')
            if not ask_user_for_confirmation():
                continue
        else:
            logging.debug('found web download match: ' + file)

        newfilename = build_filename(row, dates_by_index[index], se_code, get_filetags_end(file))
        move_file(file, row['Ermittler'], newfilename, row['Folge'])


def main():
    """Main function"""

    if options.version:
        print(os.path.basename(sys.argv[0]) + " version " + PROG_VERSION_DATE)
        sys.exit(0)

    handle_logging()

    if options.verbose and options.quiet:
        error_exit(1, "Options \"--verbose\" and \"--quiet\" found. " +
                   "This does not make any sense, you silly fool :-)")

    locale.setlocale(locale.LC_ALL, 'de_AT.utf8')

    url = r'https://de.wikipedia.org/wiki/Liste_der_Tatort-Folgen'
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'Tatort-sorter/1.0 (https://github.com/novoid/Tatort-sorter; tools@Karl-Voit.at)'})
    html = urllib.request.urlopen(req).read()
    tables = pandas.read_html(html)  # Returns list of all tables on page
    table = tables[0]  # The list of Tatort episodes

    dates_by_index, index_by_se_code, se_code_by_folge = build_season_episode_maps(table)

    # remember all already sorted episodes, even those not sorted by this script
    global history
    history = History(get_history_path())
    for folge, path in iter_sorted_files():
        history.record(folge, 'scanned', path)

    # first: web downloads which contain season and episode in their file names
    handle_web_downloads(table, dates_by_index, index_by_se_code)

    # second: MediathekView downloads which are matched by their titles

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
        # Erstausstrahlung                                         7. März 2021
        # Ermittler                                          Borowski und Sahin
        # Fall                                                               36
        # Autor                                   Peter Probst und Daniel Nocke
        # Regie                                                 Nicole Weegmann
        # Besonderheiten      Ausstrahlung anlässlich des Weltfrauentages (8...

        escaped_title = re.escape(row['Titel'])
        regex = re.compile(r'.+? Tatort .*?\s' + escaped_title + r'(\s.+$|$)')
        regex_fallback = re.compile(r'.+? Tatort .*?\s' + escaped_title + r'(\s.+$|$)', re.IGNORECASE)

        for file in get_files_in_current_directory():

            if parse_web_filename(file):
                continue  # web downloads were handled above

            if regex.match(file):
                logging.debug('found match: ' + file)
            elif regex_fallback.match(file):
                logging.warning('found case-insensitive match: ' + file + '\n' +
                                ' ' * 5 + '(Wikipedia title: "' + row['Titel'] + '")')
                if not ask_user_for_confirmation():
                    continue
            else:
                continue

            if index not in dates_by_index:
                logging.warning('Could not parse Erstausstrahlung "' + str(row['Erstausstrahlung']) +
                                '": skipping file "' + file + '"')
                continue
            mydate = dates_by_index[index]

            se_code = se_code_by_folge.get(str(row['Folge']))
            if not se_code:
                logging.warning('Could not determine season/episode for Folge ' + str(row['Folge']))

            # example file names:
            # 2011-08-28 Tatort 807 S2011E22 - Eisner 26 - Lohn der Arbeit -- karl.mp4
            # 2007-10-28 Tatort 678 S2007E30 - Thiel und Boerne 12 - Satisfaktion.mp4
            newfilename = build_filename(row, mydate, se_code, get_filetags_end(file))
            move_file(file, row['Ermittler'], newfilename, row['Folge'])

            if not newfilename.startswith(os.path.basename(file)[:10]):
                logging.warning('Please check the previous output: dates differ which could be a repetition of an ' +
                                'older episode (perfectly fine) or a mismatch according to the title (needs to be fixed).')

    logging.debug("successfully finished.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:

        logging.info("Received KeyboardInterrupt")

# END OF FILE #################################################################
