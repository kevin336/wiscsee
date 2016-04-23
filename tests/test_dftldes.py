import unittest
import simpy

from ssdbox import ftlsim_commons

import ssdbox
from utilities import utils
import flashcontroller
from ssdbox.ftlsim_commons import Extent
from ssdbox.dftldes import LpnTable, LpnTableMvpn
from config import WLRUNNER, LBAGENERATOR, LBAMULTIPROC
from commons import *
from Makefile import workflow

class FtlTest(ssdbox.dftldes.Ftl):
    def get_mappings(self):
        return self._mappings

    def get_directory(self):
        return self._directory


def create_config():
    conf = ssdbox.dftldes.Config()
    conf['SSDFramework']['ncq_depth'] = 1

    conf['flash_config']['n_pages_per_block'] = 64
    conf['flash_config']['n_blocks_per_plane'] = 2
    conf['flash_config']['n_planes_per_chip'] = 1
    conf['flash_config']['n_chips_per_package'] = 1
    conf['flash_config']['n_packages_per_channel'] = 1
    conf['flash_config']['n_channels_per_dev'] = 4

    utils.set_exp_metadata(conf, save_data = False,
            expname = 'test_expname',
            subexpname = 'test_subexpname')

    conf['ftl_type'] = 'dftldes'
    conf['simulator_class'] = 'SimulatorDESSync'

    devsize_mb = 64
    conf.n_cache_entries = conf.n_mapping_entries_per_page
    conf.set_flash_num_blocks_by_bytes(int(devsize_mb * 2**20 * 1.28))

    utils.runtime_update(conf)

    return conf


def create_recorder(conf):
    rec = ssdbox.recorder.Recorder(output_target = conf['output_target'],
        output_directory = conf['result_dir'],
        verbose_level = conf['verbose_level'],
        print_when_finished = conf['print_when_finished']
        )
    rec.disable()
    return rec

def create_oob(conf):
    oob = ssdbox.dftldes.OutOfBandAreas(conf)
    return oob

def create_blockpool(conf):
    return ssdbox.dftldes.BlockPool(conf)

def create_flashcontrolelr(conf, env, rec):
    return flashcontroller.controller.Controller3(env, conf, rec)

def create_simpy_env():
    return simpy.Environment()

def create_translation_directory(conf, oob, block_pool):
    return ssdbox.dftldes.GlobalTranslationDirectory(conf, oob, block_pool)

def create_mapping_on_flash(conf):
    return ssdbox.dftldes.MappingOnFlash(conf)

def create_victimblocks():
    conf = create_config()
    block_pool = create_blockpool(conf)
    oob = create_oob(conf)

    vbs = ssdbox.dftldes.VictimBlocks(conf, block_pool, oob)

    return vbs

def create_obj_set(conf):
    rec = create_recorder(conf)
    oob = create_oob(conf)
    block_pool = create_blockpool(conf)
    env = create_simpy_env()
    flash_controller = create_flashcontrolelr(conf, env, rec)
    directory = create_translation_directory(conf, oob, block_pool)
    gmt = create_mapping_on_flash(conf)
    victimblocks = ssdbox.dftldes.VictimBlocks(conf, block_pool, oob)

    return {'conf':conf, 'rec':rec, 'oob':oob, 'block_pool':block_pool,
            'flash_controller':flash_controller, 'env':env, 'directory':directory,
            'mapping_on_flash':gmt, 'victimblocks':victimblocks}


def create_mapping_cache(objs):
    mapping_cache = ssdbox.dftldes.MappingCache(
            confobj = objs['conf'],
            block_pool = objs['block_pool'],
            flashobj = objs['flash_controller'],
            oobobj = objs['oob'],
            recorderobj = objs['rec'],
            envobj = objs['env'],
            directory = objs['directory'],
            mapping_on_flash = objs['mapping_on_flash'])

    return mapping_cache


def create_datablockcleaner(objs):
    mappings = create_mapping_cache(objs)
    datablockcleaner = ssdbox.dftldes.DataBlockCleaner(
            conf = objs['conf'],
            flash = objs['flash_controller'],
            oob = objs['oob'],
            block_pool = objs['block_pool'],
            mappings = mappings,
            rec = objs['rec'],
            env = objs['env'])
    return datablockcleaner


