import collections

from config import LBAGENERATOR
from utilities import utils
from experimenter import *


def wearleveling_bench():
    class LocalExperimenter(Experimenter):
        def setup_workload(self):
            flashbytes = self.para.lbabytes
            zone_size = flashbytes / 8

            self.conf["workload_src"] = LBAGENERATOR
            self.conf["lba_workload_class"] = "AccessesWithDist"
            self.conf["age_workload_class"] = "NoOp"

            self.conf['AccessesWithDist'] = {
                    'lba_access_dist' : self.para.access_distribution,
                    'chunk_size'      : self.para.chunk_size,
                    'traffic_size'    : self.para.traffic_size,
                    'space_size'      : self.para.space_size,
                    'skew_factor'     : self.para.skew_factor,
                    'zipf_alpha'      : self.para.zipf_alpha,
                    }

    class ParaDict(object):
        def __init__(self):
            expname = utils.get_expname()
            lbabytes = 64*MB
            para_dict = get_shared_para_dict(expname, lbabytes)
            para_dict.update( {
                    'ftl'              : ['dftldes'],
                    'enable_simulation': [True],
                    'over_provisioning': [1.28], # 1.28 is a good number
                    'gc_high_ratio'    : [0.9],
                    'gc_low_ratio'     : [0.8],
                    'not_check_gc_setting': [False],
                    'cache_mapped_data_bytes' :[int(1*lbabytes)],
                    'segment_bytes'    : [lbabytes],
                    'snapshot_interval': [1*SEC],

                    'chunk_size'       : [64*KB],
                    'traffic_size'     : [1024*MB],
                    'space_size'       : [lbabytes],

                    'access_distribution' : ['uniform', 'hotcold', 'zipf'],
                    'skew_factor'      : [10],
                    'zipf_alpha'       : [1],
                    })
            self.parameter_combs = ParameterCombinations(para_dict)

        def __iter__(self):
            return iter(self.parameter_combs)

    def main():
        print 'here'
        for para in ParaDict():
            print para
            Parameters = collections.namedtuple("Parameters", ','.join(para.keys()))
            obj = LocalExperimenter( Parameters(**para) )
            obj.main()

    main()



def main(cmd_args):
    if cmd_args.git == True:
        shcmd("sudo -u jun git commit -am 'commit by Makefile: {commitmsg}'"\
            .format(commitmsg=cmd_args.commitmsg \
            if cmd_args.commitmsg != None else ''), ignore_error=True)
        shcmd("sudo -u jun git pull")
        shcmd("sudo -u jun git push")


def _main():
    parser = argparse.ArgumentParser(
        description="This file hold command stream." \
        'Example: python Makefile.py doexp1 '
        )
    parser.add_argument('-t', '--target', action='store')
    parser.add_argument('-c', '--commitmsg', action='store')
    parser.add_argument('-g', '--git',  action='store_true',
        help='snapshot the code by git')
    args = parser.parse_args()

    if args.target == None:
        main(args)
    else:
        # WARNING! Using argument will make it less reproducible
        # because you have to remember what argument you used!
        targets = args.target.split(';')
        for target in targets:
            eval(target)
            # profile.run(target)

if __name__ == '__main__':
    _main()




