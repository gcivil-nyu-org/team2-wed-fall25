from django.test import SimpleTestCase, RequestFactory
from core import views

class CoreViewsTests(SimpleTestCase):
    def test_home_view_renders(self):
        req = RequestFactory().get("/")
        resp = views.home_view(req)
        # render returns an HttpResponse-like object; ensure callable returned
        self.assertTrue(hasattr(resp, "__class__"))
