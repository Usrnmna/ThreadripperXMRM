import argparse
import json
from pathlib import Path
import tempfile
import unittest

import mine


class LauncherTests(unittest.TestCase):
    def test_all_64_threads(self):
        self.assertEqual(mine.select_cpus(set(range(64)), 'all'), list(range(64)))

    def test_physical_cores_with_sparse_restricted_affinity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for cpu, siblings in {2: '2,66', 66: '2,66', 67: '3,67', 127: '63,127'}.items():
                target = root / f'cpu{cpu}/topology'
                target.mkdir(parents=True)
                (target / 'thread_siblings_list').write_text(siblings)
            self.assertEqual(mine.select_cpus({2, 66, 67, 127}, 'cores', root), [2, 67, 127])

    def test_32_core_smt_topology(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for cpu in range(64):
                target = root / f'cpu{cpu}/topology'
                target.mkdir(parents=True)
                (target / 'thread_siblings_list').write_text(f'{cpu % 32},{cpu % 32 + 32}')
            self.assertEqual(mine.select_cpus(range(64), 'cores', root), list(range(32)))

    def test_cpu_range_parser(self):
        self.assertEqual(mine.cpu_list('0-3,64-67,127'), {0, 1, 2, 3, 64, 65, 66, 67, 127})
        with self.assertRaises(ValueError):
            mine.cpu_list('4-2')

    def test_json_pool_config_and_explicit_affinity(self):
        args = mine.parser().parse_args(['mine', 'pool.example:443', '4' + 'A' * 94])
        config = json.loads(json.dumps(mine.configuration(list(range(64)), args)))
        self.assertEqual(config['cpu']['rx'], list(range(64)))
        self.assertEqual(config['pools'][0]['user'], args.wallet)
        self.assertTrue(config['pools'][0]['tls'])
        self.assertEqual(config['pools'][0]['coin'], 'monero')
        self.assertFalse(config['randomx']['wrmsr'])
        self.assertFalse(config['background'])

    def test_plain_local_pool(self):
        args = mine.parser().parse_args(['mine', '127.0.0.1:3333', '4' + 'A' * 94, '--no-tls'])
        self.assertFalse(mine.configuration([0], args)['pools'][0]['tls'])

    def test_benchmark_has_no_pool_or_wallet(self):
        args = mine.parser().parse_args(['benchmark', '--workers', 'cores'])
        self.assertEqual(mine.configuration([0], args)['pools'], [])

    def test_invalid_pool_and_wallet_rejected(self):
        for value in ('host', 'host:0', 'host:65536', 'https://host:443', 'host:123/a'):
            with self.assertRaises(argparse.ArgumentTypeError):
                mine.pool_address(value)
        self.assertEqual(mine.pool_address('[::1]:3333'), '[::1]:3333')
        with self.assertRaises(argparse.ArgumentTypeError):
            mine.wallet_address('YOUR_WALLET')


if __name__ == '__main__':
    unittest.main()
