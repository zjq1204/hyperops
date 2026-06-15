from django.test import SimpleTestCase

from platformkit.api import build_paginated_payload, parse_bounded_int


class PlatformKitApiTests(SimpleTestCase):
    def test_parse_bounded_int_clamps_to_range(self):
        self.assertEqual(parse_bounded_int("0", default=5), 1)
        self.assertEqual(parse_bounded_int("200", default=5, max_value=100), 100)
        self.assertEqual(parse_bounded_int("oops", default=5), 5)

    def test_build_paginated_payload_includes_extra_fields(self):
        payload = build_paginated_payload(
            items=[{"id": 1}],
            total=10,
            page=2,
            page_size=5,
            feature_options=["workspace"],
        )

        self.assertEqual(payload["count"], 10)
        self.assertEqual(payload["page"], 2)
        self.assertEqual(payload["page_size"], 5)
        self.assertEqual(payload["results"], [{"id": 1}])
        self.assertEqual(payload["feature_options"], ["workspace"])
