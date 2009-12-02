import os
import marshal, sys, time, traceback

from collections import defaultdict
from itertools import chain, repeat
from types import CodeType, FunctionType
from urllib import urlencode

from disco.comm import CommException, download, open_remote
from disco.error import DiscoError
from disco.settings import DiscoSettings


class DefaultDict(defaultdict):
        """Like a defaultdict, but calls the default_factory with the key argument."""
        def __missing__(self, key):
                return self.default_factory(key)

def flatten(iterable):
        for item in iterable:
                if hasattr(item, '__iter__'):
                        for subitem in flatten(item):
                                yield subitem
                else:
                        yield item

def iterify(object):
        if hasattr(object, '__iter__'):
                return object
        return repeat(object, 1)

def pack(object):
        if hasattr(object, 'func_code'):
                return marshal.dumps(object.func_code)
        return marshal.dumps(object)

def unpack(string):
        object = marshal.loads(string)
        if isinstance(object, CodeType):
                return FunctionType(object, {})
        return object

def urlsplit(url):
        scheme, rest = url.split('://', 1) if '://' in url  else ('file', url)
        netloc, path = rest.split('/', 1)  if '/'   in rest else (rest ,'')
        if scheme == 'disco':
                scheme = 'http'
                netloc = '%s:%s' % (netloc, DiscoSettings()['DISCO_PORT'])
        return scheme, netloc, path

def urllist(url):
        scheme, netloc, path = urlsplit(url)
        if scheme == 'dir':
                return parse_dir(url)
        return [url]

def msg(m, c = 'MSG', job_input = ""):
        t = time.strftime("%y/%m/%d %H:%M:%S")
        if job_input:
                print >> sys.stderr, "**<%s>[%s (%s)] %s" %\
                        (c, t, job_input, m)
        else:
                print >> sys.stderr, "**<%s>[%s] %s" % (c, t, m)

def err(m):
        if sys.exc_info() == (None, None, None):
                msg(m, 'MSG')
                raise DiscoError(m)
        else:
                msg(m, 'MSG')
                raise

def data_err(m, job_input):
        if sys.exc_info() == (None, None, None):
                msg(m, 'DAT', job_input)
                raise DiscoError(m)
        else:
                traceback.print_exc()
                msg(m, 'DAT', job_input)
                raise

def jobname(address):
        scheme, x, path = urlsplit(address)
        if scheme in ('disco', 'dir', 'http'):
                return path.strip('/').split('/')[-2]
        raise DiscoError("Cannot parse jobname from %s" % address)

def pack_files(files):
        return dict((os.path.basename(f), file(f).read()) for f in files)

def external(files):
        msg = pack_files(files[1:])
        msg['op'] = file(files[0]).read()
        return msg

def disco_host(address):
        scheme, netloc, x = urlsplit(address)
        return '%s://%s' % (scheme, netloc)

def proxy_url(path, node='x'):
        settings = DiscoSettings()
        port, proxy = settings['DISCO_PORT'], settings['DISCO_PROXY']
        if proxy:
                scheme, netloc, x = urlsplit(proxy)
                return '%s://%s/disco/node/%s/%s' % (scheme, netloc, node, path)
        return 'http://%s:%s/%s' % (node, port, path)

def parse_dir(dir_url, partid = None):
        def parse_index(index):
                return [url for id, url in (line.split() for line in index)
                        if partid is None or partid == int(id)]
        settings = DiscoSettings()
        scheme, netloc, path = urlsplit(dir_url)
        if 'resultfs' in settings['DISCO_FLAGS']:
                path = '%s/data/%s' % (settings['DISCO_ROOT'], path)
                return parse_index(file(path))
        url = proxy_url(path, netloc)
        return parse_index(download(url).splitlines())

def load_oob(host, name, key):
        settings = DiscoSettings()
        params = {'name': name,
                  'key': key,
                  'proxy': bool(settings['DISCO_PROXY'])}
        url = '%s/disco/ctrl/oob_get?%s' % (host, urlencode(params))
        if 'resultfs' in settings['DISCO_FLAGS']:
                size, fd = open_remote(url, expect=302)
                location = fd.getheader('location').split('/', 3)[-1]
                path = '%s/data/%s' % (settings['DISCO_ROOT'], location)
                return file(path).read()
        return download(url, redir=True)
