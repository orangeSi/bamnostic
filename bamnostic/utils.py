from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

"""Module utilities and constants used throughout bamnostic"""

import struct
from collections import OrderedDict, namedtuple

# Python 2 doesn't put abstract base classes in the same spot as Python 3
import sys
_PY_VERSION = sys.version

if _PY_VERSION.startswith('2'):
    from collections import Sequence
else:
    from collections.abc import Sequence
    
import numbers
import warnings
import re


def format_warnings(message, category, filename, lineno, file=None, line=None):
    r"""Sets STDOUT warnings
    
    Args:
        message: the unformatted warning message being reported
        category (str): the level of warning (handled by `warnings` module)
        filename (str): filename for logging purposes (defaults to STDOUT)
        lineno (int): where the error occurred.
    
    Returns:
        formatted warning string
    """
    return ' {}:{}: {}:{}'.format(filename, lineno, category.__name__, message)

warnings.formatwarning = format_warnings

# pre-compiled structures to reduce iterative unpacking
unpack_int32 = struct.Struct('<i').unpack
unpack_int32L = struct.Struct('<l').unpack


# Helper class for performant named indexing of region of interests
class Roi:
    r"""Small __slots__ class for region of interest parsing"""
    __slots__ = ['contig', 'start', 'stop']
    
    def __init__(self, contig, start, stop):
        r""" Initialize the class
        
        Args:
            contig (str): string representation of chromosome/contig of interest
            start (int): starting base position of region of interest
            stop (int): ending base position of region of interest
        """
        self.contig, self.start, self.stop = contig, start, stop
    
    def __repr__(self):
        return 'Roi({}, {}, {})'.format(self.contig, self.start, self.stop)
        
    def __str__(self):
        return 'Roi({}, {}, {})'.format(self.contig, self.start, self.stop)