class TestMappingTable(unittest.TestCase):
    def test_modification(self):
        config = create_config()
        table = ssdbox.dftldes.MappingTable(config)

        ppn = table.lpn_to_ppn(100)
        self.assertEqual(ppn, ssdbox.dftldes.MISS)

        table.add_new_entry(lpn = 100, ppn = 200, dirty = False)
        ppn = table.lpn_to_ppn(100)
        self.assertEqual(ppn, 200)

        table.overwrite_entry(lpn = 100, ppn = 201, dirty = False)
        ppn = table.lpn_to_ppn(100)
        self.assertEqual(ppn, 201)

    def test_deleting_mvpn(self):
        config = create_config()
        table = ssdbox.dftldes.MappingTable(config)

        table.add_new_entry(lpn = 0, ppn = 100, dirty = False)
        # add an entry of another m_vpn
        table.add_new_entry(lpn = 100000, ppn = 2, dirty = False)

        table.delete_entries_of_m_vpn(m_vpn = 0)
        self.assertEqual(table.lpn_to_ppn(0), ssdbox.dftldes.MISS)
        self.assertEqual(table.lpn_to_ppn(100000), 2)

    def test_size(self):
        config = create_config()
        table = ssdbox.dftldes.MappingTable(config)

        self.assertEqual(config.n_cache_entries, table.max_n_entries)
        self.assertEqual(table.count(), 0)
        table.add_new_entry(lpn = 0, ppn = 100, dirty = False)
        self.assertEqual(table.count(), 1)
        table.remove_entry_by_lpn(lpn = 0)
        self.assertEqual(table.count(), 0)

    def test_lru(self):
        config = create_config()
        table = ssdbox.dftldes.MappingTable(config)

        table.add_new_entry(lpn = 0, ppn = 100, dirty = False)
        table.add_new_entry(lpn = 100000, ppn = 2, dirty = False)

        victim_lpn, _ = table.victim_entry()
        self.assertEqual(victim_lpn, 0)

        _ = table.lpn_to_ppn(0)
        victim_lpn, _ = table.victim_entry()
        self.assertEqual(victim_lpn, 100000)

    def test_quiet_overwrite(self):
        config = create_config()
        table = ssdbox.dftldes.MappingTable(config)

        table.add_new_entry(lpn = 0, ppn = 100, dirty = False)
        table.add_new_entry(lpn = 100000, ppn = 2, dirty = False)

        victim_lpn, _ = table.victim_entry()
        self.assertEqual(victim_lpn, 0)

        table.overwrite_quietly(lpn = 0, ppn = 200, dirty = True)

        victim_lpn, _ = table.victim_entry()
        self.assertEqual(victim_lpn, 0)

        ppn = table.lpn_to_ppn(0)
        self.assertEqual(ppn, 200)


class TestMappingCache(unittest.TestCase):
    def update_m_vpn(self, objs, mapping_cache, m_vpn):
        conf = objs['conf']
        env = objs['env']
        lpns  = conf.m_vpn_to_lpns(m_vpn)
        for lpn in lpns:
            ppn = lpn * 1000
            yield env.process(mapping_cache.update(lpn, ppn))
            ppn_in_cache = yield env.process(mapping_cache.lpn_to_ppn(lpn))
            self.assertEqual(ppn, ppn_in_cache)

    def update_proc(self, objs, mapping_cache):
        conf = objs['conf']
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        yield env.process(self.update_m_vpn(objs, mapping_cache, m_vpn = 3))
        # it should not take any time
        self.assertEqual(env.now, 0)

        yield env.process(self.update_m_vpn(objs, mapping_cache, m_vpn = 4))
        # it should only write one flash page (m_vpn=3) back to flash
        self.assertEqual(env.now, time_program_page)

        lpns  = conf.m_vpn_to_lpns(3)
        lpn = lpns[0]
        ppn = yield env.process(mapping_cache.lpn_to_ppn(lpn))
        self.assertEqual(ppn, lpn * 1000)
        self.assertEqual(env.now, time_program_page + time_program_page + \
                time_read_page)

    def test_update(self):
        conf = create_config()
        conf.n_cache_entries = conf.n_mapping_entries_per_page
        objs = create_obj_set(conf)

        mapping_cache = create_mapping_cache(objs)

        env = objs['env']
        env.process(self.update_proc(objs, mapping_cache))
        env.run()

