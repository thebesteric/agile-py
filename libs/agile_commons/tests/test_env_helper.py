"""
EnvReader 完整测试套件
使用 unittest.TestCase 框架
测试所有类型的转换：bool、int、float、str、list、dict、tuple、set、datetime、date、time
以及自动推断功能
"""
import datetime
import os
import unittest

from libs.agile_commons.src.utils.env_helper import EnvHelper


class TestEnvReaderSetMethod(unittest.TestCase):
    """测试 set() 方法 - 环境变量写入和类型序列化"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _get_env(self, key):
        """获取环境变量并记录"""
        self.env_keys.append(key)
        return os.environ.get(key)

    def test_set_empty_key_raises_error(self):
        """测试空 key 抛出异常"""
        with self.assertRaises(ValueError):
            self.env_helper.set('', 'value')

    def test_set_none_key_raises_error(self):
        """测试 None key 抛出异常"""
        with self.assertRaises(ValueError):
            self.env_helper.set(None, 'value')

    def test_set_none_value(self):
        """测试设置 None 值"""
        self.env_helper.set('SET_NONE', None)
        result = self._get_env('SET_NONE')
        self.assertEqual(result, 'none')
        # 验证读回时能正确转换
        self.assertIsNone(self.env_helper.get('SET_NONE', var_type=type(None)))

    def test_set_bool_true(self):
        """测试设置布尔值 True"""
        self.env_helper.set('SET_BOOL_TRUE', True)
        result = self._get_env('SET_BOOL_TRUE')
        self.assertEqual(result, 'true')
        # 验证读回
        self.assertTrue(self.env_helper.get('SET_BOOL_TRUE', var_type=bool))

    def test_set_bool_false(self):
        """测试设置布尔值 False"""
        self.env_helper.set('SET_BOOL_FALSE', False)
        result = self._get_env('SET_BOOL_FALSE')
        self.assertEqual(result, 'false')
        # 验证读回
        self.assertFalse(self.env_helper.get('SET_BOOL_FALSE', var_type=bool))

    def test_set_int(self):
        """测试设置整数"""
        self.env_helper.set('SET_INT', 42)
        result = self._get_env('SET_INT')
        self.assertEqual(result, '42')
        # 验证读回
        self.assertEqual(self.env_helper.get('SET_INT', var_type=int), 42)

    def test_set_int_negative(self):
        """测试设置负整数"""
        self.env_helper.set('SET_INT_NEG', -99)
        result = self._get_env('SET_INT_NEG')
        self.assertEqual(result, '-99')

    def test_set_float(self):
        """测试设置浮点数"""
        self.env_helper.set('SET_FLOAT', 3.14)
        result = self._get_env('SET_FLOAT')
        self.assertEqual(result, '3.14')
        # 验证读回
        self.assertAlmostEqual(self.env_helper.get('SET_FLOAT', var_type=float), 3.14)

    def test_set_string(self):
        """测试设置字符串"""
        self.env_helper.set('SET_STR', 'hello')
        result = self._get_env('SET_STR')
        self.assertEqual(result, 'hello')

    def test_set_string_with_spaces(self):
        """测试设置包含空格的字符串"""
        self.env_helper.set('SET_STR_SPACE', 'hello world')
        result = self._get_env('SET_STR_SPACE')
        self.assertEqual(result, 'hello world')

    def test_set_string_unicode(self):
        """测试设置 Unicode 字符串"""
        self.env_helper.set('SET_STR_UNICODE', '你好世界 🌍')
        result = self._get_env('SET_STR_UNICODE')
        self.assertEqual(result, '你好世界 🌍')

    def test_set_list(self):
        """测试设置列表"""
        self.env_helper.set('SET_LIST', [1, 2, 3])
        result = self._get_env('SET_LIST')
        self.assertEqual(result, '[1, 2, 3]')
        # 验证读回
        self.assertEqual(self.env_helper.get('SET_LIST', var_type=list), [1, 2, 3])

    def test_set_list_strings(self):
        """测试设置字符串列表"""
        self.env_helper.set('SET_LIST_STR', ['a', 'b', 'c'])
        result = self._get_env('SET_LIST_STR')
        self.assertEqual(result, '["a", "b", "c"]')

    def test_set_list_mixed(self):
        """测试设置混合类型列表"""
        self.env_helper.set('SET_LIST_MIXED', [1, 'two', 3.0])
        result = self._get_env('SET_LIST_MIXED')
        self.assertIn('1', result)
        self.assertIn('two', result)

    def test_set_dict(self):
        """测试设置字典"""
        self.env_helper.set('SET_DICT', {'key': 'value'})
        result = self._get_env('SET_DICT')
        # JSON 格式
        self.assertIn('key', result)
        self.assertIn('value', result)
        # 验证读回
        self.assertEqual(self.env_helper.get('SET_DICT', var_type=dict), {'key': 'value'})

    def test_set_dict_nested(self):
        """测试设置嵌套字典"""
        self.env_helper.set('SET_DICT_NESTED', {'outer': {'inner': 'value'}})
        result = self._get_env('SET_DICT_NESTED')
        self.assertIn('outer', result)
        self.assertIn('inner', result)

    def test_set_tuple(self):
        """测试设置元组"""
        self.env_helper.set('SET_TUPLE', (1, 2, 3))
        result = self._get_env('SET_TUPLE')
        self.assertEqual(result, '[1, 2, 3]')  # 元组序列化为 JSON list
        # 验证读回
        self.assertEqual(self.env_helper.get('SET_TUPLE', var_type=tuple), (1, 2, 3))

    def test_set_set(self):
        """测试设置集合"""
        self.env_helper.set('SET_SET', {1, 2, 3})
        result = self._get_env('SET_SET')
        # 集合序列化为 JSON list
        self.assertIn('1', result)
        self.assertIn('2', result)
        self.assertIn('3', result)

    def test_set_datetime(self):
        """测试设置日期时间"""
        dt = datetime.datetime(2026, 2, 28, 14, 30, 45)
        self.env_helper.set('SET_DATETIME', dt)
        result = self._get_env('SET_DATETIME')
        self.assertEqual(result, '2026-02-28 14:30:45')
        # 验证读回
        read_dt = self.env_helper.get('SET_DATETIME', var_type=datetime.datetime)
        self.assertEqual(read_dt, dt)

    def test_set_date(self):
        """测试设置日期"""
        d = datetime.date(2026, 2, 28)
        self.env_helper.set('SET_DATE', d)
        result = self._get_env('SET_DATE')
        self.assertEqual(result, '2026-02-28')
        # 验证读回
        read_d = self.env_helper.get('SET_DATE', var_type=datetime.date)
        self.assertEqual(read_d, d)

    def test_set_time(self):
        """测试设置时间"""
        t = datetime.time(14, 30, 45)
        self.env_helper.set('SET_TIME', t)
        result = self._get_env('SET_TIME')
        self.assertEqual(result, '14:30:45')
        # 验证读回
        read_t = self.env_helper.get('SET_TIME', var_type=datetime.time)
        self.assertEqual(read_t, t)

    def test_set_and_get_roundtrip_bool(self):
        """测试 set/get 往返 - 布尔值"""
        original = True
        self.env_helper.set('ROUNDTRIP_BOOL', original)
        retrieved = self.env_helper.get('ROUNDTRIP_BOOL')
        self.assertEqual(retrieved, original)

    def test_set_and_get_roundtrip_int(self):
        """测试 set/get 往返 - 整数"""
        original = 42
        self.env_helper.set('ROUNDTRIP_INT', original)
        retrieved = self.env_helper.get('ROUNDTRIP_INT')
        self.assertEqual(retrieved, original)

    def test_set_and_get_roundtrip_list(self):
        """测试 set/get 往返 - 列表"""
        original = [1, 2, 3]
        self.env_helper.set('ROUNDTRIP_LIST', original)
        retrieved = self.env_helper.get('ROUNDTRIP_LIST')
        self.assertEqual(retrieved, original)

    def test_set_and_get_roundtrip_dict(self):
        """测试 set/get 往返 - 字典"""
        original = {'a': 1, 'b': 2}
        self.env_helper.set('ROUNDTRIP_DICT', original)
        retrieved = self.env_helper.get('ROUNDTRIP_DICT')
        self.assertEqual(retrieved, original)

    def test_set_and_get_roundtrip_date(self):
        """测试 set/get 往返 - 日期"""
        original = datetime.date(2026, 2, 28)
        self.env_helper.set('ROUNDTRIP_DATE', original)
        retrieved = self.env_helper.get('ROUNDTRIP_DATE', var_type=datetime.date)
        self.assertEqual(retrieved, original)

    def test_set_unsupported_type_raises_error(self):
        """测试不支持的类型抛出异常"""

        class CustomClass:
            pass

        with self.assertRaises(TypeError):
            self.env_helper.set('SET_UNSUPPORTED', CustomClass())


class TestEnvReaderBasic(unittest.TestCase):
    """测试基础功能"""

    def setUp(self):
        """每个测试前清空环境变量"""
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        """每个测试后清理环境变量"""
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        """设置环境变量并记录以便清理"""
        os.environ[key] = value
        self.env_keys.append(key)

    def test_get_non_existent_key_returns_none(self):
        """测试获取不存在的环境变量返回 None"""
        result = self.env_helper.get('NON_EXISTENT_KEY')
        self.assertIsNone(result)

    def test_get_non_existent_key_returns_default(self):
        """测试获取不存在的环境变量返回默认值"""
        default = "default_value"
        result = self.env_helper.get('NON_EXISTENT_KEY', default=default)
        self.assertEqual(result, default)

    def test_get_empty_key_raises_error(self):
        """测试空的 key 抛出异常"""
        with self.assertRaises(ValueError):
            self.env_helper.get('')

    def test_get_none_key_raises_error(self):
        """测试 None 的 key 抛出异常"""
        with self.assertRaises(ValueError):
            self.env_helper.get(None)

    def test_get_empty_string_with_none_type(self):
        """测试空字符串转换为 None 类型"""
        self._set_env('EMPTY_VAR', '')
        result = self.env_helper.get('EMPTY_VAR', var_type=type(None))
        self.assertIsNone(result)


class TestEnvReaderGetRequired(unittest.TestCase):
    """测试 get_required() 方法 - 获取必需的环境变量"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_get_required_existing_key_returns_value(self):
        """测试获取存在的环境变量"""
        self._set_env('REQUIRED_KEY', 'value')
        result = self.env_helper.get_required('REQUIRED_KEY')
        self.assertEqual(result, 'value')

    def test_get_required_empty_key_raises_error(self):
        """测试空 key 抛出异常"""
        with self.assertRaises(ValueError):
            self.env_helper.get_required('')

    def test_get_required_none_key_raises_error(self):
        """测试 None key 抛出异常"""
        with self.assertRaises(ValueError):
            self.env_helper.get_required(None)

    def test_get_required_non_existent_key_raises_error(self):
        """测试不存在的 key 抛出 KeyError"""
        with self.assertRaises(KeyError) as context:
            self.env_helper.get_required('NON_EXISTENT_KEY')
        self.assertIn('NON_EXISTENT_KEY', str(context.exception))

    def test_get_required_with_explicit_type_bool(self):
        """测试获取布尔值 - 显式指定类型"""
        self._set_env('REQUIRED_BOOL', 'true')
        result = self.env_helper.get_required('REQUIRED_BOOL', var_type=bool)
        self.assertTrue(result)

    def test_get_required_with_explicit_type_int(self):
        """测试获取整数 - 显式指定类型"""
        self._set_env('REQUIRED_INT', '42')
        result = self.env_helper.get_required('REQUIRED_INT', var_type=int)
        self.assertEqual(result, 42)

    def test_get_required_with_explicit_type_float(self):
        """测试获取浮点数 - 显式指定类型"""
        self._set_env('REQUIRED_FLOAT', '3.14')
        result = self.env_helper.get_required('REQUIRED_FLOAT', var_type=float)
        self.assertAlmostEqual(result, 3.14)

    def test_get_required_with_explicit_type_list(self):
        """测试获取列表 - 显式指定类型"""
        self._set_env('REQUIRED_LIST', '[1, 2, 3]')
        result = self.env_helper.get_required('REQUIRED_LIST', var_type=list)
        self.assertEqual(result, [1, 2, 3])

    def test_get_required_with_explicit_type_dict(self):
        """测试获取字典 - 显式指定类型"""
        self._set_env('REQUIRED_DICT', '{"key": "value"}')
        result = self.env_helper.get_required('REQUIRED_DICT', var_type=dict)
        self.assertEqual(result, {'key': 'value'})

    def test_get_required_with_explicit_type_date(self):
        """测试获取日期 - 显式指定类型"""
        self._set_env('REQUIRED_DATE', '2026-02-28')
        result = self.env_helper.get_required('REQUIRED_DATE', var_type=datetime.date)
        self.assertEqual(result, datetime.date(2026, 2, 28))

    def test_get_required_with_explicit_type_datetime(self):
        """测试获取日期时间 - 显式指定类型"""
        self._set_env('REQUIRED_DT', '2026-02-28 14:30:45')
        result = self.env_helper.get_required('REQUIRED_DT', var_type=datetime.datetime)
        self.assertEqual(result, datetime.datetime(2026, 2, 28, 14, 30, 45))

    def test_get_required_with_explicit_type_time(self):
        """测试获取时间 - 显式指定类型"""
        self._set_env('REQUIRED_TIME', '14:30:45')
        result = self.env_helper.get_required('REQUIRED_TIME', var_type=datetime.time)
        self.assertEqual(result, datetime.time(14, 30, 45))

    def test_get_required_auto_convert(self):
        """测试自动推断类型"""
        self._set_env('REQUIRED_AUTO', '42')
        result = self.env_helper.get_required('REQUIRED_AUTO')
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    def test_get_required_auto_convert_bool(self):
        """测试自动推断布尔值"""
        self._set_env('REQUIRED_AUTO_BOOL', 'true')
        result = self.env_helper.get_required('REQUIRED_AUTO_BOOL')
        self.assertTrue(result)

    def test_get_required_auto_convert_list(self):
        """测试自动推断列表"""
        self._set_env('REQUIRED_AUTO_LIST', '[1, 2, 3]')
        result = self.env_helper.get_required('REQUIRED_AUTO_LIST')
        self.assertEqual(result, [1, 2, 3])

    def test_get_required_invalid_type_conversion_raises_error(self):
        """测试无效的类型转换抛出异常"""
        self._set_env('REQUIRED_INVALID', 'not_a_number')
        with self.assertRaises(TypeError):
            self.env_helper.get_required('REQUIRED_INVALID', var_type=int)

    def test_get_required_empty_string_with_none_type(self):
        """测试空字符串转换为 None 类型"""
        self._set_env('REQUIRED_EMPTY', '')
        result = self.env_helper.get_required('REQUIRED_EMPTY', var_type=type(None))
        self.assertIsNone(result)

    def test_get_required_vs_get_difference(self):
        """测试 get_required 和 get 的区别"""
        # get 不存在 key 返回 default
        result_get = self.env_helper.get('MISSING_KEY', default='default_value')
        self.assertEqual(result_get, 'default_value')

        # get_required 不存在 key 抛出异常
        with self.assertRaises(KeyError):
            self.env_helper.get_required('MISSING_KEY')


