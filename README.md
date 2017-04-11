FYI, I am currently editting this README....Mon 10 Apr 2017 10:32:58 PM CDT

WiscSee is an I/O workload analyzer that helps you understand your application
performance on SSDs. WiscSee comes with a fully functioning trace-driven SSD simulator,
WiscSim, which supports enhanced versions of multiple well-known FTLs, NCQ, multiple
channels, garbage collections, wear-leveling, page allocation policies and more.
WiscSim is implemented as a Discrete-Event Simulator.

WiscSee runs your application, collects its block I/O trace, and later feeds the trace
to WiscSim.

In this README file, you will learn

- How to download and setup WiscSee
- How to run helpful examples of WiscSee
- How to quickly start running your application on an SSD simulator
- How to produce zombie curves (a useful way of studying garbage collection overhead of your applications)

# Download and Setup

### Option 1: VM Image

We made a VirtualBox VM Image that has the complete environment ready (Ubuntu
16.04 + WiscSee + dependencies). You do not need to do any configuration. It is the easiest
option in terms of setting up. It is garanteed to run.

In order to use this option, you need to have VirtualBox (https://www.virtualbox.org/) installed before starting the following steps.

1. Download VirtualBox Image from the following address: 

```
http://pages.cs.wisc.edu/~jhe/wiscsee-vm.tar.gz
```

The SHA256 sum of the file is:

```
80c5f586d525e0fa54266984065b2b727f71c45de8940aafd7247d49db8e0070
```

2. Untar the downloaded file

3. Open the VM image with VirtualBox. 

This VM image may also work with other VM manager.

4. Login to the guest OS

```
Username: wsee
Password: abcabc
```

5. Run tests

```
cd /home/wsee/workdir/wiscsee
make test_all
```

The root password is:

```
abcabc
```

### Option 2: Git clone

WiscSee was developed in Ubuntu 14.04 with Kernel 4.5.4. Other variants of Linux
should also work. But you may need to modify `setup.env.sh` to use different
Linux package managers.

0. Clone

```
git clone https://github.com/junhe/wiscsee.git
```

1. Setup

```
cd wiscsee
make setup
```

`make setup` will execute `setup.env.sh`, which installs the dependencies of
WiscSee. 

2. Run tests

```
make test_all
```

# Run Examples

Running and reading the examples is a great way to learn WiscSee. The code of
the examples is in `tests/test_demo.py`.

To run the examples, run the following command in the WiscSee directory.

```
make run_demo
```

The examples include:

1. Collect I/O traces of running an application on a file system. You can use R
   to directly read the refined trace file for analysis. 
2. Collect I/O traces and feed the traces to the SSD simulator with DFTLDES (DFTLDES
   is an FTL based on DFTL. It is implemented as discrete-event simulation and
   supports multiple channels, NCQ, multiple page allocation strategies, logical
   space segmentation, ...) The results show various statistis about the
   internal states of the SSD.
3. Collect I/O traces and feed the traces to the SSD simulator with NKFTL (NKFTL is
   a configurable hybrid mapping FTL based on "A reconfigurable FTL (flash
   translation layer) architecture for NAND flash-based applications" by Chanik
   Park et al.. I call it "NKFTL" because the authors name the two most
   important parameters N and K. NKFTL can be configured to act like other FTLs
   such as FAST. NKFTL is implemented as discrete-event simulation and
   supports multiple channels, NCQ, multiple page allocation strategies, ...)
4. Feed synthetic trace to the SSD simulator. This is useful if you want to test
   customized access patterns on LBA. 
5. Feed existing I/O traces to the SSD simulator. Doing so avoids running the
   application for each simulation.
6. Analyze Request Scale (request size, NCQ depth) of existing traces.
7. Run an application and analyze its request scale.
8. Analyze Locality of existing traces.
9. Analyze Aligned Sequentiality of existing traces.
10. Analyze Grouping by Death Time of existing traces. By the results, you
    will be able to plot zombie curves.
11. Analyze Uniform Data Lifetime of existing traces.


# Tutorial: run your application on an SSD simulator

In this short tutorial, let's assume that the application we study is the Linux `dd`
command. We also pretend that `/dev/loop0` is an SSD. We will use `dd` to write
to a file system mounted on `/dev/loop0`. We simulate this workload on an SSD
simulator.

#### 1. Specify your application 