class TestParallelTranslation(unittest.TestCase):
    def write_proc(self, env, dftl, extent):
        yield env.process(dftl.write_ext(extent))

    def read_proc(self, env, dftl, extent):
        yield env.process(dftl.read_ext(extent))

    def access_same_vpn(self, env, dftl):
        # assert count of read and write

        # write data page ->
        writer1 = env.process(self.write_proc(env, dftl, ext))
        writer2 = env.process(self.write_proc(env, dftl, ext))

        yield env.events.AllOf([writer1, writer2])

        self.assertEqual(tp_read_count, 1)
        self.assertEqual(env.now, read + write)

    def access_different_vpn(self, env, dftl):
        # assert count of read and write
        reader = env.process(self.write_proc(env, dftl, ext1))
        writer = env.process(self.write_proc(env, dftl, ext2))

        yield env.events.AllOf([reader, writer])

        self.assertEqual(tp_read_count, 2)
        self.assertEqual(env.now, read + write)

    def test_parallel_translation(self):
        conf = create_config()
        objs = create_obj_set(conf)

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])


    def test_write(self):
        conf = create_config()
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

    def proc_test_write(self, env, dftl):
        pass

class TestWrite(unittest.TestCase):
    def test_write(self):
        conf = create_config()
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write(objs, dftl, Extent(0, 1)))
        env.run()

    def proc_test_write(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        rec = objs['rec']
        rec.enable()

        yield env.process(dftl.write_ext(ext))

        # read translation page and write data page in the same time
        self.assertEqual(env.now, max(time_read_page, time_program_page))
        self.assertEqual(rec.get_count_me("Mapping_Cache", "hit"), 0)
        self.assertEqual(rec.get_count_me("Mapping_Cache", "miss"), 1)

    def test_write_larger(self):
        conf = create_config()
        conf['stripe_size'] = 1

        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write_larger(objs, dftl, Extent(0, 2)))
        env.run()

    def proc_test_write_larger(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        rec = objs['rec']
        rec.enable()

        yield env.process(dftl.write_ext(ext))

        # writing 2 data page and reading trans page happens at the same time
        self.assertEqual(env.now, max(time_read_page, time_program_page))

        self.assertEqual(rec.get_count_me("Mapping_Cache", "miss"), 1)
        # The second lpn is a hit
        self.assertEqual(rec.get_count_me("Mapping_Cache", "hit"), 1)

    def test_write_larger2(self):
        conf = create_config()
        conf['stripe_size'] = 1
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write_larger2(objs, dftl,
            Extent(0, 4)))
        env.run()

    def proc_test_write_larger2(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        rec = objs['rec']
        rec.enable()

        yield env.process(dftl.write_ext(ext))

        # writing 4 data page and reading 1 trans page at the same time,
        # since there are only 4 channels, 1 trans read and one data page
        # write compete for one channel
        self.assertEqual(env.now, time_read_page + time_program_page)

        self.assertEqual(rec.get_count_me("Mapping_Cache", "miss"), 1)
        self.assertEqual(rec.get_count_me("Mapping_Cache", "hit"), 3)

    def test_write_2vpn(self):
        conf = create_config()
        conf['stripe_size'] = 1
        # make sure no cache miss in this test
        conf.n_cache_entries = conf.n_mapping_entries_per_page * 2

        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write_2vpn(objs, dftl,
            Extent(0, conf.n_mapping_entries_per_page * 2)))
        env.run()

    def proc_test_write_2vpn(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        rec = objs['rec']
        rec.enable()

        yield env.process(dftl.write_ext(ext))

        # read translation page, then write all 4 data pages at the same time
        self.assertEqual(env.now, time_read_page +
                (ext.lpn_count/4) * time_program_page)

        self.assertEqual(rec.get_count_me("Mapping_Cache", "miss"), 2)
        self.assertEqual(rec.get_count_me("Mapping_Cache", "hit"),
                objs['conf'].n_mapping_entries_per_page * 2 - 2)

    def test_write_outofspace(self):
        conf = create_config()
        conf['stripe_size'] = 1
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write_outofspace(objs, dftl,
            Extent(0, conf.total_num_pages())))
        env.run()

    def proc_test_write_outofspace(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        with self.assertRaises(ssdbox.blkpool.OutOfSpaceError):
            yield env.process(dftl.write_ext(ext))


class TestRead(unittest.TestCase):
    def test_read(self):
        conf = create_config()
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_read(objs, dftl, Extent(0, 1)))
        env.run()

    def proc_test_read(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        yield env.process(dftl.read_ext(ext))

        # only read translation page from flash
        # data page is not read since it is not initialized
        self.assertEqual(env.now, time_read_page)

    def test_read_larger(self):
        conf = create_config()
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        # read a whole m_vpn's lpn
        env.process(self.proc_test_read_larger(objs, dftl,
            Extent(0, conf.n_mapping_entries_per_page)))
        env.run()

    def proc_test_read_larger(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        yield env.process(dftl.read_ext(ext))

        # only read one translation page from flash
        # data page is not read since it is not initialized
        self.assertEqual(env.now, time_read_page)

    def _test_read_2tp(self):
        """
        This test fails because there is cache thrashing problem
        The solution should be that we prevent the translation page to be
        evicted while translating for a mvpn
        """
        conf = create_config()
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        # read two m_vpn's lpns
        env.process(self.proc_test_read_2tp(objs, dftl,
            Extent(0, 2 * conf.n_mapping_entries_per_page)))
        env.run()

    def proc_test_read_2tp(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        yield env.process(dftl.read_ext(ext))

        # read two translation page from flash,
        # at this time they are serialized
        # data page is not read since it is not initialized
        self.assertEqual(env.now, time_read_page * 2)


class TestSplit(unittest.TestCase):
    def test(self):
        conf = create_config()
        n = conf.n_mapping_entries_per_page

        result = ssdbox.dftldes.split_ext_to_mvpngroups(conf, Extent(0, n))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].lpn_start, 0)
        self.assertEqual(result[0].end_lpn(), n)

        result = ssdbox.dftldes.split_ext_to_mvpngroups(conf, Extent(0, n + 1))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].lpn_start, 0)
        self.assertEqual(result[0].end_lpn(), n)
        self.assertEqual(result[1].lpn_start, n)
        self.assertEqual(result[1].end_lpn(), n + 1)