class TestEnvReaderBool(unittest.TestCase):
    """测试布尔值转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_bool_true_values(self):
        """测试各种真值"""
        true_values = ['true', 'True', 'TRUE', '1', 'yes', 'YES', 'on', 'ON', 'enable', 'ENABLE']
        for value in true_values:
            with self.subTest(value=value):
                self._set_env(f'BOOL_{value}', value)
                result = self.env_helper.get(f'BOOL_{value}', var_type=bool)
                self.assertTrue(result)

    def test_bool_false_values(self):
        """测试各种假值"""
        false_values = ['false', 'False', 'FALSE', '0', 'no', 'NO', 'off', 'OFF', 'disable', 'DISABLE']
        for value in false_values:
            with self.subTest(value=value):
                self._set_env(f'BOOL_{value}', value)
                result = self.env_helper.get(f'BOOL_{value}', var_type=bool)
                self.assertFalse(result)

    def test_bool_invalid_value(self):
        """测试无效布尔值抛出异常"""
        self._set_env('BOOL_INVALID', 'maybe')
        with self.assertRaises(TypeError):
            self.env_helper.get('BOOL_INVALID', var_type=bool)

    def test_bool_auto_convert_true(self):
        """测试自动推断布尔值 - 真"""
        self._set_env('AUTO_BOOL_TRUE', 'true')
        result = self.env_helper.get('AUTO_BOOL_TRUE')
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_bool_auto_convert_false(self):
        """测试自动推断布尔值 - 假"""
        self._set_env('AUTO_BOOL_FALSE', 'false')
        result = self.env_helper.get('AUTO_BOOL_FALSE')
        self.assertIsInstance(result, bool)
        self.assertFalse(result)


class TestEnvReaderInt(unittest.TestCase):
    """测试整数转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_int_positive(self):
        """测试正整数"""
        self._set_env('INT_POSITIVE', '42')
        result = self.env_helper.get('INT_POSITIVE', var_type=int)
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)

    def test_int_negative(self):
        """测试负整数"""
        self._set_env('INT_NEGATIVE', '-42')
        result = self.env_helper.get('INT_NEGATIVE', var_type=int)
        self.assertEqual(result, -42)

    def test_int_zero(self):
        """测试零"""
        self._set_env('INT_ZERO', '0')
        result = self.env_helper.get('INT_ZERO', var_type=int)
        self.assertEqual(result, 0)

    def test_int_large_number(self):
        """测试大整数"""
        self._set_env('INT_LARGE', '9999999999')
        result = self.env_helper.get('INT_LARGE', var_type=int)
        self.assertEqual(result, 9999999999)

    def test_int_invalid(self):
        """测试无效整数抛出异常"""
        self._set_env('INT_INVALID', 'not_a_number')
        with self.assertRaises(TypeError):
            self.env_helper.get('INT_INVALID', var_type=int)

    def test_int_auto_convert(self):
        """测试自动推断整数"""
        self._set_env('AUTO_INT', '123')
        result = self.env_helper.get('AUTO_INT')
        self.assertIsInstance(result, int)
        self.assertEqual(result, 123)


