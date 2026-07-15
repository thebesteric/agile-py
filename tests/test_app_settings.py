import os
import unittest

from agile.utils.app_settings import AppSettings


class DemoSettings(AppSettings):
    """演示：通过统一前缀读取环境变量"""

    host: str = "127.0.0.1"
    port: int = 3306

    @classmethod
    def get_env_prefix(cls) -> str:
        return "DEMO_"


class AliasSettings(AppSettings):
    """演示：使用 env_field 指定自定义环境变量名"""

    token: str = AppSettings.env_field(alias="CUSTOM_TOKEN", default="")


class LowercaseSettings(AppSettings):
    """演示：get_case_sensitive=False 时使用全小写变量名"""

    host: str = "127.0.0.1"

    @classmethod
    def get_env_prefix(cls) -> str:
        return "DEMO_"

    @classmethod
    def get_case_sensitive(cls) -> bool:
        return False


class ExportEnvSettings(AppSettings):
    """演示：os_env=True 时自动写入系统环境变量"""

    @classmethod
    def get_env_prefix(cls) -> str:
        return "DEMO_"

    user: str = AppSettings.env_field(default="guest", os_env=True)
    token: str = AppSettings.env_field(alias="CUSTOM_EXPORT_TOKEN", default="", os_env=True)
    port: int = AppSettings.env_field(default=8080, os_env=True)


class ExportOverrideEnvSettings(AppSettings):
    """演示：os_env_override=True 时覆盖已有系统环境变量"""

    @classmethod
    def get_env_prefix(cls) -> str:
        return "DEMO_"

    user: str = AppSettings.env_field(default="override-user", os_env=True, os_env_override=True)


class TestAppSettings(unittest.TestCase):

    def setUp(self):
        self.env_keys: list[str] = []

    def tearDown(self):
        for key in self.env_keys:
            os.environ.pop(key, None)

    def _set_env(self, key: str, value: str):
        os.environ[key] = value
        self.env_keys.append(key)

    def test_read_settings_with_prefix(self):
        # get_case_sensitive=True：字段按全大写映射
        self._set_env("DEMO_HOST", "db.local")
        self._set_env("DEMO_PORT", "5432")

        settings = DemoSettings()

        self.assertEqual(settings.host, "db.local")
        self.assertEqual(settings.port, 5432)

    def test_read_settings_with_lowercase_mapping(self):
        self._set_env("DEMO_host", "db.local")

        settings = LowercaseSettings()

        self.assertEqual(settings.host, "db.local")

    def test_read_settings_with_alias(self):
        self._set_env("CUSTOM_TOKEN", "token-123")

        settings = AliasSettings()

        self.assertEqual(settings.token, "token-123")

    def test_subclass_model_config_is_auto_injected(self):
        self.assertEqual(DemoSettings.model_config.get("env_prefix"), "DEMO_")
        self.assertEqual(DemoSettings.model_config.get("env_nested_delimiter"), "__")

    def test_env_field_rejects_default_and_default_factory_together(self):
        with self.assertRaises(ValueError):
            AppSettings.env_field(default="x", default_factory=lambda: "y")

    def test_env_field_os_env_writes_to_system_env(self):
        self.env_keys.extend(["DEMO_USER", "CUSTOM_EXPORT_TOKEN", "DEMO_PORT"])

        settings = ExportEnvSettings()

        self.assertEqual(os.environ.get("DEMO_USER"), "guest")
        self.assertEqual(os.environ.get("CUSTOM_EXPORT_TOKEN"), "")
        self.assertEqual(os.environ.get("DEMO_PORT"), "8080")
        self.assertEqual(settings.user, "guest")

    def test_env_field_os_env_uses_setdefault_without_overwrite(self):
        self._set_env("DEMO_USER", "already-exists")

        settings = ExportEnvSettings()

        self.assertEqual(os.environ.get("DEMO_USER"), "already-exists")
        self.assertEqual(settings.user, "already-exists")

    def test_env_field_os_env_override_replaces_existing_value(self):
        self._set_env("DEMO_USER", "old-value")

        settings = ExportOverrideEnvSettings(user="override-user")

        self.assertEqual(os.environ.get("DEMO_USER"), "override-user")
        self.assertEqual(settings.user, "override-user")


if __name__ == '__main__':
    unittest.main(verbosity=2)