class TestDiscard(unittest.TestCase):
    def test_discard(self):
        conf = create_config()
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_discard(objs, dftl, Extent(0, 1)))
        env.run()

    def proc_test_discard(self, objs, dftl, ext):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        yield env.process(dftl.discard_ext(ext))

        # need to read TP, then we mark the entry as UNINITIATED in mem
        # (the entry was UNINITIATED before)
        self.assertEqual(env.now, time_read_page)

        # it takes no time since the page is UNINITIATED
        yield env.process(dftl.read_ext(ext))
        self.assertEqual(env.now, time_read_page)

        # the mapping is in cache, you just need to write data page
        yield env.process(dftl.write_ext(ext))
        self.assertEqual(env.now, time_read_page + time_program_page)

        # now you need to really read a flash page as it is inintialized
        yield env.process(dftl.read_ext(ext))
        self.assertEqual(env.now, 2 * time_read_page + time_program_page)

        # discarding takes no time as mapping is in memory
        yield env.process(dftl.discard_ext(ext))
        self.assertEqual(env.now, 2 * time_read_page + time_program_page)


class TestLpnTable(unittest.TestCase):
    def test_init(self):
        table = LpnTable(8)
        self.assertEqual(table.n_free_rows(), 8)
        self.assertEqual(table.n_locked_free_rows(), 0)
        self.assertEqual(table.n_used_rows(), 0)

    def test_ops(self):
        """
        lock before adding, also you need to tell it which row you add to
        """
        table = LpnTable(8)

        rowid = table.lock_free_row()
        self.assertEqual(table.n_free_rows(), 7)
        self.assertEqual(table.n_locked_free_rows(), 1)
        self.assertEqual(table.n_used_rows(), 0)

        table.add_lpn(rowid = rowid, lpn = 8, ppn = 88, dirty = True)
        self.assertEqual(table.lpn_to_ppn(8), 88)
        self.assertEqual(table.is_dirty(8), True)
        self.assertEqual(table.n_free_rows(), 7)
        self.assertEqual(table.n_locked_free_rows(), 0)
        self.assertEqual(table.n_used_rows(), 1)

        table.overwrite_lpn(lpn = 8, ppn = 89, dirty = False)
        self.assertEqual(table.lpn_to_ppn(8), 89)
        self.assertEqual(table.is_dirty(8), False)
        self.assertEqual(table.n_free_rows(), 7)
        self.assertEqual(table.n_locked_free_rows(), 0)
        self.assertEqual(table.n_used_rows(), 1)

        deleted_rowid = table.delete_lpn_and_lock(lpn = 8)
        self.assertEqual(rowid, deleted_rowid)
        self.assertEqual(table.has_lpn(8), False)
        self.assertEqual(table.n_free_rows(), 7)
        self.assertEqual(table.n_locked_free_rows(), 1)
        self.assertEqual(table.n_used_rows(), 0)

        table.unlock_free_row(rowid = deleted_rowid)
        self.assertEqual(table.n_free_rows(), 8)
        self.assertEqual(table.n_locked_free_rows(), 0)
        self.assertEqual(table.n_used_rows(), 0)

    def test_boundaries(self):
        table = LpnTable(8)

        for i in range(8):
            table.lock_free_row()

        self.assertEqual(table.lock_free_row(), None)

    def test_victim(self):
        conf = create_config()
        table = LpnTableMvpn(conf)

        rowid = table.lock_free_row()
        table.add_lpn(rowid = rowid, lpn = 8, ppn = 88, dirty = True)

        rowid = table.lock_free_row()
        table.add_lpn(rowid = rowid, lpn = 9, ppn = 99, dirty = True)

        victim_row = table.victim_row(None, [])

        self.assertEqual(victim_row.lpn, 8)

    def test_multiple_adds(self):
        table = LpnTable(8)

        locked_rows = table.lock_free_rows(3)
        self.assertEqual(len(locked_rows), 3)

        table.add_lpns(locked_rows, {1:11, 2:22, 3:33}, False)

        self.assertEqual(table.n_free_rows(), 5)
        self.assertEqual(table.n_locked_free_rows(), 0)
        self.assertEqual(table.n_used_rows(), 3)

        self.assertEqual(table.lpn_to_ppn(1), 11)
        self.assertEqual(table.lpn_to_ppn(2), 22)
        self.assertEqual(table.lpn_to_ppn(3), 33)

    def test_locking_lpn(self):
        table = LpnTable(8)

        locked_rows = table.lock_free_rows(3)
        self.assertEqual(len(locked_rows), 3)
        self.assertListEqual(locked_rows, [0,1,2])

        table.add_lpns(locked_rows, {1:11, 2:22, 3:33}, False)

        table.lock_lpn(1)
        self.assertEqual(table.n_free_rows(), 5)
        self.assertEqual(table.n_locked_free_rows(), 0)
        self.assertEqual(table.n_used_rows(), 2)
        self.assertEqual(table.n_locked_used_rows(), 1)