class TestEnvReaderFloat(unittest.TestCase):
    """测试浮点数转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_float_positive(self):
        """测试正浮点数"""
        self._set_env('FLOAT_POSITIVE', '3.14')
        result = self.env_helper.get('FLOAT_POSITIVE', var_type=float)
        self.assertAlmostEqual(result, 3.14)
        self.assertIsInstance(result, float)

    def test_float_negative(self):
        """测试负浮点数"""
        self._set_env('FLOAT_NEGATIVE', '-2.5')
        result = self.env_helper.get('FLOAT_NEGATIVE', var_type=float)
        self.assertAlmostEqual(result, -2.5)

    def test_float_zero(self):
        """测试浮点零"""
        self._set_env('FLOAT_ZERO', '0.0')
        result = self.env_helper.get('FLOAT_ZERO', var_type=float)
        self.assertAlmostEqual(result, 0.0)

    def test_float_scientific_notation(self):
        """测试科学计数法"""
        self._set_env('FLOAT_SCIENTIFIC', '1.23e-4')
        result = self.env_helper.get('FLOAT_SCIENTIFIC', var_type=float)
        self.assertAlmostEqual(result, 0.000123)

    def test_float_int_string(self):
        """测试整数字符串转浮点数"""
        self._set_env('FLOAT_INT', '42')
        result = self.env_helper.get('FLOAT_INT', var_type=float)
        self.assertAlmostEqual(result, 42.0)

    def test_float_auto_convert(self):
        """测试自动推断浮点数"""
        self._set_env('AUTO_FLOAT', '2.718')
        result = self.env_helper.get('AUTO_FLOAT')
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 2.718)


class TestEnvReaderStr(unittest.TestCase):
    """测试字符串转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_str_basic(self):
        """测试基础字符串"""
        self._set_env('STR_BASIC', 'hello')
        result = self.env_helper.get('STR_BASIC', var_type=str)
        self.assertEqual(result, 'hello')
        self.assertIsInstance(result, str)

    def test_str_with_spaces(self):
        """测试包含空格的字符串"""
        self._set_env('STR_SPACES', '  hello world  ')
        result = self.env_helper.get('STR_SPACES', var_type=str)
        self.assertEqual(result, 'hello world')  # 会被 strip

    def test_str_with_special_chars(self):
        """测试包含特殊字符的字符串"""
        self._set_env('STR_SPECIAL', 'hello!@#$%^&*()')
        result = self.env_helper.get('STR_SPECIAL', var_type=str)
        self.assertEqual(result, 'hello!@#$%^&*()')

    def test_str_empty(self):
        """测试空字符串"""
        self._set_env('STR_EMPTY', '')
        result = self.env_helper.get('STR_EMPTY', var_type=str)
        self.assertEqual(result, '')