def ceildiv(a, b):
    r"""Simple ceiling division to prevent importing math module
    
    Args:
        a (:obj:`numbers.Integral`): numerator
        b (:obj:`numbers.Integral`): denominator
    
    Returns:
        ceiling quotient of a and b
    """
    return -(-a // b)


def flag_decode(flag_code):
    r"""Simple read alignment flag decoder
    
    Every read within a BAM file ought to have an associated flag code. Theses
    flags are used for read filtering and QC. The flags are described below. 
    Additionally, they can be found `here <https://samtools.github.io/hts-specs/SAMv1.pdf>`_
    
    Any given read's flag is determined by the *or* (`|`) operand of all appropriate bit flags.
    
    Args:
        flag_code (int): either a standalone integer/bit flag or the read object itself
    
    Returns:
        (:obj:`list` of :obj:`tuple`): list of flag and flag description tuples.
    
    Raises:
        ValueError: if provided flag is not a valid entry
    
    Example:
        If a flag is 516 it is comprised of flag 4 and flag 512
        
        >>> flag_decode(516)
        [(4, 'read unmapped'), (512, 'QC fail')]
    
    Flags
    =====
    
    ====  =====  ==================================================================
    Int   Bit    Description
    ====  =====  ==================================================================
    
    1     0x1    Template having multiple segments in sequencing
    2     0x2    Each segment properly aligned according to the aligner
    4     0x4    Segment unmapped
    8     0x8    Next segment in the template unmapped
    16    0x10   SEQ being reverse complemented
    32    0x20   SEQ of the next segment in the template being reverse complemented
    64    0x40   The first segment in the template
    128   0x80   The last segment in the template
    256   0x100  Secondary alignment
    512   0x200  Not passing filters, such as platform/vendor quality controls
    1024  0x400  PCR or optical duplicate
    2048  0x800  Supplementary alignment
    ====  =====  ==================================================================
    
    """
    flags = {0x1 : 'read paired', 0x2: 'read mapped in proper pair',
            0x4: 'read unmapped', 0x8: 'mate unmapped',
            0x10: 'read reverse strand', 0x20: 'mate reverse strand',
            0x40: 'first in pair', 0x80: 'second in pair',
            0x100: 'secondary alignment', 0x200: 'QC fail',
            0x400: 'PCR or optical duplicate', 0x800: 'supplementary alignment'}
            
    if isinstance(flag_code, numbers.Integral):
        code = flag_code
    else:
        code = flag_code.flag
    if not isinstance(code, numbers.Integral):
        raise ValueError('Provided flag is not a valid entry')
    return [(key, flags[key]) for key in flags if key & code]


def yes_no():
    """ Simple prompt parser"""
    yes = set('yes','ye', 'y', '')
    no = set('no', 'n')
    while True:
        answer = input('Would you like to continue? [y/n] ').lower()
        if answer in yes:
            return True
        elif answer in no:
            return False
        else:
            print('Please answer "Yes" or "No"')


def region_parser(ROI, *args, **kwargs):
    r"""Parses genomic regions provided by the user.
    
    This function accepts SAM formatted regions (e.g. `'chr1:1-100'`), tab-separated
    region strings (e.g. `'chr1\t1\100'`), and positional arguments such that the 
    first argument is the string of the desired chromosome/contig. Any following 
    arguments must be integers. Lastly, if the user requires either the whole
    chromosome/contig or everything after a start position, the user should invoke
    `until_eof = True` beforehand.
    
    Args:
        ROI: either a SAM formatted region, tab-delimited region string, or iterable sequence object
        *args: variable length positional arguments containing integers for start and stop positions
        **kwags: Only implemented `kwarg` is `until_eof`
    
    Returns:
        :obj:`Roi` formatted object or None
    
    Raises:
        ValueError if the region submission is malformed or invalid
    
    Examples:
    
        >>> region_parser(['chr1', 1, 100])
        Roi(chr1, 1, 100)
        
        >>> region_parser('chr1:1-100')
        Roi(chr1, 1, 100)
        
    """
    
    # check to see if the user supplied positional arguments
    if len(args) > 0:
        ROI = [ROI] + list(args)
    
    # see if user supplied a SAM formatted region string
    elif isinstance(ROI, str):
        split_roi = ':'.join(ROI.split()).replace('-',':').split(':')
    
    # if the user supplied an :obj:`abc.Sequence` (tuple or list), convert it to a list
    elif isinstance(ROI, Sequence):
        split_roi = list(ROI)
    else:
        raise ValueError('Malformed region query')
    
    # if the user gives an integer description of chromosome, convert to string
    if type(split_roi[0]) is int:
        split_roi[0] = str(split_roi[0])
    elif isinstance(split_roi[0], str):
        split_roi[0] = split_roi[0].lower()
    else:
        raise ValueError('improper region format')
    
    # make sure the user didn't put multiple positional arguments
    if not 1 <= len(split_roi) <= 3:
        raise ValueError('Improper region format')
    
    # convert start and stop to integers
    for i, arg in enumerate(split_roi[1:]):
        split_roi[i+1] = int(arg)
    
    # make sure the user wants to continue if they have used an open-ended region
    if len(split_roi) <= 2:
        if not kwargs['until_eof']:
            warnings.warn('Fetching till end of contig. Potentially large region', RuntimeWarning )
            if yes_no():
                if len(split_roi) == 2:
                    return Roi(split_roi[0], int(split_roi[1]))
                else:
                    return Roi(split_roi[0])
            else:
                raise ValueError('User declined action')
        else:
            if len(split_roi) == 2:
                return Roi(split_roi[0], int(split_roi[1]))
            else:
                return Roi(split_roi[0])
    elif len(split_roi) == 3:
        return Roi(split_roi[0], int(split_roi[1]), int(split_roi[2]))
    else:
        return None


def unpack(fmt, _io):
    """Utility function for unpacking binary data from file object or byte
    stream.
    
    Args:
        fmt (str): the string format of the binary data to be unpacked
        _io: built-in binary format reader (default: io.BufferedRandom)
    
    Returns:
        unpacked contents from _io based on fmt string
    """
    size = struct.calcsize(fmt)
    try:
        # if it is byte object
        out = struct.unpack(fmt, _io)
    except:
        # if it is a file object
        out = struct.unpack(fmt, _io.read(size))
    if len(out) > 1:
        return out
    else:
        return out[0]


def make_virtual_offset(block_start_offset, within_block_offset):
    """Compute a BGZF virtual offset from block start and within block offsets.

    The BAM indexing scheme records read positions using a 64 bit
    'virtual offset', comprising in C terms:

    block_start_offset << 16 | within_block_offset

    Here block_start_offset is the file offset of the BGZF block
    start (unsigned integer using up to 64-16 = 48 bits), and
    within_block_offset within the (decompressed) block (unsigned
    16 bit integer).

    >>> make_virtual_offset(0, 0)
    0
    >>> make_virtual_offset(0, 1)
    1
    >>> make_virtual_offset(0, 2**16 - 1)
    65535
    >>> make_virtual_offset(0, 2**16)
    Traceback (most recent call last):
    ...
    ValueError: Require 0 <= within_block_offset < 2**16, got 65536
    """
    if within_block_offset < 0 or within_block_offset >= 65536:
       raise ValueError("Require 0 <= within_block_offset < 2**16, got %i" %
                        within_block_offset)
    if block_start_offset < 0 or block_start_offset >= 281474976710656:
       raise ValueError("Require 0 <= block_start_offset < 2**48, got %i" %
                        block_start_offset)
    return (block_start_offset << 16) | within_block_offset


def split_virtual_offset(virtual_offset):
    """Divides a 64-bit BGZF virtual offset into block start & within block offsets.

    >>> (100000, 0) == split_virtual_offset(6553600000)
    True
    >>> (100000, 10) == split_virtual_offset(6553600010)
    True

    """
    coffset = virtual_offset >> 16
    uoffset = virtual_offset ^ (coffset << 16)
    return coffset, uoffset


class LruDict(OrderedDict):
    """Simple least recently used (LRU) based dictionary that caches a given
    number of items.
    """
    
    # Need to check for versioning to ensure move-to-end is available
    import sys
    _PY_VERSION = sys.version

        
    def __init__(self, *args, **kwargs):
        """ Initialize the dictionary based on collections.OrderedDict
        
        Args:
            *args : basic positional arguments for dictionary creation
            max_cache (int): integer divisible by 2 to set max size of dictionary
            **kwargs: basic keyword arguments for dictionary creation
        """
        try:
            max_cache= kwargs.pop('max_cache', 128)
        except AttributeError:
            max_cache = 128
        OrderedDict.__init__(self, *args, **kwargs)
        self.max_cache = max_cache
        self.cull()
    
    def __str__(self):
        return 'LruDict({})'.format(self.items())
    
    def __repr__(self):
        return 'LruDict({})'.format(self.items())
    
    def cull(self):
        """Main driver function for removing LRU items from the dictionary. New
        items are added to the bottom, and removed in a FIFO order.
        """
        if self.max_cache:
            overflow = max(0, len(self) - self.max_cache)
            if overflow:
                for _ in range(overflow):
                    self.popitem(last=False)
    
    def __getitem__(self, key):
        """ Basic getter that renews LRU status upon inspection
        
        Args:
            key (str): immutable dictionary key
        """
        try:
            value = OrderedDict.__getitem__(self, key)
            
            if float(_PY_VERSION[:3]) <= 3.2:
                if not key == list(self.keys())[-1]:
                    moving = self.pop(key)
                    self[key] = moving
            else:
                self.move_to_end(key)
            return value
        except KeyError:
            pass
    
    def __setitem__(self, key, value):
        """Basic setter that adds new item to dictionary, and then performs cull()
        to ensure max_cache has not been violated.
        
        Args:
            key (str): immutable dictionary key
            value (any): any dictionary value
        """
        OrderedDict.__setitem__(self, key, value)
        self.cull()


_CIGAR_OPS = {'M': ('BAM_CMATCH', 0), 'I': ('BAM_CINS', 1), 'D': ('BAM_CDEL', 2),
            'N': ('BAM_CREF_SKIP', 3), 'S': ('BAM_CSOFT_CLIP', 4),
            'H': ('BAM_CHARD_CLIP', 5), 'P': ('BAM_CPAD', 6), '=': ('BAM_CEQUAL', 7),
            'X': ('BAM_CDIFF', 8), 'B': ('BAM_CBACK', 9)}
        

def parse_cigar(cigar_str):
    '''Parses a CIGAR string and turns it into a list of tuples
    
    Args:
        cigar_str (str): the CIGAR string as shown in SAM entry
    
    Returns:
        cigar_array (list): list of tuples of CIGAR operations (by id) and number of operations
    '''
    cigar_array = []
    for cigar_op in re.finditer(r'(?P<n_op>\d+)(?P<op>\w)', cigar_str):
        op_dict = cigar_op.groupdict()
        n_ops = int(op_dict['n_op'])
        op = _CIGAR_OPS[op_dict['op']]
        cigar_array.append((op,n_ops))
    return cigar_array


def cigar_changes(seq, cigar):
    '''Recreates the reference sequence to the extent that the CIGAR string can 
        represent.
    
    Args:
        seq (str): aligned segment sequence
        cigar (list): list of tuples of cigar operations (by id) and number of operations
    
    Returns:
        cigar_formatted_ref (str): a version of the aligned segment's reference
                                   sequence given the changes reflected in the cigar string
    
    Raises:
        ValueError: if CIGAR string is invalid
    '''
    if type(cigar) == str:
        cigar = parse_cigar(cigar)
    elif type(cigar) == list:
        pass
    else:
        raise ValueError('CIGAR must be string or list of tuples of cigar operations (by ID) and number of operations')
    cigar_formatted_ref = ''
    last_cigar_pos = 0
    for op, n_ops in cigar:
        if op in {0, 7, 8}: # matches (uses both sequence match & mismatch)
            cigar_formatted_ref += seq[last_cigar_pos:last_cigar_pos + n_ops]
            last_cigar_pos += n_ops
        elif op in {1, 4}: # insertion or clips
            last_cigar_pos += n_ops
        elif op == 3: # intron or large gaps
            tmp_ref_seq += 'N' * n_ops
        elif op == 5:
            pass
        else:
            raise ValueError('Invalid CIGAR string')
    return cigar_formatted_ref


def md_changes(seq, md_tag):
    '''Recreates the reference sequence of a given alignment to the extent that the 
    MD tag can represent. Used in conjunction with `cigar_changes` to recreate the 
    complete reference sequence
    
    Args:
        seq (str): aligned segment sequence
        md_tag (str): MD tag for associated sequence
    
    Returns:
        ref_seq (str): a version of the aligned segment's reference sequence given
                       the changes reflected in the MD tag
    '''
    ref_seq = ''
    last_md_pos = 0
    for mo in re.finditer(r'(?P<matches>\d+)|(?P<del>\^\w+?)|(?P<sub>\w)', md_tag):
        mo_group_dict = mo.groupdict()
        if mo_group_dict['matches'] is not None:
            matches = int(mo_group_dict['matches'])
            ref_seq += seq[last_md_pos:last_md_pos + matches]
            last_md_pos += matches
        elif mo_group_dict['del'] is not None:
            deletion = mo_group_dict['del']
            ref_seq += deletion[1:]
        elif mo_group_dict['sub'] is not None:
            substitution = mo_group_dict['sub']
            ref_seq += substitution
            last_md_pos += 1
        else:
            pass
    return ref_seq