class TestVPNResourcePool(unittest.TestCase):
    def access_vpn(self, env, respool, vpn):
        req = respool.get_request(vpn)
        yield req
        yield env.timeout(10)
        respool.release_request(vpn, req)

    def init_proc(self, env, respool):
        procs = []
        for i in range(3):
            p = env.process(self.access_vpn(env, respool, 88))
            procs.append(p)

            p = env.process(self.access_vpn(env, respool, 89))
            procs.append(p)

        yield simpy.events.AllOf(env, procs)
        self.assertEqual(env.now, 30)

    def test_request(self):
        env = simpy.Environment()
        respool = ssdbox.dftldes.VPNResourcePool(env)

        env.process(self.init_proc(env, respool))
        env.run()


class TestParallelDFTL(unittest.TestCase):
    def setup_config(self):
        self.conf = ssdbox.dftldes.Config()
        self.conf['SSDFramework']['ncq_depth'] = 1

        self.conf['flash_config']['n_pages_per_block'] = 2
        self.conf['flash_config']['n_blocks_per_plane'] = 2
        self.conf['flash_config']['n_planes_per_chip'] = 1
        self.conf['flash_config']['n_chips_per_package'] = 1
        self.conf['flash_config']['n_packages_per_channel'] = 1
        self.conf['flash_config']['n_channels_per_dev'] = 4

    def setup_environment(self):
        metadata_dic = utils.choose_exp_metadata(self.conf, interactive = False)
        self.conf.update(metadata_dic)

        self.conf['enable_blktrace'] = True
        self.conf['enable_simulation'] = True

    def setup_workload(self):
        w = 'write'
        r = 'read'
        d = 'discard'

        self.conf["workload_src"] = LBAGENERATOR
        self.conf["lba_workload_class"] = "ExtentTestWorkloadFLEX2"
        self.conf["lba_workload_configs"]["ExtentTestWorkloadFLEX2"] = {
                "events": [
                    (d, 1, 3),
                    (w, 1, 3),
                    (r, 1, 3)
                    ]}
        self.conf["age_workload_class"] = "NoOp"

    def setup_ftl(self):
        self.conf['ftl_type'] = 'dftldes'
        self.conf['simulator_class'] = 'SimulatorDESNew'

        devsize_mb = 2
        self.conf.mapping_cache_bytes = self.conf.n_mapping_entries_per_page \
                * self.conf['cache_entry_bytes'] # 8 bytes (64bits) needed in mem
        self.conf.set_flash_num_blocks_by_bytes(int(devsize_mb * 2**20 * 1.28))

    def my_run(self):
        utils.runtime_update(self.conf)
        workflow(self.conf)

    def test_main(self):
        self.setup_config()
        self.setup_environment()
        self.setup_workload()
        self.setup_ftl()
        self.my_run()