class TestEnvReaderList(unittest.TestCase):
    """测试列表转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_list_integers(self):
        """测试整数列表"""
        self._set_env('LIST_INTS', '[1, 2, 3]')
        result = self.env_helper.get('LIST_INTS', var_type=list)
        self.assertEqual(result, [1, 2, 3])
        self.assertIsInstance(result, list)

    def test_list_strings(self):
        """测试字符串列表"""
        self._set_env('LIST_STRS', '["a", "b", "c"]')
        result = self.env_helper.get('LIST_STRS', var_type=list)
        self.assertEqual(result, ['a', 'b', 'c'])

    def test_list_mixed(self):
        """测试混合类型列表"""
        self._set_env('LIST_MIXED', '[1, "two", 3.0, true]')
        result = self.env_helper.get('LIST_MIXED', var_type=list)
        self.assertEqual(result, [1, 'two', 3.0, True])

    def test_list_empty(self):
        """测试空列表"""
        self._set_env('LIST_EMPTY', '[]')
        result = self.env_helper.get('LIST_EMPTY', var_type=list)
        self.assertEqual(result, [])

    def test_list_auto_convert(self):
        """测试自动推断列表"""
        self._set_env('AUTO_LIST', '[1, 2, 3]')
        result = self.env_helper.get('AUTO_LIST')
        self.assertIsInstance(result, list)
        self.assertEqual(result, [1, 2, 3])


class TestEnvReaderDict(unittest.TestCase):
    """测试字典转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_dict_basic(self):
        """测试基础字典"""
        self._set_env('DICT_BASIC', '{"key": "value"}')
        result = self.env_helper.get('DICT_BASIC', var_type=dict)
        self.assertEqual(result, {'key': 'value'})
        self.assertIsInstance(result, dict)

    def test_dict_nested(self):
        """测试嵌套字典"""
        self._set_env('DICT_NESTED', '{"outer": {"inner": "value"}}')
        result = self.env_helper.get('DICT_NESTED', var_type=dict)
        self.assertEqual(result, {'outer': {'inner': 'value'}})

    def test_dict_mixed_values(self):
        """测试混合值字典"""
        self._set_env('DICT_MIXED', '{"str": "text", "int": 42, "bool": true}')
        result = self.env_helper.get('DICT_MIXED', var_type=dict)
        self.assertEqual(result, {'str': 'text', 'int': 42, 'bool': True})

    def test_dict_empty(self):
        """测试空字典"""
        self._set_env('DICT_EMPTY', '{}')
        result = self.env_helper.get('DICT_EMPTY', var_type=dict)
        self.assertEqual(result, {})

    def test_dict_auto_convert(self):
        """测试自动推断字典"""
        self._set_env('AUTO_DICT', '{"a": 1, "b": 2}')
        result = self.env_helper.get('AUTO_DICT')
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {'a': 1, 'b': 2})


