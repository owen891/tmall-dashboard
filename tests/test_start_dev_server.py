import unittest


from scripts.start_dev_server import parse_args


class StartDevServerArgTests(unittest.TestCase):
    def test_default_port_is_5000(self):
        self.assertEqual(parse_args([]).port, 5000)

    def test_port_flag_is_honored(self):
        # 此前本脚本静默丢弃全部参数：--port 8770 实际仍起在 5000，造成端口双绑。
        self.assertEqual(parse_args(['--port', '8770']).port, 8770)

    def test_unknown_arguments_fail_fast(self):
        with self.assertRaises(SystemExit):
            parse_args(['--whatever'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