class TestFTLwithMoreData(unittest.TestCase):
    def setup_config(self):
        self.conf = ssdbox.dftldes.Config()
        self.conf['SSDFramework']['ncq_depth'] = 2

        self.conf['flash_config']['page_size'] = 2048
        self.conf['flash_config']['n_pages_per_block'] = 4
        self.conf['flash_config']['n_blocks_per_plane'] = 8
        self.conf['flash_config']['n_planes_per_chip'] = 1
        self.conf['flash_config']['n_chips_per_package'] = 1
        self.conf['flash_config']['n_packages_per_channel'] = 1
        self.conf['flash_config']['n_channels_per_dev'] = 4


    def setup_environment(self):
        metadata_dic = utils.choose_exp_metadata(self.conf, interactive = False)
        self.conf.update(metadata_dic)

        self.conf['enable_blktrace'] = True
        self.conf['enable_simulation'] = True

    def setup_workload(self):
        self.conf["workload_src"] = LBAGENERATOR
        self.conf["lba_workload_class"] = "TestWorkloadFLEX3"

        traffic = 2*MB
        chunk_size = 32*KB
        page_size = self.conf['flash_config']['page_size']
        self.conf["lba_workload_configs"]["TestWorkloadFLEX3"] = {
                "op_count": traffic/chunk_size,
                "extent_size": chunk_size/page_size ,
                "ops": ['write'], 'mode': 'random'}
                # "ops": ['read', 'write', 'discard']}
        print self.conf['lba_workload_configs']['TestWorkloadFLEX3']
        self.conf["age_workload_class"] = "NoOp"

    def setup_ftl(self):
        self.conf['ftl_type'] = 'dftldes'
        self.conf['simulator_class'] = 'SimulatorDESNew'

        devsize_mb = 8
        entries_need = int(devsize_mb * 2**20 * 0.03 / self.conf['flash_config']['page_size'])
        self.conf.mapping_cache_bytes = 4 * self.conf.n_mapping_entries_per_page * self.conf['cache_entry_bytes'] # 8 bytes (64bits) needed in mem
        self.conf.set_flash_num_blocks_by_bytes(int(devsize_mb * 2**20 * 1.3))
        print "Current n_blocks_per_plane",\
            self.conf['flash_config']['n_blocks_per_plane']

    def my_run(self):
        utils.runtime_update(self.conf)
        workflow(self.conf)

    def test_main(self):
        self.setup_config()
        self.setup_environment()
        self.setup_workload()
        self.setup_ftl()
        self.my_run()


