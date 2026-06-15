from django.test import SimpleTestCase, override_settings

from platformkit.i18n import (
    get_translation_language_code,
    normalize_language_code,
    remap_accept_language_header,
)


@override_settings(
    LANGUAGE_CODE="en",
    LANGUAGES=(
        ("en", "English"),
        ("zh-hans", "Simplified Chinese"),
        ("es", "Spanish"),
    ),
    LANGUAGE_CODE_MAPPING={
        "zh-cn": "zh-hans",
        "zh": "zh-hans",
        "en-us": "en",
        "es-mx": "es",
    },
)
class PlatformKitI18nTests(SimpleTestCase):
    def test_normalize_language_code_maps_browser_variants(self):
        self.assertEqual(normalize_language_code("zh-CN"), "zh-hans")
        self.assertEqual(normalize_language_code("en_US"), "en")
        self.assertEqual(normalize_language_code("es-mx"), "es")

    def test_normalize_language_code_falls_back_to_default(self):
        self.assertEqual(normalize_language_code("fr-FR"), "en")
        self.assertEqual(normalize_language_code(""), "en")
        self.assertEqual(normalize_language_code(None), "en")

    def test_get_translation_language_code_uses_mapping(self):
        self.assertEqual(get_translation_language_code("zh-CN"), "zh-hans")
        self.assertEqual(get_translation_language_code("es-MX"), "es")
        self.assertEqual(get_translation_language_code("en-US"), "en")

    def test_remap_accept_language_header_only_rewrites_first_code(self):
        header = "zh-CN,zh;q=0.9,en;q=0.8"
        self.assertEqual(
            remap_accept_language_header(header),
            "zh-hans,zh;q=0.9,en;q=0.8",
        )

    def test_remap_accept_language_header_preserves_unknown_values(self):
        header = "fr-FR,fr;q=0.9"
        self.assertEqual(remap_accept_language_header(header), header)