class TestEnvReaderTuple(unittest.TestCase):
    """测试元组转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_tuple_basic(self):
        """测试基础元组"""
        self._set_env('TUPLE_BASIC', '[1, 2, 3]')
        result = self.env_helper.get('TUPLE_BASIC', var_type=tuple)
        self.assertEqual(result, (1, 2, 3))
        self.assertIsInstance(result, tuple)

    def test_tuple_strings(self):
        """测试字符串元组"""
        self._set_env('TUPLE_STRS', '["a", "b"]')
        result = self.env_helper.get('TUPLE_STRS', var_type=tuple)
        self.assertEqual(result, ('a', 'b'))

    def test_tuple_mixed(self):
        """测试混合类型元组"""
        self._set_env('TUPLE_MIXED', '[1, "two", 3.0]')
        result = self.env_helper.get('TUPLE_MIXED', var_type=tuple)
        self.assertEqual(result, (1, 'two', 3.0))

    def test_tuple_empty(self):
        """测试空元组"""
        self._set_env('TUPLE_EMPTY', '[]')
        result = self.env_helper.get('TUPLE_EMPTY', var_type=tuple)
        self.assertEqual(result, ())


class TestEnvReaderSet(unittest.TestCase):
    """测试集合转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_set_basic(self):
        """测试基础集合"""
        self._set_env('SET_BASIC', '[1, 2, 3]')
        result = self.env_helper.get('SET_BASIC', var_type=set)
        self.assertEqual(result, {1, 2, 3})
        self.assertIsInstance(result, set)

    def test_set_duplicates_removed(self):
        """测试重复元素被移除"""
        self._set_env('SET_DUPS', '[1, 2, 2, 3, 3, 3]')
        result = self.env_helper.get('SET_DUPS', var_type=set)
        self.assertEqual(result, {1, 2, 3})

    def test_set_strings(self):
        """测试字符串集合"""
        self._set_env('SET_STRS', '["a", "b", "c"]')
        result = self.env_helper.get('SET_STRS', var_type=set)
        self.assertEqual(result, {'a', 'b', 'c'})


