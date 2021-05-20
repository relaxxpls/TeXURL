from argparse import ArgumentParser
from pathlib import Path
import mimetypes
import re
import requests
import sys
import zlib


# ? Provides commandline interface support for the script
# ! Add support for folder name (given as --output) to be valid
# ! Setup Verbose command using logging module https://stackoverflow.com/a/49580476/14493047

def parse():
    parser = ArgumentParser(description='URL support for LaTeX')
    parser.add_argument('input', type=Path, help='Input file.')
    parser.add_argument('--output', '-o', type=Path, help='Output file.')
    parser.add_argument('--dump', '-d', type=Path, help='Folder to store the downloaded content.')
    parser.add_argument('--tag', '-t', type=str, nargs='+', default=["includegraphics", "url"],
                        help='LaTeX tags that contain required URLs.')
    parser.add_argument('--all', '-a', action='store_true', help='Flag to download every URL present.')
    parser.add_argument('--force', '-f', action='store_const', default='x', const='w',
                        help='Force overwrite if file already exists.')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Display errors on commandline. Default: Store in the log file.')
    args = parser.parse_args()

    INPUT_FILE = args.input.resolve()
    BASE_DIR = INPUT_FILE.parent
    OUTPUT_FILE = BASE_DIR / f'{INPUT_FILE.stem} TeXURL_out.tex'
    DUMP_DIR = BASE_DIR / '.TeXURL_dump/'

    try:
        open(INPUT_FILE)
    except:
        raise SystemExit(f'{sys.exc_info()[0].__name__}: {sys.exc_info()[1]}')

    # ? Use the user's output file (if valid)
    if args.output is not None:
        if args.output.resolve().is_file():
            OUTPUT_FILE = args.output
        else:
            print(f'"{args.output.resolve()}" is not a valid file (or file name).', file=sys.stderr)
            print('Switching to the default instead.', file=sys.stderr)
            print(f'Default = "{OUTPUT_FILE}")', file=sys.stderr)

    # ? Use the user's dump folder (if valid)
    if args.dump is not None:
        if args.dump.resolve().is_dir():
            DUMP_DIR = args.dump
        else:
            print(f'"{args.dump.resolve()}" is not a valid directory.', file=sys.stderr)
            print('Switching to the default instead.', file=sys.stderr)
            print(f'Default = "{DUMP_DIR}")', file=sys.stderr)

    return INPUT_FILE, OUTPUT_FILE, DUMP_DIR, args.force, args.all, args.tag, args.verbose


# ? Returns the regex to search for URLs

def get_regex(TAGS, ALL=False):
    url_regex = re.compile(
        r'(?P<pre>)'
        r'(?P<url>http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)'
        r'(?P<post>)')
    if not ALL:
        tags_merged = '|'.join(TAGS)
        url_regex = re.compile((
            r'(?P<pre>\\(?:%s){)' # 'pre' and 'post' are there so that we can replace url (middle text)
            r'(?P<url>[^}]+)'
            r'(?P<post>})') % tags_merged)
    return url_regex


# ? Checks if url passed is downloadable
# * Returns if downloadable and the file extension
# ! 1. https://stackoverflow.com/a/16511493/14493047: Check if the user is online

def chk_url(url):
    ignore_content_types = ['text/html', 'text', 'html']
    try:
        head = requests.head(url, allow_redirects=True, timeout=5)
        if head.status_code == 200:
            content_type = head.headers.get('content-type').lower()
            extension = mimetypes.guess_extension(content_type)
            for wrong_type in ignore_content_types:
                if wrong_type in content_type:
                    print(f'Skipping "{url}" as content-type = "{content_type}"', file=sys.stderr)
                    return False, None
        else:
            print(f'Skipping "{url}" as HTTP status code "{head.status_code}"', file=sys.stderr)
            return False, None
        return True, extension
    except:
        raise SystemExit(f'{sys.exc_info()[0].__name__}: {sys.exc_info()[1]}')


# ? Download content and link it
# * Download it ONLY if we hadn't previously downloaded it
# * Hash the URL using Adler-32 as it makes the filename short and sweet
# * Return POSIX path, as LaTeX doesn't recognise Windows path

def download_and_link(url_match, directory):
    url = url_match.group('url')
    try:
        valid, extension= chk_url(url)
        if not valid or extension is None:
            return url
        
        adler32_hash = zlib.adler32(url.encode('utf-8')) & 0xffffffff
        download_name = format(adler32_hash, 'x') + extension
        download_file = directory / download_name
        
        if not download_file.is_file():
            r = requests.get(url, allow_redirects=True, timeout=5)
            if r.status_code == 200:
                with open(download_file, 'wb') as f:
                    f.write(r.content)
            else:
                print(f'Skipping "{url}" as HTTP status code {r.status_code}', file=sys.stderr)
        else:
            print(f'Skipping "{url}" is content already downloaded.', file=sys.stderr)
    except:
        raise SystemExit(f'{sys.exc_info()[0].__name__}: {sys.exc_info()[1]}')
    result = url_match.group('pre') + str(download_file.as_posix()) + url_match.group('post')
    return result


# ? Download content and link it

def main():
    INPUT_FILE, OUTPUT_FILE, DUMP_DIR, FORCE, ALL, TAGS, VERBOSE = parse()
    try:
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(INPUT_FILE, 'r') as f:
            text = f.read()
        with open(OUTPUT_FILE, FORCE) as f:
            url_regex = get_regex(TAGS, ALL)
            linked_text = url_regex.sub(repl=lambda x: download_and_link(x, DUMP_DIR), string=text)
            f.write(linked_text)
    except:
        raise SystemExit(f'{sys.exc_info()[0].__name__}: {sys.exc_info()[1]}')


if __name__ == '__main__':
    main()
