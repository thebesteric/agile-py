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

    def test_title_prefix(self):
        logger = LogHelper.get_logger(name="test.title.prefix", title="[xxx]")
        with self.assertLogs("test.title.prefix", level="INFO") as captured:
            logger.info("Hello World!")
        self.assertIn("[xxx] Hello World!", captured.output[0])

if __name__ == '__main__':
    unittest.main()