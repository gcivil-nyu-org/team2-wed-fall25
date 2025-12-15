from io import BytesIO
from unittest import mock

from django.test import SimpleTestCase, RequestFactory
from django.http import Http404
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.messages.storage.fallback import FallbackStorage

from resumes import views

class ResumeViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def add_middleware(self, request):
        """
        Annotate a request object with a session and message support.
        This is required because RequestFactory does not run middleware,
        but the views use messages.success/warning.
        """
        # 1. Add Session Middleware
        session_middleware = SessionMiddleware(lambda get_response: get_response)
        session_middleware.process_request(request)
        request.session.save()

        # 2. Add Message Middleware
        message_middleware = MessageMiddleware(lambda get_response: get_response)
        message_middleware.process_request(request)
        
        # 3. Ensure storage is set (fixes specific fallback issues)
        setattr(request, '_messages', FallbackStorage(request))
        return request

    def make_user(self, has_resume=False, resume_name="resume.pdf"):
        user = mock.Mock()
        user.is_authenticated = True
        
        if has_resume:
            # Mock a FileField that exists
            resume_mock = mock.Mock()
            resume_mock.name = resume_name
            # When bool(user.resume) is called, it should return True
            resume_mock.__bool__ = lambda s: True 
            user.resume = resume_mock
        else:
            # When bool(user.resume) is called, it should return False
            user.resume = None 
            
        return user

    def test_view_resume_no_resume_redirects(self):
        request = self.factory.get("/resume/")
        request.user = self.make_user(has_resume=False)
        self.add_middleware(request) # Fixes MessageFailure

        resp = views.view_resume(request)
        
        # Should be a redirect (302)
        self.assertEqual(resp.status_code, 302)

    def test_view_resume_pdf_flag(self):
        request = self.factory.get("/resume/")
        request.user = self.make_user(has_resume=True, resume_name="a.pdf")
        self.add_middleware(request)

        with mock.patch("resumes.views.render") as mock_render:
            mock_render.return_value = mock.Mock(status_code=200)
            
            views.view_resume(request)
            
            # render should have been called
            self.assertTrue(mock_render.called)
            
            # check context (args[2]) for is_pdf
            called_ctx = mock_render.call_args[0][2]
            self.assertTrue(called_ctx.get("is_pdf"))

    def test_serve_resume_no_resume_raises(self):
        request = self.factory.get("/resume/serve")
        request.user = self.make_user(has_resume=False)
        self.add_middleware(request)

        with self.assertRaises(Http404):
            views.serve_resume(request)

    def test_serve_resume_file_not_found(self):
        request = self.factory.get("/resume/serve")
        user = self.make_user(has_resume=True)
        self.add_middleware(request)

        # Make open raise FileNotFoundError
        user.resume.open.side_effect = FileNotFoundError
        request.user = user

        with self.assertRaises(Http404):
            views.serve_resume(request)

    def test_serve_resume_success(self):
        request = self.factory.get("/resume/serve")
        user = self.make_user(has_resume=True, resume_name="myresume.pdf")
        
        # Mock the file content
        user.resume.open.return_value = BytesIO(b"pdf_content")
        request.user = user
        self.add_middleware(request)

        with mock.patch("resumes.views.FileResponse") as MockFileResponse:
            mock_resp = mock.Mock(status_code=200)
            MockFileResponse.return_value = mock_resp
            
            # Actually call the view
            views.serve_resume(request)
            
            # Ensure FileResponse was initialized
            MockFileResponse.assert_called_once()

    def test_update_resume_invalid(self):
        request = self.factory.post("/resume/update")
        request.user = self.make_user()
        self.add_middleware(request)

        with mock.patch("resumes.views.ResumeUpdateForm") as MockForm:
            form = mock.Mock()
            form.is_valid.return_value = False
            form.errors = {"resume": ["Bad file"]}
            MockForm.return_value = form

            resp = views.update_resume(request)
            
            # Depending on implementation, invalid forms usually return 200 (re-render) or 400
            # Adjust assert based on your specific view logic. 
            # If your view does `return render(..., status=400)`, keep 400. 
            # If standard Django, it's 200. I will assert not a redirect.
            self.assertNotEqual(resp.status_code, 302)

    def test_update_resume_success(self):
        request = self.factory.post("/resume/update")
        request.user = self.make_user()
        self.add_middleware(request) # Fixes MessageFailure

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
                
                # Usually success results in a redirect or a render with success message
                # Assuming 200 or 302 is acceptable success, ensuring it didn't crash
                self.assertIn(resp.status_code, [200, 302])
                
                # Optional: Check if success message was added
                messages = list(request._messages)
                self.assertTrue(len(messages) > 0)
                self.assertEqual(str(messages[0]), "Resume updated successfully!")
