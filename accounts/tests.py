from django.test import SimpleTestCase

# from .models import User

# Create your tests here.


class AlwaysPassTest(SimpleTestCase):
    def test_always_true(self):
        self.assertTrue(True)