class TestEnvReaderNone(unittest.TestCase):
    """测试 None 类型转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_none_values(self):
        """测试各种 None 值"""
        none_values = ['none', 'None', 'NONE', 'null', 'NULL', 'nil', 'NIL']
        for value in none_values:
            with self.subTest(value=value):
                self._set_env(f'NONE_{value}', value)
                result = self.env_helper.get(f'NONE_{value}', var_type=type(None))
                self.assertIsNone(result)

    def test_none_auto_convert(self):
        """测试自动推断 None"""
        self._set_env('AUTO_NONE', 'null')
        result = self.env_helper.get('AUTO_NONE')
        self.assertIsNone(result)


class TestEnvReaderDatetime(unittest.TestCase):
    """测试 datetime.datetime 转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_datetime_full_format(self):
        """测试完整日期时间格式 (YYYY-MM-DD HH:MM:SS)"""
        self._set_env('DT_FULL', '2026-02-28 14:30:45')
        result = self.env_helper.get('DT_FULL', var_type=datetime.datetime)
        self.assertIsInstance(result, datetime.datetime)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 28)
        self.assertEqual(result.hour, 14)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.second, 45)

    def test_datetime_date_only(self):
        """测试日期格式 (YYYY-MM-DD)"""
        self._set_env('DT_DATE', '2026-02-28')
        result = self.env_helper.get('DT_DATE', var_type=datetime.datetime)
        self.assertIsInstance(result, datetime.datetime)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 28)
        self.assertEqual(result.hour, 0)
        self.assertEqual(result.minute, 0)

    def test_datetime_slash_format(self):
        """测试斜杠格式 (YYYY/MM/DD HH:MM:SS)"""
        self._set_env('DT_SLASH', '2026/02/28 15:45:30')
        result = self.env_helper.get('DT_SLASH', var_type=datetime.datetime)
        self.assertIsInstance(result, datetime.datetime)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.hour, 15)

    def test_datetime_invalid(self):
        """测试无效日期时间格式"""
        self._set_env('DT_INVALID', '2026/13/45 25:70:99')
        with self.assertRaises(TypeError):
            self.env_helper.get('DT_INVALID', var_type=datetime.datetime)


