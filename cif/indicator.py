import json
import time
from datetime import datetime
import re
import pytricia
import socket
from pprint import pprint
import sys
if sys.version_info > (3,):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse
import arrow

TLP = "green"
GROUP = "everyone"

RE_IPV4 = re.compile('^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}')
# http://stackoverflow.com/a/17871737
RE_IPV6 = re.compile('(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))')
# http://goo.gl/Cztyn2 -- probably needs more work
RE_FQDN = re.compile('^((xn--)?(--)?[a-zA-Z0-9-_]+(-[a-zA-Z0-9]+)*\.)+[a-zA-Z]{2,}(--p1ai)?$')
RE_URI_SCHEMES = re.compile('^(https?|ftp)$')

IPV4_PRIVATE = pytricia.PyTricia()
IPV4_PRIVATE_NETS = [
    "0.0.0.0/8",
    "10.0.0.0/8",
    "127.0.0.0/8",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "192.0.2.0/24",
    "224.0.0.0/4",
    "240.0.0.0/5",
    "248.0.0.0/5"
]

for x in IPV4_PRIVATE_NETS:
    IPV4_PRIVATE[x] = True


class Indicator(object):

    def __init__(self, indicator=None, itype=None, tlp=TLP, tags=[], group=GROUP,
                 reporttime=arrow.get(datetime.utcnow()).datetime,
                 provider=None,  protocol=None, portlist=None,  asn=None, firsttime=None, lasttime=None,
                 asn_desc=None, cc=None, application=None, reference=None, reference_tlp=None, confidence=None):

        if isinstance(tags, str):
            tags = tags.split(",")

        self.indicator = indicator
        self.tlp = tlp
        self.provider = provider
        self.reporttime = reporttime
        self.group = group
        self.itype = itype
        self.protocol = protocol
        self.portlist = portlist
        self.tags = tags
        self.application = application
        self.reference = reference
        self.reference_tlp = reference_tlp
        self.confidence = confidence
        self.firsttime = firsttime
        self.lasttime = lasttime

        if reporttime and isinstance(reporttime, str):
            self.reporttime = arrow.get(reporttime).datetime

        if firsttime:
            self.firsttime = arrow.get(firsttime).datetime

        if lasttime:
            self.lasttime = arrow.get(lasttime).datetime

        if asn and asn.lower() == 'na':
            asn = None

        self.asn = asn

        if asn_desc and asn_desc.lower() == 'na':
            asn_desc = None

        self.asn_desc = asn_desc
        self.cc = cc

        if not itype:
            self.itype = self.resolve_obj(self.indicator)

    def magic(self, data):
        for e in data:
            try:
                itype = self.resolve_itype(e)
                i = Indicator(itype=itype, indicator=e)
                return i
            except NotImplementedError:
                pass

    def is_private(self):
        if self.itype and self.itype == 'ipv4':
            if IPV4_PRIVATE.get(self.indicator):
                return True
        return False

    def resolve_itype(self, indicator):
        return self.resolve_obj(indicator)

    def resolve_obj(self, indicator):
        def _ipv6(s):
            try:
                socket.inet_pton(socket.AF_INET6, s)
            except socket.error:
                if not re.match(RE_IPV6, s):
                    return False

            return True

        def _ipv4(s):
            try:
                socket.inet_pton(socket.AF_INET, s)
            except socket.error:
                if not re.match(RE_IPV4, s):
                    return False
            return True

        def _fqdn(s):
            if RE_FQDN.match(s):
                return 1

        def _url(s):
            u = urlparse(s)
            if re.match(RE_URI_SCHEMES, u.scheme):
                if _fqdn(u.netloc) or _ipv4(u.netloc) or _ipv6(u.netloc):
                    return True

        if _fqdn(indicator):
            return 'fqdn'
        elif _ipv6(indicator):
            return 'ipv6'
        elif _ipv4(indicator):
            return 'ipv4'
        elif _url(indicator):
            return 'url'

        raise NotImplementedError('unknown itype for "{}"'.format(indicator))

    def __repr__(self):
        o = {
            "indicator": self.indicator,
            "itype": self.itype,
            "tlp": self.tlp,
            "provider": self.provider,
            "portlist": self.portlist,
            "protocol": self.protocol,
            "tags": ",".join(self.tags),
            "asn": self.asn,
            "asn_desc": self.asn_desc,
            "cc": self.cc,
            "group": self.group,
            "reference": self.reference,
            "reference_tlp": self.reference_tlp,
            "application": self.application
        }

        if self.reporttime and isinstance(self.reporttime, datetime):
            o['reporttime'] = self.reporttime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            o['reporttime'] = self.reporttime

        if self.firsttime and isinstance(self.firsttime, datetime):
            o['firsttime'] = self.firsttime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            o['firsttime'] = self.firsttime

        if self.lasttime and isinstance(self.lasttime, datetime):
            o['lasttime'] = self.lasttime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            o['lasttime'] = self.lasttime

        try:
            return json.dumps(o, sort_keys=True)
        except UnicodeDecodeError as e:
            o['asn_desc'] = unicode(o['asn_desc'].decode('latin-1'))
            return json.dumps(o, sort_keys=True)
