# Create your tests here.
from io import BytesIO
from unittest import mock

from django.test import SimpleTestCase, RequestFactory
from django.http import Http404

from resumes import views


class ResumeViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def make_user(self, has_resume=False, resume_name="resume.pdf"):
        user = mock.Mock()
        user.is_authenticated = True
        user.has_resume = has_resume
        user.resume = mock.Mock()
        user.resume.name = resume_name
        return user

    def test_view_resume_no_resume_redirects(self):
        request = self.factory.get("/resume/")
        request.user = self.make_user(has_resume=False)

        resp = views.view_resume(request)
        # Should be a redirect
        self.assertEqual(resp.status_code, 302)

    def test_view_resume_pdf_flag(self):
        request = self.factory.get("/resume/")
        request.user = self.make_user(has_resume=True, resume_name="a.pdf")

        with mock.patch("resumes.views.render") as mock_render:
            mock_render.return_value = mock.Mock(status_code=200)
            #resp = views.view_resume(request)
            # render should have been called with is_pdf True
            called_ctx = mock_render.call_args[0][2]
            self.assertTrue(called_ctx["is_pdf"])

    def test_serve_resume_no_resume_raises(self):
        request = self.factory.get("/resume/serve")
        request.user = self.make_user(has_resume=False)

        with self.assertRaises(Http404):
            views.serve_resume(request)

    def test_serve_resume_file_not_found(self):
        request = self.factory.get("/resume/serve")
        user = self.make_user(has_resume=True)
        # Make open raise FileNotFoundError
        user.resume.open.side_effect = FileNotFoundError
        request.user = user

        with self.assertRaises(Http404):
            views.serve_resume(request)

    def test_serve_resume_success(self):
        request = self.factory.get("/resume/serve")
        user = self.make_user(has_resume=True, resume_name="myresume.pdf")
        user.resume.open.return_value = BytesIO(b"pdf")
        request.user = user

        with mock.patch("resumes.views.FileResponse") as MockFileResponse:
            mock_resp = mock.Mock()
            MockFileResponse.return_value = mock_resp
            #resp = views.serve_resume(request)
            # Ensure Content-Disposition header was set
            MockFileResponse.assert_called()

    def test_update_resume_invalid(self):
        request = self.factory.post("/resume/update")
        request.user = self.make_user()

        with mock.patch("resumes.views.ResumeUpdateForm") as MockForm:
            form = mock.Mock()
            form.is_valid.return_value = False
            form.errors = {"resume": ["Bad file"]}
            MockForm.return_value = form

            resp = views.update_resume(request)
            self.assertEqual(resp.status_code, 400)

    def test_update_resume_success(self):
        request = self.factory.post("/resume/update")
        request.user = self.make_user()

        with mock.patch("resumes.views.ResumeUpdateForm") as MockForm:
            form = mock.Mock()
            form.is_valid.return_value = True
            # save(commit=False) returns an instance to save
            user_instance = mock.Mock()
            form.save.return_value = user_instance
            MockForm.return_value = form

            with mock.patch("django.core.files.storage.default_storage") as storage:
                storage.exists.return_value = True
                storage.delete.return_value = None

                resp = views.update_resume(request)
                self.assertEqual(resp.status_code, 200)