Open `workrunner/workload.py`, add the following code

```
class LinuxDD(Workload):
    def __init__(self, confobj, workload_conf_key = None):
        super(LinuxDD, self).__init__(confobj, workload_conf_key)

    def run(self):
        mnt = self.conf["fs_mount_point"]
        cmd = "dd if=/dev/zero of={}/datafile bs=64k count=128".format(mnt)
        print cmd
        subprocess.call(cmd, shell=True)
        subprocess.call("sync")

    def stop(self):
        pass
```

In the next step we will tell WiscSee to use this class.

#### 2. Setup Experiment

Open `tests/test_demo.py`, add the following code

```
class Test_TraceAndSimulateLinuxDD(unittest.TestCase):
    def test_run(self):
        class LocalExperiment(experiment.Experiment):
            def setup_workload(self):
                self.conf['workload_class'] = "LinuxDD"

        para = experiment.get_shared_nolist_para_dict("test_exp_LinuxDD", 16*MB)
        para['device_path'] = "/dev/loop0" 
        para['filesystem'] = "ext4"
        para['ftl'] = "dftldes"
        Parameters = collections.namedtuple("Parameters", ','.join(para.keys()))
        obj = LocalExperiment( Parameters(**para) )
        obj.main()
```

We implement the experiment as a test for convenience of this tutorial.

`self.conf['workload_class'] = "LinuxDD"` tells WiscSee to use class `LinuxDD`
to run the application. 

You may check `./config_helper/experiment.py` and `config.py` for more options
of experiments.


#### 3. Run

```
./run_testclass.sh tests.test_demo.Test_TraceAndSimulateLinuxDD
```

#### 4. Check Results

WiscSee puts results to `/tmp/results/`. In my case, the results of this
experiment is in
`/tmp/results/test_exp_LinuxDD/subexp--3884625007297461212-ext4-04-10-11-48-16-3552120672700940123`.
In the directory, you will see the following files.

```
accumulator_table.txt                   value of various counters set in the simulator
app_duration.txt                        duration of running application (wall clock time)
blkparse-output-mkfs.txt                raw trace of mkfs from blktrace
blkparse-output.txt                     raw trace of running the  application on file system from blktrace
blkparse-events-for-ftlsim-mkfs.txt     refined trace
blkparse-events-for-ftlsim.txt          refined trace 
config.json                             the configuration of the experiment
dumpe2fs.out                            dumpe2fs results of ext4  
recorder.json                           various statistics, such as valid ratio distributions, number of flash writes, ...
recorder.log                            no longer used
```

# Producing zombie curves

Zombie curve is a way of characterizing GC overhead of a workload. A zombie curve
shows the sorted valid ratios (# of valid pages in a block / # of pages in a
block) of flash blocks with live data. It looks like the one below.

![Zombie Curve](media/zombie-curve.png)

Many of the examples in `tests/test_demo.py` produce data for zombie curves. The
data is stored in `recorder.json`. For example, class `TestGrouping` produces the
following entry in `recorder.json`.

```
    "ftl_func_valid_ratios": [
        {
            "1.00": 128
        }, 
        {
            "1.00": 240, 
            "0.91": 4, 
            "0.92": 12
        }, 
        {
            "0.69": 6, 
            "1.00": 368, 
            "0.67": 10
        }, 
        {
            "1.00": 496, 
            "0.17": 10, 
            "0.19": 6
        }, 
        ...
    ]
```

Each `{...}` is a snapshot of the valid ratio counts. For example, `"0.91": 4`
indicates that there are `4` flash blocks with valid ratio `0.91`. 

Using the data in `ftl_func_valid_ratios`, you can create an animation of how
the valid ratios change over time. 


# Notes

The simulation is written with Simpy (https://simpy.readthedocs.io/en/latest/).
You may want to learn some Simpy before modifying the core simulation code. 

If you have any questions, please open an issue at
https://github.com/junhe/wiscsee/issues. I'll be happy to help. 


# Citation

Please use the following bib to cite WiscSee:

```
@InProceedings{He17-Eurosys,
           title = "{The Unwritten Contract of Solid State Drives}",
          author = "{Jun He, Sudarsun Kannan, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau}",
       booktitle = "EuroSys '17",
           month = "April",
            year = "2017",
         address = "Belgrade, Serbia",
}
```