class TestVictimBlocks(unittest.TestCase):
    def test_entry(self):
        ssdbox.dftldes.VictimBlocks

    def test_init(self):
        create_victimblocks()

    def test_empty(self):
        vbs = create_victimblocks()
        self.assertEqual(len(list(vbs.iterator())), 0)

    def test_cur_blocks(self):
        """
        cur blocks should not be victim
        """
        conf = create_config()
        block_pool = create_blockpool(conf)
        oob = create_oob(conf)

        vbs = ssdbox.dftldes.VictimBlocks(conf, block_pool, oob)

        ppn = block_pool.next_data_page_to_program()

        self.assertEqual(len(list(vbs.iterator())), 0)

    def test_one_victim_candidate(self):
        conf = create_config()
        conf['flash_config']['n_channels_per_dev'] = 1
        conf['stripe_size'] = 'infinity'
        block_pool = create_blockpool(conf)
        oob = create_oob(conf)

        # use a whole block
        n = conf.n_pages_per_block
        ppns = block_pool.next_n_data_pages_to_program_striped(n)
        oob.invalidate_ppns(ppns)

        # use one more
        ppns = block_pool.next_n_data_pages_to_program_striped(1)

        vbs = ssdbox.dftldes.VictimBlocks(conf, block_pool, oob)

        victims = list(vbs.iterator())
        self.assertEqual(victims, [0])

    def test_3_victim_candidates(self):
        conf = create_config()
        conf['flash_config']['n_channels_per_dev'] = 1
        conf['stripe_size'] = 'infinity'
        block_pool = create_blockpool(conf)
        oob = create_oob(conf)

        # invalidate n-2 pages
        n = conf.n_pages_per_block
        ppns = block_pool.next_n_data_pages_to_program_striped(n)
        block0, _ = conf.page_to_block_off(ppns[0])
        for ppn in ppns:
            oob.states.validate_page(ppn)
        oob.invalidate_ppns(ppns[:-2])

        # invalidate n-1 pages
        ppns = block_pool.next_n_data_pages_to_program_striped(n)
        block1, _ = conf.page_to_block_off(ppns[0])
        for ppn in ppns:
            oob.states.validate_page(ppn)
        oob.invalidate_ppns(ppns[:-1])

        # invalidate n-3 pages
        ppns = block_pool.next_n_data_pages_to_program_striped(n)
        block2, _ = conf.page_to_block_off(ppns[0])
        for ppn in ppns:
            oob.states.validate_page(ppn)
        oob.invalidate_ppns(ppns[:-3])

        # use one more
        ppns = block_pool.next_n_data_pages_to_program_striped(1)

        vbs = ssdbox.dftldes.VictimBlocks(conf, block_pool, oob)

        victims = list(vbs.iterator())

        self.assertListEqual(victims, [block1, block0, block2])


class TestGC(unittest.TestCase):
    def test_valid_ratio(self):
        conf = create_config()
        conf['flash_config']['n_channels_per_dev'] = 1
        conf['stripe_size'] = 'infinity'
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = ssdbox.dftldes.Ftl(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write(objs, dftl))
        env.run()

    def proc_test_write(self, objs, dftl):
        env = objs['env']
        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        rec = objs['rec']
        rec.enable()

        block_pool = dftl.block_pool
        oob = dftl.oob

        victims = ssdbox.dftldes.VictimBlocks(objs['conf'], block_pool, oob)


        conf = objs['conf']
        n = conf.n_pages_per_block
        yield env.process(dftl.write_ext(Extent(0, n)))
        self.assertEqual(len(list(victims.iterator_verbose())), 0)

        yield env.process(dftl.write_ext(Extent(0, 1)))

        victim_blocks = list(victims.iterator_verbose())
        valid_ratio, block_type, block_num = victim_blocks[0]
        self.assertEqual(valid_ratio, (n-1.0)/n)

        yield env.process(dftl.write_ext(Extent(0, n)))

        victim_blocks = list(victims.iterator_verbose())
        valid_ratio, block_type, block_num = victim_blocks[0]
        self.assertEqual(valid_ratio, 0)


class TestDataBlockCleaner(unittest.TestCase):
    def test(self):
        conf = create_config()
        conf['flash_config']['n_channels_per_dev'] = 1
        conf['stripe_size'] = 'infinity'
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = FtlTest(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write(objs, dftl))
        env.run()

    def proc_test_write(self, objs, dftl):
        conf = objs['conf']
        env = objs['env']
        rec = objs['rec']
        rec.enable()

        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        block_pool = dftl.block_pool
        oob = dftl.oob
        mappings = dftl.get_mappings()

        victims = ssdbox.dftldes.VictimBlocks(objs['conf'], block_pool, oob)
        datablockcleaner = ssdbox.dftldes.DataBlockCleaner(
            conf = objs['conf'],
            flash = objs['flash_controller'],
            oob = oob,
            block_pool = block_pool,
            mappings = mappings,
            rec = objs['rec'],
            env = objs['env'])

        n = conf.n_pages_per_block
        yield env.process(dftl.write_ext(Extent(0, n)))
        yield env.process(dftl.write_ext(Extent(0, 1)))

        victim_blocks = list(victims.iterator_verbose())
        valid_ratio, block_type, victim_block = victim_blocks[0]
        self.assertEqual(oob.states.block_valid_ratio(victim_block), (n-1.0)/n)

        s = env.now
        yield env.process(datablockcleaner.clean(victim_block))

        # check the time to move n-1 valid pages
        self.assertEqual(env.now, s + (n-1)*(time_read_page+time_program_page))

        # check validation
        self.assertEqual(oob.states.block_valid_ratio(victim_block), 0)
        ppn_s, ppn_e = conf.block_to_page_range(victim_block)
        for ppn in range(ppn_s, ppn_e):
            self.assertEqual(oob.states.is_page_erased(ppn), True)

        # check blockpool
        self.assertNotIn(victim_block, block_pool.current_blocks())
        self.assertNotIn(victim_block, block_pool.used_blocks)
        self.assertIn(victim_block, block_pool.freeblocks)

        # check mapping
        ppn = yield env.process(mappings.lpn_to_ppn(0))
        block, _ = conf.page_to_block_off(ppn)
        self.assertNotEqual(block, victim_block)


