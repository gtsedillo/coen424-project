import unittest

from fallback import fallback_recommendations
from validator import validate

CATALOG = ["A", "B", "C", "D", "E", "F", "G"]


class ValidatorTest(unittest.TestCase):
    def test_good_answer(self):
        self.assertTrue(validate(["B", "C", "D"], ["A"], CATALOG).valid)

    def test_unknown_id(self):
        result = validate(["B", "NOPE"], ["A"], CATALOG)
        self.assertFalse(result.valid)
        self.assertIn("unknown", result.problems[0])

    def test_returns_requested_id(self):
        self.assertFalse(validate(["A", "B"], ["A"], CATALOG).valid)

    def test_duplicates(self):
        self.assertFalse(validate(["B", "B"], ["A"], CATALOG).valid)

    def test_too_many(self):
        self.assertFalse(validate(["A", "B", "C", "D", "E", "F"], [], CATALOG).valid)

    def test_empty_when_products_are_left(self):
        self.assertFalse(validate([], ["A"], CATALOG).valid)

    def test_empty_when_nothing_is_left(self):
        self.assertTrue(validate([], CATALOG, CATALOG).valid)


class FallbackTest(unittest.TestCase):
    def test_fallback_always_passes_the_validator(self):
        for inputs in ([], ["A"], ["A", "B", "C"], CATALOG):
            output = fallback_recommendations(CATALOG, inputs)
            self.assertTrue(validate(output, inputs, CATALOG).valid, (inputs, output))


if __name__ == "__main__":
    unittest.main()