class TestEnvReaderDate(unittest.TestCase):
    """测试 datetime.date 转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_date_dash_format(self):
        """测试短横线格式 (YYYY-MM-DD)"""
        self._set_env('DATE_DASH', '2026-02-28')
        result = self.env_helper.get('DATE_DASH', var_type=datetime.date)
        self.assertIsInstance(result, datetime.date)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 2)
        self.assertEqual(result.day, 28)

    def test_date_slash_format(self):
        """测试斜杠格式 (YYYY/MM/DD)"""
        self._set_env('DATE_SLASH', '2026/02/28')
        result = self.env_helper.get('DATE_SLASH', var_type=datetime.date)
        self.assertIsInstance(result, datetime.date)
        self.assertEqual(result.year, 2026)

    def test_date_leap_year(self):
        """测试闰年日期"""
        self._set_env('DATE_LEAP', '2024-02-29')
        result = self.env_helper.get('DATE_LEAP', var_type=datetime.date)
        self.assertEqual(result, datetime.date(2024, 2, 29))

    def test_date_invalid_day(self):
        """测试无效日期"""
        self._set_env('DATE_INVALID', '2026-02-30')
        with self.assertRaises(TypeError):
            self.env_helper.get('DATE_INVALID', var_type=datetime.date)

    def test_date_auto_convert(self):
        """测试自动推断日期"""
        self._set_env('AUTO_DATE', '2026-02-28')
        result = self.env_helper.get('AUTO_DATE')
        self.assertIsInstance(result, datetime.date)
        self.assertNotIsInstance(result, datetime.datetime)


class TestEnvReaderTime(unittest.TestCase):
    """测试 datetime.time 转换"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_time_full_format(self):
        """测试完整时间格式 (HH:MM:SS)"""
        self._set_env('TIME_FULL', '14:30:45')
        result = self.env_helper.get('TIME_FULL', var_type=datetime.time)
        self.assertIsInstance(result, datetime.time)
        self.assertEqual(result.hour, 14)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.second, 45)

    def test_time_hm_format(self):
        """测试简短时间格式 (HH:MM)"""
        self._set_env('TIME_HM', '14:30')
        result = self.env_helper.get('TIME_HM', var_type=datetime.time)
        self.assertIsInstance(result, datetime.time)
        self.assertEqual(result.hour, 14)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.second, 0)

    def test_time_midnight(self):
        """测试午夜时间"""
        self._set_env('TIME_MIDNIGHT', '00:00:00')
        result = self.env_helper.get('TIME_MIDNIGHT', var_type=datetime.time)
        self.assertEqual(result, datetime.time(0, 0, 0))

    def test_time_invalid(self):
        """测试无效时间"""
        self._set_env('TIME_INVALID', '25:70:99')
        with self.assertRaises(TypeError):
            self.env_helper.get('TIME_INVALID', var_type=datetime.time)

    def test_time_auto_convert(self):
        """测试自动推断时间"""
        self._set_env('AUTO_TIME', '14:30:45')
        result = self.env_helper.get('AUTO_TIME')
        self.assertIsInstance(result, datetime.time)


