import unittest

from agile.utils import LogHelper


class TestLogger(unittest.TestCase):

    def setUp(self):
        self.log = LogHelper.get_logger()

    def test(self):
        self.log.debug('==> debug')
        self.log.info('==> info')
        self.log.warning('==> warning')
        self.log.error('==> error')
        self.log.critical('==> critical')

if __name__ == '__main__':
    unittest.main()