class TestTransBlockCleaner(unittest.TestCase):
    def test(self):
        conf = create_config()
        conf['flash_config']['n_channels_per_dev'] = 1
        conf['stripe_size'] = 'infinity'
        # let cache just enough to hold one translation page
        conf.n_cache_entries = conf.n_mapping_entries_per_page
        objs = create_obj_set(conf)
        env = objs['env']

        dftl = FtlTest(objs['conf'], objs['rec'],
                objs['flash_controller'], objs['env'])

        env.process(self.proc_test_write(objs, dftl))
        env.run()


    def evict(self, env, mappings, lpn0, lpn1, n_evictions):
        """
        lpn0 and lpn1 are in two different m_vpns
        try to get n_evictions
        """
        yield env.process(mappings.lpn_to_ppn(lpn0))
        yield env.process(mappings.update(lpn=lpn0, ppn=8))

        lpns = [lpn1, lpn0] * n_evictions
        lpns = lpns[:n_evictions]
        for (i, lpn) in enumerate(lpns):
            # every iteration will evict one translation page
            yield env.process(mappings.lpn_to_ppn(lpn))
            yield env.process(mappings.update(lpn=lpn, ppn=i))


    def proc_test_write(self, objs, dftl):
        conf = objs['conf']
        env = objs['env']
        rec = objs['rec']
        rec.enable()

        time_read_page = objs['flash_controller'].channels[0].read_time
        time_program_page = objs['flash_controller'].channels[0].program_time

        block_pool = dftl.block_pool
        oob = dftl.oob
        mappings = dftl.get_mappings()
        directory = dftl.get_directory()

        # there should be a current translation block
        self.assertGreater(len(block_pool.current_blocks()), 0)

        victims = ssdbox.dftldes.VictimBlocks(objs['conf'], block_pool, oob)
        transblockcleaner = ssdbox.dftldes.TransBlockCleaner(
            conf = objs['conf'],
            flash = objs['flash_controller'],
            oob = oob,
            block_pool = block_pool,
            mappings = mappings,
            directory = objs['directory'],
            rec = objs['rec'],
            env = objs['env'])

        k = conf.n_mapping_entries_per_page
        n = conf.n_pages_per_block
        n_tp = conf.total_translation_pages()

        # try to evict many so we have a used translation block
        yield env.process(self.evict(env, mappings, 0, k, n))

        victim_blocks = list(victims.iterator_verbose())
        valid_ratio, block_type, victim_block = victim_blocks[0]

        self.assertEqual(valid_ratio, (n_tp - 2.0) / n)

        s = env.now
        yield env.process(transblockcleaner.clean(victim_block))

        # check the time to move n-1 valid pages
        self.assertEqual(env.now, s + (n_tp-2)*(time_read_page+time_program_page))

        # check validation
        self.assertEqual(oob.states.block_valid_ratio(victim_block), 0)
        ppn_s, ppn_e = conf.block_to_page_range(victim_block)
        for ppn in range(ppn_s, ppn_e):
            self.assertEqual(oob.states.is_page_erased(ppn), True)

        # check blockpool
        self.assertNotIn(victim_block, block_pool.current_blocks())
        self.assertNotIn(victim_block, block_pool.used_blocks)
        self.assertIn(victim_block, block_pool.freeblocks)

        # check directory
        self.assertNotEqual(conf.page_to_block_off(directory.m_vpn_to_m_ppn(0))[0],
                victim_block)


def main():
    unittest.main()

if __name__ == '__main__':
    main()