class TestEnvReaderAutoConvert(unittest.TestCase):
    """测试自动类型推断功能"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_auto_convert_priority_none(self):
        """测试优先级：None"""
        self._set_env('AUTO_NONE', 'none')
        result = self.env_helper.get('AUTO_NONE')
        self.assertIsNone(result)

    def test_auto_convert_priority_bool(self):
        """测试优先级：布尔值"""
        self._set_env('AUTO_BOOL', 'true')
        result = self.env_helper.get('AUTO_BOOL')
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_auto_convert_priority_int(self):
        """测试优先级：整数"""
        self._set_env('AUTO_INT', '42')
        result = self.env_helper.get('AUTO_INT')
        self.assertIsInstance(result, int)
        self.assertEqual(result, 42)

    def test_auto_convert_priority_float(self):
        """测试优先级：浮点数"""
        self._set_env('AUTO_FLOAT', '3.14')
        result = self.env_helper.get('AUTO_FLOAT')
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 3.14)

    def test_auto_convert_priority_json_list(self):
        """测试优先级：JSON 列表"""
        self._set_env('AUTO_JSON_LIST', '[1, 2, 3]')
        result = self.env_helper.get('AUTO_JSON_LIST')
        self.assertIsInstance(result, list)
        self.assertEqual(result, [1, 2, 3])

    def test_auto_convert_priority_json_dict(self):
        """测试优先级：JSON 字典"""
        self._set_env('AUTO_JSON_DICT', '{"a": 1}')
        result = self.env_helper.get('AUTO_JSON_DICT')
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {'a': 1})

    def test_auto_convert_priority_date(self):
        """测试优先级：日期（优先于 datetime）"""
        self._set_env('AUTO_DATE_PRIO', '2026-02-28')
        result = self.env_helper.get('AUTO_DATE_PRIO')
        self.assertIsInstance(result, datetime.date)
        self.assertNotIsInstance(result, datetime.datetime)

    def test_auto_convert_priority_datetime(self):
        """测试优先级：日期时间"""
        self._set_env('AUTO_DT_PRIO', '2026-02-28 14:30:45')
        result = self.env_helper.get('AUTO_DT_PRIO')
        self.assertIsInstance(result, datetime.datetime)

    def test_auto_convert_priority_time(self):
        """测试优先级：时间"""
        self._set_env('AUTO_TIME_PRIO', '14:30:45')
        result = self.env_helper.get('AUTO_TIME_PRIO')
        self.assertIsInstance(result, datetime.time)

    def test_auto_convert_priority_string(self):
        """测试优先级：字符串（最后）"""
        self._set_env('AUTO_STRING', 'hello')
        result = self.env_helper.get('AUTO_STRING')
        self.assertIsInstance(result, str)
        self.assertEqual(result, 'hello')

    def test_auto_convert_complete_order(self):
        """测试完整的优先级顺序"""
        # None > Bool > Int > Float > JSON > Date > DateTime > Time > String
        test_cases = [
            ('none', None, type(None)),
            ('true', True, bool),
            ('42', 42, int),
            ('3.14', 3.14, float),
            ('[1,2,3]', [1, 2, 3], list),
            ('2026-02-28', datetime.date(2026, 2, 28), datetime.date),
            ('2026-02-28 14:30:45', datetime.datetime(2026, 2, 28, 14, 30, 45), datetime.datetime),
            ('14:30:45', datetime.time(14, 30, 45), datetime.time),
            ('random_string', 'random_string', str),
        ]

        for i, (value, expected, expected_type) in enumerate(test_cases):
            with self.subTest(case=i, value=value):
                key = f'AUTO_PRIORITY_{i}'
                self._set_env(key, value)
                result = self.env_helper.get(key)
                if expected_type in (datetime.date, datetime.datetime, datetime.time):
                    # 对于日期时间类型，比较类型而不是值（因为 datetime.datetime 是 datetime.date 的子类）
                    self.assertEqual(type(result), expected_type)
                else:
                    self.assertEqual(result, expected)
                    self.assertIsInstance(result, expected_type)


class TestEnvReaderEdgeCases(unittest.TestCase):
    """测试边界情况和异常"""

    def setUp(self):
        self.env_keys = []
        self.env_helper = EnvHelper()

    def tearDown(self):
        for key in self.env_keys:
            if key in os.environ:
                del os.environ[key]

    def _set_env(self, key, value):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_whitespace_stripping(self):
        """测试空格被剥离"""
        self._set_env('WHITESPACE', '  hello  ')
        result = self.env_helper.get('WHITESPACE', var_type=str)
        self.assertEqual(result, 'hello')

    def test_case_insensitive_bool(self):
        """测试布尔值大小写不敏感"""
        self._set_env('BOOL_CASE', 'TrUe')
        result = self.env_helper.get('BOOL_CASE', var_type=bool)
        self.assertTrue(result)

    def test_case_insensitive_none(self):
        """测试 None 值大小写不敏感"""
        self._set_env('NONE_CASE', 'NuLl')
        result = self.env_helper.get('NONE_CASE', var_type=type(None))
        self.assertIsNone(result)

    def test_json_with_whitespace(self):
        """测试 JSON 包含空格"""
        self._set_env('JSON_WS', '{ "key" : "value" }')
        result = self.env_helper.get('JSON_WS', var_type=dict)
        self.assertEqual(result, {'key': 'value'})

    def test_invalid_json_string(self):
        """测试无效 JSON 字符串"""
        self._set_env('INVALID_JSON', '{invalid json}')
        # 应该作为字符串返回
        result = self.env_helper.get('INVALID_JSON')
        self.assertIsInstance(result, str)
        self.assertEqual(result, '{invalid json}')

    def test_very_long_string(self):
        """测试非常长的字符串"""
        long_str = 'a' * 10000
        self._set_env('LONG_STRING', long_str)
        result = self.env_helper.get('LONG_STRING', var_type=str)
        self.assertEqual(result, long_str)

    def test_unicode_string(self):
        """测试 Unicode 字符串"""
        self._set_env('UNICODE', '你好世界 🌍')
        result = self.env_helper.get('UNICODE', var_type=str)
        self.assertEqual(result, '你好世界 🌍')


if __name__ == '__main__':
    unittest.main()
