import copy
from environments import *
import itertools
import os
import pprint
import random

import WlRunner

def ParameterCombinations(parameter_dict):
    """
    Get all the cominbation of the values from each key
    http://tinyurl.com/nnglcs9
    Input: parameter_dict={
                    p0:[x, y, z, ..],
                    p1:[a, b, c, ..],
                    ...}
    Output: [
             {p0:x, p1:a, ..},
             {..},
             ...
            ]
    """
    d = parameter_dict
    return [dict(zip(d, v)) for v in itertools.product(*d.values())]



def build_one_run(pattern_tuple, bs, usefs, conf, traffic_size, file_size,
        fdatasync, bssplit):
    job = WlRunner.fio.JobDescription()
    # traffic_size = 1 * GB
    # traffic_size = 512 * KB

    if not usefs:
        global_sec =  {
                        'global': {
                            'ioengine'  : 'libaio',
                            'io_size'   : int(traffic_size),
                            'size'  : int(file_size),
                            'filename'  : '/dev/sdc',
                            'direct'    : 1,
                            'iodepth'   :1,
                            'bs'        : bs,
                            'bssplit'   : bssplit
                            }
                }
    else:
        # with filesystem
        global_sec =  {
                        'global': {
                            'ioengine'  : 'sync',
                            'io_size'   : int(traffic_size),
                            'filesize'  : int(file_size),
                            'bs'        : bs,
                            'iodepth'   :1,
                            'fdatasync'     :fdatasync,
                            'bssplit'   : bssplit,
                            'direct'    :1
                            }
                }
    job.add_section(global_sec)

    for i, pat in enumerate(pattern_tuple):
        # jobname = '-'.join(['JOB', "_".join(pattern_tuple), pat, str(i)])
        if not usefs:
            d = { pat:
                        {
                         'rw': pat,
                         'offset': i * traffic_size
                         # 'write_iolog': 'joblog.'+str(i)
                        }
                }
        else:
            # use file system
            d = { pat:
                        {
                         'rw': pat,
                         # 'write_iolog': 'joblog.'+str(i)
                         'filename': os.path.join(conf['fs_mount_point'],
                                        'fio.data.'+str(i))
                        }
                }

        job.add_section(d)

    return job

def build_runs_with_a_set_of_patterns(blocksize, traffic_size, fs, dev_mb, file_size, fdatasync,
        bssplit):
    patterns = ['read', 'write', 'randread', 'randwrite']
    two_ways = list(itertools.combinations_with_replacement(patterns, 2))
    patterns = [ (p, ) for p in patterns]
    patterns.extend(two_ways)

    # override
    # patterns = [('randwrite', 'randwrite'), ('randwrite',)]
    patterns = [('randwrite', )]

    parameters = [ {'pattern': p} for p in patterns ]

    for para in parameters:
        para['bs'] = blocksize
        para['traffic_size'] = int(traffic_size)
        para['fs'] = fs
        para['dev_mb'] = dev_mb
        para['file_size'] = file_size
        para['fdatasync'] = fdatasync
        para['bssplit'] = bssplit

    return parameters

def build_patterns():
    # for blocksize in [4*KB, 64*KB, 256*KB]:
    para_dict = {
            'blocksize'      : [WlRunner.fio.HIDE_ATTR],
            'fs'             : ['ext4'],
            'dev_mb'         : [1024],
            'file_size'      : [256*MB],
            'traffic_size'   : [256*MB],
            'fdatasync'      : [WlRunner.fio.HIDE_ATTR],
            'bssplit'        : ['8kb/100', '8kb/95:64kb/5', '8kb/50:64kb/50',
                                '8kb/5:64kb/95', '64kb/100']
            }

    parameter_combs = ParameterCombinations(para_dict)

    parameters = []
    for para in parameter_combs:
        # para = copy.deepcopy(para_item)
        pattern_set = build_runs_with_a_set_of_patterns(blocksize = para['blocksize'],
                                  fs        = para['fs'],
                                  dev_mb    = para['dev_mb'],
                                  traffic_size = para['traffic_size'],
                                  file_size = para['file_size'],
                                  fdatasync = para['fdatasync'],
                                  bssplit   = para['bssplit']
                                  )
        parameters.extend(pattern_set)

    parameters = parameters * 2
    random.shuffle( parameters )
    pprint.pprint( parameters )

    return parameters

